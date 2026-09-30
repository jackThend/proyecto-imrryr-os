"""Rutas y clientes compartidos por todos los routers del dashboard.

Solo infraestructura (paths, credenciales del backend OpenCode): la lógica
de negocio vive en skills/ y config/, y los routers solo la invocan.
"""
from __future__ import annotations

import base64
import os
from pathlib import Path

from config.defaults import OPENCODE_PASSWORD_DEFAULT, chat_timeout_seconds

__all__ = ["chat_timeout_seconds"]

# --- rutas (deps.py vive en dashboard/api/) ---
ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_DIR = ROOT / "dashboard"
ENV_FILE = ROOT / "config" / ".env"
DB_PATH = ROOT / "vault" / "sqlite" / "imrryr.db"
AGENTES_DIR = ROOT / "agentes"
SEMILLAS_DIR = ROOT / "semillas"
ADJUNTOS_DIR = SEMILLAS_DIR / "adjuntos"
STATIC_DIR = DASHBOARD_DIR / "static"
FONDOS_DIR = STATIC_DIR / "fondos"

AGENTES_ELIMINADOS_DIR = AGENTES_DIR / "_eliminados"


def _opencode_port() -> int:
    return int(os.environ.get("OPENCODE_PORT") or 4040)


def _opencode_password() -> str:
    return os.environ.get("OPENCODE_SERVER_PASSWORD") or OPENCODE_PASSWORD_DEFAULT


def _ruta_modelo() -> dict[str, str]:
    """{"providerID", "modelID"} de la cuenta de IA activa (Ajustes > Cuentas de IA).

    Por defecto es el alias estable de LiteLLM (imrryr-llm / imrryr-activo):
    cambiar de proveedor nunca requiere tocar el código. Solo las cuentas de un
    proveedor nativo de OpenCode (Zen gratis) salen por otro provider; ver
    config/cuentas_ia.py::modelo_para_agente.
    """
    from ruta_modelo import modelo_para_agente
    return modelo_para_agente()


def _opencode_auth_headers() -> dict[str, str]:
    token = base64.b64encode(f"opencode:{_opencode_password()}".encode()).decode()
    return {"Authorization": f"Basic {token}", "Content-Type": "application/json"}
