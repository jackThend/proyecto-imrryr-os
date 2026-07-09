#!/usr/bin/env python3
"""
server.py — Servidor del Dashboard de Escritorio (Fase 6)
===========================================================
FastAPI que sirve la interfaz visual y las APIs de datos para los widgets.

Uso:
    python dashboard/server.py              # :3000 por defecto
    python dashboard/server.py --port 3000

Endpoints:
    GET  /                       → Dashboard HTML
    GET  /api/widgets            → Lista de widgets disponibles (desde /agentes/*.yaml)
    GET  /api/finanzas           → Datos de gastos (SQLite), incluye por_mes
    GET  /api/finanzas/export    → Exporta los gastos filtrados a CSV
    PUT  /api/finanzas/gastos/{id}    → Corrige un gasto (comercio/categoría/monto)
    DELETE /api/finanzas/gastos/{id}  → Elimina un gasto
    POST /api/finanzas/importar/estimar   → Cuenta ~cuántos correos bancarios hay (sin traerlos)
    POST /api/finanzas/importar/iniciar   → Arranca (o retoma) la importación histórica en segundo plano
    GET  /api/finanzas/importar/estado    → Progreso de la importación en curso
    POST /api/finanzas/importar/cancelar  → Cancela una importación en curso
    GET  /api/finanzas/importar/informe   → Informe de gastos importados agrupado por banco
    GET  /api/semillas           → Lista de ideas (ver skills/semillas.py)
    POST /api/semillas           → Crea una idea
    GET  /api/semillas/{id}      → Detalle de una idea (con adjuntos)
    PUT  /api/semillas/{id}      → Edita título/contenido/etiquetas
    POST /api/semillas/{id}/estado   → Cambia de etapa (puede crear un proyecto)
    POST /api/semillas/{id}/adjunto  → Sube una imagen/archivo adjunto
    GET  /api/proyectos          → Lista de proyectos
    PUT  /api/proyectos/{id}     → Edita un proyecto
    GET  /api/correo/cuentas         → Cuentas de correo configuradas (password oculto)
    POST /api/correo/cuentas         → Crea/edita una cuenta
    DELETE /api/correo/cuentas/{id}  → Elimina una cuenta
    GET  /api/correo/bandeja         → Correos recientes de una cuenta
    GET  /api/correo/borradores      → Borradores pendientes/enviados/descartados
    POST /api/correo/borradores/{id}/enviar     → Envía un borrador (única vía real de envío)
    POST /api/correo/borradores/{id}/descartar  → Descarta un borrador
    GET  /api/oportunidades           → Lista de oportunidades de fondos (ver skills/guardar_oportunidad.py)
    POST /api/oportunidades/{id}/estado  → Cambia el estado de una oportunidad
    GET  /api/ajustes/fondo       → URL del fondo personalizado (modo Creativo), o null si no hay
    POST /api/ajustes/fondo       → Sube una imagen de fondo personalizada
    DELETE /api/ajustes/fondo     → Vuelve al fondo por defecto
    GET  /api/ajustes/cuentas-ia          → Cuentas de IA configuradas (api_key oculta)
    POST /api/ajustes/cuentas-ia          → Crea/edita una cuenta de IA
    DELETE /api/ajustes/cuentas-ia/{id}   → Elimina una cuenta de IA
    POST /api/ajustes/cuentas-ia/{id}/activar  → Activa una cuenta (reinicia LiteLLM)
    GET  /api/ajustes/cuentas-git          → Cuentas de GitHub configuradas (token oculto)
    POST /api/ajustes/cuentas-git          → Crea/edita una cuenta de GitHub
    DELETE /api/ajustes/cuentas-git/{id}   → Elimina una cuenta de GitHub
    POST /api/ajustes/cuentas-git/{id}/activar   → Marca cuál cuenta usa repo_web por defecto
    GET  /api/ajustes/cuentas-social       → Cuentas de Meta Graph API configuradas (token oculto)
    POST /api/ajustes/cuentas-social       → Crea/edita una cuenta social
    DELETE /api/ajustes/cuentas-social/{id}      → Elimina una cuenta social
    POST /api/ajustes/cuentas-social/{id}/activar → Marca cuál cuenta usa redes_sociales por defecto
    GET  /api/modulos                     → Lista módulos/agentes activos e inactivos + eliminados
    GET  /api/modulos/password-estado     → Si ya existe una contraseña de administrador configurada
    POST /api/modulos/configurar-password → Crea la contraseña (solo la primera vez)
    POST /api/modulos/verificar-password  → Verifica una contraseña
    POST /api/modulos/{id}/activar        → Reactiva un módulo (sync_agentes.py corre después)
    POST /api/modulos/{id}/desactivar     → Desactiva un módulo sin borrar sus datos
    POST /api/modulos/{id}/eliminar       → Requiere password; mueve el YAML a agentes/_eliminados/
    POST /api/modulos/{id}/restaurar      → Recupera un módulo eliminado
    GET  /api/rrss/posts          → Lista posts programados para redes sociales
    POST /api/rrss/posts          → Programa un post nuevo (sin pasar por el LLM)
    GET  /api/compras/seguimientos       → Lista productos en seguimiento de precio
    POST /api/compras/seguimientos       → Crea un seguimiento nuevo
    DELETE /api/compras/seguimientos/{id} → Elimina un seguimiento (y sus ofertas)
    GET  /api/compras/prefs       → Cuenta de correo + destinatario del digest diario
    POST /api/compras/prefs      → Guarda esas preferencias
    GET  /api/agenda/eventos?rango=hoy|semana|mes → Lista eventos activos (sin pasar por el LLM)
    POST /api/agenda/eventos                  → Crea un evento nuevo (avisos: "08:00,17:00")
    POST /api/agenda/eventos/{id}/cancelar    → Cancela un evento
    GET  /api/navegacion/ultimo-audio     → Último audio TTS generado (para reproducirlo)
    POST /api/navegacion/transcribir      → Sube audio del micrófono, devuelve texto (Whisper local)
    GET  /api/pendientes                  → Lista la lista de pendientes
    POST /api/pendientes                  → Crea un pendiente
    POST /api/pendientes/{id}/hecho       → Marca (des)hecho un pendiente
    DELETE /api/pendientes/{id}           → Elimina un pendiente
    POST /api/chat               → Envía prompt a OpenCode (agente configurable)
"""
from __future__ import annotations

