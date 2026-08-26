"""API: Agenda (eventos) y Pendientes — lectura/alta directa, sin pasar por el LLM."""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/api/agenda/eventos")
async def listar_eventos_agenda(rango: str = "hoy", anio: int | None = None, mes: int | None = None):
    from skills.agenda import agenda as agenda_skill
    return agenda_skill(accion="que_tengo", cuando=rango, anio=anio, mes=mes)


@router.post("/api/agenda/eventos")
async def crear_evento_agenda(datos: dict):
    from skills.agenda import agenda as agenda_skill
    return agenda_skill(
        accion="crear", titulo=datos.get("titulo", ""), fecha=datos.get("fecha", ""),
        hora=datos.get("hora", "09:00"), duracion=datos.get("duracion", 60),
        descripcion=datos.get("descripcion", ""), avisos=datos.get("avisos", ""),
    )


@router.post("/api/agenda/eventos/{evento_id}/cancelar")
async def cancelar_evento_agenda(evento_id: int):
    from skills.agenda import agenda as agenda_skill
    return agenda_skill(accion="cancelar", evento_id=evento_id)


@router.get("/api/pendientes")
async def listar_pendientes_endpoint():
    from skills.pendientes import pendientes as pendientes_skill
    return pendientes_skill(accion="listar")


@router.post("/api/pendientes")
async def crear_pendiente_endpoint(datos: dict):
    from skills.pendientes import pendientes as pendientes_skill
    return pendientes_skill(accion="crear", texto=datos.get("texto", ""))


@router.post("/api/pendientes/{pendiente_id}/hecho")
async def marcar_pendiente_hecho_endpoint(pendiente_id: int, datos: dict):
    from skills.pendientes import pendientes as pendientes_skill
    return pendientes_skill(accion="marcar_hecho", pendiente_id=pendiente_id, hecho=bool(datos.get("hecho", True)))


@router.delete("/api/pendientes/{pendiente_id}")
async def eliminar_pendiente_endpoint(pendiente_id: int):
    from skills.pendientes import pendientes as pendientes_skill
    return pendientes_skill(accion="eliminar", pendiente_id=pendiente_id)
