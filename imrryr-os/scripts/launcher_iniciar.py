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


def mostrar_error(titulo: str, mensaje: str) -> None:
    """Muestra un diálogo de error nativo en Windows."""
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, mensaje, titulo, 0x10)
    except Exception:
        pass


def obtener_python_runtime(root: Path) -> Path:
    """Busca el intérprete Python GUI (pythonw.exe) o portátil en runtime/ o en .venv/."""
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

    # Si estamos en modo desarrollo sin compilar (no frozen)
    if not getattr(sys, "frozen", False):
        return Path(sys.executable)

    # Buscar en PATH del sistema como último recurso
    import shutil
    for name in ("pythonw", "python"):
        py_path = shutil.which(name)
        if py_path:
            return Path(py_path)

    return Path("")


def main() -> int:
    root = obtener_root()

    # 1. Detectar entorno o runtime de Python
    python_exe = obtener_python_runtime(root)

    if not python_exe or not python_exe.exists():
        install_script = root / "install.py"
        if not install_script.exists():
            install_script = root / "scripts" / "install.py"

        if install_script.exists() and not getattr(sys, "frozen", False):
            flags = 0x08000000 if sys.platform == "win32" else 0
            res = subprocess.run([sys.executable, str(install_script)], cwd=str(root), creationflags=flags)
            if res.returncode != 0:
                mostrar_error("Imrryr OS", "Falló la instalación inicial de dependencias.")
                return 1
            python_exe = obtener_python_runtime(root)
        else:
            mostrar_error(
                "Imrryr OS",
                "No se encontró el runtime embebido de Imrryr OS.\n"
                "Por favor reinstala la aplicación usando 'Imrryr_OS_Setup.exe'.",
            )
            return 1

    # 2. Ejecutar startup.py
    startup_script = root / "scripts" / "startup.py"
    if not startup_script.exists():
        mostrar_error("Imrryr OS", f"No se encontró el script de arranque en:\n{startup_script}")
        return 1

    cmd = [str(python_exe), str(startup_script)] + sys.argv[1:]
    flags = 0x08000000 if sys.platform == "win32" else 0

    try:
        log_dir = root / "vault" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "launcher.log"

        with log_file.open("a", encoding="utf-8") as out:
            proc = subprocess.run(
                cmd,
                cwd=str(root),
                creationflags=flags,
                stdout=out,
                stderr=out,
            )
        if proc.returncode != 0:
            ultimas = ""
            if log_file.exists():
                try:
                    lineas = log_file.read_text(encoding="utf-8", errors="replace").strip().splitlines()
                    ultimas = "\n".join(lineas[-6:])
                except Exception:
                    pass
            mostrar_error(
                "Imrryr OS - Error de inicio",
                f"No se pudieron iniciar los servicios de Imrryr OS.\n\nDetalles:\n{ultimas or 'Código de error: ' + str(proc.returncode)}",
            )
        return proc.returncode
    except KeyboardInterrupt:
        shutdown_script = root / "scripts" / "shutdown.py"
        if shutdown_script.exists():
            subprocess.run([str(python_exe), str(shutdown_script)], cwd=str(root), creationflags=flags)
        return 0


if __name__ == "__main__":
    sys.exit(main())