import base64
import json
import os
import re
import subprocess
import time
import sys
from pathlib import Path

import uvicorn
import yaml
from dotenv import load_dotenv
from fastapi import FastAPI, File, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / "config" / ".env"
DB_PATH = ROOT / "vault" / "sqlite" / "imrryr.db"
AGENTES_DIR = ROOT / "agentes"
SEMILLAS_DIR = ROOT / "semillas"
ADJUNTOS_DIR = SEMILLAS_DIR / "adjuntos"
STATIC_DIR = Path(__file__).parent / "static"
FONDOS_DIR = STATIC_DIR / "fondos"

ADJUNTOS_DIR.mkdir(parents=True, exist_ok=True)
FONDOS_DIR.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT / "skills"))
sys.path.insert(0, str(ROOT))  # para 'from correo.config import ...'

if ENV_FILE.exists():
    load_dotenv(ENV_FILE)

app = FastAPI(title="Imrryr Dashboard", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.mount("/adjuntos", StaticFiles(directory=str(ADJUNTOS_DIR)), name="adjuntos")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Una sesión de OpenCode por agente (proceso único, usuario único — coherente
# con el modelo local-first de Imrryr OS). Sin esto, hablar con "creativo" y
# luego con "build" en la misma sesión compartida podía confundir el contexto.
_opencode_sessions: dict[str, str] = {}


def _opencode_port() -> int:
    return int(os.environ.get("OPENCODE_PORT") or 4040)


def _opencode_password() -> str:
    return os.environ.get("OPENCODE_SERVER_PASSWORD", "imryyr-local-pass")


def _modelo_activo() -> str:
    """Alias estable de LiteLLM (ver config/litellm_config.yaml) que siempre
    apunta a la cuenta de IA que el usuario eligió en Ajustes > Cuentas de IA
    (config/cuentas_ia.py). Cambiar de proveedor nunca requiere tocar esto."""
    return "imrryr-activo"


def _opencode_auth_headers() -> dict[str, str]:
    token = base64.b64encode(f"opencode:{_opencode_password()}".encode()).decode()
    return {"Authorization": f"Basic {token}", "Content-Type": "application/json"}


# ---------------------------------------------------------------------------
# HTML Dashboard (single-page app embebida)
# ---------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def dashboard():
    html = (Path(__file__).parent / "dashboard.html").read_text(encoding="utf-8")
    return HTMLResponse(html)


# ---------------------------------------------------------------------------
# API: Widgets dinámicos (lee /agentes/*.yaml)
# ---------------------------------------------------------------------------
@app.get("/api/widgets")
async def list_widgets():
    widgets = []
    if AGENTES_DIR.exists():
        for fpath in sorted(AGENTES_DIR.glob("*.yaml")):
            try:
                data = yaml.safe_load(fpath.read_text(encoding="utf-8"))
                if data and data.get("activo", True):
                    widgets.append({
                        "id": fpath.stem,
                        "nombre": data.get("nombre", fpath.stem),
                        "descripcion": data.get("descripcion", ""),
                        "herramientas": data.get("herramientas_permitidas", []),
                    })
            except Exception as e:
                pass
    return {"widgets": widgets}


# ---------------------------------------------------------------------------
# API: Finanzas (desde SQLite)
# ---------------------------------------------------------------------------
def _consultar_gastos(desde: str | None = None, hasta: str | None = None, limite: int = 20) -> dict:
    """desde/hasta son fechas ISO (YYYY-MM-DD), inclusivas. Sin ellas, trae todo.

    No hay "reportes congelados": los gastos ya quedan permanentes en SQLite
    apenas se insertan (vía inyectar_gasto), así que filtrar por rango aquí
    siempre es exacto — no hace falta recalcular nada con IA. Reusado tanto
    por /api/finanzas como por /api/finanzas/export."""
    if not DB_PATH.exists():
        return {"gastos": [], "total": 0, "por_categoria": {}, "por_mes": {}, "anios_disponibles": []}

    import sqlite3
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        condiciones = []
        params: list = []
        if desde:
            condiciones.append("fecha >= ?")
            params.append(desde)
        if hasta:
            condiciones.append("fecha <= ?")
            params.append(hasta)
        where = f"WHERE {' AND '.join(condiciones)}" if condiciones else ""

        cur = conn.execute(f"SELECT * FROM gastos {where} ORDER BY fecha DESC LIMIT ?", (*params, limite))
        gastos = [dict(row) for row in cur.fetchall()]

        cur = conn.execute(f"SELECT COALESCE(SUM(monto), 0) as total FROM gastos {where}", params)
        total = cur.fetchone()["total"]

        cur = conn.execute(
            f"SELECT categoria, COUNT(*) as count, SUM(monto) as subtotal FROM gastos {where} GROUP BY categoria",
            params,
        )
        por_categoria = {row["categoria"]: {"count": row["count"], "subtotal": row["subtotal"]} for row in cur.fetchall()}

        cur = conn.execute(
            f"SELECT substr(fecha,1,7) as mes, SUM(monto) as subtotal FROM gastos {where} GROUP BY mes ORDER BY mes",
            params,
        )
        por_mes = {row["mes"]: row["subtotal"] for row in cur.fetchall() if row["mes"]}

        cur = conn.execute("SELECT DISTINCT substr(fecha, 1, 4) as anio FROM gastos ORDER BY anio DESC")
        anios_disponibles = [row["anio"] for row in cur.fetchall() if row["anio"]]

        return {"gastos": gastos, "total": total, "por_categoria": por_categoria, "por_mes": por_mes, "anios_disponibles": anios_disponibles}
    finally:
        conn.close()


@app.get("/api/finanzas")
async def get_finanzas(limite: int = 20, desde: str | None = None, hasta: str | None = None):
    return _consultar_gastos(desde, hasta, limite)


@app.get("/api/finanzas/export")
async def exportar_finanzas(desde: str | None = None, hasta: str | None = None):
    import csv
    import io

    datos = _consultar_gastos(desde, hasta, limite=100000)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["fecha", "monto", "comercio", "categoria", "descripcion", "fuente"])
    for g in datos["gastos"]:
        writer.writerow([g["fecha"], g["monto"], g["comercio"], g["categoria"], g.get("descripcion", ""), g.get("fuente", "")])

    nombre = "gastos"
    if desde or hasta:
        nombre += f"_{desde or ''}_{hasta or ''}"
    from fastapi.responses import Response
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{nombre}.csv"'},
    )


