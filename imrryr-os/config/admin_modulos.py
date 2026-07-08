#!/usr/bin/env python3
"""
admin_modulos.py — Contraseña de administrador para el panel de Módulos
==========================================================================
Es una barrera contra borrados accidentales, no un sistema de permisos por
usuario: una sola contraseña compartida, pensada para que un técnico la
configure una vez por instalación. Se guarda como hash + sal en
config/admin_modulos.json (gitignored) — nunca en texto plano. El servidor
la vuelve a pedir en cada acción destructiva real; no existe una sesión
que la recuerde entre pestañas o reinicios.

Uso:
    from config.admin_modulos import esta_configurada, establecer_password, verificar_password
"""
from __future__ import annotations

import hashlib
import json
import secrets
from pathlib import Path

RUTA = Path(__file__).resolve().parent / "admin_modulos.json"


def _hash(password: str, sal: str) -> str:
    return hashlib.sha256((sal + password).encode("utf-8")).hexdigest()


def esta_configurada() -> bool:
    return RUTA.exists()


def establecer_password(nueva: str) -> dict:
    if not nueva or len(nueva) < 4:
        return {"ok": False, "error": "La contraseña debe tener al menos 4 caracteres"}
    sal = secrets.token_hex(16)
    RUTA.write_text(json.dumps({"sal": sal, "hash": _hash(nueva, sal)}), encoding="utf-8")
    return {"ok": True}


def verificar_password(intento: str) -> bool:
    if not RUTA.exists():
        return False
    try:
        datos = json.loads(RUTA.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False
    return secrets.compare_digest(_hash(intento or "", datos.get("sal", "")), datos.get("hash", ""))
