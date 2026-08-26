"""Constantes compartidas por scripts independientes y por el dashboard.

Único hogar del default de la contraseña del servidor OpenCode: startup.py
la usa al arrancar y los clientes (dashboard, smoke_test) al conectarse.
Vivía copiada a mano en tres archivos y bastaba que uno quedara viejo para
que el healthcheck fallara con un 401 críptico.
"""
from __future__ import annotations

OPENCODE_PASSWORD_DEFAULT = "imrryr-local-pass"