@app.put("/api/finanzas/gastos/{gasto_id}")
async def editar_gasto_endpoint(gasto_id: int, datos: dict):
    import inyectar_gasto
    return inyectar_gasto.actualizar_gasto(
        gasto_id,
        comercio=datos.get("comercio", ""),
        categoria=datos.get("categoria", ""),
        monto=datos.get("monto") or 0,
        descripcion=datos.get("descripcion", ""),
    )


@app.delete("/api/finanzas/gastos/{gasto_id}")
async def eliminar_gasto_endpoint(gasto_id: int):
    import inyectar_gasto
    return inyectar_gasto.eliminar_gasto(gasto_id)


# ---------------------------------------------------------------------------
# API: Importación histórica de correos bancarios (ver finanzas/importador_historico.py)
# ---------------------------------------------------------------------------
QUERY_BANCARIA_DEFECTO = "(compra OR cargo OR transacción OR transaccion OR pago OR abono) (banco OR tarjeta)"
CUENTA_GMAIL_FINANZAS = "gmail_principal"  # Financiero usa una única cuenta Gmail fija (config/gmail_credentials.json)


@app.post("/api/finanzas/importar/estimar")
async def estimar_importacion(datos: dict | None = None):
    from finanzas import importador_historico as importador
    query = (datos or {}).get("query") or QUERY_BANCARIA_DEFECTO
    return importador.estimar(query)


@app.post("/api/finanzas/importar/iniciar")
async def iniciar_importacion(datos: dict | None = None):
    from finanzas import importador_historico as importador
    query = (datos or {}).get("query") or QUERY_BANCARIA_DEFECTO
    return importador.iniciar(CUENTA_GMAIL_FINANZAS, query, tipo="historico")


@app.get("/api/finanzas/importar/estado")
async def estado_importacion():
    from finanzas import importador_historico as importador
    estado = importador.obtener_estado(tipo="historico", cuenta_correo_id=CUENTA_GMAIL_FINANZAS)
    return {"importacion": estado}


@app.post("/api/finanzas/importar/cancelar")
async def cancelar_importacion(datos: dict):
    from finanzas import importador_historico as importador
    importacion_id = datos.get("importacion_id")
    if not importacion_id:
        return JSONResponse({"ok": False, "error": "falta 'importacion_id'"}, status_code=400)
    return importador.cancelar(importacion_id)


@app.get("/api/finanzas/importar/informe")
async def informe_importacion():
    from finanzas import importador_historico as importador
    return {"bancos": importador.informe_por_banco()}


