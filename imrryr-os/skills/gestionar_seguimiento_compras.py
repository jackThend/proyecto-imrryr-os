#!/usr/bin/env python3
"""
gestionar_seguimiento_compras.py — Skill: CRUD de productos en seguimiento
================================================================================
El usuario le pide al Agente de Compras que siga un producto (con rango de
precio objetivo y tiendas preferidas); esta skill guarda/lista/desactiva/
elimina esas filas en productos_seguimiento. La revisión de precios en sí
(scraper_tiendas + el envío del correo) la hace el scheduler una vez al día
vía skills/enviar_digest_compras.py — esta skill nunca dispara scraping.

Uso:
    python skills/gestionar_seguimiento_compras.py --accion listar
"""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "vault" / "sqlite" / "imrryr.db"


def log(msg: str) -> None:
    print(f"[gestionar_seguimiento_compras] {msg}", flush=True)


def _crear(producto: str, precio_min: float | None, precio_max: float | None, tiendas: str) -> dict[str, Any]:
    if not producto:
        return {"ok": False, "error": "falta 'producto'"}
    conn = sqlite3.connect(str(DB_PATH))
    try:
        cur = conn.execute(
            "INSERT INTO productos_seguimiento (producto, precio_min, precio_max, tiendas) VALUES (?, ?, ?, ?)",
            (producto, precio_min, precio_max, tiendas or "mercadolibre,falabella,paris,ripley"),
        )
        conn.commit()
        log(f"Seguimiento creado #{cur.lastrowid}: {producto}")
        return {"ok": True, "id": cur.lastrowid}
    finally:
        conn.close()


def _listar() -> dict[str, Any]:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.execute("SELECT * FROM productos_seguimiento ORDER BY created_at DESC")
        return {"ok": True, "seguimientos": [dict(row) for row in cur.fetchall()]}
    finally:
        conn.close()


def _desactivar(seguimiento_id: int) -> dict[str, Any]:
    conn = sqlite3.connect(str(DB_PATH))
    try:
        conn.execute("UPDATE productos_seguimiento SET activo = 0 WHERE id = ?", (seguimiento_id,))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


def _eliminar(seguimiento_id: int) -> dict[str, Any]:
    conn = sqlite3.connect(str(DB_PATH))
    try:
        conn.execute("DELETE FROM ofertas_encontradas WHERE seguimiento_id = ?", (seguimiento_id,))
        conn.execute("DELETE FROM productos_seguimiento WHERE id = ?", (seguimiento_id,))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


def gestionar_seguimiento_compras(
    accion: str = "",
    producto: str = "",
    precio_min: float | None = None,
    precio_max: float | None = None,
    tiendas: str = "",
    seguimiento_id: int | None = None,
) -> dict:
    """Punto de entrada MCP. accion: crear | listar | desactivar | eliminar"""
    if accion == "crear":
        return _crear(producto, precio_min, precio_max, tiendas)
    if accion == "listar":
        return _listar()
    if accion == "desactivar":
        if seguimiento_id is None:
            return {"ok": False, "error": "falta seguimiento_id"}
        return _desactivar(seguimiento_id)
    if accion == "eliminar":
        if seguimiento_id is None:
            return {"ok": False, "error": "falta seguimiento_id"}
        return _eliminar(seguimiento_id)
    return {"ok": False, "error": f"acción desconocida: {accion}"}


def main() -> int:
    ap = argparse.ArgumentParser(description="CRUD de productos en seguimiento")
    ap.add_argument("--accion", type=str, required=True)
    ap.add_argument("--producto", type=str, default="")
    ap.add_argument("--precio-min", type=float, default=None, dest="precio_min")
    ap.add_argument("--precio-max", type=float, default=None, dest="precio_max")
    ap.add_argument("--tiendas", type=str, default="")
    ap.add_argument("--id", type=int, default=None, dest="seguimiento_id")
    args = ap.parse_args()

    resultado = gestionar_seguimiento_compras(
        accion=args.accion, producto=args.producto, precio_min=args.precio_min,
        precio_max=args.precio_max, tiendas=args.tiendas, seguimiento_id=args.seguimiento_id,
    )
    print(resultado)
    return 0 if resultado.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
