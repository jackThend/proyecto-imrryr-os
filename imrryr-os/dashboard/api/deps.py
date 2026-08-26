"""Rutas y clientes compartidos por todos los routers del dashboard.

Solo infraestructura (paths, credenciales del backend OpenCode): la lógica
de negocio vive en skills/ y config/, y los routers solo la invocan.
"""
from __future__ import annotations

import base64
import os
from pathlib import Path

from config.defaults import OPENCODE_PASSWORD_DEFAULT

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


def _modelo_activo() -> str:
    """Alias estable de LiteLLM (ver config/litellm_config.yaml) que siempre
    apunta a la cuenta de IA que el usuario eligió en Ajustes > Cuentas de IA
    (config/cuentas_ia.py). Cambiar de proveedor nunca requiere tocar esto."""
    return "imrryr-activo"


def _opencode_auth_headers() -> dict[str, str]:
    token = base64.b64encode(f"opencode:{_opencode_password()}".encode()).decode()
    return {"Authorization": f"Basic {token}", "Content-Type": "application/json"}
