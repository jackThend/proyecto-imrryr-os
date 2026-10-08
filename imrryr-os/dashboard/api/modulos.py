"""API: Gestión de Módulos/Agentes (protegida por contraseña, ver config/admin_modulos.py)."""
from __future__ import annotations

import re
import sqlite3
import subprocess
import sys
from pathlib import Path

import yaml
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from api import deps

router = APIRouter()

AGENTES_PROTEGIDOS = {"agente_build", "agente_asistente"}  # agentes del núcleo, no se eliminan

ICONOS_POR_MODULO = {
    "agente_financiero": "chart", "agente_creativo": "bulb", "agente_crm": "users",
    "agente_investigador": "trophy", "agente_secretario": "mail", "guardia_seguridad": "shield",
    "agente_rrss_web": "globe", "agente_compras": "cart", "agente_agenda": "calendar",
    "agente_navegacion": "search",
}
DESCRIPCION_DATOS_POR_MODULO = {
    "agente_financiero": "Gastos registrados y el progreso de importación bancaria (tablas gastos, importaciones).",
    "agente_creativo": "Ideas y proyectos guardados, con sus adjuntos (tablas semillas, proyectos, adjuntos_semilla).",
    "agente_investigador": "Oportunidades de fondos encontradas (tabla oportunidades_fondos).",
    "agente_secretario": "Cuentas de correo configuradas y borradores pendientes (correo/cuentas.json, tabla borradores_pendientes).",
    "agente_rrss_web": "Posts programados para redes sociales (tabla posts_programados). Las credenciales de GitHub/Meta se gestionan en Ajustes y no se borran con el módulo.",
    "agente_compras": "Productos en seguimiento y ofertas encontradas (tablas productos_seguimiento, ofertas_encontradas).",
    "agente_agenda": "Eventos agendados (tabla eventos). Los recordatorios puntuales siguen en la tabla recordatorios, compartida con otras funciones del sistema.",
    "agente_navegacion": "No guarda datos propios — solo el último audio generado (archivo temporal, se reemplaza en cada lectura).",
}
TABLAS_POR_MODULO = {
    "agente_financiero": ["gastos", "importaciones"],
    "agente_creativo": ["semillas", "proyectos", "adjuntos_semilla"],
    "agente_investigador": ["oportunidades_fondos"],
    "agente_secretario": ["borradores_pendientes"],
    "agente_rrss_web": ["posts_programados"],
    "agente_compras": ["productos_seguimiento", "ofertas_encontradas"],
    "agente_agenda": ["eventos"],
    "agente_navegacion": [],
}


def _leer_modulos_de(carpeta: Path, eliminado: bool = False) -> list[dict]:
    modulos = []
    if not carpeta.exists():
        return modulos
    for fpath in sorted(carpeta.glob("*.yaml")):
        if fpath.stem in AGENTES_PROTEGIDOS:
            continue
        try:
            data = yaml.safe_load(fpath.read_text(encoding="utf-8")) or {}
        except Exception:
            continue
        modulos.append({
            "id": fpath.stem,
            "nombre": data.get("nombre", fpath.stem),
            "descripcion": data.get("descripcion", ""),
            "herramientas": data.get("herramientas_permitidas", []),
            "activo": False if eliminado else bool(data.get("activo", True)),
            "icono": ICONOS_POR_MODULO.get(fpath.stem, "modulos"),
            "datos_asociados": DESCRIPCION_DATOS_POR_MODULO.get(fpath.stem, ""),
            "eliminado": eliminado,
        })
    return modulos


def _fijar_activo_yaml(fpath: Path, activo: bool) -> None:
    texto = fpath.read_text(encoding="utf-8")
    nuevo_valor = "true" if activo else "false"
    if re.search(r"(?m)^activo:\s*\S+", texto):
        texto = re.sub(r"(?m)^activo:\s*\S+", f"activo: {nuevo_valor}", texto)
    else:
        texto = texto.rstrip("\n") + f"\nactivo: {nuevo_valor}\n"
    fpath.write_text(texto, encoding="utf-8")


def _sincronizar_agentes() -> None:
    subprocess.run([sys.executable, str(deps.ROOT / "scripts" / "sync_agentes.py")], cwd=str(deps.ROOT))


