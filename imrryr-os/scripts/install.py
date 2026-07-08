#!/usr/bin/env python3
"""
install.py — Instalador autónomo de Imrryr OS
===============================================
Ejecutar después de descomprimir un paquete generado por package.py.

Uso:
    python install.py
    python install.py --quick   # solo crear .env y BD, sin venv

Perfiles: tech (completo), pyme (comercial, sin código)
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

def _detectar_root() -> Path:
    """En el paquete distribuible (dist/), install.py vive en la raíz del
    proyecto (lo copia scripts/package.py). En el repo fuente, en cambio,
    vive dentro de scripts/ — un nivel más abajo. Detectamos cuál es el
    caso mirando si 'config/' y 'requirements.txt' están junto a este
    archivo o un nivel arriba."""
    aqui = Path(__file__).resolve().parent
    if (aqui / "requirements.txt").exists() or (aqui / "config").exists():
        return aqui
    return aqui.parent


ROOT = _detectar_root()


def log(msg: str) -> None:
    print(f"[install] {msg}", flush=True)


def detect_profile() -> str:
    manifest = ROOT / "manifest.json"
    if manifest.exists():
        import json
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
            return data.get("perfil", "desconocido")
        except Exception:
            pass
    # Fallback: detectar por presencia de agente_build.yaml
    if (ROOT / "agentes" / "agente_build.yaml").exists():
        return "Tech (completo)"
    return "Pyme (comercial)"


def check_python() -> bool:
    if sys.version_info < (3, 10):
        log(f"ERROR: Python {sys.version_info.major}.{sys.version_info.minor} es muy antiguo.")
        log("Se necesita Python 3.10+. Descarga: https://python.org")
        return False
    log(f"Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro} OK")
    return True


def create_env() -> bool:
    env_example = ROOT / "config" / ".env.example"
    env_file = ROOT / "config" / ".env"

    if env_file.exists():
        content = env_file.read_text(encoding="utf-8")
        if "GEMINI_API_KEY=" in content and "GEMINI_API_KEY=\n" not in content:
            log(".env ya configurado")
            return True

    if not env_example.exists():
        log("WARN: no se encuentra config/.env.example")
        return False

    shutil.copy2(env_example, env_file)
    log(".env creado desde plantilla.")
    log("IMPORTANTE: Edita config/.env y agrega tu GEMINI_API_KEY")
    return True


def create_venv() -> bool:
    venv_dir = ROOT / ".venv"
    if venv_dir.exists():
        log("Entorno virtual ya existe (.venv/)")
        return True

    log("Creando entorno virtual...")
    result = subprocess.run(
        [sys.executable, "-m", "venv", str(venv_dir)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        log(f"ERROR al crear venv: {result.stderr}")
        return False
    log("Entorno virtual creado")
    return True


def install_deps() -> bool:
    venv_dir = ROOT / ".venv"
    pip = str(venv_dir / "Scripts" / "pip.exe") if os.name == "nt" else str(venv_dir / "bin" / "pip")

    req_file = ROOT / "requirements.txt"
    if not req_file.exists():
        log("WARN: no hay requirements.txt")
        return True

    log("Instalando dependencias...")
    result = subprocess.run(
        [pip, "install", "-r", str(req_file)],
        capture_output=True, text=True, timeout=300,
    )
    if result.returncode != 0:
        log(f"ERROR instalando dependencias: {result.stderr[-500:]}")
        return False
    log("Dependencias instaladas")
    return True


def init_db() -> bool:
    venv_dir = ROOT / ".venv"
    python = str(venv_dir / "Scripts" / "python.exe") if os.name == "nt" else str(venv_dir / "bin" / "python")

    init_script = ROOT / "scripts" / "init_db.py"
    if not init_script.exists():
        log("WARN: scripts/init_db.py no encontrado")
        return True

    log("Inicializando base de datos...")
    result = subprocess.run(
        [python, str(init_script)],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        log(f"ERROR inicializando BD: {result.stderr}")
        return False
    log("Base de datos lista")
    return True


def print_next_steps():
    profile_name = detect_profile()
    log(f"")
    log("=" * 60)
    log(f"  Imrryr OS instalado — Perfil: {profile_name}")
    log("=" * 60)
    log(f"")
    log("  Proximos pasos:")
    log(f"  1. Edita config/.env con tu GEMINI_API_KEY")
    log(f"  2. python scripts/startup.py")
    log(f"  3. Abre http://localhost:3000 en tu navegador")
    log(f"")
    log(f"  Para detener: python scripts/shutdown.py")
    log(f"  Para cambiar modelo: python scripts/switch_model.py")
    log(f"")


def main() -> int:
    ap = argparse.ArgumentParser(description="Instalador de Imrryr OS")
    ap.add_argument("--quick", action="store_true", help="Saltar creacion de venv e instalacion de deps")
    args = ap.parse_args()

    if not check_python():
        return 1

    create_env()

    if not args.quick:
        if not create_venv():
            return 1
        if not install_deps():
            return 1
        if not init_db():
            return 1

    print_next_steps()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
