#!/usr/bin/env python3
"""ast_navigation — Skill forjada: protocolo de navegación estructural (FETCH).

Fase FETCH del ciclo de 5 fases. Registra qué entidades del grafo AST
fueron consultadas para cada tarea, cumpliendo la regla del manifiesto:
"Nunca inyectar repositorios enteros; leer solo líneas de entidades
afectadas identificadas en el subgrafo".

Este módulo no reemplaza al MCP codebase-memory: es el registro
determinista de qué se consultó y el índice ligero de patrones de
consulta disponibles (Progressive Tool Disclosure).
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

AI_OS = Path(__file__).resolve().parent.parent
REGISTRO = AI_OS / "fetch_log.json"

# Índice ligero de patrones de consulta del MCP codebase-memory
# (Progressive Tool Disclosure: solo nombres + una línea; la doc
# completa se inyecta al invocar la herramienta real).
PATRONES = {
    "search_graph": "Buscar funciones/clases/rutas por texto, regex o semántica.",
    "trace_path": "Rastrear llamadores/callees y flujo de datos de un símbolo.",
    "get_code_snippet": "Leer el código fuente exacto de un qualified_name.",
    "query_graph": "Cypher multi-hop sobre el grafo (agregaciones, hotspots).",
    "get_architecture": "Overview estructural, clusters, capas y boundaries.",
    "check_index_coverage": "Verificar cobertura del índice por ruta o scope.",
    "detect_changes": "Blast radius de un diff (impacto transitivo).",
}


def log(msg: str) -> None:
    print(f"[ast-navigation] {msg}", flush=True)


def cargar_registro() -> list[dict]:
    if REGISTRO.exists():
        return json.loads(REGISTRO.read_text(encoding="utf-8"))
    return []


def registrar_consulta(tarea: str, patron: str, entidades: list[str]) -> dict:
    """Registra una consulta FETCH: patrón usado y entidades afectadas.

    entidades: qualified_names o rutas parciales identificadas en el
    subgrafo. La lectura posterior debe limitarse a esas líneas.
    """
    registro = cargar_registro()
    entrada = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "tarea": tarea,
        "patron": patron,
        "entidades": entidades,
    }
    registro.append(entrada)
    REGISTRO.write_text(json.dumps(registro, indent=2, ensure_ascii=False), encoding="utf-8")
    log(f"FETCH registrado: {len(entidades)} entidades para '{tarea}'")
    return entrada


def entidades_de_tarea(tarea: str) -> list[dict]:
    """Devuelve las consultas FETCH asociadas a una tarea."""
    return [e for e in cargar_registro() if e["tarea"] == tarea]


def main() -> int:
    ap = argparse.ArgumentParser(description="Protocolo FETCH del ciclo 5-fases")
    ap.add_argument("--registrar", action="store_true", help="Registrar una consulta")
    ap.add_argument("--tarea", type=str, default="")
    ap.add_argument("--patron", type=str, default="search_graph")
    ap.add_argument("--entidades", type=str, nargs="*", default=[])
    ap.add_argument("--listar", type=str, metavar="TAREA", help="Consultas de una tarea")
    ap.add_argument("--patrones", action="store_true", help="Índice ligero de patrones")
    args = ap.parse_args()

    if args.patrones:
        for nombre, resumen in PATRONES.items():
            print(f"  {nombre}: {resumen}")
        return 0
    if args.registrar:
        if not args.tarea:
            log("ERROR: --registrar requiere --tarea")
            return 1
        if not args.entidades:
            log("ERROR: --entidades requiere al menos un qualified_name")
            return 1
        if args.patron not in PATRONES:
            log(f"ERROR: patrón desconocido '{args.patron}'. Válidos: {', '.join(PATRONES)}")
            return 1
        print(json.dumps(registrar_consulta(args.tarea, args.patron, args.entidades), indent=2))
        return 0
    if args.listar:
        print(json.dumps(entidades_de_tarea(args.listar), indent=2, ensure_ascii=False))
        return 0

    ap.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())