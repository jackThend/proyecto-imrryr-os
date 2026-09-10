#!/usr/bin/env python3
"""
launcher_iniciar.py — Lanzador nativo ejecutable de Imrryr OS
=============================================================
Compilable a 'Iniciar Imrryr OS.exe'.
Detecta la raíz del proyecto, inicializa el entorno si falta y arranca
los servicios mediante scripts/startup.py.
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
    """Busca el intérprete Python portátil autónomo en runtime/ o en .venv/."""
    candidatos = [
        root / "runtime" / "python.exe",
        root / "runtime" / "Scripts" / "python.exe",
        root / ".venv" / "Scripts" / "python.exe",
        root / ".venv" / "bin" / "python",
    ]
    for cand in candidatos:
        if cand.exists():
            return cand

    # Si estamos en modo desarrollo sin compilar (no frozen)
    if not getattr(sys, "frozen", False):
        return Path(sys.executable)

    # Buscar en PATH del sistema como último recurso
    import shutil
    py_path = shutil.which("python")
    if py_path:
        return Path(py_path)

    return Path("")


def main() -> int:
    root = obtener_root()
    print("=" * 60)
    print("  Iniciando Imrryr OS (Lanzador Autónomo)")
    print(f"  Directorio base: {root}")
    print("=" * 60)

    # 1. Detectar entorno o runtime de Python
    python_exe = obtener_python_runtime(root)

    if not python_exe or not python_exe.exists():
        print("\n[!] No se detectó un entorno de Python ('runtime/' o '.venv/').")
        install_script = root / "install.py"
        if not install_script.exists():
            install_script = root / "scripts" / "install.py"

        if install_script.exists() and not getattr(sys, "frozen", False):
            print("[*] Iniciando instalación automática del sistema...")
            res = subprocess.run([sys.executable, str(install_script)], cwd=str(root))
            if res.returncode != 0:
                print("\n[ERROR] Falló la instalación inicial. Revisa los mensajes anteriores.")
                input("\nPresiona Enter para salir...")
                return 1
            python_exe = obtener_python_runtime(root)
        else:
            print("\n[ERROR] No se encontró el runtime embebido de Imrryr OS.")
            print("Por favor, reinstala la aplicación usando el instalador oficial 'Imrryr_OS_Setup.exe'.")
            input("\nPresiona Enter para salir...")
            return 1

    # 2. Ejecutar startup.py
    startup_script = root / "scripts" / "startup.py"
    if not startup_script.exists():
        print(f"[ERROR] No se encontró el archivo de arranque en: {startup_script}")
        input("\nPresiona Enter para salir...")
        return 1

    print(f"\n[*] Usando motor Python: {python_exe}")
    print("[*] Levantando servicios de Imrryr OS...")
    cmd = [str(python_exe), str(startup_script)] + sys.argv[1:]
    try:
        proc = subprocess.run(cmd, cwd=str(root))
        return proc.returncode
    except KeyboardInterrupt:
        print("\n[*] Interrupcion recibida. Deteniendo servicios...")
        shutdown_script = root / "scripts" / "shutdown.py"
        if shutdown_script.exists():
            subprocess.run([str(python_exe), str(shutdown_script)], cwd=str(root))
        return 0


if __name__ == "__main__":
    sys.exit(main())
