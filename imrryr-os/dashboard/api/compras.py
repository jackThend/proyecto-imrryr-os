"""API: Compras — seguimientos de precio (lectura/alta directa) + preferencias de digest."""
from __future__ import annotations

import json

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from api import deps

router = APIRouter()

COMPRAS_PREFS_PATH = deps.ROOT / "config" / "compras_prefs.json"


@router.get("/api/compras/seguimientos")
async def listar_seguimientos_compras():
    from skills.gestionar_seguimiento_compras import gestionar_seguimiento_compras
    return gestionar_seguimiento_compras(accion="listar")


@router.post("/api/compras/seguimientos")
async def crear_seguimiento_compras(datos: dict):
    from skills.gestionar_seguimiento_compras import gestionar_seguimiento_compras
    return gestionar_seguimiento_compras(
        accion="crear", producto=datos.get("producto", ""),
        precio_min=datos.get("precio_min"), precio_max=datos.get("precio_max"),
        tiendas=datos.get("tiendas", ""),
    )


@router.delete("/api/compras/seguimientos/{seguimiento_id}")
async def eliminar_seguimiento_compras(seguimiento_id: int):
    from skills.gestionar_seguimiento_compras import gestionar_seguimiento_compras
    return gestionar_seguimiento_compras(accion="eliminar", seguimiento_id=seguimiento_id)


@router.get("/api/compras/prefs")
async def get_compras_prefs():
    if not COMPRAS_PREFS_PATH.exists():
        return {"cuenta_correo_id": "", "destinatario": ""}
    return json.loads(COMPRAS_PREFS_PATH.read_text(encoding="utf-8"))


@router.post("/api/compras/prefs")
async def set_compras_prefs(datos: dict):
    COMPRAS_PREFS_PATH.parent.mkdir(parents=True, exist_ok=True)
    COMPRAS_PREFS_PATH.write_text(json.dumps(datos, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"ok": True}
