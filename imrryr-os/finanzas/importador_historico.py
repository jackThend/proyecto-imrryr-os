#!/usr/bin/env python3
"""
importador_historico.py — Importación de correos bancarios en segundo plano
=====================================================================================
Corre en un hilo daemon (no bloquea al dashboard) y procesa los correos de una
cuenta de Gmail en tandas paginadas (ver skills/leer_gmail.py):

  1. Por cada correo, intenta el parser determinista (finanzas/parsers_bancarios.py,
     sin IA, gratis).
  2. Los que el parser no logra entender se agrupan (hasta LOTE_IA) y se le piden
     a la IA en UNA sola llamada por lote, no una por correo — así cientos de
     correos históricos no agotan la cuota diaria del proveedor de IA activo.
  3. Después de cada tanda se guarda el progreso en la tabla `importaciones`
     (checkpoint real) — si se interrumpe, la próxima corrida retoma ahí mismo.
  4. Si la IA responde con un límite de cuota (429) o se cuelga (el patrón ya
     conocido de Gemini free-tier: la cuota agotada a veces se ve como demora,
     no como error), la importación se pausa con gracia (estado='pausada_cuota')
     y se reintenta en la próxima corrida (el scheduler de startup.py la retoma
     al día siguiente; el usuario también puede reintentar manualmente).

Este mismo pipeline sirve tanto para la importación histórica (todo el correo)
como para la sincronización diaria incremental (solo correo nuevo, ver
scripts/startup.py) — el volumen diario es chico y normalmente ni se acerca al
límite de cuota.
"""
from __future__ import annotations

import base64
import json
import os
import re
import sqlite3
import sys
import threading
import time
from email.utils import parsedate_to_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "vault" / "sqlite" / "imrryr.db"
LOTE_IA = 25
PAUSA_ENTRE_LOTES_SEG = 2
INTERVALO_SYNC_DEFECTO_SEGS = 24 * 60 * 60  # 24 horas por defecto


def obtener_intervalo_sync() -> int:
    """Retorna el intervalo de sincronización periódica en segundos.
    Lee primero FINANZAS_SYNC_INTERVAL_SECS del entorno, luego
    config/finanzas_prefs.json ('intervalo_sync_segundos'), y finalmente
    el defecto (86400s).
    """
    env_val = os.environ.get("FINANZAS_SYNC_INTERVAL_SECS")
    if env_val:
        try:
            val = int(env_val)
            if val > 0:
                return val
        except ValueError:
            pass

    prefs_file = ROOT / "config" / "finanzas_prefs.json"
    if prefs_file.is_file():
        try:
            data = json.loads(prefs_file.read_text(encoding="utf-8"))
            val = int(data.get("intervalo_sync_segundos", 0))
            if val > 0:
                return val
        except Exception:
            pass

    return INTERVALO_SYNC_DEFECTO_SEGS


sys.path.insert(0, str(ROOT / "skills"))
sys.path.insert(0, str(ROOT))
import inyectar_gasto  # noqa: E402
import leer_gmail  # noqa: E402

from finanzas.parsers_bancarios import detectar_banco, intentar_extraer  # noqa: E402

_trabajos_activos: set[int] = set()  # ids de importaciones con un hilo corriendo (evita duplicar)


def log(msg: str) -> None:
    print(f"[importador_historico] {msg}", flush=True)


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _fecha_iso(fecha_header: str) -> str:
    try:
        return parsedate_to_datetime(fecha_header).date().isoformat()
    except (TypeError, ValueError):
        from datetime import date
        return date.today().isoformat()


def estimar(query: str) -> dict:
    return leer_gmail.contar_correos(query)


def obtener_estado(importacion_id: int | None = None, tipo: str = "historico", cuenta_correo_id: str = "") -> dict | None:
    conn = _conn()
    try:
        if importacion_id:
            fila = conn.execute("SELECT * FROM importaciones WHERE id = ?", (importacion_id,)).fetchone()
        else:
            fila = conn.execute(
                "SELECT * FROM importaciones WHERE tipo = ? AND cuenta_correo_id = ? ORDER BY id DESC LIMIT 1",
                (tipo, cuenta_correo_id),
            ).fetchone()
        return dict(fila) if fila else None
    finally:
        conn.close()


