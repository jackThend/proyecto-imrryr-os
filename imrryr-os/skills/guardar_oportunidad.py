#!/usr/bin/env python3
"""
guardar_oportunidad.py — Skill: Registra una oportunidad de fondo concursable
================================================================================
Usada por el Agente Investigador tras cruzar los hallazgos de scraper_fondos
con el Perfil de Negocio (leer_perfil_negocio). No se mezcla con la tabla de
gastos: una oportunidad de financiamiento no es un gasto.

Uso:
    python skills/guardar_oportunidad.py --fuente sercotec --hallazgo "Fondo Crece" --listar
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "vault" / "sqlite" / "imrryr.db"


def log(msg: str) -> None:
    print(f"[guardar_oportunidad] {msg}", flush=True)


def guardar_oportunidad(
    fuente: str,
    hallazgo: str,
    monto_estimado: str = "",
    fecha_cierre: str = "",
    relevancia_nota: str = "",
) -> int:
    if not DB_PATH.exists():
        log("ERROR: Base de datos no encontrada. Ejecuta: python scripts/init_db.py")
        return 0

    conn = sqlite3.connect(str(DB_PATH))
    try:
        cur = conn.execute(
            "INSERT INTO oportunidades_fondos (fuente, hallazgo, monto_estimado, fecha_cierre, relevancia_nota) "
            "VALUES (?, ?, ?, ?, ?)",
            (fuente, hallazgo, monto_estimado, fecha_cierre, relevancia_nota),
        )
        conn.commit()
        log(f"Oportunidad guardada: {hallazgo} ({fuente})")
        return cur.lastrowid or 0
    finally:
        conn.close()


def listar_oportunidades(estado: str = "", limite: int = 20) -> list[dict]:
    if not DB_PATH.exists():
        return []
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        if estado:
            cur = conn.execute(
                "SELECT * FROM oportunidades_fondos WHERE estado = ? ORDER BY created_at DESC LIMIT ?",
                (estado, limite),
            )
        else:
            cur = conn.execute(
                "SELECT * FROM oportunidades_fondos ORDER BY created_at DESC LIMIT ?",
                (limite,),
            )
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def cambiar_estado_oportunidad(id: int, estado: str, relevancia_nota: str = "") -> dict:
    """Marca una oportunidad como revisada/postulada/descartada. No es una acción
    irreversible (a diferencia de enviar un correo), así que el propio Agente
    Investigador puede llamarla directamente al terminar de evaluar un hallazgo."""
    if not DB_PATH.exists():
        return {"ok": False, "error": "Base de datos no encontrada. Ejecuta: python scripts/init_db.py"}
    conn = sqlite3.connect(str(DB_PATH))
    try:
        if relevancia_nota:
            conn.execute(
                "UPDATE oportunidades_fondos SET estado = ?, relevancia_nota = ? WHERE id = ?",
                (estado, relevancia_nota, id),
            )
        else:
            conn.execute("UPDATE oportunidades_fondos SET estado = ? WHERE id = ?", (estado, id))
        conn.commit()
        log(f"Oportunidad #{id} -> {estado}")
        return {"ok": True}
    finally:
        conn.close()


def main() -> int:
    ap = argparse.ArgumentParser(description="Guarda o lista oportunidades de fondos concursables")
    ap.add_argument("--fuente", type=str, default=None)
    ap.add_argument("--hallazgo", type=str, default=None)
    ap.add_argument("--monto-estimado", type=str, default="")
    ap.add_argument("--fecha-cierre", type=str, default="")
    ap.add_argument("--relevancia-nota", type=str, default="")
    ap.add_argument("--listar", action="store_true")
    ap.add_argument("--estado", type=str, default="")
    args = ap.parse_args()

    if args.listar:
        print(json.dumps(listar_oportunidades(args.estado), ensure_ascii=True, indent=2))
        return 0

    if not args.fuente or not args.hallazgo:
        ap.print_help()
        return 1

    guardar_oportunidad(args.fuente, args.hallazgo, args.monto_estimado, args.fecha_cierre, args.relevancia_nota)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