# ---------------------------------------------------------------------------
# API: Ideas/Proyectos ("Pinterest de ideas", ver skills/semillas.py)
# ---------------------------------------------------------------------------
@app.get("/api/semillas")
async def get_semillas(estado: str = ""):
    import semillas as _semillas
    return {"semillas": _semillas.listar_semillas(estado)}


@app.post("/api/semillas")
async def crear_semilla_endpoint(datos: dict):
    import semillas as _semillas
    titulo = datos.get("titulo", "")
    contenido = datos.get("contenido", "")
    if not titulo or not contenido:
        return JSONResponse({"ok": False, "error": "faltan titulo o contenido"}, status_code=400)
    return _semillas.crear_semilla(titulo, contenido, etiquetas=datos.get("etiquetas"), fuente="dashboard")


@app.get("/api/semillas/{semilla_id}")
async def get_semilla(semilla_id: int):
    import semillas as _semillas
    resultado = _semillas.obtener_semilla(semilla_id)
    if resultado.get("ok") is False:
        return JSONResponse(resultado, status_code=404)
    return resultado


@app.put("/api/semillas/{semilla_id}")
async def actualizar_semilla_endpoint(semilla_id: int, datos: dict):
    import semillas as _semillas
    return _semillas.actualizar_semilla(
        semilla_id,
        titulo=datos.get("titulo", ""),
        contenido=datos.get("contenido", ""),
        etiquetas=datos.get("etiquetas"),
    )


@app.post("/api/semillas/{semilla_id}/estado")
async def cambiar_estado_endpoint(semilla_id: int, datos: dict):
    import semillas as _semillas
    return _semillas.cambiar_estado_semilla(semilla_id, datos.get("estado", ""))


@app.post("/api/semillas/{semilla_id}/adjunto")
async def subir_adjunto(semilla_id: int, archivo: UploadFile = File(...)):
    import semillas as _semillas
    carpeta = ADJUNTOS_DIR / str(semilla_id)
    carpeta.mkdir(parents=True, exist_ok=True)
    nombre_seguro = Path(archivo.filename).name  # sin path traversal
    destino = carpeta / nombre_seguro
    destino.write_bytes(await archivo.read())
    ruta_publica = f"/adjuntos/{semilla_id}/{nombre_seguro}"
    return _semillas.adjuntar_archivo_semilla(semilla_id, ruta_publica)


@app.get("/api/proyectos")
async def get_proyectos(estado: str = ""):
    import semillas as _semillas
    return {"proyectos": _semillas.listar_proyectos(estado)}


@app.put("/api/proyectos/{proyecto_id}")
async def actualizar_proyecto_endpoint(proyecto_id: int, datos: dict):
    import semillas as _semillas
    return _semillas.actualizar_proyecto(
        proyecto_id,
        descripcion=datos.get("descripcion", ""),
        estado=datos.get("estado", ""),
        tecnologias=datos.get("tecnologias", ""),
    )


# ---------------------------------------------------------------------------
# API: Agente Secretario (Bandeja de correo multi-proveedor)
#
# El envío real de un correo SOLO ocurre acá (POST .../enviar), nunca desde
# una tool del agente — ver skills/secretario.py.
# ---------------------------------------------------------------------------
@app.get("/api/correo/cuentas")
async def get_cuentas_correo():
    from correo.config import cuentas_seguras
    return {"cuentas": cuentas_seguras()}


@app.post("/api/correo/cuentas")
async def set_cuenta_correo(datos: dict):
    from correo.config import guardar_cuenta
    return guardar_cuenta(datos)


@app.delete("/api/correo/cuentas/{cuenta_id}")
async def eliminar_cuenta_correo(cuenta_id: str):
    from correo.config import quitar_cuenta
    return quitar_cuenta(cuenta_id)


@app.get("/api/correo/bandeja")
async def get_bandeja(cuenta_id: str = "", max_resultados: int = 10):
    if not cuenta_id:
        return {"correos": []}
    import secretario
    return {"correos": secretario.leer_correo(cuenta_id, max_resultados)}


@app.get("/api/correo/borradores")
async def get_borradores(estado: str = "pendiente"):
    import secretario
    return {"borradores": secretario.listar_borradores(estado)}


@app.post("/api/correo/borradores/{borrador_id}/enviar")
async def enviar_borrador_endpoint(borrador_id: int):
    import secretario
    return secretario.enviar_borrador(borrador_id)


@app.post("/api/correo/borradores/{borrador_id}/descartar")
async def descartar_borrador_endpoint(borrador_id: int):
    import secretario
    return secretario.descartar_borrador(borrador_id)


# ---------------------------------------------------------------------------
# API: Perfil de Negocio (usado por el Agente Investigador para filtrar fondos)
# ---------------------------------------------------------------------------
@app.get("/api/perfil-negocio")
async def get_perfil_negocio():
    import perfil_negocio
    return perfil_negocio.leer_perfil_negocio()


@app.post("/api/perfil-negocio")
async def set_perfil_negocio(datos: dict):
    import perfil_negocio
    return perfil_negocio.actualizar_perfil_negocio(datos)


