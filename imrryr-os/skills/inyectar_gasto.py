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


def insertar_gasto(
    monto: float,
    comercio: str,
    categoria: str = "general",
    descripcion: str = "",
    fuente: str = "skill",
    fuente_id: str | None = None,
    fecha: str | None = None,
    banco: str = "",
) -> int:
    """fuente_id identifica el correo/transacción de origen (ej. el ID del
    mensaje de Gmail). Si ya existe un gasto con ese fuente_id, se omite el
    duplicado en vez de insertarlo de nuevo — permite pedir "procesa mis
    correos de 2025" más de una vez sin duplicar filas. `fecha` es la fecha
    real de la transacción (ISO 8601); si no se indica, se usa hoy (útil para
    inserciones manuales, pero la importación histórica siempre debe pasarla)."""
    if not DB_PATH.exists():
        log("ERROR: Base de datos no encontrada. Ejecuta: python scripts/init_db.py")
        return 0

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.execute(
            "INSERT INTO gastos (fecha, monto, comercio, categoria, descripcion, fuente, fuente_id, banco) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (fecha or date.today().isoformat(), monto, comercio, categoria, descripcion, fuente, fuente_id, banco),
        )
        conn.commit()
        log(f"Gasto insertado: ${monto} en {comercio} ({categoria})")
        return cur.lastrowid or 0
    except sqlite3.IntegrityError:
        log(f"Gasto ya registrado antes (fuente_id={fuente_id}); se omite duplicado")
        return 0
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


def inyectar_gasto(
    monto: float,
    comercio: str,
    categoria: str = "general",
    descripcion: str = "",
    fuente_id: str | None = None,
) -> dict:
    """Punto de entrada MCP (nombre = nombre de la skill, ver mcp_server/skills_server.py)."""
    return {"id": insertar_gasto(monto, comercio, categoria, descripcion, fuente_id=fuente_id)}


def actualizar_gasto(
    id: int,
    comercio: str = "",
    categoria: str = "",
    monto: float = 0,
    descripcion: str = "",
) -> dict:
    """Corrige un gasto ya registrado (nombre de comercio, categoría, monto o
    descripción). Solo se actualizan los campos que vengan con valor — así el
    agente puede, por ejemplo, corregir solo la categoría cuando el usuario le
    pida "revisa mis gastos y arregla las categorías", sin tocar el resto."""
    if not DB_PATH.exists():
        return {"ok": False, "error": "Base de datos no encontrada. Ejecuta: python scripts/init_db.py"}

    campos, valores = [], []
    if comercio:
        campos.append("comercio = ?")
        valores.append(comercio)
    if categoria:
        campos.append("categoria = ?")
        valores.append(categoria)
    if monto:
        campos.append("monto = ?")
        valores.append(monto)
    if descripcion:
        campos.append("descripcion = ?")
        valores.append(descripcion)
    if not campos:
        return {"ok": False, "error": "no se indicó ningún campo para actualizar"}

    conn = sqlite3.connect(str(DB_PATH))
    try:
        valores.append(id)
        cur = conn.execute(f"UPDATE gastos SET {', '.join(campos)} WHERE id = ?", valores)
        conn.commit()
        if cur.rowcount == 0:
            return {"ok": False, "error": f"no existe el gasto #{id}"}
        log(f"Gasto #{id} actualizado")
        return {"ok": True}
    finally:
        conn.close()


def eliminar_gasto(id: int) -> dict:
    if not DB_PATH.exists():
        return {"ok": False, "error": "Base de datos no encontrada."}
    conn = sqlite3.connect(str(DB_PATH))
    try:
        cur = conn.execute("DELETE FROM gastos WHERE id = ?", (id,))
        conn.commit()
        if cur.rowcount == 0:
            return {"ok": False, "error": f"no existe el gasto #{id}"}
        log(f"Gasto #{id} eliminado")
        return {"ok": True}
    finally:
        conn.close()


def main() -> int:
    ap = argparse.ArgumentParser(description="Inserta un gasto en SQLite")
    ap.add_argument("--monto", type=float, default=None)
    ap.add_argument("--comercio", type=str, default=None)
    ap.add_argument("--categoria", type=str, default="general")
    ap.add_argument("--descripcion", type=str, default="")
    ap.add_argument("--fuente-id", type=str, default=None, help="ID del correo/transacción de origen (evita duplicados)")
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

    insertar_gasto(args.monto, args.comercio, args.categoria, args.descripcion, fuente_id=args.fuente_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
