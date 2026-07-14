#!/usr/bin/env python3
"""
uso_ia.py — Registro y consulta del uso diario de IA
=====================================================
NO es una skill de agente (sin .mcp.json a propósito, igual que errores_ia.py
— ver la nota ahí sobre por qué estos helpers compartidos viven en skills/).

Cada turno de conversación que pasa por el proveedor de IA se registra acá,
desde los dos canales que existen: el chat del dashboard y WhatsApp. Es un
PROXY del gasto de cuota, no un medidor exacto — un turno donde el agente usa
herramientas puede costar varias llamadas reales a la API, así que el número
real gastado es mayor o igual al contador. Para la cuenta gratuita de Gemini
(20 llamadas/día para todo el sistema) esto alcanza para orientar al usuario
antes de que se estrelle contra el tope sin aviso.
"""
from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "vault" / "sqlite" / "imrryr.db"

# Tope diario de la cuenta gratuita de Gemini. Si el usuario activa una
# cuenta paga u otro proveedor en Ajustes > Cuentas de IA, el indicador
# sigue mostrando el conteo pero el tope deja de ser una barrera real.
LIMITE_GRATUITO = 20


def registrar_uso(canal: str, agente: str = "") -> None:
    """Registra un turno de conversación. Nunca lanza — perder un registro
    de uso jamás debe romper la conversación en sí."""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        try:
            conn.execute(
                "INSERT INTO uso_ia (fecha, canal, agente) VALUES (?, ?, ?)",
                (date.today().isoformat(), canal, agente),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception:
        pass


def uso_de_hoy() -> dict:
    """Devuelve {"hoy": N, "limite": 20}. Si la DB no existe todavía, hoy=0."""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        try:
            n = conn.execute(
                "SELECT COUNT(*) FROM uso_ia WHERE fecha = ?", (date.today().isoformat(),)
            ).fetchone()[0]
        finally:
            conn.close()
    except Exception:
        n = 0
    return {"hoy": n, "limite": LIMITE_GRATUITO}
