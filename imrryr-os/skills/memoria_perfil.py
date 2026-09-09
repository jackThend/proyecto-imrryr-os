#!/usr/bin/env python3
"""
memoria_perfil.py — Skill: Memoria Jerárquica de Usuario (Estilo Mem0 / Letta)
==================================================================================
Permite a cualquier agente registrar y consultar hechos duraderos, preferencias,
reglas de negocio o información clave sobre el usuario que deben persistir a lo
largo del tiempo en vault/sqlite/imrryr.db (tabla memoria_usuario).
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "vault" / "sqlite" / "imrryr.db"


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS memoria_usuario (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            categoria   TEXT NOT NULL,
            clave       TEXT NOT NULL UNIQUE,
            valor       TEXT NOT NULL,
            fuente      TEXT DEFAULT 'chat',
            updated_at  TEXT DEFAULT (datetime('now'))
        )
    """)
    return conn


def guardar_hecho_memoria(clave: str, valor: str, categoria: str = "preferencia") -> dict[str, Any]:
    """Guarda o actualiza un hecho relevante o preferencia sobre el usuario."""
    clave_clean = clave.strip().lower()
    categoria_clean = categoria.strip().lower() or "preferencia"
    conn = _conn()
    try:
        conn.execute(
            "INSERT INTO memoria_usuario (categoria, clave, valor, updated_at) "
            "VALUES (?, ?, ?, datetime('now')) "
            "ON CONFLICT(clave) DO UPDATE SET valor = excluded.valor, categoria = excluded.categoria, updated_at = datetime('now')",
            (categoria_clean, clave_clean, valor.strip()),
        )
        conn.commit()
        return {
            "ok": True,
            "mensaje": f"Hecho recordado: [{categoria_clean}] {clave_clean} = {valor.strip()}",
            "clave": clave_clean,
            "categoria": categoria_clean,
        }
    finally:
        conn.close()


def consultar_memoria_usuario(categoria: str = "") -> list[dict[str, Any]]:
    """Consulta la lista de hechos recordados sobre el usuario, opcionalmente filtrando por categoría."""
    conn = _conn()
    try:
        if categoria:
            cur = conn.execute(
                "SELECT categoria, clave, valor, updated_at FROM memoria_usuario WHERE categoria = ? ORDER BY clave",
                (categoria.strip().lower(),),
            )
        else:
            cur = conn.execute(
                "SELECT categoria, clave, valor, updated_at FROM memoria_usuario ORDER BY categoria, clave"
            )
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def borrar_hecho_memoria(clave: str) -> dict[str, Any]:
    """Elimina un hecho específico de la memoria del usuario."""
    conn = _conn()
    try:
        cur = conn.execute("DELETE FROM memoria_usuario WHERE clave = ?", (clave.strip().lower(),))
        conn.commit()
        return {"ok": cur.rowcount > 0, "clave": clave}
    finally:
        conn.close()


def main() -> int:
    ap = argparse.ArgumentParser(description="Gestión de memoria de usuario (Mem0-style)")
    ap.add_argument("--accion", choices=["guardar", "consultar", "borrar"], default="consultar")
    ap.add_argument("--clave", type=str, default="")
    ap.add_argument("--valor", type=str, default="")
    ap.add_argument("--categoria", type=str, default="")
    args = ap.parse_args()

    if args.accion == "guardar":
        if not args.clave or not args.valor:
            print(json.dumps({"error": "clave y valor son obligatorios para guardar"}))
            return 1
        res = guardar_hecho_memoria(args.clave, args.valor, args.categoria or "preferencia")
        print(json.dumps(res, ensure_ascii=False, indent=2))
    elif args.accion == "borrar":
        res = borrar_hecho_memoria(args.clave)
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        res = consultar_memoria_usuario(args.categoria)
        print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())