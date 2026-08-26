#!/usr/bin/env python3
"""
recordatorios.py — Skill: Gestión de recordatorios y alarmas proactivas
=======================================================================
Fase 5.3: Programa recordatorios que disparan mensajes a la hora señalada.
Usa SQLite como almacén de persistencia.

Uso:
    python skills/recordatorios.py --crear "Revisar presupuesto" --cuando "2026-07-01 17:00"
    python skills/recordatorios.py --listar
    python skills/recordatorios.py --ejecutar  # revisa y dispara vencidos
"""
from __future__ import annotations

import argparse
import sqlite3
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "vault" / "sqlite" / "imrryr.db"


def log(msg: str) -> None:
    print(f"[recordatorios] {msg}", flush=True)


def _init_table():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS recordatorios (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            mensaje     TEXT NOT NULL,
            programado  TEXT NOT NULL,       -- ISO 8601
            disparado   INTEGER DEFAULT 0,
            destino     TEXT DEFAULT 'whatsapp',
            created_at  TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.commit()
    conn.close()


def crear_recordatorio(mensaje: str, cuando: str, destino: str = "whatsapp") -> int:
    _init_table()
    conn = sqlite3.connect(str(DB_PATH))
    try:
        cur = conn.execute(
            "INSERT INTO recordatorios (mensaje, programado, destino) VALUES (?, ?, ?)",
            (mensaje, cuando, destino),
        )
        conn.commit()
        log(f"Recordatorio creado: '{mensaje}' para {cuando}")
        return cur.lastrowid or 0
    finally:
        conn.close()


def listar_pendientes() -> list[dict]:
    _init_table()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.execute(
            "SELECT * FROM recordatorios WHERE disparado = 0 ORDER BY programado ASC"
        )
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def ejecutar_vencidos() -> int:
    _init_table()
    ahora = datetime.now().isoformat(timespec="minutes")
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.execute(
            "SELECT * FROM recordatorios WHERE disparado = 0 AND programado <= ?",
            (ahora,),
        )
        vencidos = [dict(row) for row in cur.fetchall()]

        for r in vencidos:
            log(f"DISPARANDO: {r['mensaje']}")
            _notificar(r["mensaje"])
            conn.execute("UPDATE recordatorios SET disparado = 1 WHERE id = ?", (r["id"],))

        conn.commit()
        log(f"{len(vencidos)} recordatorio(s) disparado(s)")
        return len(vencidos)
    finally:
        conn.close()


def _notificar(mensaje: str):
    """Envía la notificación como mensaje saliente real (no simula un mensaje entrante)."""
    try:
        import httpx
        r = httpx.post(
            "http://localhost:5050/api/gateway/enviar",
            json={"texto": f"Recordatorio: {mensaje}"},
            timeout=10,
        )
        if r.status_code == 200 and r.json().get("enviado"):
            log("Notificacion enviada por WhatsApp")
        else:
            log(f"El gateway no pudo enviar la notificacion: {r.text[:200]}")
    except Exception as e:
        log(f"No se pudo notificar (¿está corriendo el gateway en :5050?): {e}")


def recordatorios(
    crear: str | None = None,
    cuando: str | None = None,
    ejecutar: bool = False,
    listar: bool = False,
) -> dict:
    """Punto de entrada MCP (nombre = nombre de la skill, ver mcp_server/skills_server.py).
    Crea, lista o dispara recordatorios pendientes según qué parámetros vengan."""
    if crear and cuando:
        return {"creado": crear_recordatorio(crear, cuando)}
    if ejecutar:
        return {"disparados": ejecutar_vencidos()}
    if listar:
        return {"pendientes": listar_pendientes()}
    return {"error": "especifica crear+cuando, ejecutar=true o listar=true"}


def main() -> int:
    ap = argparse.ArgumentParser(description="Gestor de recordatorios")
    ap.add_argument("--crear", type=str, help="Mensaje del recordatorio")
    ap.add_argument("--cuando", type=str, help="Fecha/hora ISO (YYYY-MM-DD HH:MM)")
    ap.add_argument("--listar", action="store_true", help="Listar pendientes")
    ap.add_argument("--ejecutar", action="store_true", help="Disparar vencidos")
    args = ap.parse_args()

    if args.crear and args.cuando:
        crear_recordatorio(args.crear, args.cuando)
        return 0

    if args.listar:
        pendientes = listar_pendientes()
        if not pendientes:
            log("No hay recordatorios pendientes.")
        for r in pendientes:
            print(f"  [{r['id']}] {r['programado']} - {r['mensaje']} ({'listo' if r['disparado'] else 'pendiente'})")
        return 0

    if args.ejecutar:
        ejecutar_vencidos()
        return 0

    ap.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
