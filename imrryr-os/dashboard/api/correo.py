"""API: Agente Secretario (bandeja de correo multi-proveedor).

El envío real de un correo SOLO ocurre acá (POST .../enviar), nunca desde
una tool del agente — ver skills/secretario.py.
"""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/api/correo/cuentas")
async def get_cuentas_correo():
    from correo.config import cuentas_seguras
    return {"cuentas": cuentas_seguras()}


@router.post("/api/correo/cuentas")
async def set_cuenta_correo(datos: dict):
    from correo.config import guardar_cuenta
    return guardar_cuenta(datos)


@router.delete("/api/correo/cuentas/{cuenta_id}")
async def eliminar_cuenta_correo(cuenta_id: str):
    from correo.config import quitar_cuenta
    return quitar_cuenta(cuenta_id)


@router.get("/api/correo/bandeja")
async def get_bandeja(cuenta_id: str = "", max_resultados: int = 10):
    if not cuenta_id:
        return {"correos": []}
    import secretario
    return {"correos": secretario.leer_correo(cuenta_id, max_resultados)}


@router.get("/api/correo/borradores")
async def get_borradores(estado: str = "pendiente"):
    import secretario
    return {"borradores": secretario.listar_borradores(estado)}


@router.post("/api/correo/borradores/{borrador_id}/enviar")
async def enviar_borrador_endpoint(borrador_id: int):
    import secretario
    return secretario.enviar_borrador(borrador_id)


@router.post("/api/correo/borradores/{borrador_id}/descartar")
async def descartar_borrador_endpoint(borrador_id: int):
    import secretario
    return secretario.descartar_borrador(borrador_id)
