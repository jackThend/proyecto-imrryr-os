#!/usr/bin/env python3
"""
config.py — Configuración compartida del Gateway de WhatsApp (Fase 5)
========================================================================
Único punto de verdad sobre qué conector de WhatsApp está activo: la vía
local (whatsapp-web.js + QR, sin cuenta Meta) o la Cloud API oficial de
Meta. webhook_server.py, el sidecar de Node y el dashboard leen/escriben
este archivo para no duplicar el estado en tres lugares distintos.

Uso:
    from gateway.config import leer_config, guardar_config, modo_activo
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = Path(__file__).resolve().parent / "gateway_config.json"

Modo = Literal["local", "cloud"]

DEFAULTS: dict[str, Any] = {
    "modo": "local",
    "cloud": {
        "phone_number_id": "",
        "access_token": "",
        "verify_token": "",
    },
    "local": {
        "conectado": False,
    },
}


def leer_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return json.loads(json.dumps(DEFAULTS))  # copia profunda
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return json.loads(json.dumps(DEFAULTS))

    # merge superficial con defaults para tolerar archivos antiguos/incompletos
    merged = json.loads(json.dumps(DEFAULTS))
    merged.update({k: v for k, v in data.items() if k != "cloud" and k != "local"})
    merged["cloud"].update(data.get("cloud", {}))
    merged["local"].update(data.get("local", {}))
    return merged


def guardar_config(nuevo: dict[str, Any]) -> dict[str, Any]:
    actual = leer_config()
    if "modo" in nuevo:
        actual["modo"] = nuevo["modo"]
    if "cloud" in nuevo:
        actual["cloud"].update(nuevo["cloud"])
    if "local" in nuevo:
        actual["local"].update(nuevo["local"])

    CONFIG_PATH.write_text(json.dumps(actual, indent=2, ensure_ascii=False), encoding="utf-8")
    return actual


def modo_activo() -> Modo:
    return leer_config().get("modo", "local")
