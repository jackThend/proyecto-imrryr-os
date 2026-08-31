#!/usr/bin/env python3
"""deterministic_validate — Skill forjada: fase VALIDATE del ciclo 5-fases.

Cómputo determinista puro: ruff (lint de errores reales) + pytest.
Nunca usa inferencia del LLM para diagnosticar. Si hay errores,
inyecta ÚNICAMENTE archivo, línea y mensaje exacto (manifiesto §2.3),
sin volcar salidas completas al contexto.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
VENV_PY = ROOT / ".venv" / "Scripts" / "python.exe"
RUFF_TOML = ROOT / "ruff.toml"
TESTS_DIR = ROOT / "tests"


def log(msg: str) -> None:
    print(f"[validate] {msg}", flush=True)


def _python() -> str:
    return str(VENV_PY) if VENV_PY.exists() else sys.executable


def lint(archivos: list[str]) -> dict:
    """Ruff con las reglas reales del proyecto. Solo archivo:línea: mensaje."""
    cmd = [_python(), "-m", "ruff", "check", "--config", str(RUFF_TOML), "--output-format", "concise"]
    cmd += archivos or ["."]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120, cwd=str(ROOT))
        errores = [
            line
            for line in proc.stdout.splitlines()
            if line.strip() and not line.startswith(("Found", "warning"))
        ]
        return {"ok": proc.returncode == 0, "errores": errores[:20], "total": proc.returncode != 0 and len(errores) or 0}
    except subprocess.TimeoutExpired:
        return {"ok": False, "errores": ["ruff: timeout 120s"], "total": 1}


def tests(rapidos: bool = True) -> dict:
    """Pytest hermético. rápido=True solo tests/, False todo el repo."""
    objetivo = str(TESTS_DIR) if rapidos else "."
    cmd = [_python(), "-m", "pytest", objetivo, "-q", "--tb=no"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600, cwd=str(ROOT))
        resumen = ""
        for line in proc.stdout.splitlines():
            if line.startswith(("passed", "failed", "error")) or " passed" in line or "==" in line:
                resumen = line.strip()
        return {"ok": proc.returncode == 0, "resumen": resumen or proc.stdout[-300:]}
    except subprocess.TimeoutExpired:
        return {"ok": False, "resumen": "pytest: timeout 600s"}


def validar(archivos: list[str]) -> dict:
    """VALIDATE completo: lint primero (barato), tests después (caros)."""
    log("VALIDATE: lint (ruff)...")
    r = lint(archivos)
    if not r["ok"]:
        log(f"Lint con {r['total']} errores — corregir antes de correr tests")
        return {"fase": "lint", **r}
    log("Lint OK. VALIDATE: tests (pytest hermético)...")
    t = tests()
    log(f"Tests: {'OK' if t['ok'] else 'FALLO'} — {t['resumen']}")
    return {
        "fase": "completa",
        "lint": {"ok": True, "errores": []},
        "tests": t,
        "ok": t["ok"],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="VALIDATE: ruff + pytest, diagnóstico exacto")
    ap.add_argument("--archivos", type=str, nargs="*", default=[], help="Archivos modificados (lint enfocado)")
    ap.add_argument("--solo-lint", action="store_true", help="Solo ruff, sin pytest")
    ap.add_argument("--json", action="store_true", help="Salida JSON")
    args = ap.parse_args()

    resultado = lint(args.archivos) if args.solo_lint else validar(args.archivos)
    if args.json:
        print(json.dumps(resultado, indent=2, ensure_ascii=False))
    return 0 if resultado.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())