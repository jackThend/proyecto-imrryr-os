#!/usr/bin/env python3
"""
region.py — País/región del usuario (Tanda P, base para feriados en Tanda R)
=================================================================================
Un solo campo por ahora (código de país ISO de 2 letras, ej. "CL"), pensado
para crecer si más adelante se necesita zona horaria u otros datos de
localización. Lo consume el Agente de Agenda para saber contra qué país
consultar feriados (Nager.Date), en vez de asumir Chile a fuego.

Uso:
    from config.region import leer_region, actualizar_region
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REGION_PATH = Path(__file__).resolve().parent / "region.json"

DEFAULTS: dict[str, Any] = {"pais": "CL"}


def leer_region() -> dict[str, Any]:
    if not REGION_PATH.exists():
        return dict(DEFAULTS)
    try:
        data = json.loads(REGION_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return dict(DEFAULTS)
    return {**DEFAULTS, **data}


def actualizar_region(datos: dict[str, Any]) -> dict[str, Any]:
    actual = leer_region()
    if datos.get("pais"):
        actual["pais"] = str(datos["pais"]).upper()
    REGION_PATH.write_text(json.dumps(actual, indent=2, ensure_ascii=False), encoding="utf-8")
    return actual
