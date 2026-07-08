#!/usr/bin/env python3
"""
secretario.py — Skill: Agente Secretario (correo multi-proveedor)
=====================================================================
Despacha a correo/proveedores/gmail.py o correo/proveedores/imap_generico.py
según el proveedor configurado en cada cuenta (correo/config.py) — mismo
patrón que el gateway dual de WhatsApp (un módulo de config + conectores
intercambiables).

IMPORTANTE (seguridad, decisión del usuario): el Agente Secretario NUNCA
envía correos por su cuenta. `crear_borrador_respuesta` solo GUARDA un
borrador en SQLite (tabla borradores_pendientes); el envío real solo ocurre
cuando el humano hace clic en "Enviar" en el dashboard, que llama a
enviar_borrador(). Por eso listar_borradores/enviar_borrador/descartar_borrador
NO tienen manifiesto .mcp.json — el agente ni siquiera tiene la herramienta
para invocarlos, no es solo una instrucción de prompt.

Uso:
    python skills/secretario.py --listar-borradores
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "vault" / "sqlite" / "imrryr.db"

sys.path.insert(0, str(ROOT))
from correo.config import obtener_cuenta  # noqa: E402
from correo.proveedores import gmail as _gmail  # noqa: E402
from correo.proveedores import imap_generico as _imap  # noqa: E402

_PROVEEDORES = {"gmail": _gmail, "imap": _imap}


def log(msg: str) -> None:
    print(f"[correo] {msg}", flush=True)


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _proveedor_de(cuenta_id: str):
    cuenta = obtener_cuenta(cuenta_id)
    if not cuenta:
        return None, None
    modulo = _PROVEEDORES.get(cuenta.get("proveedor", ""))
    return cuenta, modulo


# --- Herramientas del agente (con manifiesto MCP) ---
def leer_correo(cuenta_id: str, max_resultados: int = 5, query: str = "") -> list[dict]:
    cuenta, modulo = _proveedor_de(cuenta_id)
    if not modulo:
        log(f"Cuenta '{cuenta_id}' no configurada o proveedor desconocido")
        return []
    return modulo.leer_correo(cuenta, max_resultados, query)


def archivar_correo(cuenta_id: str, mensaje_id: str) -> dict:
    cuenta, modulo = _proveedor_de(cuenta_id)
    if not modulo:
        return {"ok": False, "error": f"cuenta '{cuenta_id}' no configurada"}
    return modulo.archivar_correo(cuenta, mensaje_id)


def crear_borrador_respuesta(
    cuenta_id: str,
    destinatario: str,
    cuerpo: str,
    asunto: str = "",
    mensaje_id_original: str = "",
) -> dict:
    """Guarda un borrador PENDIENTE DE APROBACIÓN — nunca lo envía. El humano
    lo revisa y lo envía con un clic desde el dashboard."""
    if not DB_PATH.exists():
        return {"ok": False, "error": "Base de datos no encontrada. Ejecuta: python scripts/init_db.py"}

    conn = _conn()
    try:
        cur = conn.execute(
            "INSERT INTO borradores_pendientes (cuenta_id, destinatario, asunto, cuerpo, mensaje_id_original) "
            "VALUES (?, ?, ?, ?, ?)",
            (cuenta_id, destinatario, asunto, cuerpo, mensaje_id_original),
        )
        conn.commit()
        log(f"Borrador #{cur.lastrowid} creado para {destinatario} (pendiente de aprobación)")
        return {"ok": True, "id": cur.lastrowid, "estado": "pendiente"}
    finally:
        conn.close()


# --- Funciones solo para el dashboard (SIN manifiesto MCP: el agente no puede llamarlas) ---
def listar_borradores(estado: str = "pendiente") -> list[dict]:
    if not DB_PATH.exists():
        return []
    conn = _conn()
    try:
        if estado:
            cur = conn.execute("SELECT * FROM borradores_pendientes WHERE estado = ? ORDER BY created_at DESC", (estado,))
        else:
            cur = conn.execute("SELECT * FROM borradores_pendientes ORDER BY created_at DESC")
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def enviar_borrador(id: int) -> dict:
    """Único punto del sistema que realmente envía un correo. Solo lo debe
    llamar el endpoint del dashboard cuando el humano hace clic en 'Enviar'."""
    conn = _conn()
    try:
        fila = conn.execute("SELECT * FROM borradores_pendientes WHERE id = ?", (id,)).fetchone()
        if not fila:
            return {"ok": False, "error": f"no existe el borrador #{id}"}
        if fila["estado"] != "pendiente":
            return {"ok": False, "error": f"el borrador #{id} ya está '{fila['estado']}'"}

        cuenta, modulo = _proveedor_de(fila["cuenta_id"])
        if not modulo:
            return {"ok": False, "error": f"cuenta '{fila['cuenta_id']}' no configurada"}

        resultado = modulo.enviar_correo(cuenta, fila["destinatario"], fila["asunto"] or "", fila["cuerpo"])
        if resultado.get("ok"):
            conn.execute(
                "UPDATE borradores_pendientes SET estado = 'enviado', updated_at = datetime('now') WHERE id = ?",
                (id,),
            )
            conn.commit()
        return resultado
    finally:
        conn.close()


def descartar_borrador(id: int) -> dict:
    conn = _conn()
    try:
        conn.execute(
            "UPDATE borradores_pendientes SET estado = 'descartado', updated_at = datetime('now') WHERE id = ?",
            (id,),
        )
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


def main() -> int:
    ap = argparse.ArgumentParser(description="Agente Secretario: correo multi-proveedor")
    ap.add_argument("--listar-borradores", action="store_true")
    ap.add_argument("--estado", type=str, default="pendiente")
    args = ap.parse_args()

    if args.listar_borradores:
        print(json.dumps(listar_borradores(args.estado), ensure_ascii=True, indent=2))
        return 0

    ap.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