def informe_por_banco(cuenta_correo_id: str = "") -> list[dict]:
    conn = _conn()
    try:
        cur = conn.execute(
            "SELECT COALESCE(NULLIF(banco,''),'Sin identificar') as banco, COUNT(*) as cantidad, SUM(monto) as total "
            "FROM gastos WHERE fuente IN ('gmail_historico','gmail') GROUP BY banco ORDER BY total DESC"
        )
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def iniciar(cuenta_correo_id: str, query: str, tipo: str = "historico") -> dict:
    """Crea (o retoma) una importación y la corre en un hilo aparte. Devuelve
    de inmediato — el progreso se consulta con obtener_estado()."""
    conn = _conn()
    try:
        existente = conn.execute(
            "SELECT * FROM importaciones WHERE tipo = ? AND cuenta_correo_id = ? AND estado IN ('pendiente','en_progreso','pausada_cuota') "
            "ORDER BY id DESC LIMIT 1",
            (tipo, cuenta_correo_id),
        ).fetchone()
        if existente:
            importacion_id = existente["id"]
            conn.execute("UPDATE importaciones SET estado = 'en_progreso' WHERE id = ?", (importacion_id,))
        else:
            estimado = estimar(query).get("estimado", 0)
            cur = conn.execute(
                "INSERT INTO importaciones (tipo, cuenta_correo_id, estado, query_gmail, total_estimado) "
                "VALUES (?, ?, 'en_progreso', ?, ?)",
                (tipo, cuenta_correo_id, query, estimado),
            )
            importacion_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()

    if importacion_id not in _trabajos_activos:
        _trabajos_activos.add(importacion_id)
        hilo = threading.Thread(target=_ejecutar, args=(importacion_id,), daemon=True)
        hilo.start()
    return {"ok": True, "importacion_id": importacion_id}


def cancelar(importacion_id: int) -> dict:
    conn = _conn()
    try:
        conn.execute(
            "UPDATE importaciones SET estado = 'cancelada', actualizado_at = datetime('now') WHERE id = ?",
            (importacion_id,),
        )
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


# --- El worker que corre en el hilo daemon ---
def _ejecutar(importacion_id: int) -> None:
    try:
        conn = _conn()
        fila = conn.execute("SELECT * FROM importaciones WHERE id = ?", (importacion_id,)).fetchone()
        conn.close()
        if not fila:
            return

        query = fila["query_gmail"] or ""
        cursor = fila["cursor_pagina"]
        procesados = fila["procesados"] or 0
        agregados = fila["agregados"] or 0

        while True:
            if _estado_actual(importacion_id) == "cancelada":
                log(f"Importación #{importacion_id} cancelada por el usuario")
                return

            pagina = leer_gmail.leer_gmail_paginado(query, cursor=cursor, tamano_pagina=LOTE_IA)
            correos = pagina["mensajes"]
            if not correos:
                _marcar_completada(importacion_id, procesados, agregados)
                return

            sin_resolver = []
            for correo in correos:
                resultado = intentar_extraer(correo.get("subject", ""), correo.get("body", ""))
                procesados += 1
                if resultado:
                    ok = _insertar(correo, resultado["monto"], resultado["comercio"], resultado["categoria"])
                    if ok:
                        agregados += 1
                else:
                    sin_resolver.append(correo)

            if sin_resolver:
                try:
                    extraidos = _pedir_extraccion_lote(sin_resolver)
                except _CuotaAgotada:
                    _guardar_progreso(importacion_id, cursor, procesados, agregados, estado="pausada_cuota")
                    log(f"Importación #{importacion_id} pausada por límite de cuota — se retomará después")
                    return
                for correo, extraido in zip(sin_resolver, extraidos):
                    if not extraido or extraido.get("omitir"):
                        continue
                    ok = _insertar(
                        correo,
                        extraido.get("monto"),
                        extraido.get("comercio", "Comercio desconocido"),
                        extraido.get("categoria", "general"),
                        banco_llm=extraido.get("banco", ""),
                    )
                    if ok:
                        agregados += 1

            cursor = pagina["siguiente_cursor"]
            _guardar_progreso(importacion_id, cursor, procesados, agregados, estado="en_progreso")
            if not cursor:
                _marcar_completada(importacion_id, procesados, agregados)
                return
            time.sleep(PAUSA_ENTRE_LOTES_SEG)
    finally:
        _trabajos_activos.discard(importacion_id)