@router.get("/api/agentes-disponibles")
async def agentes_disponibles():
    """Agentes que existen en ESTA instalación y están activos, con el id que usa el panel
    (`agente_agenda.yaml` -> "agenda"). El panel oculta las pestañas de los demás: cada perfil
    empaqueta solo parte de los agentes, y mostrar una pestaña sin su agente daba error 500
    al escribirle (verificado: pyme listaba Agenda, Compras, Correo, RRSS, Navegación y Código)."""
    ids = []
    for fpath in deps.AGENTES_DIR.glob("*.yaml"):
        try:
            data = yaml.safe_load(fpath.read_text(encoding="utf-8")) or {}
        except Exception:
            continue
        if data.get("activo", True):
            ids.append(fpath.stem.removeprefix("agente_"))
    return {"agentes": sorted(ids)}


@router.get("/api/modulos")
async def listar_modulos():
    return {
        "modulos": _leer_modulos_de(deps.AGENTES_DIR),
        "eliminados": _leer_modulos_de(deps.AGENTES_ELIMINADOS_DIR, eliminado=True),
    }


@router.get("/api/modulos/password-estado")
async def modulos_password_estado():
    from config import admin_modulos
    return {"configurada": admin_modulos.esta_configurada()}


@router.post("/api/modulos/configurar-password")
async def modulos_configurar_password(datos: dict):
    from config import admin_modulos
    if admin_modulos.esta_configurada():
        return JSONResponse({"ok": False, "error": "La contraseña ya está configurada"}, status_code=400)
    return admin_modulos.establecer_password(datos.get("password", ""))


@router.post("/api/modulos/verificar-password")
async def modulos_verificar_password(datos: dict):
    from config import admin_modulos
    return {"ok": admin_modulos.verificar_password(datos.get("password", ""))}


@router.post("/api/modulos/{modulo_id}/activar")
async def activar_modulo(modulo_id: str):
    fpath = deps.AGENTES_DIR / f"{modulo_id}.yaml"
    if not fpath.exists():
        return JSONResponse({"ok": False, "error": "no existe ese módulo"}, status_code=404)
    _fijar_activo_yaml(fpath, True)
    _sincronizar_agentes()
    return {"ok": True}


@router.post("/api/modulos/{modulo_id}/desactivar")
async def desactivar_modulo(modulo_id: str):
    fpath = deps.AGENTES_DIR / f"{modulo_id}.yaml"
    if not fpath.exists():
        return JSONResponse({"ok": False, "error": "no existe ese módulo"}, status_code=404)
    _fijar_activo_yaml(fpath, False)
    _sincronizar_agentes()
    return {"ok": True}


@router.post("/api/modulos/{modulo_id}/eliminar")
async def eliminar_modulo(modulo_id: str, datos: dict):
    from config import admin_modulos
    if not admin_modulos.verificar_password(datos.get("password", "")):
        return JSONResponse({"ok": False, "error": "Contraseña incorrecta"}, status_code=403)

    fpath = deps.AGENTES_DIR / f"{modulo_id}.yaml"
    if not fpath.exists():
        return JSONResponse({"ok": False, "error": "no existe ese módulo"}, status_code=404)

    deps.AGENTES_ELIMINADOS_DIR.mkdir(parents=True, exist_ok=True)
    fpath.rename(deps.AGENTES_ELIMINADOS_DIR / fpath.name)

    if datos.get("borrar_datos"):
        conn = sqlite3.connect(str(deps.DB_PATH))
        try:
            for tabla in TABLAS_POR_MODULO.get(modulo_id, []):
                conn.execute(f"DELETE FROM {tabla}")
            conn.commit()
        finally:
            conn.close()

    _sincronizar_agentes()
    return {"ok": True}


@router.post("/api/modulos/{modulo_id}/restaurar")
async def restaurar_modulo(modulo_id: str):
    origen = deps.AGENTES_ELIMINADOS_DIR / f"{modulo_id}.yaml"
    if not origen.exists():
        return JSONResponse({"ok": False, "error": "no existe en eliminados"}, status_code=404)
    origen.rename(deps.AGENTES_DIR / f"{modulo_id}.yaml")
    _sincronizar_agentes()
    return {"ok": True}
