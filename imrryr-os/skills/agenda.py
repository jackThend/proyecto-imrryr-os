#!/usr/bin/env python3
"""
agenda.py — Skill: Agenda del usuario (tabla eventos)
=========================================================
Distinto de skills/recordatorios.py: `recordatorios` es para avisos puntuales
de una sola vez sin una "actividad" real detrás (ej. "recuérdame llamar a X
en 2 horas"); `eventos` es la agenda de verdad — actividades con fecha/hora,
consultables por "qué tengo hoy/mañana/esta semana" o "qué hice ayer". No se
fusionan las tablas porque tienen semánticas distintas (recordatorio = disparo
único con flag `disparado`; evento = entidad con estado propio y hasta dos
avisos independientes: al inicio del día y 1h antes).

Los avisos por WhatsApp (`enviar_resumen_diario`, `avisar_eventos_1h_antes`)
son 100% deterministas — sin IA — y los llama scripts/scheduler.py; nunca se
disparan si el usuario no activó el flag correspondiente para ese evento
("solo si se lo pides").

skills/crear_evento.py (generación de archivos .ics) se reusa tal cual como
utilidad de exportación opcional, no se reemplaza.

Uso:
    python skills/agenda.py --accion que_tengo --cuando hoy
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx

from crear_evento import CALENDAR_DIR, generar_ics

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "vault" / "sqlite" / "imrryr.db"

sys.path.insert(0, str(ROOT))
from config.region import leer_region  # noqa: E402

_cache_feriados: dict[str, list[str]] = {}


def log(msg: str) -> None:
    print(f"[agenda] {msg}", flush=True)


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _resolver_fecha(cuando: str, fecha: str) -> str | None:
    if fecha:
        return fecha
    hoy = date.today()
    if cuando in ("mañana", "manana"):
        return (hoy + timedelta(days=1)).isoformat()
    if cuando == "hoy" or not cuando:
        return hoy.isoformat()
    return None


def _crear(
    titulo: str, fecha: str, hora: str, duracion_min: int, descripcion: str,
    avisar_dia_inicio: bool, avisar_1h_antes: bool, exportar_ics: bool,
) -> dict[str, Any]:
    if not titulo or not fecha:
        return {"ok": False, "error": "faltan 'titulo' y/o 'fecha'"}

    ics_ruta = ""
    if exportar_ics:
        try:
            CALENDAR_DIR.mkdir(parents=True, exist_ok=True)
            fecha_obj = date.fromisoformat(fecha)
            contenido = generar_ics(titulo, fecha_obj, hora, duracion_min, False, descripcion)
            safe_name = titulo.lower().replace(" ", "_").replace("/", "_")[:30]
            ruta = CALENDAR_DIR / f"{safe_name}_{fecha}.ics"
            ruta.write_text(contenido, encoding="utf-8")
            ics_ruta = str(ruta)
        except (OSError, ValueError) as e:
            log(f"no se pudo exportar .ics: {e}")

    conn = _conn()
    try:
        cur = conn.execute(
            """INSERT INTO eventos (titulo, descripcion, fecha, hora, duracion_min,
               avisar_dia_inicio, avisar_1h_antes, ics_generado)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (titulo, descripcion, fecha, hora, duracion_min,
             int(avisar_dia_inicio), int(avisar_1h_antes), ics_ruta or None),
        )
        conn.commit()
        log(f"Evento creado #{cur.lastrowid}: {titulo} el {fecha} {hora}")
        return {"ok": True, "id": cur.lastrowid}
    finally:
        conn.close()


def _que_tengo(cuando: str) -> dict[str, Any]:
    hoy = date.today()
    conn = _conn()
    try:
        if cuando == "semana":
            desde, hasta = hoy.isoformat(), (hoy + timedelta(days=7)).isoformat()
            filas = conn.execute(
                "SELECT * FROM eventos WHERE estado='activo' AND fecha BETWEEN ? AND ? ORDER BY fecha, hora",
                (desde, hasta),
            ).fetchall()
        else:
            fecha = _resolver_fecha(cuando, "")
            filas = conn.execute(
                "SELECT * FROM eventos WHERE estado='activo' AND fecha = ? ORDER BY hora", (fecha,)
            ).fetchall()
        return {"ok": True, "eventos": [dict(f) for f in filas]}
    finally:
        conn.close()


def _que_hice(cuando: str) -> dict[str, Any]:
    ayer = (date.today() - timedelta(days=1)).isoformat()
    conn = _conn()
    try:
        filas = conn.execute("SELECT * FROM eventos WHERE fecha = ? ORDER BY hora", (ayer,)).fetchall()
        return {"ok": True, "eventos": [dict(f) for f in filas]}
    finally:
        conn.close()


def _cancelar(evento_id: int) -> dict[str, Any]:
    conn = _conn()
    try:
        conn.execute("UPDATE eventos SET estado='cancelado', updated_at=datetime('now') WHERE id = ?", (evento_id,))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


def _feriados_del_anio(anio: int, pais: str) -> list[str]:
    clave = f"{pais}:{anio}"
    if clave in _cache_feriados:
        return _cache_feriados[clave]
    try:
        r = httpx.get(f"https://date.nager.at/api/v3/PublicHolidays/{anio}/{pais}", timeout=15)
        r.raise_for_status()
        fechas = [item["date"] for item in r.json()]
        _cache_feriados[clave] = fechas
        return fechas
    except (httpx.HTTPError, KeyError, ValueError) as e:
        log(f"no se pudo consultar feriados de {pais}/{anio}: {e}")
        return []


