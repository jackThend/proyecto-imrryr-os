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
    "finanzas",
    "correo",
    "mcp_server",
    "bin",
]

# Archivos base siempre incluidos
CORE_FILES = [
    "requirements.txt",
    "install.ps1",
    "install.sh",
    "imrryr.ico",
]

# Espejo del .gitignore: lo que es secreto o dato del usuario NUNCA entra al
# distributable. Antes solo se excluía .env y el zip se llevaba la sesión de
# WhatsApp (.wwebjs_auth), las credenciales de config/*.json, los fondos
# personales del dashboard y hasta node_modules del sidecar.
IGNORE_PATTERNS = shutil.ignore_patterns(
    # basura de entorno / build
    "__pycache__", "*.pyc", ".pytest_cache", ".venv", ".run", "node_modules", "tmp",
    # secretos y estado local (el .env.example lo regenera create_env_template)
    ".env", ".env.*",
    "cuentas_*.json", "admin_modulos.json", "gmail_*", "*.pickle",
    "scheduler_estado.json", "ultimo_audio.json", "compras_prefs.json",
    "region.json", "agenda_prefs.json", "gateway_config.json",
    # se genera en cada equipo desde opencode.template.json (lleva rutas absolutas y la cuenta activa)
    "opencode.json",
    # sesión de WhatsApp local
    ".wwebjs_auth", ".wwebjs_cache", "qr.png",
    # contenido personal del usuario dentro de carpetas de código
    "fondos", "audios", "privado", "eventos", "vault",
)


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
            shutil.copytree(src, dst, ignore=IGNORE_PATTERNS)
            log(f"  Core: {dirname}/")

    for fname in CORE_FILES:
        src = ROOT / fname
        if src.exists():
            shutil.copy2(src, PKG_DIR / fname)
            log(f"  Core: {fname}")

    # semillas/ es dato del usuario: viaja VACÍA como estructura lista para usar.
    (PKG_DIR / "semillas" / "adjuntos").mkdir(parents=True, exist_ok=True)
    (PKG_DIR / "semillas" / ".gitkeep").write_text("", encoding="utf-8")
    log("  Core: semillas/ (estructura vacía, sin datos)")


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


CORE_SKILLS = [
    "uso_ia.py",
    "errores_ia.py",
    "ruta_modelo.py",
    "perfil_negocio.py",
    "confirmacion_hitl.py",
    "memoria_perfil.py",
    "inyectar_gasto.py",
    "leer_gmail.py",
    "consultar_memoria_vectorial.py",
    "generar_cotizacion_pdf.py",
]


def resolve_profile_skills(profile: dict) -> tuple[set[str], set[str]]:
    """Determina los scripts .py y manifiestos .mcp.json requeridos por el perfil."""
    import yaml

    scripts_necesarios = set(profile.get("skills", []))
    scripts_necesarios.update(CORE_SKILLS)
    mcp_jsons_necesarios = set()

    for agente_file in profile.get("agentes", []):
        agente_path = ROOT / "agentes" / agente_file
        if not agente_path.exists():
            continue
        try:
            agente_data = yaml.safe_load(agente_path.read_text(encoding="utf-8")) or {}
            for tool_name in agente_data.get("herramientas_permitidas", []):
                mcp_path = ROOT / "skills" / f"{tool_name}.mcp.json"
                if mcp_path.exists():
                    mcp_jsons_necesarios.add(mcp_path.name)
                    try:
                        mcp_data = json.loads(mcp_path.read_text(encoding="utf-8"))
                        script_rel = mcp_data.get("script", "")
                        if script_rel:
                            scripts_necesarios.add(Path(script_rel).name)
                    except Exception:
                        pass
                py_path = ROOT / "skills" / f"{tool_name}.py"
                if py_path.exists():
                    scripts_necesarios.add(py_path.name)
        except Exception:
            pass

    bloqueos = profile.get("bloqueos", [])
    if "ejecutar_script_python" in bloqueos or "terminal" in bloqueos:
        scripts_necesarios.discard("ejecutar_script.py")
        mcp_jsons_necesarios.discard("ejecutar_script.mcp.json")

    return scripts_necesarios, mcp_jsons_necesarios


def copy_skills(profile: dict):
    """Copia los skills y manifiestos MCP necesarios para el perfil."""
    dst_dir = PKG_DIR / "skills"
    dst_dir.mkdir(exist_ok=True)

    scripts_necesarios, mcp_jsons = resolve_profile_skills(profile)

    for skill_file in sorted(scripts_necesarios):
        src = ROOT / "skills" / skill_file
        if src.exists():
            shutil.copy2(src, dst_dir / skill_file)
            log(f"  Skill: {skill_file}")
            mcp_src = src.with_suffix(".mcp.json")
            if mcp_src.exists():
                mcp_jsons.add(mcp_src.name)
        else:
            log(f"  WARN: skill {skill_file} no encontrado")

    for mcp_file in sorted(mcp_jsons):
        src = ROOT / "skills" / mcp_file
        if src.exists() and not (dst_dir / mcp_file).exists():
            shutil.copy2(src, dst_dir / mcp_file)
            log(f"  MCP: {mcp_file}")


