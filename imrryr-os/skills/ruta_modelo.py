#!/usr/bin/env python3
"""
ruta_modelo.py — Qué provider/modelo debe usar OpenCode para la cuenta de IA activa
====================================================================================
NO es una skill de agente (sin .mcp.json a propósito, igual que errores_ia.py y
uso_ia.py). Vive en skills/ porque es el único directorio en el sys.path del
dashboard, del gateway y del importador de finanzas: dentro del gateway,
gateway/config.py le hace sombra al paquete config/, así que un
`from config.cuentas_ia import ...` no funcionaría ahí. Por eso cuentas_ia.py
se carga por ruta de archivo, y la lógica real vive en un único lugar
(config/cuentas_ia.py::modelo_para_agente).
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

_CUENTAS_IA = Path(__file__).resolve().parent.parent / "config" / "cuentas_ia.py"
_POR_DEFECTO = {"providerID": "imrryr-llm", "modelID": "imrryr-activo"}


def modelo_para_agente() -> dict[str, str]:
    """{"providerID", "modelID"}; ante cualquier fallo, la ruta estándar por LiteLLM."""
    try:
        spec = importlib.util.spec_from_file_location("_imrryr_cuentas_ia", _CUENTAS_IA)
        modulo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modulo)  # type: ignore[union-attr]
        return modulo.modelo_para_agente()
    except Exception:
        return dict(_POR_DEFECTO)
