#!/usr/bin/env python3
"""
respaldo_db.py — Respaldo local de la base de datos (Tanda X)
=====================================================================
Todos los datos del usuario (gastos, eventos, seguimientos de compras,
mensajes de WhatsApp, oportunidades...) viven en un único archivo SQLite.
Local-first significa que la soberanía de los datos es del usuario — pero
también que nadie más tiene una copia. Este módulo cierra esa brecha con
respaldos locales automáticos:

  - Usa la API de backup de sqlite3 (no un copy del archivo), que es segura
    aunque la DB esté en uso por el dashboard/scheduler en ese momento.
  - Un respaldo por día en vault/backups/imrryr_YYYY-MM-DD.db (correr dos
    veces el mismo día simplemente sobreescribe el del día).
  - Retención: se conservan los últimos RETENCION_DIAS respaldos; los más
    viejos se borran solos para no crecer sin límite.
  - vault/ ya está en .gitignore — los respaldos nunca van al repo.

Restaurar es manual y deliberadamente simple: detener los servicios y
copiar el archivo de respaldo sobre vault/sqlite/imrryr.db.

Uso:
    python scripts/respaldo_db.py            # crea un respaldo ahora
    python scripts/respaldo_db.py --listar   # muestra los existentes
"""
from __future__ import annotations

import argparse
import sqlite3
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "vault" / "sqlite" / "imrryr.db"
BACKUPS_DIR = ROOT / "vault" / "backups"
RETENCION = 14  # respaldos (≈ días) a conservar


def log(msg: str) -> None:
    print(f"[respaldo_db] {msg}", flush=True)


def _purgar_viejos() -> int:
    """Borra los respaldos más viejos que excedan la retención. Devuelve cuántos borró."""
    respaldos = sorted(BACKUPS_DIR.glob("imrryr_*.db"))
    excedentes = respaldos[:-RETENCION] if len(respaldos) > RETENCION else []
    for viejo in excedentes:
        viejo.unlink()
        log(f"respaldo viejo purgado: {viejo.name}")
    return len(excedentes)


def crear_respaldo() -> dict:
    """Crea (o sobreescribe) el respaldo de hoy. Seguro con la DB en uso."""
    if not DB_PATH.exists():
        return {"ok": False, "error": "la base de datos no existe todavía"}
    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    destino = BACKUPS_DIR / f"imrryr_{date.today().isoformat()}.db"

    origen = sqlite3.connect(str(DB_PATH))
    try:
        copia = sqlite3.connect(str(destino))
        try:
            origen.backup(copia)
        finally:
            copia.close()
    finally:
        origen.close()

    purgados = _purgar_viejos()
    tamano_kb = destino.stat().st_size // 1024
    log(f"respaldo creado: {destino.name} ({tamano_kb} KB)")
    return {"ok": True, "archivo": destino.name, "tamano_kb": tamano_kb, "purgados": purgados}


def listar_respaldos() -> list[dict]:
    if not BACKUPS_DIR.exists():
        return []
    return [
        {"archivo": p.name, "tamano_kb": p.stat().st_size // 1024}
        for p in sorted(BACKUPS_DIR.glob("imrryr_*.db"), reverse=True)
    ]


def main() -> int:
    ap = argparse.ArgumentParser(description="Respaldo local de la base de datos")
    ap.add_argument("--listar", action="store_true")
    args = ap.parse_args()
    if args.listar:
        for r in listar_respaldos():
            print(f"  {r['archivo']}  {r['tamano_kb']} KB")
        return 0
    resultado = crear_respaldo()
    print(resultado)
    return 0 if resultado.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
