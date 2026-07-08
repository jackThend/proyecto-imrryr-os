#!/usr/bin/env python3
"""
cuentas_git.py — Cuentas de GitHub (repos que el Agente RRSS/Web puede administrar)
=====================================================================================
Cada instalación de Imrryr OS configura su propio repositorio y su propio
token — nada de esto va en .env ni queda hardcodeado a un desarrollador
específico. Mismo patrón que config/cuentas_ia.py: un JSON local (gitignored)
con hash/token en texto plano solo en disco local, nunca commiteado, y una
función que enmascara el token antes de exponerlo al dashboard.

Uso:
    from config.cuentas_git import listar_cuentas, guardar_cuenta, activar_cuenta
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CUENTAS_PATH = Path(__file__).resolve().parent / "cuentas_git.json"


def log(msg: str) -> None:
    print(f"[cuentas_git] {msg}", flush=True)


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
    """Copia de listar_cuentas() con 'token' enmascarado, para exponer al dashboard."""
    seguras = []
    for cuenta in _leer_todas():
        copia = dict(cuenta)
        if copia.get("token"):
            copia["token"] = "*" * 6
        seguras.append(copia)
    return seguras


def guardar_cuenta(datos: dict[str, Any]) -> dict[str, Any]:
    """Crea o actualiza (por 'id') una cuenta de GitHub. Campos: id, nombre,
    repo_url, ruta_local (dónde clonar/ya clonado), token, rama (default 'main')."""
    cuenta_id = datos.get("id")
    if not cuenta_id:
        return {"ok": False, "error": "falta 'id'"}
    if not datos.get("repo_url"):
        return {"ok": False, "error": "falta 'repo_url'"}

    datos.setdefault("rama", "main")
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
    """Marca una cuenta como la activa (la que usa repo_web si no se especifica cuenta_id)."""
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
