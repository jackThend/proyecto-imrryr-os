#!/usr/bin/env python3
"""
agenda.py — Skill: Agenda del usuario (tabla eventos + avisos_evento)
=========================================================================
Distinto de skills/recordatorios.py: `recordatorios` es para avisos puntuales
de una sola vez sin una "actividad" real detrás (ej. "recuérdame llamar a X
en 2 horas"); `eventos` es la agenda de verdad — actividades con fecha/hora,
consultables por "qué tengo hoy/mañana/esta semana/este mes" o "qué hice
ayer". No se fusionan las tablas porque tienen semánticas distintas.

Cada evento puede tener CUALQUIER cantidad de avisos a horas libres (tabla
avisos_evento) — no dos flags fijos como antes. Así "mándame un mensaje a
las 8 y a las 5 este jueves, tengo médico a las 6" se traduce en un evento
("médico", jueves 18:00) con dos filas en avisos_evento (08:00 y 17:00).

Los avisos por WhatsApp (`avisar_eventos_programados`) son 100% deterministas
— sin IA — y los llama scripts/scheduler.py cada minuto; nunca se disparan
si el usuario no pidió explícitamente ese aviso para ese evento.

skills/crear_evento.py (generación de archivos .ics) se reusa tal cual como
utilidad de exportación opcional, no se reemplaza.

Uso:
    python skills/agenda.py --accion que_tengo --cuando hoy
"""
from __future__ import annotations

import argparse
import calendar
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


def _con_avisos(conn: sqlite3.Connection, filas: list[sqlite3.Row]) -> list[dict]:
    eventos = []
    for f in filas:
        ev = dict(f)
        avisos = conn.execute(
            "SELECT hora_aviso, disparado FROM avisos_evento WHERE evento_id = ? ORDER BY hora_aviso",
            (ev["id"],),
        ).fetchall()
        ev["avisos"] = [dict(a) for a in avisos]
        eventos.append(ev)
    return eventos


def _crear(
    titulo: str, fecha: str, hora: str, duracion_min: int, descripcion: str,
    avisos: list[str], exportar_ics: bool,
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
            "INSERT INTO eventos (titulo, descripcion, fecha, hora, duracion_min, ics_generado) VALUES (?, ?, ?, ?, ?, ?)",
            (titulo, descripcion, fecha, hora, duracion_min, ics_ruta or None),
        )
        evento_id = cur.lastrowid
        for hora_aviso in avisos:
            conn.execute(
                "INSERT INTO avisos_evento (evento_id, hora_aviso) VALUES (?, ?)", (evento_id, hora_aviso)
            )
        conn.commit()
        log(f"Evento creado #{evento_id}: {titulo} el {fecha} {hora}" + (f" (avisos: {', '.join(avisos)})" if avisos else ""))
        return {"ok": True, "id": evento_id}
    finally:
        conn.close()


def _proximo_despues(conn: sqlite3.Connection, fecha_limite: str) -> dict | None:
    """Primer evento activo posterior a la ventana que se consultó.

    Existe para que un "no tienes nada esta semana" no se lea como "no tienes
    nada". Caso real que lo motivó: con un dentista agendado para el jueves 20,
    preguntar "¿qué tengo agendado?" un día 12 respondía "sin eventos" — cierto
    para los próximos 7 días, pero engañoso, porque la cita caía al día 8.
    Devolviendo además el próximo evento, el agente puede cerrar la respuesta
    con "lo más próximo es el dentista el jueves 20".
    """
    fila = conn.execute(
        "SELECT * FROM eventos WHERE estado='activo' AND fecha > ? ORDER BY fecha, hora LIMIT 1",
        (fecha_limite,),
    ).fetchone()
    return _con_avisos(conn, [fila])[0] if fila else None


