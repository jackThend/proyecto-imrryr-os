#!/usr/bin/env python3
"""
cuentas_social.py — Cuentas de redes sociales (Meta Graph API: Facebook + Instagram)
=======================================================================================
Cada instalación configura su propia app de Meta for Developers, su propia
Página de Facebook y (opcional) su cuenta de Instagram Business/Creator
vinculada — nada hardcodeado a un desarrollador específico. Mismo patrón que
config/cuentas_ia.py y config/cuentas_git.py.

OJO: publicar vía Graph API requiere que la app de Meta pase App Review para
los permisos pages_manage_posts / instagram_content_publish — mientras la app
esté en modo desarrollo, solo funciona para el propio usuario-admin de esa
app o cuentas agregadas como tester. Esto es un trámite externo ante Meta,
no algo que este módulo pueda resolver.

Uso:
    from config.cuentas_social import listar_cuentas, guardar_cuenta, activar_cuenta
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CUENTAS_PATH = Path(__file__).resolve().parent / "cuentas_social.json"


def log(msg: str) -> None:
    print(f"[cuentas_social] {msg}", flush=True)


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


def cuentas_seguras() -> list[dict[str, Any]]:
    """Copia de listar_cuentas() con 'access_token' enmascarado, para exponer al dashboard."""
    seguras = []
    for cuenta in _leer_todas():
        copia = dict(cuenta)
        if copia.get("access_token"):
            copia["access_token"] = "*" * 6
        seguras.append(copia)
    return seguras


def guardar_cuenta(datos: dict[str, Any]) -> dict[str, Any]:
    """Crea o actualiza (por 'id') una cuenta social. Campos: id, nombre,
    page_id (Facebook Page ID), ig_business_id (opcional), access_token."""
    cuenta_id = datos.get("id")
    if not cuenta_id:
        return {"ok": False, "error": "falta 'id'"}
    if not datos.get("page_id"):
        return {"ok": False, "error": "falta 'page_id'"}

    cuentas = _leer_todas()
    for i, cuenta in enumerate(cuentas):
        if cuenta.get("id") == cuenta_id:
            cuentas[i] = {**cuenta, **datos}
            _guardar_todas(cuentas)
            return {"ok": True, "cuenta": cuentas[i]}

    nueva = {"activa": False, **datos}
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


def activar_cuenta(cuenta_id: str) -> dict[str, Any]:
    cuentas = _leer_todas()
    activada = None
    for c in cuentas:
        c["activa"] = c.get("id") == cuenta_id
        if c["activa"]:
            activada = c
    if not activada:
        return {"ok": False, "error": f"no existe la cuenta '{cuenta_id}'"}
    _guardar_todas(cuentas)
    return {"ok": True, "cuenta": activada}
