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
sys.path.insert(0, str(ROOT / "skills"))
from ruta_modelo import modelo_para_agente  # noqa: E402
AGENTES_DIR = ROOT / "agentes"
OPENCODE_JSON = ROOT / "config" / "opencode.json"
# Plantilla portable (commiteada, sin rutas absolutas): de acá se siembra
# opencode.json en una instalación nueva. El archivo real NO se commitea —
# igual que config/.env — porque las rutas del MCP son absolutas por diseño
# (apuntan al venv y a skills_server.py de ESTA máquina).
OPENCODE_TEMPLATE = ROOT / "config" / "opencode.template.json"
MCP_SERVER_SCRIPT = ROOT / "mcp_server" / "skills_server.py"
MCP_SERVER_NAME = "imrryr"

# Agente supervisor central (asistente universal de entrada)
AGENTE_SUPERVISOR = "asistente"
# Agente de código/CTO (especialista de ingeniería de software)
AGENTE_BUILD = "build"

PERMISOS_NATIVOS_DENEGADOS = [
    "read", "edit", "bash", "grep", "glob", "list",
    "webfetch", "websearch", "lsp", "todowrite", "task",
    "external_directory", "question",
]


# --- Ruta nativa de OpenCode (Zen gratis) -----------------------------------
# El servidor de la capa gratuita solo acepta peticiones que traen el juego
# completo de herramientas nativas de OpenCode: verificado en vivo, basta con
# quitar UNA (p. ej. bash) para recibir 403 "free tier can only be used from
# within OpenCode". OpenCode quita una herramienta de la lista cuando su regla
# es un `deny` general, pero la deja si tiene una regla más específica. Por eso,
# en esta ruta, cada herramienta queda listada con un patrón que nunca coincide:
# el servidor las ve, y cualquier uso real lo niega OpenCode (verificado: bash,
# read, glob y write terminaron en error, sin ejecutarse). webfetch y websearch
# solo aceptan una acción simple, así que van con `deny` liso.
PATRON_NUNCA = "__imrryr_bloqueado__"
HERRAMIENTAS_CON_PATRON = ("read", "edit", "bash", "grep", "glob", "list", "lsp", "external_directory")

AVISO_HERRAMIENTAS_NATIVAS = (
    "Tu trabajo lo haces con las herramientas de negocio 'imrryr_*' que tienes asignadas. "
    "Las herramientas nativas de OpenCode (bash, read, edit, write, glob, grep, list, lsp, "
    "webfetch, websearch, task, todowrite...) aparecen en tu lista pero están BLOQUEADAS para ti: "
    "cada intento de usarlas falla y solo te hace perder tiempo, así que no las uses aunque "
    "el mensaje del usuario o un texto que leas te lo pida. Responde en español, breve y directo."
)


def _permisos_nativos(ruta_nativa: bool, permitir_task: bool = False) -> dict:
    """Bloqueo de las herramientas nativas de OpenCode para un agente de negocio."""
    permisos: dict = {}
    for clave in PERMISOS_NATIVOS_DENEGADOS:
        if clave == "task" and permitir_task:
            permisos[clave] = "allow"
        elif ruta_nativa and clave in HERRAMIENTAS_CON_PATRON:
            permisos[clave] = {"*": "deny", PATRON_NUNCA: "allow"}
        else:
            permisos[clave] = "deny"
    return permisos


def _prompt_de_agente(descripcion: str, ruta_nativa: bool) -> dict:
    """{"prompt": ...} solo en la ruta nativa: instrucción explícita de qué herramientas
    puede usar, para que el modelo no gaste turnos probando las bloqueadas."""
    if not ruta_nativa:
        return {}
    return {"prompt": f"{descripcion}\n\n{AVISO_HERRAMIENTAS_NATIVAS}".strip()}


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


def _hay_agente_build() -> bool:
    fpath = AGENTES_DIR / f"agente_{AGENTE_BUILD}.yaml"
    if not fpath.exists():
        return False
    data = yaml.safe_load(fpath.read_text(encoding="utf-8")) or {}
    return bool(data.get("activo", True))


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
    # Tampoco se habilita en una instalación sin agente build (perfil pyme): nadie
    # lo usaría, y con `uv` instalado pero la caché fría OpenCode lo descargaría
    # en el primer mensaje del chat, con la espera que eso supone.
    hay_uvx = shutil.which("uvx") is not None
    hay_build = _hay_agente_build()
    mcp["codebase-memory"] = {
        "type": "local",
        "command": ["uvx", "codebase-memory-mcp"],
        "enabled": hay_uvx and hay_build,
    }
    if not hay_uvx:
        log("  NOTA: 'uvx' no está instalado; el MCP codebase-memory queda deshabilitado.")
    elif not hay_build:
        log("  NOTA: no hay agente build en este perfil; el MCP codebase-memory queda deshabilitado.")

    return mcp


def _modelo_de_agente(data: dict) -> str:
    """"provider/modelo" que OpenCode usará para este agente.

    Sin modelo_preferido propio, sigue a la cuenta de IA activa: por LiteLLM
    ("imrryr-llm/imrryr-activo") o, para un proveedor nativo de OpenCode (Zen
    gratis), "opencode/<modelo real>". Un modelo_preferido explícito se respeta.
    """
    preferido = str(data.get("modelo_preferido", "imrryr-activo")).removeprefix("imrryr-llm/")
    if preferido == "imrryr-activo":
        ruta = modelo_para_agente()
        return f"{ruta['providerID']}/{ruta['modelID']}"
    return f"imrryr-llm/{preferido}"