# ---------------------------------------------------------------------------
# API: Fondo personalizado (tema Creativo, ver Ajustes → Apariencia)
# ---------------------------------------------------------------------------
@app.get("/api/ajustes/fondo")
async def get_fondo_personalizado():
    archivos = list(FONDOS_DIR.glob("personalizado.*"))
    if not archivos:
        return {"url": None}
    return {"url": f"/static/fondos/{archivos[0].name}"}


@app.post("/api/ajustes/fondo")
async def set_fondo_personalizado(archivo: UploadFile = File(...)):
    for viejo in FONDOS_DIR.glob("personalizado.*"):
        viejo.unlink()
    extension = Path(archivo.filename).suffix or ".jpg"
    destino = FONDOS_DIR / f"personalizado{extension}"
    destino.write_bytes(await archivo.read())
    return {"ok": True, "url": f"/static/fondos/{destino.name}"}


@app.delete("/api/ajustes/fondo")
async def eliminar_fondo_personalizado():
    for viejo in FONDOS_DIR.glob("personalizado.*"):
        viejo.unlink()
    return {"ok": True}


# ---------------------------------------------------------------------------
# API: Oportunidades / Concursos (ver skills/guardar_oportunidad.py)
# ---------------------------------------------------------------------------
@app.get("/api/oportunidades")
async def get_oportunidades(estado: str = ""):
    import guardar_oportunidad
    return {"oportunidades": guardar_oportunidad.listar_oportunidades(estado)}


@app.post("/api/oportunidades/{oportunidad_id}/estado")
async def cambiar_estado_oportunidad_endpoint(oportunidad_id: int, datos: dict):
    import guardar_oportunidad
    estado = datos.get("estado", "")
    if not estado:
        return JSONResponse({"ok": False, "error": "falta 'estado'"}, status_code=400)
    return guardar_oportunidad.cambiar_estado_oportunidad(oportunidad_id, estado, datos.get("relevancia_nota", ""))


# ---------------------------------------------------------------------------
# API: Cuentas de IA (qué proveedor/modelo usan todos los agentes)
# ---------------------------------------------------------------------------
@app.get("/api/ajustes/cuentas-ia")
async def get_cuentas_ia():
    from config import cuentas_ia
    return {"cuentas": cuentas_ia.cuentas_seguras(), "proveedores": cuentas_ia.PROVEEDORES}


@app.post("/api/ajustes/cuentas-ia")
async def set_cuenta_ia(datos: dict):
    from config import cuentas_ia
    return cuentas_ia.guardar_cuenta(datos)


@app.delete("/api/ajustes/cuentas-ia/{cuenta_id}")
async def eliminar_cuenta_ia(cuenta_id: str):
    from config import cuentas_ia
    return cuentas_ia.quitar_cuenta(cuenta_id)


@app.post("/api/ajustes/cuentas-ia/{cuenta_id}/activar")
async def activar_cuenta_ia(cuenta_id: str):
    from config import cuentas_ia
    return cuentas_ia.activar_cuenta(cuenta_id)


# ---------------------------------------------------------------------------
# API: Cuentas de GitHub (repos que el Agente RRSS/Web puede administrar)
# ---------------------------------------------------------------------------
@app.get("/api/ajustes/cuentas-git")
async def get_cuentas_git():
    from config import cuentas_git
    return {"cuentas": cuentas_git.cuentas_seguras()}


@app.post("/api/ajustes/cuentas-git")
async def set_cuenta_git(datos: dict):
    from config import cuentas_git
    return cuentas_git.guardar_cuenta(datos)


@app.delete("/api/ajustes/cuentas-git/{cuenta_id}")
async def eliminar_cuenta_git(cuenta_id: str):
    from config import cuentas_git
    return cuentas_git.quitar_cuenta(cuenta_id)


@app.post("/api/ajustes/cuentas-git/{cuenta_id}/activar")
async def activar_cuenta_git(cuenta_id: str):
    from config import cuentas_git
    return cuentas_git.activar_cuenta(cuenta_id)


# ---------------------------------------------------------------------------
# API: Cuentas de redes sociales (Meta Graph API: Facebook + Instagram)
# ---------------------------------------------------------------------------
@app.get("/api/ajustes/cuentas-social")
async def get_cuentas_social():
    from config import cuentas_social
    return {"cuentas": cuentas_social.cuentas_seguras()}


@app.post("/api/ajustes/cuentas-social")
async def set_cuenta_social(datos: dict):
    from config import cuentas_social
    return cuentas_social.guardar_cuenta(datos)


@app.delete("/api/ajustes/cuentas-social/{cuenta_id}")
async def eliminar_cuenta_social(cuenta_id: str):
    from config import cuentas_social
    return cuentas_social.quitar_cuenta(cuenta_id)


@app.post("/api/ajustes/cuentas-social/{cuenta_id}/activar")
async def activar_cuenta_social(cuenta_id: str):
    from config import cuentas_social
    return cuentas_social.activar_cuenta(cuenta_id)


# ---------------------------------------------------------------------------
# API: Gestión de Módulos/Agentes (protegida por contraseña, ver config/admin_modulos.py)
# ---------------------------------------------------------------------------
AGENTES_ELIMINADOS_DIR = AGENTES_DIR / "_eliminados"
AGENTE_NATIVO_EXCLUIDO = "agente_build"  # agente nativo de OpenCode, sync_agentes.py lo excluye igual

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
        if fpath.stem == AGENTE_NATIVO_EXCLUIDO:
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
    subprocess.run([sys.executable, str(ROOT / "scripts" / "sync_agentes.py")], cwd=str(ROOT))


