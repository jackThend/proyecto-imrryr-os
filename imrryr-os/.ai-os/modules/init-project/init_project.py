#!/usr/bin/env python3
"""init-project — Módulo de Inicialización Interactiva (Tanda VI).

Se activa al iniciar un proyecto nuevo o cuando no existe .ai-os/PROJECT_SPEC.md.
Conduce una entrevista estructurada con el usuario para definir el alcance,
realiza benchmarking y genera conjuntamente el mapa conceptual y el plan técnico.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AI_OS = ROOT / ".ai-os"
PROJECT_SPEC = AI_OS / "PROJECT_SPEC.md"
PLAN = AI_OS / "PLAN.md"
CONFIG = AI_OS / "config.json"


def log(msg: str) -> None:
    print(f"[init-project] {msg}", flush=True)


def proyecto_existe() -> bool:
    return PROJECT_SPEC.exists() and PLAN.exists()


def entrevista_inicial() -> dict:
    """Conduce entrevista estructurada y devuelve respuestas del usuario."""
    preguntas = {
        "nombre": "¿Cómo se llama tu proyecto?",
        "descripcion": "¿Qué hace tu proyecto? (descripción funcional desde la perspectiva del usuario)",
        "flujos": "¿Cuáles son los flujos principales de usuario? (enuméralos)",
        "datos": "¿Qué datos maneja? (tipos, origen, persistencia deseada)",
        "stack_pref": "¿Hay preferencia tecnológica? (lenguaje, framework, DB)",
        "restricciones": "¿Qué restricciones existen? (local-first, nube, compliance, etc.)",
    }
    respuestas = {}
    for clave, pregunta in preguntas.items():
        respuestas[clave] = input(f"\n> {pregunta} ").strip()
    return respuestas


def generar_spec(respuestas: dict) -> str:
    """Genera contenido para PROJECT_SPEC.md a partir de las respuestas."""
    return f"""# AI-OS PROJECT SPEC — {respuestas.get("nombre", "Proyecto")}

## Mapa Conceptual
{respuestas.get("descripcion", "")}

## Objetivos
- Generado mediante inicialización interactiva del AI-OS
- Confirmado por el usuario

## Flujos UX Principales
{respuestas.get("flujos", "")}

## Datos
{respuestas.get("datos", "")}

## Stack Preferido
{respuestas.get("stack_pref", "")}

## Restricciones
{respuestas.get("restricciones", "")}

## Reglas de Gobernanza (Manifesto AI-OS)
- [SÍ] Todo cambio de arquitectura actualiza este archivo antes de codificar
- [SÍ] Toda sesión registra en LOGBOOK.md
- [SÍ] Herramientas deterministas locales sobre inferencia del LLM
- [NO] Nombres de variables o dependencias sin consultar el grafo AST
- [NO] Modificaciones directas al núcleo sin sandbox previo
"""


def generar_plan(respuestas: dict) -> str:
    """Genera contenido para PLAN.md."""
    return f"""# AI-OS PLAN — {respuestas.get("nombre", "Proyecto")}

## Arquitectura Técnica
Pendiente de definición técnica detallada. Usar el interview result como base.

## Stack Tecnológico
- Preferencia declarada: {respuestas.get("stack_pref", "sin preferir")}

## Contratos de Datos
{respuestas.get("datos", "")}

## Estrategia de APIs
Pendiente.

## Fases SDD Obligatorias
1. Constitución — Completada (inicialización)
2. Especificación UX — Especificación generada
3. Plan Técnico — Este archivo
4. Desglose de Tareas — Por iteración

## Tareas Pendientes
- Definir stack técnico detallado
- Definir contratos de datos
- Definir estrategia de tests
"""


def inicializar() -> int:
    if proyecto_existe():
        log("El proyecto ya tiene PROJECT_SPEC.md y PLAN.md. Usar /init-project con --force para regenerar.")
        return 0

    log("Inicialización interactiva del proyecto AI-OS")
    respuestas = entrevista_inicial()

    AI_OS.mkdir(parents=True, exist_ok=True)

    (AI_OS / "PROJECT_SPEC.md").write_text(generar_spec(respuestas), encoding="utf-8")
    (AI_OS / "PLAN.md").write_text(generar_plan(respuestas), encoding="utf-8")

    log("PROJECT_SPEC.md y PLAN.md generados.")
    log("Siguiente paso: iteración manual con el ciclo SDD (PLAN -> FETCH -> EXECUTE -> VALIDATE -> LOG)")
    return 0


def main() -> int:
    return inicializar()


if __name__ == "__main__":
    raise SystemExit(main())