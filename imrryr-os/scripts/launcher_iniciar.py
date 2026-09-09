#!/usr/bin/env python3
"""
launcher_iniciar.py — Lanzador nativo ejecutable de Imrryr OS
=============================================================
Compilable a 'Iniciar Imrryr OS.exe'.
Detecta la raíz del proyecto, inicializa el entorno si falta y arranca
los servicios mediante scripts/startup.py.
"""
from __future__ import annotations

import os
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


def main() -> int:
    root = obtener_root()
    print("=" * 60)
    print("  Iniciando Imrryr OS (Lanzador Nativo)")
    print(f"  Directorio base: {root}")
    print("=" * 60)

    # 1. Detectar entorno virtual Python
    python_venv = root / ".venv" / "Scripts" / "python.exe" if os.name == "nt" else root / ".venv" / "bin" / "python"

    if not python_venv.exists():
        print("\n[!] No se detecto el entorno virtual (.venv).")
        install_script = root / "install.py"
        if not install_script.exists():
            install_script = root / "scripts" / "install.py"

        if install_script.exists():
            print("[*] Iniciando instalacion automatica del sistema...")
            res = subprocess.run([sys.executable, str(install_script)], cwd=str(root))
            if res.returncode != 0:
                print("\n[ERROR] Fallo la instalacion inicial. Revisa los mensajes anteriores.")
                input("\nPresiona Enter para salir...")
                return 1
        else:
            print(f"[ERROR] No se encontro install.py en {root}.")
            input("\nPresiona Enter para salir...")
            return 1

    # 2. Ejecutar startup.py
    startup_script = root / "scripts" / "startup.py"
    if not startup_script.exists():
        print(f"[ERROR] No se encontro {startup_script}.")
        input("\nPresiona Enter para salir...")
        return 1

    print("\n[*] Levantando servicios de Imrryr OS...")
    cmd = [str(python_venv), str(startup_script)] + sys.argv[1:]
    try:
        proc = subprocess.run(cmd, cwd=str(root))
        return proc.returncode
    except KeyboardInterrupt:
        print("\n[*] Interrupcion recibida. Deteniendo servicios...")
        shutdown_script = root / "scripts" / "shutdown.py"
        if shutdown_script.exists():
            subprocess.run([str(python_venv), str(shutdown_script)], cwd=str(root))
        return 0


if __name__ == "__main__":
    sys.exit(main())
