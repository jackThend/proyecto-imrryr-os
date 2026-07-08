#!/usr/bin/env python3
"""
crear_evento.py — Skill: Genera archivos .ics para el calendario
=================================================================
Uso:
    python skills/crear_evento.py --titulo "Reunion" --fecha 2026-07-01 --hora 15:00 --duracion 60
    python skills/crear_evento.py --titulo "Pago" --fecha 2026-07-05 --todo-dia
"""
from __future__ import annotations

import argparse
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CALENDAR_DIR = ROOT / "docs" / "eventos"


def log(msg: str) -> None:
    print(f"[crear_evento] {msg}", flush=True)


def generar_ics(titulo: str, fecha: date, hora: str = "09:00", duracion_min: int = 60, todo_dia: bool = False, descripcion: str = "") -> str:
    event_id = str(uuid.uuid4())
    dt_start = datetime.strptime(f"{fecha}T{hora}", "%Y-%m-%dT%H:%M")
    dt_end = dt_start + timedelta(minutes=duracion_min)

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Imrryr OS//Eventos//ES",
        "BEGIN:VEVENT",
        f"UID:{event_id}",
        f"DTSTART:{dt_start.strftime('%Y%m%dT%H%M%S')}",
        f"DTEND:{dt_end.strftime('%Y%m%dT%H%M%S')}",
        f"SUMMARY:{titulo}",
    ]

    if descripcion:
        descripcion_ics = descripcion.replace("\n", "\\n")
        lines.append(f"DESCRIPTION:{descripcion_ics}")

    lines.extend(["END:VEVENT", "END:VCALENDAR"])
    return "\r\n".join(lines)


def crear_evento(
    titulo: str,
    fecha: str | None = None,
    hora: str = "09:00",
    duracion: int = 60,
    descripcion: str = "",
) -> dict:
    """Punto de entrada MCP (nombre = nombre de la skill, ver mcp_server/skills_server.py)."""
    fecha_obj = date.fromisoformat(fecha) if fecha else date.today()
    return {"archivo": generar_ics(titulo, fecha_obj, hora, duracion, False, descripcion)}


def main() -> int:
    ap = argparse.ArgumentParser(description="Genera archivos .ics de calendario")
    ap.add_argument("--titulo", type=str, required=True)
    ap.add_argument("--fecha", type=str, default=date.today().isoformat())
    ap.add_argument("--hora", type=str, default="09:00")
    ap.add_argument("--duracion", type=int, default=60)
    ap.add_argument("--todo-dia", action="store_true")
    ap.add_argument("--descripcion", type=str, default="")
    args = ap.parse_args()

    CALENDAR_DIR.mkdir(parents=True, exist_ok=True)

    fecha = date.fromisoformat(args.fecha)
    ics_content = generar_ics(
        titulo=args.titulo,
        fecha=fecha,
        hora=args.hora if not args.todo_dia else "00:00",
        duracion_min=args.duracion if not args.todo_dia else 1440,
        todo_dia=args.todo_dia,
        descripcion=args.descripcion,
    )

    safe_name = args.titulo.lower().replace(" ", "_").replace("/", "_")[:30]
    ics_path = CALENDAR_DIR / f"{safe_name}_{fecha.isoformat()}.ics"
    ics_path.write_text(ics_content, encoding="utf-8")
    log(f"Evento creado: {ics_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
