"""Constantes compartidas por scripts independientes y por el dashboard.

Único hogar del default de la contraseña del servidor OpenCode: startup.py
la usa al arrancar y los clientes (dashboard, smoke_test) al conectarse.
Vivía copiada a mano en tres archivos y bastaba que uno quedara viejo para
que el healthcheck fallara con un 401 críptico.
"""
from __future__ import annotations

import os

OPENCODE_PASSWORD_DEFAULT = "imrryr-local-pass"
CHAT_TIMEOUT_SECONDS_DEFAULT = 300


def chat_timeout_seconds() -> int:
    """Devuelve el timeout común de una conversación con el modelo.

    Un valor inválido en .env no debe impedir que arranque el sistema; en ese
    caso se conserva el default seguro de cinco minutos.
    """
    try:
        return max(1, int(os.environ.get("IMRRYR_CHAT_TIMEOUT_SECONDS") or CHAT_TIMEOUT_SECONDS_DEFAULT))
    except (TypeError, ValueError):
        return CHAT_TIMEOUT_SECONDS_DEFAULT
