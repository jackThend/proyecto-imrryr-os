#!/usr/bin/env python3
"""
init_db.py — Inicializa la Memoria Relacional (SQLite)
=======================================================
Fase 2.3: Crea la base de datos SQLite con el esquema de Gastos.

Uso:
    python scripts/init_db.py
    python scripts/init_db.py --reset   # borra y recrea tablas
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_DIR = ROOT / "vault" / "sqlite"
DB_PATH = DB_DIR / "imrryr.db"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS gastos (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha           TEXT    NOT NULL,            -- ISO 8601: 2026-06-28
    monto           REAL    NOT NULL,
    comercio        TEXT    NOT NULL,
    categoria       TEXT    NOT NULL DEFAULT 'general',
    descripcion     TEXT,
    fuente          TEXT    DEFAULT 'manual',    -- manual, gmail, webhook
    created_at      TEXT    DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS proyectos (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre          TEXT    NOT NULL UNIQUE,
    descripcion     TEXT,
    estado          TEXT    DEFAULT 'activo',     -- activo, pausado, completado
    tecnologias     TEXT,                         -- comma-separated
    created_at      TEXT    DEFAULT (datetime('now')),
    updated_at      TEXT    DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS semillas (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    titulo          TEXT    NOT NULL,
    descripcion     TEXT,
    etiquetas       TEXT,                         -- comma-separated tags
    estado          TEXT    DEFAULT 'pendiente',  -- pendiente, evaluada, adoptada
    fuente          TEXT    DEFAULT 'manual',     -- manual, whatsapp, web
    created_at      TEXT    DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_gastos_fecha ON gastos(fecha);
CREATE INDEX IF NOT EXISTS idx_gastos_categoria ON gastos(categoria);
CREATE INDEX IF NOT EXISTS idx_proyectos_estado ON proyectos(estado);
CREATE INDEX IF NOT EXISTS idx_semillas_estado ON semillas(estado);
"""


def log(msg: str) -> None:
    print(f"[db] {msg}", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser(description="Inicializa la base de datos SQLite")
    ap.add_argument("--reset", action="store_true", help="Borrar y recrear tablas")
    args = ap.parse_args()

    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")

    if args.reset:
        conn.executescript("DROP TABLE IF EXISTS gastos; DROP TABLE IF EXISTS proyectos; DROP TABLE IF EXISTS semillas;")
        log("Tablas eliminadas.")

    conn.executescript(SCHEMA_SQL)
    conn.commit()

    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
    tables = [row[0] for row in cur.fetchall()]
    log(f"BD inicializada: {DB_PATH}")
    log(f"Tablas: {', '.join(tables)}")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