def create_env_template(profile: dict):
    """Crea .env.example limpio para el cliente."""
    env_lines = [
        "# =====================================================================",
        "# Imrryr OS — Variables de entorno (PERFIL: " + profile.get("nombre", "personalizado") + ")",
        "# Generado por package.py el " + date.today().isoformat(),
        "# =====================================================================",
        "#",
        "# La cuenta de IA se activa desde el dashboard: Ajustes > Cuentas de IA",
        "# (acepta Gemini, OpenCode GO u Ollama local — ver cuentas_ia.py).",
        "GEMINI_API_KEY=",
        "",
        "# --- Puertos locales ---",
        "LITELLM_PORT=4000",
        "OPENCODE_PORT=4040",
        "DASHBOARD_PORT=3000",
        "IMRRYR_CHAT_TIMEOUT_SECONDS=300",
        "",
        "# --- Auth servidor OpenCode ---",
        "OPENCODE_SERVER_PASSWORD=cambia_esta_password",
        "",
        "# --- Modelo ---",
        "# Vacío a propósito (neutralidad de modelos): el sistema usa el alias",
        "# imrryr-activo, que apunta a la cuenta activada en el dashboard.",
        "DEFAULT_MODEL=",
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
    log("1. Activa tu cuenta de IA en Ajustes > Cuentas de IA (dashboard)")
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


def bundle_portable_runtime(pkg_dir: Path) -> bool:
    """Empaqueta un runtime de Python portátil y autónomo en pkg_dir/runtime."""
    runtime_dir = pkg_dir / "runtime"
    if runtime_dir.exists():
        shutil.rmtree(runtime_dir)
    runtime_dir.mkdir(parents=True, exist_ok=True)

    base = Path(sys.base_prefix)
    venv = Path(sys.prefix)

    log("  Runtime: Copiando intérprete Python y librerías base...")
    for f in base.glob("*.exe"):
        shutil.copy2(f, runtime_dir / f.name)
    for f in base.glob("*.dll"):
        shutil.copy2(f, runtime_dir / f.name)

    # DLLs
    if (base / "DLLs").exists():
        shutil.copytree(base / "DLLs", runtime_dir / "DLLs", ignore=shutil.ignore_patterns("*.pdb"))

    # Lib estándar
    if (base / "Lib").exists():
        shutil.copytree(
            base / "Lib",
            runtime_dir / "Lib",
            ignore=shutil.ignore_patterns("site-packages", "test", "idlelib", "__pycache__"),
        )

    # site-packages desde el entorno virtual
    log("  Runtime: Copiando paquetes preinstalados (site-packages)...")
    site_packages = venv / "Lib" / "site-packages"
    if site_packages.exists():
        shutil.copytree(
            site_packages,
            runtime_dir / "Lib" / "site-packages",
            ignore=shutil.ignore_patterns("__pycache__"),
        )

    # Scripts del venv (incluye litellm.exe, etc.)
    scripts_src = venv / "Scripts"
    if scripts_src.exists():
        shutil.copytree(
            scripts_src,
            runtime_dir / "Scripts",
            ignore=shutil.ignore_patterns("__pycache__"),
        )

    # Archivo ._pth para resolución relativa
    pth_content = """.
DLLs
Lib
Lib\\site-packages
import site
"""
    (runtime_dir / "python313._pth").write_text(pth_content, encoding="utf-8")
    log("  Runtime: python313._pth configurado para resolución autónoma.")

    # Precompilar bytecode de paquetes pesados para acelerar el arranque en frío
    try:
        import compileall
        log("  Runtime: Precompilando bytecode (.pyc) para acelerar primer arranque...")
        compileall.compile_dir(str(runtime_dir / "Lib" / "site-packages" / "litellm"), quiet=1)
        compileall.compile_dir(str(runtime_dir / "Lib" / "site-packages" / "fastapi"), quiet=1)
        compileall.compile_dir(str(runtime_dir / "Lib" / "site-packages" / "uvicorn"), quiet=1)
    except Exception:
        pass

    return True


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
    ap.add_argument("--standalone", action="store_true", help="Incluir runtime portátil de Python para distribución autónoma")
    ap.add_argument("--no-zip", action="store_true", help="No crear archivo .zip final (útil para compilar instalador .exe)")
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
    copy_skills(profile)
    create_env_template(profile)
    create_install_script(profile)
    create_manifest(profile)

    if args.standalone:
        log("Incorporando runtime portátil de Python en el paquete...")
        bundle_portable_runtime(PKG_DIR)

    if not args.no_zip:
        zip_path = create_zip(args.profile)
        size_mb = zip_path.stat().st_size / (1024 * 1024)
        log("Empaquetado completado:")
        log(f"  Perfil: {profile['nombre']}")
        log(f"  Archivo: {zip_path.name}")
        log(f"  Tamaño: {size_mb:.1f} MB")
    else:
        log("Empaquetado en carpeta completado (sin zip): dist/imrryr-os-pkg")

    log(f"  Contenido: {len(profile.get('agentes', []))} agentes, {len(profile.get('skills', []))} skills")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
