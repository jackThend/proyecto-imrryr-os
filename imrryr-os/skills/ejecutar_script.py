#!/usr/bin/env python3
"""
ejecutar_script.py — Skill: Ejecuta un script Python (sandboxed) para el Agente Build
========================================================================================
Por seguridad, NO es una terminal genérica: solo permite ejecutar archivos
.py que vivan dentro de scripts/ o skills/ (whitelist de carpetas), con
timeout, usando el intérprete del venv del propio proyecto. No acepta
comandos de shell arbitrarios.

Uso:
    python skills/ejecutar_script.py --script scripts/smoke_test.py
    python skills/ejecutar_script.py --script skills/inyectar_gasto.py --args --listar
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CARPETAS_PERMITIDAS = ("scripts", "skills")


def log(msg: str) -> None:
    print(f"[ejecutar_script] {msg}", flush=True)


def _python_venv() -> Path:
    candidato = ROOT / ".venv" / "Scripts" / "python.exe"
    if candidato.exists():
        return candidato
    candidato = ROOT / ".venv" / "bin" / "python"
    if candidato.exists():
        return candidato
    return Path(sys.executable)


def ejecutar_script(ruta_relativa: str, argumentos: list[str] | None = None, timeout_segundos: int = 60) -> dict:
    argumentos = argumentos or []
    candidata = (ROOT / ruta_relativa).resolve()

    try:
        relativa = candidata.relative_to(ROOT)
    except ValueError:
        return {"ok": False, "error": "Ruta fuera de imrryr-os/"}

    if not relativa.parts or relativa.parts[0] not in CARPETAS_PERMITIDAS:
        return {"ok": False, "error": f"Solo se permiten scripts dentro de {CARPETAS_PERMITIDAS}"}
    if candidata.suffix != ".py":
        return {"ok": False, "error": "Solo se permite ejecutar archivos .py"}
    if not candidata.exists():
        return {"ok": False, "error": "El script no existe"}

    try:
        resultado = subprocess.run(
            [str(_python_venv()), str(candidata), *argumentos],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=timeout_segundos,
        )
        return {
            "ok": resultado.returncode == 0,
            "codigo_salida": resultado.returncode,
            "stdout": resultado.stdout[-4000:],
            "stderr": resultado.stderr[-4000:],
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"Timeout tras {timeout_segundos}s"}


def main() -> int:
    ap = argparse.ArgumentParser(description="Ejecuta un script Python dentro del sandbox scripts/ o skills/")
    ap.add_argument("--script", type=str, required=True)
    ap.add_argument("--args", nargs=argparse.REMAINDER, default=[])
    ap.add_argument("--timeout", type=int, default=60)
    args = ap.parse_args()

    resultado = ejecutar_script(args.script, args.args, args.timeout)
    print(json.dumps(resultado, ensure_ascii=True, indent=2))
    return 0 if resultado["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