def _insertar(correo: dict, monto, comercio: str, categoria: str, banco_llm: str = "") -> bool:
    if not monto:
        return False
    banco = banco_llm or detectar_banco(correo.get("from", ""))
    id_insertado = inyectar_gasto.insertar_gasto(
        monto=float(monto),
        comercio=comercio,
        categoria=categoria or "general",
        descripcion=correo.get("subject", ""),
        fuente="gmail_historico",
        fuente_id=correo["id"],
        fecha=_fecha_iso(correo.get("date", "")),
        banco=banco,
    )
    return id_insertado > 0


def _estado_actual(importacion_id: int) -> str:
    conn = _conn()
    try:
        fila = conn.execute("SELECT estado FROM importaciones WHERE id = ?", (importacion_id,)).fetchone()
        return fila["estado"] if fila else ""
    finally:
        conn.close()


def _guardar_progreso(importacion_id: int, cursor: str | None, procesados: int, agregados: int, estado: str) -> None:
    conn = _conn()
    try:
        conn.execute(
            "UPDATE importaciones SET cursor_pagina = ?, procesados = ?, agregados = ?, estado = ?, actualizado_at = datetime('now') WHERE id = ?",
            (cursor, procesados, agregados, estado, importacion_id),
        )
        conn.commit()
    finally:
        conn.close()


def _marcar_completada(importacion_id: int, procesados: int, agregados: int) -> None:
    from datetime import date
    conn = _conn()
    try:
        conn.execute(
            "UPDATE importaciones SET procesados = ?, agregados = ?, estado = 'completada', marca_agua = ?, "
            "actualizado_at = datetime('now'), completado_at = datetime('now') WHERE id = ?",
            (procesados, agregados, date.today().isoformat(), importacion_id),
        )
        conn.commit()
        log(f"Importación #{importacion_id} completada: {procesados} correos, {agregados} gastos agregados")
    finally:
        conn.close()


def sincronizar_diario(cuenta_correo_id: str, query_base: str) -> dict:
    """Sincronización incremental: solo trae correos nuevos desde la última
    vez (marca de agua guardada en `importaciones` tipo='diario'). Pensada
    para llamarse al iniciar Imrryr OS y cada 24h mientras siga corriendo
    (ver scripts/startup.py) — el volumen diario es chico, así que normalmente
    no se acerca al límite de cuota de la IA."""
    from datetime import date, timedelta

    conn = _conn()
    try:
        fila = conn.execute(
            "SELECT * FROM importaciones WHERE tipo = 'diario' AND cuenta_correo_id = ? ORDER BY id DESC LIMIT 1",
            (cuenta_correo_id,),
        ).fetchone()
    finally:
        conn.close()

    desde = fila["marca_agua"] if fila and fila["marca_agua"] else (date.today() - timedelta(days=30)).isoformat()
    query = f'{query_base} after:{desde.replace("-", "/")}'
    return iniciar(cuenta_correo_id, query, tipo="diario")


# --- Llamada a la IA por lote (una sola llamada para hasta LOTE_IA correos) ---
class _CuotaAgotada(Exception):
    pass


def _opencode_port() -> int:
    return int(os.environ.get("OPENCODE_PORT") or 4040)


