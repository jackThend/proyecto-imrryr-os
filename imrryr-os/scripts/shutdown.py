#!/usr/bin/env python3
"""
shutdown.py — Detención limpia del backend (Fase 1.3.5)
========================================================
Lee los PIDs guardados por startup.py en .run/ y detiene LiteLLM +
OpenCode de forma ordenada, liberando los puertos :4000 y :4040.

En Windows usa taskkill /T (árbol de procesos) porque LiteLLM/OpenCode
suelen spawnear hijos (uvicorn workers, bun, etc.).

Uso:
    python scripts/shutdown.py
"""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUN_DIR = ROOT / ".run"

PID_FILES = {
    "Dashboard": RUN_DIR / "dashboard.pid",
    "LiteLLM": RUN_DIR / "litellm.pid",
    "OpenCode": RUN_DIR / "opencode.pid",
    "Gateway": RUN_DIR / "gateway.pid",
    "WhatsApp local": RUN_DIR / "whatsapp_local.pid",
}


def log(msg: str) -> None:
    print(f"[shutdown] {msg}", flush=True)


def kill_pid(name: str, pid_file: Path) -> None:
    if not pid_file.exists():
        log(f"{name}: sin PID registrado ({pid_file.name}).")
        return
    try:
        pid = int(pid_file.read_text(encoding="utf-8").strip())
    except ValueError:
        log(f"{name}: PID inválido en {pid_file}.")
        pid_file.unlink(missing_ok=True)
        return

    if not _pid_alive(pid):
        log(f"{name}: proceso {pid} ya no está vivo.")
        pid_file.unlink(missing_ok=True)
        return

    _kill_tree(pid)
    # esperar a que libere el puerto
    for _ in range(10):
        if not _pid_alive(pid):
            break
        time.sleep(0.5)

    if _pid_alive(pid):
        log(f"{name}: PID {pid} no terminó; forzando (-KILL).")
        _kill_tree(pid, force=True)
    log(f"{name} detenido (PID {pid}).")
    pid_file.unlink(missing_ok=True)


# --------------------------------------------------------------------------
def _pid_alive(pid: int) -> bool:
    if os.name == "nt":
        r = subprocess.run(
            ["taskkill", "/FI", f"PID eq {pid}", "/NH"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        return "No tasks" not in r.stdout
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def _kill_tree(pid: int, force: bool = False) -> None:
    if os.name == "nt":
        # /T mata el árbol de procesos hijos. /F si force.
        flags = ["/F", "/T"] if force else ["/T"]
        subprocess.run(["taskkill", *flags, "/PID", str(pid)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    else:
        sig = signal.SIGKILL if force else signal.SIGTERM
        try:
            os.killpg(os.getpgid(pid), sig)
        except ProcessLookupError:
            pass


def main() -> int:
    if not RUN_DIR.exists():
        log("No hay directorio .run/. Nada que detener.")
        return 0
    for name, pid_file in PID_FILES.items():
        kill_pid(name, pid_file)
    log("Backend detenido.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
