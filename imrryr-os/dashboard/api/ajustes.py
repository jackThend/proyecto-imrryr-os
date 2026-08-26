"""API: Ajustes — fondo personalizado y cuentas de IA, GitHub y redes sociales."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, File, UploadFile

from api import deps

router = APIRouter()


# ---------------------------------------------------------------------------
# API: Fondo personalizado (tema Creativo, ver Ajustes → Apariencia)
# ---------------------------------------------------------------------------
@router.get("/api/ajustes/fondo")
async def get_fondo_personalizado():
    archivos = list(deps.FONDOS_DIR.glob("personalizado.*"))
    if not archivos:
        return {"url": None}
    return {"url": f"/static/fondos/{archivos[0].name}"}


@router.post("/api/ajustes/fondo")
async def set_fondo_personalizado(archivo: UploadFile = File(...)):
    for viejo in deps.FONDOS_DIR.glob("personalizado.*"):
        viejo.unlink()
    extension = Path(archivo.filename).suffix or ".jpg"
    destino = deps.FONDOS_DIR / f"personalizado{extension}"
    destino.write_bytes(await archivo.read())
    return {"ok": True, "url": f"/static/fondos/{destino.name}"}


@router.delete("/api/ajustes/fondo")
async def eliminar_fondo_personalizado():
    for viejo in deps.FONDOS_DIR.glob("personalizado.*"):
        viejo.unlink()
    return {"ok": True}


# ---------------------------------------------------------------------------
# API: Cuentas de IA (qué proveedor/modelo usan todos los agentes)
# ---------------------------------------------------------------------------
@router.get("/api/ajustes/cuentas-ia")
async def get_cuentas_ia():
    from config import cuentas_ia
    return {"cuentas": cuentas_ia.cuentas_seguras(), "proveedores": cuentas_ia.PROVEEDORES}


@router.post("/api/ajustes/cuentas-ia")
async def set_cuenta_ia(datos: dict):
    from config import cuentas_ia
    return cuentas_ia.guardar_cuenta(datos)


@router.delete("/api/ajustes/cuentas-ia/{cuenta_id}")
async def eliminar_cuenta_ia(cuenta_id: str):
    from config import cuentas_ia
    return cuentas_ia.quitar_cuenta(cuenta_id)


@router.post("/api/ajustes/cuentas-ia/{cuenta_id}/activar")
async def activar_cuenta_ia(cuenta_id: str):
    from config import cuentas_ia
    return cuentas_ia.activar_cuenta(cuenta_id)


@router.post("/api/ajustes/cuentas-ia/modelos")
async def modelos_disponibles_ia(datos: dict):
    """Catálogo en vivo del proveedor (ej. OpenCode GO no lo publica en su web).

    La API key viaja del navegador al servidor local solo cuando la cuenta aún
    no existe; si ya está guardada, basta con mandar 'cuenta_id' y el secreto
    nunca sale del disco. La respuesta jamás incluye la key.
    """
    from config import cuentas_ia
    return cuentas_ia.listar_modelos_remotos(
        proveedor=datos.get("proveedor", ""),
        api_key=datos.get("api_key", ""),
        cuenta_id=datos.get("cuenta_id", ""),
    )


# ---------------------------------------------------------------------------
# API: Cuentas de GitHub (repos que el Agente RRSS/Web puede administrar)
# ---------------------------------------------------------------------------
@router.get("/api/ajustes/cuentas-git")
async def get_cuentas_git():
    from config import cuentas_git
    return {"cuentas": cuentas_git.cuentas_seguras()}


@router.post("/api/ajustes/cuentas-git")
async def set_cuenta_git(datos: dict):
    from config import cuentas_git
    return cuentas_git.guardar_cuenta(datos)


@router.delete("/api/ajustes/cuentas-git/{cuenta_id}")
async def eliminar_cuenta_git(cuenta_id: str):
    from config import cuentas_git
    return cuentas_git.quitar_cuenta(cuenta_id)


@router.post("/api/ajustes/cuentas-git/{cuenta_id}/activar")
async def activar_cuenta_git(cuenta_id: str):
    from config import cuentas_git
    return cuentas_git.activar_cuenta(cuenta_id)


# ---------------------------------------------------------------------------
# API: Cuentas de redes sociales (Meta Graph API: Facebook + Instagram)
# ---------------------------------------------------------------------------
@router.get("/api/ajustes/cuentas-social")
async def get_cuentas_social():
    from config import cuentas_social
    return {"cuentas": cuentas_social.cuentas_seguras()}


@router.post("/api/ajustes/cuentas-social")
async def set_cuenta_social(datos: dict):
    from config import cuentas_social
    return cuentas_social.guardar_cuenta(datos)


@router.delete("/api/ajustes/cuentas-social/{cuenta_id}")
async def eliminar_cuenta_social(cuenta_id: str):
    from config import cuentas_social
    return cuentas_social.quitar_cuenta(cuenta_id)


@router.post("/api/ajustes/cuentas-social/{cuenta_id}/activar")
async def activar_cuenta_social(cuenta_id: str):
    from config import cuentas_social
    return cuentas_social.activar_cuenta(cuenta_id)
