#!/usr/bin/env python3
"""
enviar_digest_compras.py — Skill: revisa precios y manda el digest diario
================================================================================
100% determinista, sin IA: el scheduler (scripts/scheduler.py) llama a esto
una vez al día. NO se expone como herramienta del Agente de Compras (no está
en herramientas_permitidas de agentes/agente_compras.yaml) — mismo
aislamiento que enviar_correo() nunca se expone directo al Secretario, esto
es una tarea de mantenimiento, no una acción conversacional.

Usa la cuenta de correo que el usuario eligió en Ajustes > Compras (guardada
en config/compras_prefs.json) para mandarse el digest a su propia casilla —
no le escribe a nadie más.

Uso:
    python skills/enviar_digest_compras.py
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "vault" / "sqlite" / "imrryr.db"
PREFS_PATH = ROOT / "config" / "compras_prefs.json"

sys.path.insert(0, str(ROOT))
from correo.config import obtener_cuenta  # noqa: E402
from correo.proveedores import gmail as _gmail  # noqa: E402
from correo.proveedores import imap_generico as _imap  # noqa: E402

from scraper_tiendas import scraper_tiendas  # noqa: E402

_PROVEEDORES = {"gmail": _gmail, "imap": _imap}


def log(msg: str) -> None:
    print(f"[enviar_digest_compras] {msg}", flush=True)


def _prefs() -> dict:
    if not PREFS_PATH.exists():
        return {}
    try:
        return json.loads(PREFS_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _revisar_seguimiento(conn: sqlite3.Connection, fila: sqlite3.Row) -> list[dict]:
    resultados = scraper_tiendas(fila["producto"], fila["tiendas"])
    nuevas = []
    for tienda, ofertas in resultados.items():
        for oferta in ofertas:
            precio = oferta["precio"]
            if fila["precio_min"] is not None and precio < fila["precio_min"]:
                continue
            if fila["precio_max"] is not None and precio > fila["precio_max"]:
                continue
            conn.execute(
                "INSERT INTO ofertas_encontradas (seguimiento_id, tienda, titulo, precio, url) VALUES (?, ?, ?, ?, ?)",
                (fila["id"], tienda, oferta["titulo"], precio, oferta["url"]),
            )
            nuevas.append({"producto": fila["producto"], "tienda": tienda, **oferta})
    conn.execute(
        "UPDATE productos_seguimiento SET ultimo_chequeo = datetime('now') WHERE id = ?", (fila["id"],)
    )
    return nuevas


def _armar_digest(ofertas: list[dict]) -> str:
    lineas = ["Ofertas encontradas hoy:", ""]
    por_producto: dict[str, list[dict]] = {}
    for o in ofertas:
        por_producto.setdefault(o["producto"], []).append(o)
    for producto, items in por_producto.items():
        lineas.append(f"• {producto}:")
        for it in sorted(items, key=lambda x: x["precio"]):
            lineas.append(f"    - {it['tienda']}: ${it['precio']:,.0f} — {it['titulo']} ({it['url']})".replace(",", "."))
        lineas.append("")
    return "\n".join(lineas)


def enviar_digest_compras() -> dict:
    """Punto de entrada MCP (y llamado por import directo desde el scheduler)."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        seguimientos = conn.execute("SELECT * FROM productos_seguimiento WHERE activo = 1").fetchall()
        if not seguimientos:
            return {"enviado": False, "motivo": "sin productos en seguimiento"}

        todas_las_ofertas: list[dict] = []
        for fila in seguimientos:
            todas_las_ofertas.extend(_revisar_seguimiento(conn, fila))
        conn.commit()

        if not todas_las_ofertas:
            log("sin ofertas nuevas dentro de rango hoy")
            return {"enviado": False, "motivo": "sin ofertas nuevas dentro de rango"}

        prefs = _prefs()
        cuenta_id = prefs.get("cuenta_correo_id", "")
        destinatario = prefs.get("destinatario", "")
        cuenta = obtener_cuenta(cuenta_id) if cuenta_id else None
        if not cuenta or not destinatario:
            log("falta elegir cuenta de correo y/o destinatario en Ajustes > Compras — no se pudo enviar el digest")
            return {"enviado": False, "motivo": "sin cuenta de correo o destinatario configurado", "ofertas_encontradas": len(todas_las_ofertas)}

        modulo = _PROVEEDORES.get(cuenta.get("proveedor", ""))
        if not modulo:
            return {"enviado": False, "motivo": "proveedor de correo desconocido"}

        cuerpo = _armar_digest(todas_las_ofertas)
        modulo.enviar_correo(cuenta, destinatario, "Ofertas de hoy — Imrryr OS", cuerpo)
        log(f"digest enviado con {len(todas_las_ofertas)} oferta(s)")
        return {"enviado": True, "ofertas_encontradas": len(todas_las_ofertas)}
    finally:
        conn.close()


if __name__ == "__main__":
    print(enviar_digest_compras())