def _opencode_auth_headers() -> dict[str, str]:
    password = os.environ.get("OPENCODE_SERVER_PASSWORD", "imryyr-local-pass")
    token = base64.b64encode(f"opencode:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def _pedir_extraccion_lote(correos: list[dict]) -> list[dict | None]:
    """Un solo turno de chat con el Agente Financiero para todos los correos
    del lote a la vez — el costo en cuota de IA es por lote, no por correo."""
    import httpx

    lineas = []
    for i, correo in enumerate(correos):
        cuerpo = (correo.get("body") or correo.get("snippet") or "")[:500]
        lineas.append(f'[{i}] De: {correo.get("from","")}\nAsunto: {correo.get("subject","")}\nCuerpo: {cuerpo}')

    prompt = (
        "Tengo correos bancarios que no pude interpretar automáticamente. Para cada uno, "
        "extrae el monto (número, sin símbolo de moneda), el comercio, una categoría "
        "(restaurante, supermercado, transporte, combustible, suscripciones, salud, servicios, u otra "
        "que tenga sentido) y el banco si se identifica. Si un correo no es una transacción real, "
        "pon \"omitir\": true en su lugar. Responde SOLO con un array JSON de exactamente "
        f"{len(correos)} objetos, en el mismo orden, formato: "
        '[{"monto": 12345, "comercio": "...", "categoria": "...", "banco": "...", "omitir": false}, ...]\n\n'
        + "\n\n".join(lineas)
    )

    port = _opencode_port()
    headers = _opencode_auth_headers()
    with httpx.Client(timeout=90) as client:
        try:
            r = client.post(
                f"http://localhost:{port}/session",
                headers=headers,
                json={"agent": "financiero", "model": {"id": "imrryr-activo", "providerID": "imrryr-llm"}},
            )
            r.raise_for_status()
            sid = r.json().get("data", {}).get("id") or r.json().get("id")

            r = client.post(
                f"http://localhost:{port}/session/{sid}/message",
                headers=headers,
                json={
                    "agent": "financiero",
                    "model": {"providerID": "imrryr-llm", "modelID": "imrryr-activo"},
                    "parts": [{"type": "text", "text": prompt}],
                },
            )
            r.raise_for_status()
        except httpx.TimeoutException:
            # Ver docs/entorno.md: la cuota agotada de Gemini free-tier a veces se
            # ve como una demora/cuelgue, no como un 429 explícito.
            raise _CuotaAgotada("timeout esperando respuesta (posible cuota agotada)")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                raise _CuotaAgotada("límite de solicitudes alcanzado (429)")
            raise

        data = r.json()
        texto = "".join(p.get("text", "") for p in data.get("parts", []) if p.get("type") == "text")
        if not texto:
            texto = _esperar_texto(client, port, headers, sid)

    return _parsear_json_lote(texto, len(correos))


def _esperar_texto(client, port: int, headers: dict, sid: str, intentos: int = 6, espera: float = 1.5) -> str:
    for _ in range(intentos):
        r = client.get(
            f"http://localhost:{port}/session/{sid}/message",
            headers=headers, params={"order": "desc", "limit": 5},
        )
        r.raise_for_status()
        cuerpo = r.json()
        mensajes = cuerpo.get("data", []) if isinstance(cuerpo, dict) else cuerpo
        for msg in mensajes:
            if msg.get("info", {}).get("role") != "assistant":
                continue
            texto = "".join(p.get("text", "") for p in msg.get("parts", []) if p.get("type") == "text")
            if texto:
                return texto
            break
        time.sleep(espera)
    return ""


def _parsear_json_lote(texto: str, cantidad_esperada: int) -> list[dict | None]:
    match = re.search(r"\[.*\]", texto, re.DOTALL)
    if not match:
        return [None] * cantidad_esperada
    try:
        resultado = json.loads(match.group(0))
    except json.JSONDecodeError:
        return [None] * cantidad_esperada
    if not isinstance(resultado, list):
        return [None] * cantidad_esperada
    if len(resultado) < cantidad_esperada:
        resultado += [None] * (cantidad_esperada - len(resultado))
    return resultado[:cantidad_esperada]
