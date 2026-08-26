"""API: Oportunidades de fondos y Perfil de Negocio (dominio del Agente Investigador)."""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()


@router.get("/api/oportunidades")
async def get_oportunidades(estado: str = ""):
    import guardar_oportunidad
    return {"oportunidades": guardar_oportunidad.listar_oportunidades(estado)}


@router.post("/api/oportunidades/{oportunidad_id}/estado")
async def cambiar_estado_oportunidad_endpoint(oportunidad_id: int, datos: dict):
    import guardar_oportunidad
    estado = datos.get("estado", "")
    if not estado:
        return JSONResponse({"ok": False, "error": "falta 'estado'"}, status_code=400)
    return guardar_oportunidad.cambiar_estado_oportunidad(oportunidad_id, estado, datos.get("relevancia_nota", ""))


# ---------------------------------------------------------------------------
# API: Perfil de Negocio (usado por el Agente Investigador para filtrar fondos)
# ---------------------------------------------------------------------------
@router.get("/api/perfil-negocio")
async def get_perfil_negocio():
    import perfil_negocio
    return perfil_negocio.leer_perfil_negocio()


@router.post("/api/perfil-negocio")
async def set_perfil_negocio(datos: dict):
    import perfil_negocio
    return perfil_negocio.actualizar_perfil_negocio(datos)
