"""Configuración compartida de la suite de tests.

Los tests cubren SOLO la lógica determinista (parsers, limpieza de texto,
rangos de fecha) — nada que dependa de servicios vivos, red o IA. Todo lo
que toca la DB usa una base temporal creada con el esquema real de
scripts/init_db.py, nunca la DB del usuario en vault/.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
# Mismos dos sys.path que usa dashboard/server.py: skills/ para imports no
# calificados entre skills, ROOT para config.* / finanzas.* / scripts.*
sys.path.insert(0, str(ROOT / "skills"))
sys.path.insert(0, str(ROOT))


@pytest.fixture
def db_temporal(tmp_path):
    """Una DB SQLite temporal con el esquema real del proyecto."""
    from scripts.init_db import SCHEMA_SQL

    ruta = tmp_path / "imrryr_test.db"
    conn = sqlite3.connect(str(ruta))
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    conn.close()
    return ruta