def _es_feriado(cuando: str, fecha: str) -> dict[str, Any]:
    fecha_resuelta = _resolver_fecha(cuando or "mañana", fecha)
    if not fecha_resuelta:
        return {"ok": False, "error": "no se pudo resolver la fecha"}
    pais = leer_region().get("pais", "CL")
    anio = int(fecha_resuelta.split("-")[0])
    feriados = _feriados_del_anio(anio, pais)
    return {"ok": True, "fecha": fecha_resuelta, "es_feriado": fecha_resuelta in feriados}


def _notificar_whatsapp(texto: str) -> bool:
    try:
        r = httpx.post("http://localhost:5050/api/gateway/enviar", json={"texto": texto}, timeout=10)
        return r.status_code == 200 and bool(r.json().get("enviado"))
    except httpx.HTTPError as e:
        log(f"no se pudo notificar (¿está corriendo el gateway en :5050?): {e}")
        return False


def enviar_resumen_diario() -> dict:
    """Determinista, sin IA — llamado por el scheduler. Solo incluye eventos
    que el usuario marcó explícitamente con avisar_dia_inicio=1; si no hay
    ninguno hoy, no manda nada."""
    hoy = date.today().isoformat()
    conn = _conn()
    try:
        filas = conn.execute(
            "SELECT * FROM eventos WHERE estado='activo' AND fecha = ? AND avisar_dia_inicio = 1 ORDER BY hora",
            (hoy,),
        ).fetchall()
    finally:
        conn.close()
    if not filas:
        return {"enviado": False, "motivo": "sin eventos marcados para avisar hoy"}

    lineas = ["Tu agenda de hoy:", ""]
    for f in filas:
        lineas.append(f"• {f['hora']} — {f['titulo']}")
    enviado = _notificar_whatsapp("\n".join(lineas))
    return {"enviado": enviado, "eventos": len(filas)}


def avisar_eventos_1h_antes() -> int:
    """Determinista, sin IA — llamado por el scheduler cada minuto. Ventana de
    tolerancia de ±5 min alrededor de 'ahora + 1h' para no depender de que el
    tick caiga exactamente en el minuto exacto."""
    ahora = datetime.now()
    objetivo = ahora + timedelta(hours=1)
    ventana_inicio = (objetivo - timedelta(minutes=5)).strftime("%H:%M")
    ventana_fin = (objetivo + timedelta(minutes=5)).strftime("%H:%M")
    hoy = ahora.date().isoformat()

    conn = _conn()
    try:
        filas = conn.execute(
            """SELECT * FROM eventos WHERE estado='activo' AND avisar_1h_antes = 1
               AND aviso_1h_disparado = 0 AND fecha = ? AND hora BETWEEN ? AND ?""",
            (hoy, ventana_inicio, ventana_fin),
        ).fetchall()
        avisados = 0
        for f in filas:
            if _notificar_whatsapp(f"En una hora: {f['titulo']} ({f['hora']})"):
                conn.execute("UPDATE eventos SET aviso_1h_disparado = 1 WHERE id = ?", (f["id"],))
                avisados += 1
        conn.commit()
        return avisados
    finally:
        conn.close()


def agenda(
    accion: str = "",
    titulo: str = "",
    fecha: str = "",
    hora: str = "09:00",
    duracion: int = 60,
    descripcion: str = "",
    avisar_dia_inicio: bool = False,
    avisar_1h_antes: bool = False,
    cuando: str = "",
    exportar_ics: bool = False,
    evento_id: int | None = None,
) -> dict:
    """Punto de entrada MCP. accion: crear | que_tengo | que_hice | es_feriado | cancelar"""
    if accion == "crear":
        return _crear(titulo, _resolver_fecha(cuando, fecha) or fecha, hora, duracion, descripcion,
                      avisar_dia_inicio, avisar_1h_antes, exportar_ics)
    if accion == "que_tengo":
        return _que_tengo(cuando or "hoy")
    if accion == "que_hice":
        return _que_hice(cuando)
    if accion == "es_feriado":
        return _es_feriado(cuando, fecha)
    if accion == "cancelar":
        if evento_id is None:
            return {"ok": False, "error": "falta evento_id"}
        return _cancelar(evento_id)
    return {"ok": False, "error": f"acción desconocida: {accion}"}


def main() -> int:
    ap = argparse.ArgumentParser(description="Agenda del usuario")
    ap.add_argument("--accion", type=str, required=True)
    ap.add_argument("--titulo", type=str, default="")
    ap.add_argument("--fecha", type=str, default="")
    ap.add_argument("--hora", type=str, default="09:00")
    ap.add_argument("--duracion", type=int, default=60)
    ap.add_argument("--descripcion", type=str, default="")
    ap.add_argument("--avisar-dia-inicio", action="store_true", dest="avisar_dia_inicio")
    ap.add_argument("--avisar-1h-antes", action="store_true", dest="avisar_1h_antes")
    ap.add_argument("--cuando", type=str, default="")
    ap.add_argument("--exportar-ics", action="store_true", dest="exportar_ics")
    ap.add_argument("--id", type=int, default=None, dest="evento_id")
    args = ap.parse_args()

    resultado = agenda(
        accion=args.accion, titulo=args.titulo, fecha=args.fecha, hora=args.hora,
        duracion=args.duracion, descripcion=args.descripcion,
        avisar_dia_inicio=args.avisar_dia_inicio, avisar_1h_antes=args.avisar_1h_antes,
        cuando=args.cuando, exportar_ics=args.exportar_ics, evento_id=args.evento_id,
    )
    print(resultado)
    return 0 if resultado.get("ok", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
