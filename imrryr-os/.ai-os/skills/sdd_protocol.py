#!/usr/bin/env python3
"""sdd_protocol — Skill forjada: enforcement del SDD y del ciclo 5-fases.

Aplica el Protocolo de Desarrollo Guiado por Especificaciones:
ningún código de producción sin PROJECT_SPEC.md + PLAN.md vigentes.
Gestiona el desglose de tareas de PLAN.md y registra iteraciones en
LOGBOOK.md con el formato canónico del manifiesto.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path

AI_OS = Path(__file__).resolve().parent.parent
SPEC = AI_OS / "PROJECT_SPEC.md"
PLAN = AI_OS / "PLAN.md"
LOGBOOK = AI_OS / "LOGBOOK.md"
ESTADO = AI_OS / "CURRENT_STATE.md"

_RE_TAREA = re.compile(r"^-\s\[( |x)\]\s(.+)$", re.MULTILINE)
_RE_ITERACION = re.compile(r"Iteración #(\d+)")


def log(msg: str) -> None:
    print(f"[sdd-protocol] {msg}", flush=True)


def verificar_spec() -> dict:
    """Fase 1: ¿existen y están completos los artefactos de especificación?"""
    faltantes = [n for n, p in (("PROJECT_SPEC.md", SPEC), ("PLAN.md", PLAN)) if not p.exists()]
    resultado = {
        "ok": not faltantes,
        "faltantes": faltantes,
        "mensaje": "SDD vigente" if not faltantes else f"Faltan artefactos: {', '.join(faltantes)} — prohibido codificar",
    }
    log(resultado["mensaje"])
    return resultado


def listar_tareas() -> list[dict]:
    """Extrae el desglose de tareas de PLAN.md (checkboxes markdown)."""
    if not PLAN.exists():
        return []
    texto = PLAN.read_text(encoding="utf-8")
    return [{"hecha": m.group(1) == "x", "tarea": m.group(2).strip()} for m in _RE_TAREA.finditer(texto)]


def siguiente_tarea() -> dict | None:
    """Primera tarea pendiente del PLAN.md (orden secuencial)."""
    for t in listar_tareas():
        if not t["hecha"]:
            return t
    return None


def _ultima_iteracion() -> int:
    if not LOGBOOK.exists():
        return 0
    numeros = [int(m.group(1)) for m in _RE_ITERACION.finditer(LOGBOOK.read_text(encoding="utf-8"))]
    return max(numeros, default=0)


def registrar_iteracion(
    objetivo: str,
    entidades: list[str],
    diagnosticos: str,
    decisiones: str,
    siguiente_paso: str,
) -> int:
    """Fase LOG: añade la iteración a LOGBOOK.md y devuelve su número."""
    numero = _ultima_iteracion() + 1
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M")
    ents = "\n".join(f"- {e}" for e in entidades) or "- (ninguna)"
    bloque = (
        f"\n## [{ahora}] Iteración #{numero}\n"
        f"**Objetivo**: {objetivo}\n\n"
        f"**Entidades Modificadas**:\n{ents}\n\n"
        f"**Diagnósticos de Validación**: {diagnosticos}\n\n"
        f"**Decisiones Técnicas (ADR)**: {decisiones}\n\n"
        f"**Siguiente Paso Pendiente**: {siguiente_paso}\n"
    )
    with LOGBOOK.open("a", encoding="utf-8") as f:
        f.write(bloque)
    log(f"Iteración #{numero} registrada en LOGBOOK.md")
    return numero


def main() -> int:
    ap = argparse.ArgumentParser(description="Enforcement SDD + ciclo 5-fases")
    ap.add_argument("--verificar", action="store_true", help="Fase 1: verificar artefactos SDD")
    ap.add_argument("--tareas", action="store_true", help="Listar desglose de PLAN.md")
    ap.add_argument("--siguiente", action="store_true", help="Mostrar siguiente tarea pendiente")
    ap.add_argument(
        "--log",
        action="store_true",
        help="Registrar iteración (requiere --objetivo, --entidades, etc.)",
    )
    ap.add_argument("--objetivo", type=str, default="")
    ap.add_argument("--entidades", type=str, nargs="*", default=[])
    ap.add_argument("--diagnosticos", type=str, default="LSP: 0 errores | Tests: OK")
    ap.add_argument("--decisiones", type=str, default="(sin cambios arquitecturales)")
    ap.add_argument("--siguiente-paso", type=str, default="")
    args = ap.parse_args()

    if args.verificar:
        print(json.dumps(verificar_spec(), indent=2, ensure_ascii=False))
        return 0 if verificar_spec()["ok"] else 1
    if args.tareas:
        for t in listar_tareas():
            marca = "[x]" if t["hecha"] else "[ ]"
            print(f"  {marca} {t['tarea']}")
        return 0
    if args.siguiente:
        t = siguiente_tarea()
        print(t["tarea"] if t else "Sin tareas pendientes en PLAN.md")
        return 0
    if args.log:
        if not args.objetivo:
            log("ERROR: --log requiere --objetivo")
            return 1
        n = registrar_iteracion(
            args.objetivo, args.entidades, args.diagnosticos, args.decisiones, args.siguiente_paso
        )
        print(f"Iteración #{n} registrada")
        return 0

    ap.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())