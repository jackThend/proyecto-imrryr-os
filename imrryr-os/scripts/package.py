#!/usr/bin/env python3
"""
package.py — Empaquetador White-Label (Fase 7)
================================================
Toma un perfil (tech/pyme/custom), copia solo los componentes
necesarios y genera un distributable listo para instalar.

Uso:
    python scripts/package.py --profile pyme
    python scripts/package.py --profile tech
    python scripts/package.py --profile custom
    python scripts/package.py --list-profiles
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import zipfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROFILES_DIR = ROOT / "profiles"
DIST_DIR = ROOT / "dist"
PKG_DIR = DIST_DIR / "imrryr-os-pkg"

# Siempre se incluyen (independiente del perfil)
CORE_DIRS = [
    "config",
    "scripts",
    "dashboard",
    "gateway",
    "docs",
    "semillas",
]

CORE_FILES = [
    "requirements.txt",
]


def log(msg: str) -> None:
    print(f"[package] {msg}", flush=True)


def list_profiles() -> list[str]:
    return sorted([f.stem for f in PROFILES_DIR.glob("*.yaml") if f.stem != "custom"])


def load_profile(name: str) -> dict:
    path = PROFILES_DIR / f"{name}.yaml"
    if not path.exists():
        log(f"ERROR: Perfil '{name}' no encontrado.")
        sys.exit(1)
    import yaml
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def clean_pkg_dir():
    if PKG_DIR.exists():
        shutil.rmtree(PKG_DIR)
    PKG_DIR.mkdir(parents=True, exist_ok=True)


def copy_core():
    """Copia archivos y carpetas base del sistema."""
    for dirname in CORE_DIRS:
        src = ROOT / dirname
        if src.exists():
            dst = PKG_DIR / dirname
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns(".venv", "__pycache__", ".run", ".gitkeep", ".env"))
            log(f"  Core: {dirname}/")

    for fname in CORE_FILES:
        src = ROOT / fname
        if src.exists():
            shutil.copy2(src, PKG_DIR / fname)
            log(f"  Core: {fname}")


def copy_agents(agent_list: list[str]):
    """Copia solo los agentes del perfil."""
    dst_dir = PKG_DIR / "agentes"
    dst_dir.mkdir(exist_ok=True)

    for agent_file in agent_list:
        src = ROOT / "agentes" / agent_file
        if src.exists():
            shutil.copy2(src, dst_dir / agent_file)
            log(f"  Agente: {agent_file}")
        else:
            log(f"  WARN: agente {agent_file} no encontrado")

    # Crear archivo de bloqueo si el perfil no tiene Build
    build_present = any("build" in a.lower() for a in agent_list)
    if not build_present:
        (dst_dir / ".build_bloqueado").write_text(
            "Agente Build desactivado por perfil. "
            "Para reactivar: borra este archivo y copia agente_build.yaml manualmente.",
            encoding="utf-8",
        )
        log("  Build bloqueado (perfil sin codigo)")


def copy_skills(skill_list: list[str]):
    """Copia solo los skills del perfil + sus manifiestos MCP."""
    dst_dir = PKG_DIR / "skills"
    dst_dir.mkdir(exist_ok=True)

    for skill_file in skill_list:
        src = ROOT / "skills" / skill_file
        if src.exists():
            shutil.copy2(src, dst_dir / skill_file)
            log(f"  Skill: {skill_file}")

            # Copiar manifiesto MCP si existe
            mcp_src = src.with_suffix(".mcp.json")
            if mcp_src.exists():
                shutil.copy2(mcp_src, dst_dir / mcp_src.name)
        else:
            log(f"  WARN: skill {skill_file} no encontrado")


def create_env_template(profile: dict):
    """Crea .env.example limpio para el cliente."""
    env_lines = [
        "# =====================================================================",
        "# Imrryr OS — Variables de entorno (PERFIL: " + profile.get("nombre", "personalizado") + ")",
        "# Generado por package.py el " + date.today().isoformat(),
        "# =====================================================================",
        "#",
        "# OBTENER: https://aistudio.google.com/apikey",
        "GEMINI_API_KEY=",
        "",
        "# --- Puertos locales ---",
        "LITELLM_PORT=4000",
        "OPENCODE_PORT=4040",
        "DASHBOARD_PORT=3000",
        "",
        "# --- Auth servidor OpenCode ---",
        "OPENCODE_SERVER_PASSWORD=cambia_esta_password",
        "",
        "# --- Modelo por defecto ---",
        "DEFAULT_MODEL=gemini-flash",
    ]

    if profile.get("modulos", {}).get("terminal", True):
        env_lines.extend([
            "",
            "# --- Terminal (solo perfil Tech) ---",
            "TERMINAL_HABILITADA=true",
        ])

    (PKG_DIR / "config" / ".env.example").write_text("\n".join(env_lines) + "\n", encoding="utf-8")
    log("  .env.example creado")


def create_install_script(profile: dict):
    """Copia install.py al paquete."""
    src = ROOT / "scripts" / "install.py"
    if src.exists():
        shutil.copy2(src, PKG_DIR / "install.py")
    else:
        # Crear install.py por defecto si no existe
        install_code = '''#!/usr/bin/env python3
"""Imrryr OS — Instalador automatico"""
import subprocess, sys, shutil, os
from pathlib import Path
ROOT = Path(__file__).resolve().parent

def log(m): print(f"[install] {m}", flush=True)

def main():
    log("=== Imrryr OS Instalador ===")
    log("Perfil: ''' + profile.get("nombre", "personalizado") + '''")
    
    # Verificar Python
    if sys.version_info < (3, 11):
        log("ERROR: Se necesita Python 3.11+")
        return 1
    
    # Crear .env desde .env.example
    env_example = ROOT / "config" / ".env.example"
    env_file = ROOT / "config" / ".env"
    if not env_file.exists() and env_example.exists():
        shutil.copy2(env_example, env_file)
        log(".env creado desde plantilla. EDITALO con tu API key.")
    
    # Crear venv
    venv_dir = ROOT / ".venv"
    if not venv_dir.exists():
        log("Creando entorno virtual...")
        subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)
    
    # Instalar dependencias
    log("Instalando dependencias...")
    pip = str(venv_dir / "Scripts" / "pip.exe") if os.name == "nt" else str(venv_dir / "bin" / "pip")
    subprocess.run([pip, "install", "-r", str(ROOT / "requirements.txt")], check=True)
    
    # Inicializar BD
    python = str(venv_dir / "Scripts" / "python.exe") if os.name == "nt" else str(venv_dir / "bin" / "python")
    subprocess.run([python, "scripts/init_db.py"], check=True)
    
    log("Instalacion completada.")
    log("1. Edita config/.env con tu GEMINI_API_KEY")
    log("2. Ejecuta: python scripts/startup.py")
    log("3. Abre: http://localhost:3000")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
'''
        (PKG_DIR / "install.py").write_text(install_code, encoding="utf-8")
    log("  install.py copiado")


def create_manifest(profile: dict):
    """Crea manifest.json con metadatos del paquete."""
    manifest = {
        "nombre": profile.get("nombre", "Imrryr OS"),
        "version": "1.0.0",
        "fecha": date.today().isoformat(),
        "perfil": profile.get("descripcion", ""),
        "agentes": len(profile.get("agentes", [])),
        "skills": len(profile.get("skills", [])),
        "modulos": profile.get("modulos", {}),
    }
    (PKG_DIR / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    log("  manifest.json creado")


def create_zip(profile_name: str):
    """Comprime el paquete en un zip."""
    zip_path = DIST_DIR / f"imrryr-os-{profile_name}.zip"
    if zip_path.exists():
        zip_path.unlink()

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for fpath in PKG_DIR.rglob("*"):
            if fpath.is_file():
                arcname = fpath.relative_to(PKG_DIR.parent)
                zf.write(fpath, arcname)

    log(f"Paquete creado: {zip_path}")
    return zip_path


def main() -> int:
    ap = argparse.ArgumentParser(description="Empaquetador White-Label Imrryr OS")
    ap.add_argument("--profile", "-p", choices=list_profiles() + ["custom"], help="Perfil a empaquetar")
    ap.add_argument("--list-profiles", action="store_true", help="Listar perfiles disponibles")
    args = ap.parse_args()

    if args.list_profiles:
        print("Perfiles disponibles:")
        for name in list_profiles():
            profile = load_profile(name)
            print(f"  - {name}: {profile.get('descripcion', '')}")
        return 0

    if not args.profile:
        ap.print_help()
        return 1

    profile = load_profile(args.profile)
    log(f"Empaquetando perfil: {profile['nombre']}")

    DIST_DIR.mkdir(parents=True, exist_ok=True)
    clean_pkg_dir()

    copy_core()
    copy_agents(profile.get("agentes", []))
    copy_skills(profile.get("skills", []))
    create_env_template(profile)
    create_install_script(profile)
    create_manifest(profile)

    zip_path = create_zip(args.profile)
    size_mb = zip_path.stat().st_size / (1024 * 1024)

    log(f"Empaquetado completado:")
    log(f"  Perfil: {profile['nombre']}")
    log(f"  Archivo: {zip_path.name}")
    log(f"  Tamaño: {size_mb:.1f} MB")
    log(f"  Contenido: {len(profile.get('agentes', []))} agentes, {len(profile.get('skills', []))} skills")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
