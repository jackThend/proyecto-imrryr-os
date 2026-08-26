"""API: Ideas/Proyectos ("Pinterest de ideas", ver skills/semillas.py)."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, File, UploadFile
from fastapi.responses import JSONResponse

from api import deps

router = APIRouter()


@router.get("/api/semillas")
async def get_semillas(estado: str = ""):
    import semillas as _semillas
    return {"semillas": _semillas.listar_semillas(estado)}


@router.post("/api/semillas")
async def crear_semilla_endpoint(datos: dict):
    import semillas as _semillas
    titulo = datos.get("titulo", "")
    contenido = datos.get("contenido", "")
    if not titulo or not contenido:
        return JSONResponse({"ok": False, "error": "faltan titulo o contenido"}, status_code=400)
    return _semillas.crear_semilla(titulo, contenido, etiquetas=datos.get("etiquetas"), fuente="dashboard")


@router.get("/api/semillas/{semilla_id}")
async def get_semilla(semilla_id: int):
    import semillas as _semillas
    resultado = _semillas.obtener_semilla(semilla_id)
    if resultado.get("ok") is False:
        return JSONResponse(resultado, status_code=404)
    return resultado


@router.put("/api/semillas/{semilla_id}")
async def actualizar_semilla_endpoint(semilla_id: int, datos: dict):
    import semillas as _semillas
    return _semillas.actualizar_semilla(
        semilla_id,
        titulo=datos.get("titulo", ""),
        contenido=datos.get("contenido", ""),
        etiquetas=datos.get("etiquetas"),
    )


@router.post("/api/semillas/{semilla_id}/estado")
async def cambiar_estado_endpoint(semilla_id: int, datos: dict):
    import semillas as _semillas
    return _semillas.cambiar_estado_semilla(semilla_id, datos.get("estado", ""))


@router.post("/api/semillas/{semilla_id}/adjunto")
async def subir_adjunto(semilla_id: int, archivo: UploadFile = File(...)):
    import semillas as _semillas
    carpeta = deps.ADJUNTOS_DIR / str(semilla_id)
    carpeta.mkdir(parents=True, exist_ok=True)
    nombre_seguro = Path(archivo.filename).name  # sin path traversal
    destino = carpeta / nombre_seguro
    destino.write_bytes(await archivo.read())
    ruta_publica = f"/adjuntos/{semilla_id}/{nombre_seguro}"
    return _semillas.adjuntar_archivo_semilla(semilla_id, ruta_publica)


@router.get("/api/proyectos")
async def get_proyectos(estado: str = ""):
    import semillas as _semillas
    return {"proyectos": _semillas.listar_proyectos(estado)}


@router.put("/api/proyectos/{proyecto_id}")
async def actualizar_proyecto_endpoint(proyecto_id: int, datos: dict):
    import semillas as _semillas
    return _semillas.actualizar_proyecto(
        proyecto_id,
        descripcion=datos.get("descripcion", ""),
        estado=datos.get("estado", ""),
        tecnologias=datos.get("tecnologias", ""),
    )
