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
    html = html.replace("__IMRRYR_CHAT_TIMEOUT_MS__", str(deps.chat_timeout_seconds() * 1000))
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
    return uso_de_hoy(incluir_detalles=True)


@router.post("/api/uso-ia/presupuesto")
async def actualizar_presupuesto_ia(payload: dict):
    from uso_ia import guardar_limite_diario
    limite = int(payload.get("limite_diario", 20))
    res = guardar_limite_diario(limite)
    if not res.get("ok"):
        return JSONResponse(res, status_code=400)
    return res


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


# ---------------------------------------------------------------------------
# API: Human-In-The-Loop (HITL) Autorizaciones pendientes
# ---------------------------------------------------------------------------
@router.get("/api/hitl/pendientes")
async def listar_hitl_pendientes(agente: str = ""):
    from skills.confirmacion_hitl import listar_solicitudes_pendientes
    return {"solicitudes": listar_solicitudes_pendientes(agente)}


@router.post("/api/hitl/{solicitud_id}/resolver")
async def resolver_hitl(solicitud_id: int, payload: dict):
    from skills.confirmacion_hitl import resolver_solicitud
    decision = payload.get("decision", "")
    res = resolver_solicitud(solicitud_id, decision)
    if not res.get("ok"):
        return JSONResponse(res, status_code=400)
    return res


# ---------------------------------------------------------------------------
# API: Estado de desarrollo y proyectos (Agente Build)
# ---------------------------------------------------------------------------
@router.get("/api/codigo/estado")
async def get_codigo_estado():
    """Devuelve el estado del repositorio y el archivo de seguimiento de proyecto."""
    import subprocess
    root = deps.ROOT
    current_state_file = root / ".ai-os" / "CURRENT_STATE.md"
    contenido_state = ""
    if current_state_file.exists():
        try:
            contenido_state = current_state_file.read_text(encoding="utf-8")
        except Exception:
            pass

    branch = "main"
    ultimo_commit = ""
    try:
        r_b = subprocess.run(["git", "branch", "--show-current"], cwd=str(root), capture_output=True, text=True)
        if r_b.returncode == 0 and r_b.stdout.strip():
            branch = r_b.stdout.strip()
        r_c = subprocess.run(["git", "log", "-1", "--oneline"], cwd=str(root), capture_output=True, text=True)
        if r_c.returncode == 0 and r_c.stdout.strip():
            ultimo_commit = r_c.stdout.strip()
    except Exception:
        pass

    estado_final = contenido_state.strip() or f"Rama activa: {branch}\nÚltimo commit: {ultimo_commit}\n\nListo para recibir instrucciones de desarrollo."
    return {
        "ok": True,
        "ruta": str(root),
        "branch": branch,
        "ultimo_commit": ultimo_commit,
        "estado": estado_final,
    }


# ---------------------------------------------------------------------------
# API: Cierre ordenado del sistema desde la interfaz
# ---------------------------------------------------------------------------
@router.post("/api/sistema/apagar")
async def apagar_sistema():
    """Apaga ordenadamente los servicios de Imrryr OS."""
    import sys
    import threading

    def _shutdown():
        import subprocess
        import time
        time.sleep(0.5)
        root = deps.ROOT
        py_exe = sys.executable
        shutdown_script = root / "scripts" / "shutdown.py"
        if shutdown_script.exists():
            subprocess.run([py_exe, str(shutdown_script)], cwd=str(root))

    threading.Thread(target=_shutdown, daemon=True).start()
    return {"ok": True, "mensaje": "Imrryr OS se está deteniendo..."}



