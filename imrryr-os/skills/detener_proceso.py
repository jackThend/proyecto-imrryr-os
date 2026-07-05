#!/usr/bin/env python3
"""
detener_proceso.py — Skill: Detiene un proceso atascado (Guardia de Seguridad)
================================================================================
Usada tras monitorear_procesos.py cuando un proceso supera el timeout_max
(300s por defecto). Intenta una terminación limpia (SIGTERM) antes de forzar
el cierre (SIGKILL).

Uso:
    python skills/detener_proceso.py --pid 12345
    python skills/detener_proceso.py --pid 12345 --forzar
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def log(msg: str) -> None:
    print(f"[detener_proceso] {msg}", flush=True)


def detener_proceso(pid: int, forzar: bool = False) -> dict:
    import psutil

    try:
        proceso = psutil.Process(pid)
        nombre = proceso.name()
    except psutil.NoSuchProcess:
        return {"pid": pid, "detenido": False, "motivo": "el proceso ya no existe"}

    try:
        if forzar:
            proceso.kill()
        else:
            proceso.terminate()
        try:
            proceso.wait(timeout=5)
        except psutil.TimeoutExpired:
            proceso.kill()
        return {"pid": pid, "detenido": True, "nombre_proceso": nombre}
    except psutil.AccessDenied:
        return {"pid": pid, "detenido": False, "motivo": "acceso denegado por el sistema operativo"}


def main() -> int:
    ap = argparse.ArgumentParser(description="Detiene un proceso por PID")
    ap.add_argument("--pid", type=int, required=True)
    ap.add_argument("--forzar", action="store_true", help="Usar SIGKILL directamente en vez de terminación limpia")
    args = ap.parse_args()

    resultado = detener_proceso(args.pid, args.forzar)
    log(json.dumps(resultado, ensure_ascii=True))
    return 0 if resultado["detenido"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
