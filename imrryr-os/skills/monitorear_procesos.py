#!/usr/bin/env python3
"""
monitorear_procesos.py — Skill: Observabilidad de procesos (Guardia de Seguridad)
==================================================================================
Lista los procesos hijos de OpenCode/LiteLLM (los PIDs quedan registrados en
.run/*.pid por scripts/startup.py) y marca cuáles llevan más tiempo activo
que el timeout_max declarado en agentes/guardia_seguridad.yaml (300s).

Uso:
    python skills/monitorear_procesos.py
    python skills/monitorear_procesos.py --timeout 300
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PID_DIR = ROOT / ".run"
PROCESOS_RAIZ = ("opencode", "litellm", "gateway", "whatsapp_local")


def log(msg: str) -> None:
    print(f"[monitorear_procesos] {msg}", flush=True)


def _leer_pid(nombre: str) -> int | None:
    pid_file = PID_DIR / f"{nombre}.pid"
    if not pid_file.exists():
        return None
    try:
        return int(pid_file.read_text().strip())
    except ValueError:
        return None


def listar_procesos(timeout_segundos: int = 300) -> list[dict]:
    import psutil

    resultado = []
    ahora = time.time()

    for nombre in PROCESOS_RAIZ:
        pid_raiz = _leer_pid(nombre)
        if pid_raiz is None or not psutil.pid_exists(pid_raiz):
            continue
        try:
            proceso_raiz = psutil.Process(pid_raiz)
        except psutil.NoSuchProcess:
            continue

        candidatos = [proceso_raiz, *proceso_raiz.children(recursive=True)]
        for proc in candidatos:
            try:
                segundos_activo = ahora - proc.create_time()
                resultado.append({
                    "pid": proc.pid,
                    "nombre_proceso": proc.name(),
                    "cmdline": " ".join(proc.cmdline())[:200],
                    "servicio": nombre,
                    "segundos_activo": round(segundos_activo, 1),
                    "atascado": segundos_activo > timeout_segundos,
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

    return resultado


def main() -> int:
    ap = argparse.ArgumentParser(description="Lista procesos monitoreados y marca los atascados")
    ap.add_argument("--timeout", type=int, default=300, help="Segundos a partir de los cuales un proceso se considera atascado")
    args = ap.parse_args()

    procesos = listar_procesos(args.timeout)
    atascados = [p for p in procesos if p["atascado"]]
    log(f"Procesos monitoreados: {len(procesos)} | Atascados: {len(atascados)}")
    print(json.dumps(procesos, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
