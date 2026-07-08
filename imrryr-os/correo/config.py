#!/usr/bin/env python3
"""
config.py — Configuración compartida de cuentas de correo (Fase Tanda F)
===========================================================================
Único punto de verdad sobre qué cuentas de correo están configuradas y con
qué proveedor (gmail o imap genérico — este último cubre correo de hosting
propio, Outlook u otro proveedor con contraseña de aplicación). El
dashboard y skills/correo.py leen/escriben este archivo.

Uso:
    from correo.config import listar_cuentas, guardar_cuenta, quitar_cuenta
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CUENTAS_PATH = Path(__file__).resolve().parent / "cuentas.json"

CAMPOS_IMAP = ("imap_host", "imap_port", "smtp_host", "smtp_port", "usuario", "password")


def _leer_todas() -> list[dict[str, Any]]:
    if not CUENTAS_PATH.exists():
        return []
    try:
        data = json.loads(CUENTAS_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    return data.get("cuentas", []) if isinstance(data, dict) else []


def _guardar_todas(cuentas: list[dict[str, Any]]) -> None:
    CUENTAS_PATH.parent.mkdir(parents=True, exist_ok=True)
    CUENTAS_PATH.write_text(json.dumps({"cuentas": cuentas}, indent=2, ensure_ascii=False), encoding="utf-8")


def listar_cuentas() -> list[dict[str, Any]]:
    return _leer_todas()


def obtener_cuenta(cuenta_id: str) -> dict[str, Any] | None:
    for cuenta in _leer_todas():
        if cuenta.get("id") == cuenta_id:
            return cuenta
    return None


def guardar_cuenta(datos: dict[str, Any]) -> dict[str, Any]:
    """Crea o actualiza (por 'id') una cuenta de correo."""
    cuentas = _leer_todas()
    cuenta_id = datos.get("id")
    if not cuenta_id:
        return {"ok": False, "error": "falta 'id'"}

    for i, cuenta in enumerate(cuentas):
        if cuenta.get("id") == cuenta_id:
            cuentas[i] = {**cuenta, **datos}
            _guardar_todas(cuentas)
            return {"ok": True, "cuenta": cuentas[i]}

    nueva = {"activo": True, **datos}
    cuentas.append(nueva)
    _guardar_todas(cuentas)
    return {"ok": True, "cuenta": nueva}


def quitar_cuenta(cuenta_id: str) -> dict[str, Any]:
    cuentas = _leer_todas()
    restantes = [c for c in cuentas if c.get("id") != cuenta_id]
    if len(restantes) == len(cuentas):
        return {"ok": False, "error": f"no existe la cuenta '{cuenta_id}'"}
    _guardar_todas(restantes)
    return {"ok": True}


def cuentas_seguras() -> list[dict[str, Any]]:
    """Copia de listar_cuentas() con 'password' oculto, para exponer al dashboard."""
    seguras = []
    for cuenta in _leer_todas():
        copia = dict(cuenta)
        if copia.get("password"):
            copia["password"] = "*" * 6
        seguras.append(copia)
    return seguras
