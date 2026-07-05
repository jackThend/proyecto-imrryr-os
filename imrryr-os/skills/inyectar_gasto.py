#!/usr/bin/env python3
"""
inyectar_gasto.py — Skill: Inserta un gasto en la base SQLite
===============================================================
Uso:
    python skills/inyectar_gasto.py --monto 15000 --comercio "AWS" --categoria "software"
    python skills/inyectar_gasto.py --monto 5000 --comercio "Netflix" --categoria "suscripciones"
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "vault" / "sqlite" / "imrryr.db"


def log(msg: str) -> None:
    print(f"[inyectar_gasto] {msg}", flush=True)


def insertar_gasto(monto: float, comercio: str, categoria: str = "general", descripcion: str = "", fuente: str = "skill") -> int:
    if not DB_PATH.exists():
        log(f"ERROR: Base de datos no encontrada. Ejecuta: python scripts/init_db.py")
        return 1

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.execute(
            "INSERT INTO gastos (fecha, monto, comercio, categoria, descripcion, fuente) VALUES (?, ?, ?, ?, ?, ?)",
            (date.today().isoformat(), monto, comercio, categoria, descripcion, fuente),
        )
        conn.commit()
        log(f"Gasto insertado: ${monto} en {comercio} ({categoria})")
        return cur.lastrowid or 0
    finally:
        conn.close()


def listar_gastos(limite: int = 10) -> list[dict]:
    if not DB_PATH.exists():
        return []
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.execute("SELECT * FROM gastos ORDER BY fecha DESC LIMIT ?", (limite,))
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def main() -> int:
    ap = argparse.ArgumentParser(description="Inserta un gasto en SQLite")
    ap.add_argument("--monto", type=float, default=None)
    ap.add_argument("--comercio", type=str, default=None)
    ap.add_argument("--categoria", type=str, default="general")
    ap.add_argument("--descripcion", type=str, default="")
    ap.add_argument("--listar", action="store_true", help="Listar últimos gastos")
    args = ap.parse_args()

    if args.listar:
        gastos = listar_gastos()
        for g in gastos:
            print(f"  [{g['fecha']}] ${g['monto']:>8.2f} | {g['comercio']:<20} | {g['categoria']}")
        return 0

    if args.monto is None or args.comercio is None:
        ap.print_help()
        return 1

    insertar_gasto(args.monto, args.comercio, args.categoria, args.descripcion)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
