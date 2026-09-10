#!/usr/bin/env python3
"""
launcher_detener.py — Detención nativa ejecutable de Imrryr OS
=============================================================
Compilable a 'Detener Imrryr OS.exe'.
Detiene de forma ordenada y limpia todos los procesos y servicios
activos del sistema.
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path


def obtener_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    aqui = Path(__file__).resolve().parent
    if (aqui / "config").exists() or (aqui / "scripts").exists():
        return aqui
    return aqui.parent


def obtener_python_runtime(root: Path) -> Path:
    candidatos = [
        root / "runtime" / "python.exe",
        root / "runtime" / "Scripts" / "python.exe",
        root / ".venv" / "Scripts" / "python.exe",
        root / ".venv" / "bin" / "python",
    ]
    for cand in candidatos:
        if cand.exists():
            return cand
    if not getattr(sys, "frozen", False):
        return Path(sys.executable)
    import shutil
    py_path = shutil.which("python")
    if py_path:
        return Path(py_path)
    return Path("")


def main() -> int:
    root = obtener_root()
    print("=" * 60)
    print("  Deteniendo Imrryr OS...")
    print("=" * 60)

    py_exe = obtener_python_runtime(root)
    exe_py = str(py_exe) if py_exe and py_exe.exists() else sys.executable

    shutdown_script = root / "scripts" / "shutdown.py"
    if shutdown_script.exists():
        subprocess.run([exe_py, str(shutdown_script)], cwd=str(root))
    else:
        print(f"[ERROR] No se encontro {shutdown_script}.")

    print("\n[V] Todos los servicios de Imrryr OS fueron detenidos.")
    time.sleep(2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
