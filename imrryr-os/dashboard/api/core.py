"""Núcleo: HTML del dashboard, widgets, estado del sistema, uso de IA y respaldos."""
from __future__ import annotations

import os
import socket
from pathlib import Path

import yaml
from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse

from api import deps

router = APIRouter()


# ---------------------------------------------------------------------------
# HTML Dashboard (single-page app embebida)
# ---------------------------------------------------------------------------
@router.get("/", response_class=HTMLResponse)
async def dashboard():
    html = (Path(__file__).resolve().parents[1] / "dashboard.html").read_text(encoding="utf-8")
    return HTMLResponse(html)


# ---------------------------------------------------------------------------
# API: Widgets dinámicos (lee /agentes/*.yaml)
# ---------------------------------------------------------------------------
@router.get("/api/widgets")
async def list_widgets():
    widgets = []
    if deps.AGENTES_DIR.exists():
        for fpath in sorted(deps.AGENTES_DIR.glob("*.yaml")):
            try:
                data = yaml.safe_load(fpath.read_text(encoding="utf-8"))
                if data and data.get("activo", True):
                    widgets.append({
                        "id": fpath.stem,
                        "nombre": data.get("nombre", fpath.stem),
                        "descripcion": data.get("descripcion", ""),
                        "herramientas": data.get("herramientas_permitidas", []),
                    })
            except Exception:
                pass
    return {"widgets": widgets}


# ---------------------------------------------------------------------------
# API: Estado del sistema
# ---------------------------------------------------------------------------
@router.get("/api/status")
async def system_status():
    # Puertos desde el entorno (el dashboard carga config/.env al arrancar):
    # si el usuario cambia LITELLM_PORT u OPENCODE_PORT, este panel sigue
    # diciendo la verdad. El gateway no es configurable por .env hoy: :5050.
    servicios = {}
    for name, port in [
        ("litellm", int(os.environ.get("LITELLM_PORT") or 4000)),
        ("opencode", int(os.environ.get("OPENCODE_PORT") or 4040)),
        ("gateway", 5050),
    ]:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.settimeout(1)
            servicios[name] = s.connect_ex(("127.0.0.1", port)) == 0
        finally:
            s.close()
    return {"servicios": servicios}


# ---------------------------------------------------------------------------
# API: Uso diario de IA (proxy por turnos de conversación, ver skills/uso_ia.py)
# ---------------------------------------------------------------------------
@router.get("/api/uso-ia")
async def uso_ia_hoy():
    from uso_ia import uso_de_hoy
    return uso_de_hoy()


# ---------------------------------------------------------------------------
# API: Respaldos locales de la base de datos
# ---------------------------------------------------------------------------
@router.get("/api/respaldos")
async def listar_respaldos_db():
    from scripts.respaldo_db import listar_respaldos
    return {"respaldos": listar_respaldos()}


@router.post("/api/respaldos")
async def crear_respaldo_db():
    from scripts.respaldo_db import crear_respaldo
    resultado = crear_respaldo()
    if not resultado.get("ok"):
        return JSONResponse({"error": resultado.get("error", "no se pudo respaldar")}, status_code=500)
    return resultado
