#!/usr/bin/env python3
"""
skills_server.py — Servidor MCP local que expone las skills de Imrryr OS
==========================================================================
Puente entre las skills atómicas de Python (imrryr-os/skills/*.py) y el
motor de OpenCode: cada skill se registra aquí como una tool MCP real,
invocable por los agentes según los permisos declarados en
config/opencode.json (agent.<nombre>.permission.skill).

Auto-discovery (sin registro manual): al arrancar, este servidor escanea
skills/*.mcp.json, importa el módulo indicado en "script" y registra la
función pública que se llama igual que "name" como una tool MCP real.
MCPServer construye el schema de argumentos inspeccionando la firma real de
la función de Python — el .mcp.json solo aporta nombre/descripción/qué
módulo importar, no hace falta traducirlo a tipos.

Agregar una skill nueva es: crear skills/x.py (con una función pública
llamada igual que la skill) + skills/x.mcp.json — sin tocar este archivo.

No se ejecuta a mano: lo arranca OpenCode como subproceso stdio.

Migración mcp 2.x (RFC 2026-08-31): FastMCP fue renombrado a MCPServer;
add_tool(fn, name=, description=) y run(transport="stdio") conservan su
firma, y el servidor v2 atiende clientes del protocolo 2025 (como el
cliente MCP de OpenCode) sin configuración adicional.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = ROOT / "skills"
sys.path.insert(0, str(SKILLS_DIR))

from mcp.server import MCPServer  # noqa: E402

mcp = MCPServer("imrryr")

_modulos_cargados: dict[str, ModuleType] = {}


def _log(msg: str) -> None:
    print(f"[skills_server] {msg}", file=sys.stderr, flush=True)


def _cargar_modulo(ruta_script: str) -> ModuleType:
    """Importa skills/x.py por ruta de archivo (no por nombre de paquete), cacheado
    para que dos manifiestos que comparten script (ej. guardar_oportunidad.py con
    dos tools) no importen el módulo dos veces."""
    if ruta_script in _modulos_cargados:
        return _modulos_cargados[ruta_script]

    ruta_absoluta = ROOT / ruta_script
    spec = importlib.util.spec_from_file_location(ruta_absoluta.stem, ruta_absoluta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)  # type: ignore[union-attr]
    _modulos_cargados[ruta_script] = modulo
    return modulo


def _registrar_skills() -> int:
    registradas = 0
    for manifest_path in sorted(SKILLS_DIR.glob("*.mcp.json")):
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            nombre = manifest["name"]
            script = manifest["script"]
            descripcion = manifest.get("description", "")

            modulo = _cargar_modulo(script)
            fn = getattr(modulo, nombre)
            mcp.add_tool(fn, name=nombre, description=descripcion)
            registradas += 1
        except Exception as e:
            _log(f"ADVERTENCIA: no se pudo registrar {manifest_path.name}: {e}")

    _log(f"{registradas} skill(s) registradas desde {SKILLS_DIR}")
    return registradas


_registrar_skills()

if __name__ == "__main__":
    mcp.run()
