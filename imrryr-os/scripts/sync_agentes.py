#!/usr/bin/env python3
"""
sync_agentes.py — Escaneo de /agentes hacia OpenCode (Fase 4.1, Hot-Plugging real)
====================================================================================
Hasta ahora, agentes/*.yaml y skills/*.py eran solo metadata que leía el
propio dashboard: OpenCode (el motor) no los conocía, por lo que ningún
agente podía usar sus skills de verdad. Este script cierra esa brecha:

  1. Registra mcp_server/skills_server.py como servidor MCP local en
     config/opencode.json (clave "mcp") — expone las skills como tools reales.
  2. Convierte cada agentes/*.yaml (salvo "build", que es el agente nativo
     de OpenCode con permisos elevados) en un subagente real de OpenCode
     (clave "agent"), con permission.skill restringido exactamente a las
     herramientas listadas en herramientas_permitidas — ninguna otra tool
     nativa (bash, edit, read libre, etc.) queda disponible para ellos.

Si borras un agentes/*.yaml o le quitas una herramienta, este script (que
startup.py corre en cada arranque) refleja el cambio en opencode.json sin
tocar código: es el escaneo de "Carpetas Dinámicas" que describe la Fase 4.

opencode.json no se commitea (rutas absolutas de esta máquina). En una
instalación nueva se siembra desde config/opencode.template.json, que es
portable y commiteable — mismo patrón que config/.env vs .env.example.

Uso:
    python scripts/sync_agentes.py
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
AGENTES_DIR = ROOT / "agentes"
OPENCODE_JSON = ROOT / "config" / "opencode.json"
# Plantilla portable (commiteada, sin rutas absolutas): de acá se siembra
# opencode.json en una instalación nueva. El archivo real NO se commitea —
# igual que config/.env — porque las rutas del MCP son absolutas por diseño
# (apuntan al venv y a skills_server.py de ESTA máquina).
OPENCODE_TEMPLATE = ROOT / "config" / "opencode.template.json"
MCP_SERVER_SCRIPT = ROOT / "mcp_server" / "skills_server.py"
MCP_SERVER_NAME = "imrryr"

# El agente Build es el agente primario nativo de OpenCode (permisos
# elevados por diseño, ver agentes/agente_build.yaml): no se convierte en
# subagente ni se restringe aquí. Su sandbox de seguridad vive dentro de
# leer_archivo.py/escribir_archivo.py/ejecutar_script.py.
AGENTE_NATIVO = "build"

PERMISOS_NATIVOS_DENEGADOS = [
    "read", "edit", "bash", "grep", "glob", "list",
    "webfetch", "websearch", "lsp", "todowrite", "task",
    "external_directory", "question",
]


def log(msg: str) -> None:
    print(f"[sync_agentes] {msg}", flush=True)


def _python_venv() -> str:
    candidato = ROOT / ".venv" / "Scripts" / "python.exe"
    if candidato.exists():
        return str(candidato)
    candidato = ROOT / ".venv" / "bin" / "python"
    if candidato.exists():
        return str(candidato)
    return sys.executable


def _slug_a_id(nombre_archivo: str) -> str:
    return nombre_archivo.removeprefix("agente_")


def construir_mcp_config() -> dict:
    """Servidores MCP que ve OpenCode.

    Se declaran AQUÍ, en la config del proyecto, y no en la config personal de
    quien desarrolla: así viajan con la app al empaquetarla y el sistema se
    comporta igual en cualquier PC (ver la nota de aislamiento en
    scripts/startup.py).
    """
    mcp = {
        MCP_SERVER_NAME: {
            "type": "local",
            "command": [_python_venv(), str(MCP_SERVER_SCRIPT)],
            "enabled": True,
        }
    }

    # codebase-memory: exploración de código sin leer archivos a lo bruto.
    # Solo le sirve al agente `build`, que es el único que trabaja con código;
    # los subagentes de negocio (agenda, finanzas, compras...) lo tienen
    # denegado por su allowlist de skills, así que no les añade ruido.
    # Requiere `uv` (uvx). Si no está instalado se declara deshabilitado en vez
    # de omitirlo: queda visible en la config, y activarlo es instalar uv.
    hay_uvx = shutil.which("uvx") is not None
    mcp["codebase-memory"] = {
        "type": "local",
        "command": ["uvx", "codebase-memory-mcp"],
        "enabled": hay_uvx,
    }
    if not hay_uvx:
        log("  NOTA: 'uvx' no está instalado; el MCP codebase-memory queda deshabilitado.")

    return mcp


def construir_agent_config() -> dict:
    agentes_json: dict[str, dict] = {}

    if not AGENTES_DIR.exists():
        return agentes_json

    for fpath in sorted(AGENTES_DIR.glob("*.yaml")):
        agent_id = _slug_a_id(fpath.stem)
        if agent_id == AGENTE_NATIVO or fpath.stem == AGENTE_NATIVO:
            continue

        data = yaml.safe_load(fpath.read_text(encoding="utf-8")) or {}
        if not data.get("activo", True):
            log(f"  SKIP {fpath.name} (activo: false)")
            continue

        herramientas = data.get("herramientas_permitidas", [])
        # Sin default de proveedor: si un agente no declara modelo_preferido,
        # usa el alias de la cuenta activa (Ajustes > Cuentas de IA) en vez de
        # caer a un modelo concreto de un proveedor puntual.
        modelo = str(data.get("modelo_preferido", "imrryr-activo")).removeprefix("imrryr-llm/")

        permission_skill = {f"{MCP_SERVER_NAME}_{h}": "allow" for h in herramientas}
        permission_skill[f"{MCP_SERVER_NAME}_*"] = "deny"
        permission_skill["*"] = "deny"

        permission = {clave: "deny" for clave in PERMISOS_NATIVOS_DENEGADOS}
        permission["skill"] = permission_skill

        agentes_json[agent_id] = {
            "description": str(data.get("descripcion", "")).strip(),
            "mode": "subagent",
            "model": f"imrryr-llm/{modelo}",
            "permission": permission,
        }
        log(f"  OK {fpath.name} -> agente '{agent_id}' ({len(herramientas)} herramientas)")

    _agregar_build(agentes_json)
    return agentes_json


def _agregar_build(agentes_json: dict[str, dict]) -> None:
    """Escribe también el agente 'build' en opencode.json.

    Antes se omitía por completo por ser el agente primario nativo, pero eso
    dejaba su 'descripcion' de agentes/agente_build.yaml sin efecto: OpenCode
    usaba su build genérico, que no sabe que existen subagentes. Resultado:
    ante "¿qué tengo agendado hoy?" respondía que no podía, en vez de delegar
    en el subagente de agenda. Como build es el único punto de entrada de
    WhatsApp y del chat del inicio, sin esto esos dos canales solo servían
    para temas de código.

    NO se le aplican PERMISOS_NATIVOS_DENEGADOS: build conserva sus permisos
    elevados (incluida la tool 'task', que es justamente la que usa para
    delegar). Su sandbox real vive en leer_archivo/escribir_archivo/
    ejecutar_script.
    """
    fpath = AGENTES_DIR / f"agente_{AGENTE_NATIVO}.yaml"
    if not fpath.exists():
        return
    data = yaml.safe_load(fpath.read_text(encoding="utf-8")) or {}
    descripcion = str(data.get("descripcion", "")).strip()

    # Lista explícita de a quién puede delegar: sin los nombres exactos, el
    # modelo tiene que adivinar el parámetro de la tool 'task'.
    subagentes = sorted(agentes_json.keys())
    if subagentes:
        descripcion += (
            "\n\nSubagentes disponibles para delegar con la herramienta 'task' "
            "(usa exactamente estos nombres): " + ", ".join(subagentes) + ". "
            "Cuando la petición sea del dominio de uno de ellos, delega en vez "
            "de responder que no puedes."
        )

    modelo = str(data.get("modelo_preferido", "imrryr-activo")).removeprefix("imrryr-llm/")
    agentes_json[AGENTE_NATIVO] = {
        "description": descripcion,
        "mode": "primary",
        "model": f"imrryr-llm/{modelo}",
    }
    log(f"  OK {fpath.name} -> agente primario '{AGENTE_NATIVO}' (delega en {len(subagentes)} subagentes)")


def _sembrar_desde_plantilla() -> bool:
    """Instalación nueva: copia la plantilla portable a opencode.json.

    La parte estática (provider LiteLLM en :4000) viaja commiteada sin rutas
    absolutas; las claves "mcp" y "agent" las agrega este script abajo con
    los paths reales de esta máquina."""
    if OPENCODE_JSON.exists():
        return True
    if not OPENCODE_TEMPLATE.exists():
        log(f"ERROR: no existe {OPENCODE_JSON} ni la plantilla {OPENCODE_TEMPLATE}")
        return False
    OPENCODE_JSON.write_text(OPENCODE_TEMPLATE.read_text(encoding="utf-8"), encoding="utf-8")
    log(f"opencode.json sembrado desde {OPENCODE_TEMPLATE.name}")
    return True


def main() -> int:
    if not _sembrar_desde_plantilla():
        return 1

    cfg = json.loads(OPENCODE_JSON.read_text(encoding="utf-8"))

    cfg["mcp"] = construir_mcp_config()
    log(f"Servidor MCP registrado: {MCP_SERVER_NAME}")

    cfg["agent"] = construir_agent_config()

    OPENCODE_JSON.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    log(f"{len(cfg['agent'])} subagentes sincronizados en {OPENCODE_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
