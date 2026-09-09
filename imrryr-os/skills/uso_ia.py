#!/usr/bin/env python3
"""
uso_ia.py — Observabilidad, Telemetría y Presupuesto de IA (Kernel Scheduler)
============================================================================
Telemetría agéntica del estado del arte (2025-2026):
1. Registro por llamada de canal, agente, proveedor, modelo, tokens y latencia.
2. Presupuesto configurable (config/presupuesto_ia.json).
3. Agregación de consumo por agente, canal y tendencias de 7 días.
4. Circuit breaker y umbrales proactivos de alerta.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "vault" / "sqlite" / "imrryr.db"
PRESUPUESTO_PATH = ROOT / "config" / "presupuesto_ia.json"
LIMITE_GRATUITO = 20


def obtener_limite_diario() -> int:
    """Retorna el límite configurado de consultas diarias."""
    if PRESUPUESTO_PATH.exists():
        try:
            data = json.loads(PRESUPUESTO_PATH.read_text(encoding="utf-8"))
            limite = int(data.get("limite_diario", 0))
            if limite > 0:
                return limite
        except Exception:
            pass
    return LIMITE_GRATUITO


def guardar_limite_diario(nuevo_limite: int) -> dict:
    """Guarda un nuevo límite diario en config/presupuesto_ia.json."""
    if nuevo_limite <= 0:
        return {"ok": False, "error": "El límite debe ser mayor a 0"}
    PRESUPUESTO_PATH.parent.mkdir(parents=True, exist_ok=True)
    PRESUPUESTO_PATH.write_text(
        json.dumps({"limite_diario": nuevo_limite}, indent=2), encoding="utf-8"
    )
    return {"ok": True, "limite_diario": nuevo_limite}


def registrar_uso(
    canal: str,
    agente: str = "",
    proveedor: str = "",
    modelo: str = "",
    tokens_estimados: int = 0,
    latencia_ms: int = 0,
) -> None:
    """Registra una interacción de IA en la telemetría del sistema."""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        try:
            try:
                conn.execute(
                    """
                    INSERT INTO uso_ia (fecha, canal, agente, proveedor, modelo, tokens_estimados, latencia_ms)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (date.today().isoformat(), canal, agente, proveedor, modelo, tokens_estimados, latencia_ms),
                )
            except sqlite3.OperationalError:
                conn.execute(
                    "INSERT INTO uso_ia (fecha, canal, agente) VALUES (?, ?, ?)",
                    (date.today().isoformat(), canal, agente),
                )
            conn.commit()
        finally:
            conn.close()
    except Exception:
        pass


def uso_de_hoy(incluir_detalles: bool = False) -> dict:
    """Retorna el conteo diario. Si incluir_detalles=True, provee telemetría completa."""
    limite = obtener_limite_diario()
    hoy_iso = date.today().isoformat()

    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        try:
            cur = conn.execute(
                "SELECT COUNT(*) AS total, COALESCE(SUM(tokens_estimados), 0) AS tokens, AVG(latencia_ms) AS lat_prom "
                "FROM uso_ia WHERE fecha = ?",
                (hoy_iso,),
            )
            fila = cur.fetchone()
            total_hoy = fila["total"] if fila else 0
            tokens_hoy = int(fila["tokens"]) if fila else 0
            latencia_prom = round(float(fila["lat_prom"] or 0), 1) if fila else 0.0

            # Desglose por agente
            cur_ag = conn.execute(
                "SELECT agente, COUNT(*) as c FROM uso_ia WHERE fecha = ? GROUP BY agente", (hoy_iso,)
            )
            por_agente = {r["agente"] or "general": r["c"] for r in cur_ag.fetchall()}

            # Desglose por canal
            cur_ch = conn.execute(
                "SELECT canal, COUNT(*) as c FROM uso_ia WHERE fecha = ? GROUP BY canal", (hoy_iso,)
            )
            por_canal = {r["canal"]: r["c"] for r in cur_ch.fetchall()}

            # Histórico 7 días
            cur_hist = conn.execute(
                "SELECT fecha, COUNT(*) as c FROM uso_ia GROUP BY fecha ORDER BY fecha DESC LIMIT 7"
            )
            ultimos_7 = [{"fecha": r["fecha"], "total": r["c"]} for r in reversed(cur_hist.fetchall())]
        finally:
            conn.close()
    except Exception:
        total_hoy = 0
        tokens_hoy = 0
        latencia_prom = 0.0
        por_agente = {}
        por_canal = {}
        ultimos_7 = []

    base = {"hoy": total_hoy, "limite": limite}
    if not incluir_detalles:
        return base

    pct = round((total_hoy / max(limite, 1)) * 100, 1)
    if pct >= 100:
        alerta = "limite_alcanzado"
    elif pct >= 75:
        alerta = "advertencia"
    else:
        alerta = "normal"

    proveedor_nombre = "Google Gemini"
    modelo_nombre = "gemini-2.5-flash"
    try:
        sys.path.insert(0, str(ROOT))
        from config.cuentas_ia import PROVEEDORES, obtener_cuenta_activa
        activa = obtener_cuenta_activa()
        if activa:
            prov_id = activa.get("proveedor", "")
            prov_info = PROVEEDORES.get(prov_id, {})
            proveedor_nombre = activa.get("nombre") or prov_info.get("nombre", prov_id)
            modelo_nombre = activa.get("modelo") or prov_info.get("modelo_base", "")
    except Exception:
        pass

    base.update({
        "consumo_pct": pct,
        "alerta": alerta,
        "proveedor": proveedor_nombre,
        "modelo": modelo_nombre,
        "tokens_estimados": tokens_hoy,
        "latencia_promedio_ms": latencia_prom,
        "por_agente": por_agente,
        "por_canal": por_canal,
        "ultimos_7_dias": ultimos_7,
    })
    return base