@app.get("/api/modulos")
async def listar_modulos():
    return {
        "modulos": _leer_modulos_de(AGENTES_DIR),
        "eliminados": _leer_modulos_de(AGENTES_ELIMINADOS_DIR, eliminado=True),
    }


@app.get("/api/modulos/password-estado")
async def modulos_password_estado():
    from config import admin_modulos
    return {"configurada": admin_modulos.esta_configurada()}


@app.post("/api/modulos/configurar-password")
async def modulos_configurar_password(datos: dict):
    from config import admin_modulos
    if admin_modulos.esta_configurada():
        return JSONResponse({"ok": False, "error": "La contraseña ya está configurada"}, status_code=400)
    return admin_modulos.establecer_password(datos.get("password", ""))


@app.post("/api/modulos/verificar-password")
async def modulos_verificar_password(datos: dict):
    from config import admin_modulos
    return {"ok": admin_modulos.verificar_password(datos.get("password", ""))}


@app.post("/api/modulos/{modulo_id}/activar")
async def activar_modulo(modulo_id: str):
    fpath = AGENTES_DIR / f"{modulo_id}.yaml"
    if not fpath.exists():
        return JSONResponse({"ok": False, "error": "no existe ese módulo"}, status_code=404)
    _fijar_activo_yaml(fpath, True)
    _sincronizar_agentes()
    return {"ok": True}


@app.post("/api/modulos/{modulo_id}/desactivar")
async def desactivar_modulo(modulo_id: str):
    fpath = AGENTES_DIR / f"{modulo_id}.yaml"
    if not fpath.exists():
        return JSONResponse({"ok": False, "error": "no existe ese módulo"}, status_code=404)
    _fijar_activo_yaml(fpath, False)
    _sincronizar_agentes()
    return {"ok": True}


@app.post("/api/modulos/{modulo_id}/eliminar")
async def eliminar_modulo(modulo_id: str, datos: dict):
    from config import admin_modulos
    if not admin_modulos.verificar_password(datos.get("password", "")):
        return JSONResponse({"ok": False, "error": "Contraseña incorrecta"}, status_code=403)

    fpath = AGENTES_DIR / f"{modulo_id}.yaml"
    if not fpath.exists():
        return JSONResponse({"ok": False, "error": "no existe ese módulo"}, status_code=404)

    AGENTES_ELIMINADOS_DIR.mkdir(parents=True, exist_ok=True)
    fpath.rename(AGENTES_ELIMINADOS_DIR / fpath.name)

    if datos.get("borrar_datos"):
        import sqlite3
        conn = sqlite3.connect(str(DB_PATH))
        try:
            for tabla in TABLAS_POR_MODULO.get(modulo_id, []):
                conn.execute(f"DELETE FROM {tabla}")
            conn.commit()
        finally:
            conn.close()

    _sincronizar_agentes()
    return {"ok": True}


@app.post("/api/modulos/{modulo_id}/restaurar")
async def restaurar_modulo(modulo_id: str):
    origen = AGENTES_ELIMINADOS_DIR / f"{modulo_id}.yaml"
    if not origen.exists():
        return JSONResponse({"ok": False, "error": "no existe en eliminados"}, status_code=404)
    origen.rename(AGENTES_DIR / f"{modulo_id}.yaml")
    _sincronizar_agentes()
    return {"ok": True}


# ---------------------------------------------------------------------------
# API: RRSS y Web — posts programados (lectura/alta directa, sin pasar por el LLM)
# ---------------------------------------------------------------------------
@app.get("/api/rrss/posts")
async def listar_posts_programados():
    import sqlite3
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.execute("SELECT * FROM posts_programados ORDER BY programado_at DESC")
        return {"posts": [dict(row) for row in cur.fetchall()]}
    finally:
        conn.close()


@app.post("/api/rrss/posts")
async def crear_post_programado(datos: dict):
    import sqlite3
    contenido = datos.get("contenido", "")
    plataformas = datos.get("plataformas", "")
    programado_at = datos.get("programado_at", "")
    if not contenido or not plataformas or not programado_at:
        return JSONResponse({"ok": False, "error": "faltan contenido, plataformas o programado_at"}, status_code=400)
    conn = sqlite3.connect(str(DB_PATH))
    try:
        cur = conn.execute(
            "INSERT INTO posts_programados (contenido, media_ruta, plataformas, programado_at) VALUES (?, ?, ?, ?)",
            (contenido, datos.get("media_ruta", ""), plataformas, programado_at),
        )
        conn.commit()
        return {"ok": True, "id": cur.lastrowid}
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# API: Compras — seguimientos de precio (lectura/alta directa) + preferencias de digest
# ---------------------------------------------------------------------------
@app.get("/api/compras/seguimientos")
async def listar_seguimientos_compras():
    from skills.gestionar_seguimiento_compras import gestionar_seguimiento_compras
    return gestionar_seguimiento_compras(accion="listar")


