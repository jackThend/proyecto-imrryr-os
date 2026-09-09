#!/usr/bin/env python3
"""
confirmacion_hitl.py — Skill / Sistema Human-in-the-Loop (HITL)
================================================================
Permite a cualquier agente de Imrryr OS (Asistente, Build, CRM, Secretario)
suspender una acción sensible (envío masivo, modificación crítica de archivos,
ejecución de scripts externos o transferencias) y solicitar autorización
explícita al usuario a través del Dashboard.

Cumple con el estándar de seguridad AI-OS 2026 de compuertas HITL:
el agente no adivina permisos ni ejecuta operaciones de riesgo a ciegas.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "vault" / "sqlite" / "imrryr.db"


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def solicitar_autorizacion_humana(
    agente: str,
    accion: str,
    resumen_humano: str,
    parametros: dict | str | None = None,
) -> dict:
    """Registra una solicitud de autorización pendiente en la base de datos.
    El dashboard notificará al usuario para que apruebe o rechace la acción.
    """
    if isinstance(parametros, dict):
        params_str = json.dumps(parametros, ensure_ascii=False)
    elif isinstance(parametros, str):
        params_str = parametros
    else:
        params_str = "{}"

    conn = _conn()
    try:
        cur = conn.execute(
            """
            INSERT INTO solicitudes_hitl (agente, accion, parametros, resumen_humano, estado, creado_at)
            VALUES (?, ?, ?, ?, 'pendiente', datetime('now'))
            """,
            (agente, accion, params_str, resumen_humano),
        )
        solicitud_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()

    return {
        "ok": True,
        "requiere_aprobacion": True,
        "solicitud_id": solicitud_id,
        "estado": "pendiente",
        "mensaje": (
            f"La acción '{accion}' requiere autorización del usuario. "
            f"Solicitud #{solicitud_id} registrada. Esperando confirmación en el Dashboard."
        ),
    }


def listar_solicitudes_pendientes(agente: str = "") -> list[dict]:
    """Lista las solicitudes pendientes de confirmación."""
    conn = _conn()
    try:
        if agente:
            cur = conn.execute(
                "SELECT * FROM solicitudes_hitl WHERE estado = 'pendiente' AND agente = ? ORDER BY id DESC",
                (agente,),
            )
        else:
            cur = conn.execute(
                "SELECT * FROM solicitudes_hitl WHERE estado = 'pendiente' ORDER BY id DESC"
            )
        filas = cur.fetchall()
        resultado = []
        for r in filas:
            item = dict(r)
            try:
                item["parametros"] = json.loads(item["parametros"])
            except Exception:
                pass
            resultado.append(item)
        return resultado
    finally:
        conn.close()


def resolver_solicitud(solicitud_id: int, decision: str) -> dict:
    """Resuelve una solicitud de autorización humana ('aprobado' o 'rechazado')."""
    decision = decision.lower().strip()
    if decision not in ("aprobado", "rechazado"):
        return {"ok": False, "error": "La decisión debe ser 'aprobado' o 'rechazado'"}

    ahora = datetime.now().isoformat()
    conn = _conn()
    try:
        cur = conn.execute(
            """
            UPDATE solicitudes_hitl
            SET estado = ?, resuelto_at = ?
            WHERE id = ? AND estado = 'pendiente'
            """,
            (decision, ahora, solicitud_id),
        )
        if cur.rowcount == 0:
            return {"ok": False, "error": f"Solicitud #{solicitud_id} no encontrada o ya resuelta"}
        conn.commit()
        return {"ok": True, "solicitud_id": solicitud_id, "nuevo_estado": decision}
    finally:
        conn.close()


def verificar_estado_solicitud(solicitud_id: int) -> dict:
    """Verifica si una solicitud fue aprobada, rechazada o sigue pendiente."""
    conn = _conn()
    try:
        fila = conn.execute(
            "SELECT * FROM solicitudes_hitl WHERE id = ?", (solicitud_id,)
        ).fetchone()
        if not fila:
            return {"ok": False, "error": f"Solicitud #{solicitud_id} no encontrada"}
        item = dict(fila)
        try:
            item["parametros"] = json.loads(item["parametros"])
        except Exception:
            pass
        return {"ok": True, "solicitud": item}
    finally:
        conn.close()


def main() -> int:
    ap = argparse.ArgumentParser(description="Gestor Human-in-the-Loop (HITL)")
    ap.add_argument("--listar", action="store_true", help="Listar solicitudes pendientes")
    ap.add_argument("--solicitar", action="store_true", help="Crear solicitud")
    ap.add_argument("--agente", type=str, default="asistente")
    ap.add_argument("--accion", type=str, default="")
    ap.add_argument("--resumen", type=str, default="")
    ap.add_argument("--resolver", type=int, help="ID de la solicitud a resolver")
    ap.add_argument("--decision", type=str, choices=["aprobado", "rechazado"])
    args = ap.parse_args()

    if args.listar:
        pendientes = listar_solicitudes_pendientes(args.agente if args.agente != "asistente" else "")
        print(json.dumps(pendientes, ensure_ascii=False, indent=2))
        return 0

    if args.solicitar and args.accion:
        res = solicitar_autorizacion_humana(args.agente, args.accion, args.resumen or args.accion)
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0

    if args.resolver and args.decision:
        res = resolver_solicitud(args.resolver, args.decision)
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0

    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())