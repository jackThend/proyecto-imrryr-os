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
        root / "runtime" / "pythonw.exe",
        root / "runtime" / "python.exe",
        root / "runtime" / "Scripts" / "pythonw.exe",
        root / "runtime" / "Scripts" / "python.exe",
        root / ".venv" / "Scripts" / "pythonw.exe",
        root / ".venv" / "Scripts" / "python.exe",
        root / ".venv" / "bin" / "python",
    ]
    for cand in candidatos:
        if cand.exists():
            return cand
    if not getattr(sys, "frozen", False):
        return Path(sys.executable)
    import shutil
    for name in ("pythonw", "python"):
        py_path = shutil.which(name)
        if py_path:
            return Path(py_path)
    return Path("")


def main() -> int:
    root = obtener_root()
    py_exe = obtener_python_runtime(root)
    exe_py = str(py_exe) if py_exe and py_exe.exists() else sys.executable

    flags = 0x08000000 if sys.platform == "win32" else 0

    shutdown_script = root / "scripts" / "shutdown.py"
    if shutdown_script.exists():
        log_dir = root / "vault" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "launcher_detener.log"
        with log_file.open("a", encoding="utf-8") as out:
            subprocess.run(
                [exe_py, str(shutdown_script)],
                cwd=str(root),
                creationflags=flags,
                stdout=out,
                stderr=out,
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
