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

Uso:
    python scripts/sync_agentes.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
AGENTES_DIR = ROOT / "agentes"
OPENCODE_JSON = ROOT / "config" / "opencode.json"
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
    return {
        MCP_SERVER_NAME: {
            "type": "local",
            "command": [_python_venv(), str(MCP_SERVER_SCRIPT)],
            "enabled": True,
        }
    }


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
        modelo = str(data.get("modelo_preferido", "gemini-flash")).removeprefix("imryyr-llm/")

        permission_skill = {f"{MCP_SERVER_NAME}_{h}": "allow" for h in herramientas}
        permission_skill[f"{MCP_SERVER_NAME}_*"] = "deny"
        permission_skill["*"] = "deny"

        permission = {clave: "deny" for clave in PERMISOS_NATIVOS_DENEGADOS}
        permission["skill"] = permission_skill

        agentes_json[agent_id] = {
            "description": str(data.get("descripcion", "")).strip(),
            "mode": "subagent",
            "model": f"imryyr-llm/{modelo}",
            "permission": permission,
        }
        log(f"  OK {fpath.name} -> agente '{agent_id}' ({len(herramientas)} herramientas)")

    return agentes_json


def main() -> int:
    if not OPENCODE_JSON.exists():
        log(f"ERROR: no existe {OPENCODE_JSON}")
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