def _que_tengo(cuando: str, anio: int | None, mes: int | None) -> dict[str, Any]:
    hoy = date.today()
    conn = _conn()
    try:
        if cuando == "semana":
            desde, hasta = hoy.isoformat(), (hoy + timedelta(days=7)).isoformat()
            filas = conn.execute(
                "SELECT * FROM eventos WHERE estado='activo' AND fecha BETWEEN ? AND ? ORDER BY fecha, hora",
                (desde, hasta),
            ).fetchall()
        elif cuando == "mes":
            anio_ = anio or hoy.year
            mes_ = mes or hoy.month
            ultimo_dia = calendar.monthrange(anio_, mes_)[1]
            desde = date(anio_, mes_, 1).isoformat()
            hasta = date(anio_, mes_, ultimo_dia).isoformat()
            filas = conn.execute(
                "SELECT * FROM eventos WHERE estado='activo' AND fecha BETWEEN ? AND ? ORDER BY fecha, hora",
                (desde, hasta),
            ).fetchall()
        else:
            fecha = _resolver_fecha(cuando, "")
            hasta = fecha or hoy.isoformat()
            filas = conn.execute(
                "SELECT * FROM eventos WHERE estado='activo' AND fecha = ? ORDER BY hora", (fecha,)
            ).fetchall()

        resultado: dict[str, Any] = {"ok": True, "eventos": _con_avisos(conn, filas)}
        if not filas:
            # Solo cuando no hay nada en la ventana: si sí hay eventos, añadir
            # el siguiente sería ruido.
            resultado["proximo_evento"] = _proximo_despues(conn, hasta)
        return resultado
    finally:
        conn.close()


def _que_hice(cuando: str) -> dict[str, Any]:
    ayer = (date.today() - timedelta(days=1)).isoformat()
    conn = _conn()
    try:
        filas = conn.execute("SELECT * FROM eventos WHERE fecha = ? ORDER BY hora", (ayer,)).fetchall()
        return {"ok": True, "eventos": _con_avisos(conn, filas)}
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


def avisar_eventos_programados() -> int:
    """Determinista, sin IA — llamado por el scheduler cada minuto. Revisa
    avisos_evento por hora exacta (HH:MM) contra eventos activos de hoy;
    cada aviso es de una sola vez (se marca disparado=1 al enviarse)."""
    ahora = datetime.now()
    hora_actual = ahora.strftime("%H:%M")
    hoy = ahora.date().isoformat()

    conn = _conn()
    try:
        filas = conn.execute(
            """SELECT av.id AS aviso_id, av.hora_aviso, e.titulo, e.hora AS hora_evento
               FROM avisos_evento av JOIN eventos e ON av.evento_id = e.id
               WHERE av.disparado = 0 AND e.estado = 'activo' AND e.fecha = ? AND av.hora_aviso = ?""",
            (hoy, hora_actual),
        ).fetchall()
        avisados = 0
        for f in filas:
            texto = f"Recordatorio de tu agenda: {f['titulo']} ({f['hora_evento']})"
            if _notificar_whatsapp(texto):
                conn.execute("UPDATE avisos_evento SET disparado = 1 WHERE id = ?", (f["aviso_id"],))
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
    avisos: str = "",
    cuando: str = "",
    anio: int | None = None,
    mes: int | None = None,
    exportar_ics: bool = False,
    evento_id: int | None = None,
) -> dict:
    """Punto de entrada MCP. accion: crear | que_tengo | que_hice | es_feriado | cancelar
    avisos: horarios de aviso separados por coma, ej. '08:00,17:00' (opcional)
    cuando (para que_tengo): hoy | mañana | semana | mes"""
    if accion == "crear":
        lista_avisos = [h.strip() for h in avisos.split(",") if h.strip()]
        return _crear(titulo, _resolver_fecha(cuando, fecha) or fecha, hora, duracion, descripcion,
                      lista_avisos, exportar_ics)
    if accion == "que_tengo":
        return _que_tengo(cuando or "hoy", anio, mes)
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
    ap.add_argument("--avisos", type=str, default="", help="ej. '08:00,17:00'")
    ap.add_argument("--cuando", type=str, default="")
    ap.add_argument("--anio", type=int, default=None)
    ap.add_argument("--mes", type=int, default=None)
    ap.add_argument("--exportar-ics", action="store_true", dest="exportar_ics")
    ap.add_argument("--id", type=int, default=None, dest="evento_id")
    args = ap.parse_args()

    resultado = agenda(
        accion=args.accion, titulo=args.titulo, fecha=args.fecha, hora=args.hora,
        duracion=args.duracion, descripcion=args.descripcion, avisos=args.avisos,
        cuando=args.cuando, anio=args.anio, mes=args.mes,
        exportar_ics=args.exportar_ics, evento_id=args.evento_id,
    )
    print(resultado)
    return 0 if resultado.get("ok", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