@app.post("/api/compras/seguimientos")
async def crear_seguimiento_compras(datos: dict):
    from skills.gestionar_seguimiento_compras import gestionar_seguimiento_compras
    return gestionar_seguimiento_compras(
        accion="crear", producto=datos.get("producto", ""),
        precio_min=datos.get("precio_min"), precio_max=datos.get("precio_max"),
        tiendas=datos.get("tiendas", ""),
    )


@app.delete("/api/compras/seguimientos/{seguimiento_id}")
async def eliminar_seguimiento_compras(seguimiento_id: int):
    from skills.gestionar_seguimiento_compras import gestionar_seguimiento_compras
    return gestionar_seguimiento_compras(accion="eliminar", seguimiento_id=seguimiento_id)


@app.get("/api/agenda/eventos")
async def listar_eventos_agenda(rango: str = "hoy", anio: int | None = None, mes: int | None = None):
    from skills.agenda import agenda as agenda_skill
    return agenda_skill(accion="que_tengo", cuando=rango, anio=anio, mes=mes)


@app.post("/api/agenda/eventos")
async def crear_evento_agenda(datos: dict):
    from skills.agenda import agenda as agenda_skill
    return agenda_skill(
        accion="crear", titulo=datos.get("titulo", ""), fecha=datos.get("fecha", ""),
        hora=datos.get("hora", "09:00"), duracion=datos.get("duracion", 60),
        descripcion=datos.get("descripcion", ""), avisos=datos.get("avisos", ""),
    )


@app.get("/api/pendientes")
async def listar_pendientes_endpoint():
    from skills.pendientes import pendientes as pendientes_skill
    return pendientes_skill(accion="listar")


@app.post("/api/pendientes")
async def crear_pendiente_endpoint(datos: dict):
    from skills.pendientes import pendientes as pendientes_skill
    return pendientes_skill(accion="crear", texto=datos.get("texto", ""))


@app.post("/api/pendientes/{pendiente_id}/hecho")
async def marcar_pendiente_hecho_endpoint(pendiente_id: int, datos: dict):
    from skills.pendientes import pendientes as pendientes_skill
    return pendientes_skill(accion="marcar_hecho", pendiente_id=pendiente_id, hecho=bool(datos.get("hecho", True)))


@app.delete("/api/pendientes/{pendiente_id}")
async def eliminar_pendiente_endpoint(pendiente_id: int):
    from skills.pendientes import pendientes as pendientes_skill
    return pendientes_skill(accion="eliminar", pendiente_id=pendiente_id)


@app.post("/api/agenda/eventos/{evento_id}/cancelar")
async def cancelar_evento_agenda(evento_id: int):
    from skills.agenda import agenda as agenda_skill
    return agenda_skill(accion="cancelar", evento_id=evento_id)


ULTIMO_AUDIO_PATH = ROOT / "config" / "ultimo_audio.json"
AUDIOS_TEMP_DIR = ROOT / "vault" / "audios_temp"


@app.get("/api/navegacion/ultimo-audio")
async def get_ultimo_audio():
    if not ULTIMO_AUDIO_PATH.exists():
        return {"url": None}
    return json.loads(ULTIMO_AUDIO_PATH.read_text(encoding="utf-8"))


@app.post("/api/navegacion/transcribir")
async def transcribir_audio_navegacion(archivo: UploadFile = File(...)):
    from skills.transcribir_audio import transcribir

    AUDIOS_TEMP_DIR.mkdir(parents=True, exist_ok=True)
    extension = Path(archivo.filename).suffix or ".webm"
    ruta_temp = AUDIOS_TEMP_DIR / f"grabacion_{int(time.time() * 1000)}{extension}"
    ruta_temp.write_bytes(await archivo.read())
    try:
        texto = transcribir(str(ruta_temp))
        return {"ok": True, "texto": texto}
    finally:
        ruta_temp.unlink(missing_ok=True)


COMPRAS_PREFS_PATH = ROOT / "config" / "compras_prefs.json"


@app.get("/api/compras/prefs")
async def get_compras_prefs():
    if not COMPRAS_PREFS_PATH.exists():
        return {"cuenta_correo_id": "", "destinatario": ""}
    return json.loads(COMPRAS_PREFS_PATH.read_text(encoding="utf-8"))


