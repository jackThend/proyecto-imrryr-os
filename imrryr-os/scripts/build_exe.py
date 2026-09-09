#!/usr/bin/env python3
"""
build_exe.py — Compilador de Ejecutables Nativos para Imrryr OS
==============================================================
Compila los lanzadores nativos 'Iniciar Imrryr OS.exe' y 'Detener Imrryr OS.exe'
usando PyInstaller, limpia artefactos temporales y opcionalmente compila el
instalador de Windows (Inno Setup) si está disponible.

Uso:
    python scripts/build_exe.py
    python scripts/build_exe.py --dest dist/bin
    python scripts/build_exe.py --profile pyme
    python scripts/build_exe.py --profile tech
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
DIST_DIR = ROOT / "dist"
BIN_DIR = DIST_DIR / "bin"


def log(msg: str) -> None:
    print(f"[build_exe] {msg}", flush=True)


def get_python_exe() -> str:
    venv_py = ROOT / ".venv" / "Scripts" / "python.exe"
    if venv_py.exists():
        return str(venv_py)
    return sys.executable


def compilar_lanzadores(dest_dir: Path) -> bool:
    """Compila los lanzadores nativos Iniciar y Detener hacia dest_dir."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    python_exe = get_python_exe()

    log(f"Compilando lanzadores nativos hacia: {dest_dir}")

    # 1. Compilar Iniciar Imrryr OS.exe
    cmd_iniciar = [
        python_exe,
        "-m",
        "PyInstaller",
        "--onefile",
        "--name",
        "Iniciar Imrryr OS",
        "--clean",
        str(SCRIPTS_DIR / "launcher_iniciar.py"),
        "--distpath",
        str(dest_dir),
    ]
    log("  [1/2] Compilando 'Iniciar Imrryr OS.exe'...")
    res1 = subprocess.run(cmd_iniciar, cwd=str(ROOT), capture_output=True, text=True)
    if res1.returncode != 0:
        log(f"ERROR compilando Iniciar Imrryr OS: {res1.stderr}")
        return False

    # 2. Compilar Detener Imrryr OS.exe
    cmd_detener = [
        python_exe,
        "-m",
        "PyInstaller",
        "--onefile",
        "--name",
        "Detener Imrryr OS",
        "--clean",
        str(SCRIPTS_DIR / "launcher_detener.py"),
        "--distpath",
        str(dest_dir),
    ]
    log("  [2/2] Compilando 'Detener Imrryr OS.exe'...")
    res2 = subprocess.run(cmd_detener, cwd=str(ROOT), capture_output=True, text=True)
    if res2.returncode != 0:
        log(f"ERROR compilando Detener Imrryr OS: {res2.stderr}")
        return False

    # 3. Limpiar residuos de build
    limpiar_residuos()

    exe_iniciar = dest_dir / "Iniciar Imrryr OS.exe"
    exe_detener = dest_dir / "Detener Imrryr OS.exe"
    if exe_iniciar.exists() and exe_detener.exists():
        log(f"  OK: {exe_iniciar.name} ({exe_iniciar.stat().st_size / (1024*1024):.1f} MB)")
        log(f"  OK: {exe_detener.name} ({exe_detener.stat().st_size / (1024*1024):.1f} MB)")
        return True
    return False


def limpiar_residuos() -> None:
    """Elimina carpetas build y archivos .spec generados por PyInstaller."""
    build_dir = ROOT / "build"
    if build_dir.exists():
        try:
            shutil.rmtree(build_dir)
        except Exception:
            pass

    for spec_file in ROOT.glob("*.spec"):
        try:
            spec_file.unlink(missing_ok=True)
        except Exception:
            pass


def generar_inno_setup_script(profile_name: str = "pyme") -> Path:
    """Genera el archivo imrryr_setup.iss para compilar instaladores con Inno Setup."""
    iss_path = ROOT / "imrryr_setup.iss"
    iss_content = f"""; Imrryr OS — Inno Setup Script
#define MyAppName "Imrryr OS"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Imrryr OS"
#define MyAppURL "http://localhost:3000"
#define MyAppExeName "Iniciar Imrryr OS.exe"

[Setup]
AppId={{{{657FCC94-E6CC-4E4E-A72A-8FE81B16EC51}}}}
AppName={{#MyAppName}}
AppVersion={{#MyAppVersion}}
AppPublisher={{#MyAppPublisher}}
AppPublisherURL={{#MyAppURL}}
DefaultDirName={{autopf}}\\{{#MyAppName}}
DefaultGroupName={{#MyAppName}}
DisableProgramGroupPage=yes
OutputDir={DIST_DIR}
OutputBaseFilename=Imrryr_OS_Setup_{profile_name}
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "{{cm:CreateDesktopIcon}}"; GroupDescription: "{{cm:AdditionalIcons}}"

[Files]
Source: "{DIST_DIR}\\imrryr-os-pkg\\*"; DestDir: "{{app}}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{{group}}\\{{#MyAppName}}"; Filename: "{{app}}\\{{#MyAppExeName}}"
Name: "{{group}}\\Detener Imrryr OS"; Filename: "{{app}}\\Detener Imrryr OS.exe"
Name: "{{autodesktop}}\\{{#MyAppName}}"; Filename: "{{app}}\\{{#MyAppExeName}}"; Tasks: desktopicon
Name: "{{autodesktop}}\\Detener Imrryr OS"; Filename: "{{app}}\\Detener Imrryr OS.exe"; Tasks: desktopicon

[Run]
Filename: "{{app}}\\{{#MyAppExeName}}"; Description: "{{cm:LaunchProgram,{{#StringChange(MyAppName, '&', '&&')}}}}"; Flags: nowait postinstall skipifsilent
"""
    iss_path.write_text(iss_content, encoding="utf-8")
    log(f"Guión de instalador Inno Setup generado: {iss_path.name}")
    return iss_path


def main() -> int:
    ap = argparse.ArgumentParser(description="Compilador de Ejecutables Nativos para Imrryr OS")
    ap.add_argument("--dest", "-d", type=str, default=None, help="Directorio destino de los ejecutables")
    ap.add_argument("--profile", "-p", type=str, default=None, help="Perfil a empaquetar y compilar (ej. pyme o tech)")
    args = ap.parse_args()

    target_dir = Path(args.dest) if args.dest else BIN_DIR

    if args.profile:
        log(f"Empaquetando perfil '{args.profile}' con ejecutables...")
        pkg_script = SCRIPTS_DIR / "package.py"
        res_pkg = subprocess.run([get_python_exe(), str(pkg_script), "--profile", args.profile], cwd=str(ROOT))
        if res_pkg.returncode != 0:
            log("ERROR durante el empaquetado base.")
            return 1
        target_dir = DIST_DIR / "imrryr-os-pkg"

    ok = compilar_lanzadores(target_dir)
    if not ok:
        log("Fallo en la compilación de ejecutables.")
        return 1

    generar_inno_setup_script(args.profile or "default")

    log("Compilación de ejecutables completada con éxito.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
