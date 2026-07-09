#!/usr/bin/env python3
"""
pendientes.py — Skill: Lista de pendientes (sin fecha fija, a diferencia de los eventos)
============================================================================================
Complementa a skills/agenda.py: los eventos tienen fecha/hora, los pendientes
no — son cosas sueltas que hay que hacer en algún momento. El Agente de
Agenda tiene acceso a ambos.

Uso:
    python skills/pendientes.py --accion listar
"""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "vault" / "sqlite" / "imrryr.db"


def log(msg: str) -> None:
    print(f"[pendientes] {msg}", flush=True)


def _crear(texto: str) -> dict[str, Any]:
    if not texto:
        return {"ok": False, "error": "falta 'texto'"}
    conn = sqlite3.connect(str(DB_PATH))
    try:
        cur = conn.execute("INSERT INTO pendientes (texto) VALUES (?)", (texto,))
        conn.commit()
        log(f"Pendiente creado #{cur.lastrowid}: {texto}")
        return {"ok": True, "id": cur.lastrowid}
    finally:
        conn.close()


def _listar() -> dict[str, Any]:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        filas = conn.execute("SELECT * FROM pendientes ORDER BY hecho ASC, created_at DESC").fetchall()
        return {"ok": True, "pendientes": [dict(f) for f in filas]}
    finally:
        conn.close()


def _marcar_hecho(pendiente_id: int, hecho: bool) -> dict[str, Any]:
    conn = sqlite3.connect(str(DB_PATH))
    try:
        conn.execute("UPDATE pendientes SET hecho = ? WHERE id = ?", (int(hecho), pendiente_id))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


def _eliminar(pendiente_id: int) -> dict[str, Any]:
    conn = sqlite3.connect(str(DB_PATH))
    try:
        conn.execute("DELETE FROM pendientes WHERE id = ?", (pendiente_id,))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


def pendientes(
    accion: str = "", texto: str = "", pendiente_id: int | None = None, hecho: bool = True,
) -> dict:
    """Punto de entrada MCP. accion: crear | listar | marcar_hecho | eliminar"""
    if accion == "crear":
        return _crear(texto)
    if accion == "listar":
        return _listar()
    if accion == "marcar_hecho":
        if pendiente_id is None:
            return {"ok": False, "error": "falta pendiente_id"}
        return _marcar_hecho(pendiente_id, hecho)
    if accion == "eliminar":
        if pendiente_id is None:
            return {"ok": False, "error": "falta pendiente_id"}
        return _eliminar(pendiente_id)
    return {"ok": False, "error": f"acción desconocida: {accion}"}


def main() -> int:
    ap = argparse.ArgumentParser(description="Lista de pendientes")
    ap.add_argument("--accion", type=str, required=True)
    ap.add_argument("--texto", type=str, default="")
    ap.add_argument("--id", type=int, default=None, dest="pendiente_id")
    ap.add_argument("--no-hecho", action="store_false", dest="hecho")
    args = ap.parse_args()

    resultado = pendientes(accion=args.accion, texto=args.texto, pendiente_id=args.pendiente_id, hecho=args.hecho)
    print(resultado)
    return 0 if resultado.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