@app.post("/api/compras/prefs")
async def set_compras_prefs(datos: dict):
    COMPRAS_PREFS_PATH.parent.mkdir(parents=True, exist_ok=True)
    COMPRAS_PREFS_PATH.write_text(json.dumps(datos, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"ok": True}


# ---------------------------------------------------------------------------
# API: Chat (usa una sesión real de OpenCode -> acceso a agentes y skills)
#
# OpenCode expone dos familias de endpoints de sesión: `/api/session/...`
# (asíncrona: /prompt solo admite el mensaje en una cola y hay que
# esperar/consultar aparte) y `/session/...` (síncrona: POST .../message
# devuelve la respuesta ya generada). Usamos la segunda porque es la que
# realmente usa el CLI de OpenCode (`opencode run`) y no requiere hacer
# polling.
# ---------------------------------------------------------------------------
async def _get_or_create_session(client, agent: str) -> str:
    if agent in _opencode_sessions:
        return _opencode_sessions[agent]

    r = await client.post(
        f"http://localhost:{_opencode_port()}/session",
        headers=_opencode_auth_headers(),
        json={"agent": agent, "model": {"id": _modelo_activo(), "providerID": "imryyr-llm"}},
        timeout=15,
    )
    r.raise_for_status()
    data = r.json()
    sid = data.get("data", {}).get("id") or data.get("id")
    if not sid:
        raise RuntimeError(f"Respuesta inesperada al crear sesión: {data}")
    _opencode_sessions[agent] = sid
    return sid


async def _esperar_texto_final(client, sid: str, intentos: int = 8, espera: float = 1.5) -> str:
    """Cuando el agente encadena llamadas a herramientas (tool -> tool -> texto),
    el POST /session/{id}/message puede devolver antes de que el mensaje final
    con texto exista todavía — la acción de las herramientas ya se ejecutó, solo
    falta que redacte la respuesta. Se sondea la lista de mensajes de la sesión
    unos segundos hasta encontrar el último turno del asistente con texto."""
    import asyncio

    for _ in range(intentos):
        r = await client.get(
            f"http://localhost:{_opencode_port()}/session/{sid}/message",
            headers=_opencode_auth_headers(),
            params={"order": "desc", "limit": 5},
            timeout=15,
        )
        r.raise_for_status()
        cuerpo = r.json()
        mensajes = cuerpo.get("data", []) if isinstance(cuerpo, dict) else cuerpo
        for msg in mensajes:
            if msg.get("info", {}).get("role") != "assistant":
                continue
            texto = "".join(p.get("text", "") for p in msg.get("parts", []) if p.get("type") == "text")
            if texto:
                return texto
            break  # el más reciente ya se revisó y no tiene texto; esperar y reintentar
        await asyncio.sleep(espera)
    return ""


@app.post("/api/chat")
async def chat(request: Request):
    import httpx

    body = await request.json()
    mensaje = body.get("mensaje", "")
    agente = body.get("agente", "build")

    try:
        async with httpx.AsyncClient() as client:
            sid = await _get_or_create_session(client, agente)
            r = await client.post(
                f"http://localhost:{_opencode_port()}/session/{sid}/message",
                headers=_opencode_auth_headers(),
                json={
                    "agent": agente,
                    "model": {"providerID": "imryyr-llm", "modelID": _modelo_activo()},
                    "parts": [{"type": "text", "text": mensaje}],
                },
                timeout=120,
            )
            r.raise_for_status()
            data = r.json()

            respuesta = "".join(p.get("text", "") for p in data.get("parts", []) if p.get("type") == "text")
            if not respuesta:
                respuesta = await _esperar_texto_final(client, sid)

        if not respuesta:
            herramientas = [p.get("tool") for p in data.get("parts", []) if p.get("type") == "tool"]
            respuesta = f"Listo, usé: {', '.join(herramientas)}." if herramientas else "(sin respuesta de texto)"

        return {"respuesta": respuesta, "session_id": sid}
    except Exception as e:
        # La sesión de este agente pudo quedar inválida (ej. OpenCode se reinició); se recrea en el próximo intento.
        _opencode_sessions.pop(agente, None)
        return JSONResponse({"error": str(e)}, status_code=500)


# ---------------------------------------------------------------------------
# API: Estado del sistema
# ---------------------------------------------------------------------------
@app.get("/api/status")
async def system_status():
    import socket
    servicios = {}
    for name, port in [("litellm", 4000), ("opencode", 4040), ("gateway", 5050)]:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.settimeout(1)
            servicios[name] = s.connect_ex(("127.0.0.1", port)) == 0
        finally:
            s.close()
    return {"servicios": servicios}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def _iniciar_scheduler_finanzas() -> None:
    """Sincroniza correos bancarios nuevos al iniciar el dashboard y cada 24h
    mientras siga corriendo — cubre tanto "cada vez que inicio sesión en
    Imrryr OS" como "todos los días", sin necesitar un scheduler del sistema
    operativo. `startup.py` es un lanzador que termina apenas los servicios
    quedan arriba, así que el hilo vive aquí, en el proceso que sí se queda
    corriendo mientras el dashboard está abierto (ver finanzas/importador_historico.py)."""
    import threading
    import time

    def _loop():
        from finanzas import importador_historico as importador
        while True:
            try:
                importador.sincronizar_diario(CUENTA_GMAIL_FINANZAS, QUERY_BANCARIA_DEFECTO)
            except Exception as e:
                print(f"[dashboard] sincronización diaria de Finanzas falló: {e}", flush=True)
            time.sleep(24 * 60 * 60)

    threading.Thread(target=_loop, daemon=True).start()


def main():
    import argparse
    ap = argparse.ArgumentParser(description="Servidor del Dashboard Imrryr OS")
    ap.add_argument("--port", type=int, default=3000)
    args = ap.parse_args()
    _iniciar_scheduler_finanzas()
    from scripts.scheduler import iniciar_scheduler_generico
    iniciar_scheduler_generico()
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="info")


if __name__ == "__main__":
    main()