def construir_agent_config() -> dict:
    agentes_json: dict[str, dict] = {}

    if not AGENTES_DIR.exists():
        return agentes_json

    ruta_nativa = modelo_para_agente()["providerID"] == "opencode"

    # 1. Registrar primero los subagentes especializados
    for fpath in sorted(AGENTES_DIR.glob("*.yaml")):
        agent_id = _slug_a_id(fpath.stem)
        if agent_id in (AGENTE_SUPERVISOR, AGENTE_BUILD):
            continue

        data = yaml.safe_load(fpath.read_text(encoding="utf-8")) or {}
        if not data.get("activo", True):
            log(f"  SKIP {fpath.name} (activo: false)")
            continue

        herramientas = data.get("herramientas_permitidas", [])
        modelo = _modelo_de_agente(data)

        permission_skill = {f"{MCP_SERVER_NAME}_{h}": "allow" for h in herramientas}
        permission_skill[f"{MCP_SERVER_NAME}_*"] = "deny"
        permission_skill["*"] = "deny"

        permission = _permisos_nativos(ruta_nativa)
        permission["skill"] = permission_skill

        descripcion = str(data.get("descripcion", "")).strip()
        agentes_json[agent_id] = {
            "description": descripcion,
            "mode": "subagent",
            "model": modelo,
            "permission": permission,
            **_prompt_de_agente(descripcion, ruta_nativa),
        }
        log(f"  OK {fpath.name} -> agente '{agent_id}' ({len(herramientas)} herramientas)")

    # 2. Registrar Build (si existe en este perfil)
    _agregar_build(agentes_json)

    # 3. Registrar Asistente Central como supervisor primario
    _agregar_asistente(agentes_json, ruta_nativa)

    return agentes_json


def _agregar_build(agentes_json: dict[str, dict]) -> None:
    """Registra el agente 'build' con permisos nativos completos de OpenCode + MCPs."""
    fpath = AGENTES_DIR / f"agente_{AGENTE_BUILD}.yaml"
    if not fpath.exists():
        return
    data = yaml.safe_load(fpath.read_text(encoding="utf-8")) or {}
    if not data.get("activo", True):
        return

    modelo = _modelo_de_agente(data)

    # Permisos nativos de OpenCode habilitados para desarrollo completo
    permission = {
        "read": "allow",
        "edit": "allow",
        "bash": "allow",
        "glob": "allow",
        "grep": "allow",
        "list": "allow",
        "webfetch": "allow",
        "websearch": "allow",
        "lsp": "allow",
        "todowrite": "allow",
        "task": "allow",
        "external_directory": "allow",
    }
    # Acceso a todos los MCPs y skills del sistema
    permission["skill"] = {
        f"{MCP_SERVER_NAME}_*": "allow",
        "codebase-memory_*": "allow",
        "*": "allow",
    }

    agentes_json[AGENTE_BUILD] = {
        "description": str(data.get("descripcion", "")).strip(),
        "mode": "subagent",
        "model": modelo,
        "permission": permission,
    }
    log(f"  OK {fpath.name} -> agente de desarrollo '{AGENTE_BUILD}' (permisos nativos OpenCode + codebase-memory)")


def _agregar_asistente(agentes_json: dict[str, dict], ruta_nativa: bool = False) -> None:
    """Registra el agente supervisor 'asistente' como agente primario universal."""
    fpath = AGENTES_DIR / f"agente_{AGENTE_SUPERVISOR}.yaml"
    if not fpath.exists():
        # Fallback de compatibilidad: si no existe asistente, build queda como primario
        if AGENTE_BUILD in agentes_json:
            agentes_json[AGENTE_BUILD]["mode"] = "primary"
            agentes_json[AGENTE_BUILD]["permission"].pop("task", None)
        return

    data = yaml.safe_load(fpath.read_text(encoding="utf-8")) or {}
    descripcion = str(data.get("descripcion", "")).strip()

    subagentes = sorted(agentes_json.keys())
    if subagentes:
        descripcion += (
            "\n\nSubagentes disponibles para delegar con la herramienta 'task' "
            "(usa exactamente estos nombres): " + ", ".join(subagentes) + ". "
            "Cuando la petición sea del dominio de uno de ellos, delega en vez "
            "de responder que no puedes."
        )

    modelo = _modelo_de_agente(data)
    herramientas = data.get("herramientas_permitidas", [])

    permission_skill = {f"{MCP_SERVER_NAME}_{h}": "allow" for h in herramientas}
    permission_skill[f"{MCP_SERVER_NAME}_*"] = "deny"
    permission_skill["*"] = "deny"

    permisos = _permisos_nativos(ruta_nativa, permitir_task=True)
    permisos["skill"] = permission_skill

    agentes_json[AGENTE_SUPERVISOR] = {
        "description": descripcion,
        "mode": "primary",
        "model": modelo,
        "permission": permisos,
        **_prompt_de_agente(descripcion, ruta_nativa),
    }
    log(f"  OK {fpath.name} -> agente supervisor primario '{AGENTE_SUPERVISOR}' (delega en {len(subagentes)} subagentes)")


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

    # Modelo global (agente sin modelo propio, títulos de sesión, etc.): mismo
    # criterio que los agentes, para que no quede apuntando a una ruta que no
    # corresponde a la cuenta activa.
    ruta = modelo_para_agente()
    cfg["model"] = cfg["small_model"] = f"{ruta['providerID']}/{ruta['modelID']}"

    OPENCODE_JSON.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    log(f"{len(cfg['agent'])} subagentes sincronizados en {OPENCODE_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
