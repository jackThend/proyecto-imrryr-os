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
    """Compila los lanzadores nativos Imrryr OS y Detener hacia dest_dir sin consola y con icono."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    python_exe = get_python_exe()
    ico_path = ROOT / "imrryr.ico"

    log(f"Compilando lanzadores nativos hacia: {dest_dir}")

    # Asegurar que el icono esté disponible en el paquete
    if ico_path.exists():
        shutil.copy2(str(ico_path), str(dest_dir / "imrryr.ico"))

    # 1. Compilar Imrryr OS.exe (sin consola, modo ventana)
    cmd_iniciar = [
        python_exe,
        "-m",
        "PyInstaller",
        "--onefile",
        "--windowed",
        "--name",
        "Imrryr OS",
        "--clean",
        str(SCRIPTS_DIR / "launcher_iniciar.py"),
        "--distpath",
        str(dest_dir),
    ]
    if ico_path.exists():
        cmd_iniciar.extend(["--icon", str(ico_path)])

    log("  [1/2] Compilando 'Imrryr OS.exe' (modo aplicación sin consola)...")
    res1 = subprocess.run(cmd_iniciar, cwd=str(ROOT), capture_output=True, text=True)
    if res1.returncode != 0:
        log(f"ERROR compilando Imrryr OS: {res1.stderr}")
        return False

    # 2. Compilar Detener Imrryr OS.exe (sin consola)
    cmd_detener = [
        python_exe,
        "-m",
        "PyInstaller",
        "--onefile",
        "--windowed",
        "--name",
        "Detener Imrryr OS",
        "--clean",
        str(SCRIPTS_DIR / "launcher_detener.py"),
        "--distpath",
        str(dest_dir),
    ]
    if ico_path.exists():
        cmd_detener.extend(["--icon", str(ico_path)])

    log("  [2/2] Compilando 'Detener Imrryr OS.exe'...")
    res2 = subprocess.run(cmd_detener, cwd=str(ROOT), capture_output=True, text=True)
    if res2.returncode != 0:
        log(f"ERROR compilando Detener Imrryr OS: {res2.stderr}")
        return False

    # 3. Limpiar residuos de build
    limpiar_residuos()

    exe_iniciar = dest_dir / "Imrryr OS.exe"
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


def find_iscc() -> Path | None:
    """Busca el compilador de Inno Setup (ISCC.exe)."""
    iscc = shutil.which("ISCC") or shutil.which("ISCC.exe")
    if iscc:
        return Path(iscc)
    candidatos = [
        Path(r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"),
        Path(r"C:\Program Files\Inno Setup 6\ISCC.exe"),
        Path(r"C:\Users") / Path.home().name / r"AppData\Local\Programs\Inno Setup 6\ISCC.exe",
    ]
    for cand in candidatos:
        if cand.exists():
            return cand
    return None


def compilar_inno_setup(profile_name: str = "pyme") -> bool:
    """Compila el instalador de Windows (.exe) usando Inno Setup."""
    iscc = find_iscc()
    if not iscc:
        log("AVISO: Compilador Inno Setup (ISCC.exe) no detectado en el sistema.")
        log("       Para generar el instalador .exe, instale Inno Setup 6.")
        return False

    iss_path = ROOT / "imrryr_setup.iss"
    if not iss_path.exists():
        generar_inno_setup_script(profile_name)

    log(f"Compilando instalador oficial con Inno Setup ({iscc.name})...")
    cmd = [
        str(iscc),
        f"/DMyAppProfile={profile_name}",
        str(iss_path),
    ]
    res = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
    if res.returncode != 0:
        log(f"ERROR al compilar con Inno Setup:\n{res.stderr}\n{res.stdout}")
        return False

    installer_path = DIST_DIR / f"Imrryr_OS_Setup_{profile_name}.exe"
    if installer_path.exists():
        size_mb = installer_path.stat().st_size / (1024 * 1024)
        log(f"  [EXITO] Instalador compilado: {installer_path.name} ({size_mb:.1f} MB)")
        log(f"  Ruta completa: {installer_path}")
        return True
    log("Inno Setup finalizó pero no se localizó el archivo de salida.")
    return False


def generar_inno_setup_script(profile_name: str = "pyme") -> Path:
    """Genera el archivo imrryr_setup.iss para compilar instaladores con Inno Setup."""
    iss_path = ROOT / "imrryr_setup.iss"
    ico_path = ROOT / "imrryr.ico"
    setup_icon = f"SetupIconFile={ico_path}\n" if ico_path.exists() else ""

    iss_content = f"""; Imrryr OS — Inno Setup Script
#define MyAppName "Imrryr OS"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Imrryr OS"
#define MyAppURL "http://localhost:3000"
#define MyAppExeName "Imrryr OS.exe"
#ifndef MyAppProfile
  #define MyAppProfile "{profile_name}"
#endif

[Setup]
AppId={{{{657FCC94-E6CC-4E4E-A72A-8FE81B16EC51}}}}
AppName={{#MyAppName}}
AppVersion={{#MyAppVersion}}
AppPublisher={{#MyAppPublisher}}
AppPublisherURL={{#MyAppURL}}
PrivilegesRequired=lowest
DefaultDirName={{localappdata}}\\Programs\\{{#MyAppName}}
DefaultGroupName={{#MyAppName}}
DisableProgramGroupPage=yes
OutputDir={DIST_DIR}
OutputBaseFilename=Imrryr_OS_Setup_{{#MyAppProfile}}
{setup_icon}Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "{{cm:CreateDesktopIcon}}"; GroupDescription: "{{cm:AdditionalIcons}}"

[InstallDelete]
; Limpiar accesos directos antiguos si existieran de versiones previas
Type: files; Name: "{{autodesktop}}\\Iniciar Imrryr OS.lnk"
Type: files; Name: "{{autodesktop}}\\Detener Imrryr OS.lnk"

[Files]
Source: "{DIST_DIR}\\imrryr-os-pkg\\*"; DestDir: "{{app}}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{ROOT}\\imrryr.ico"; DestDir: "{{app}}"; Flags: ignoreversion

[Icons]
Name: "{{group}}\\{{#MyAppName}}"; Filename: "{{app}}\\{{#MyAppExeName}}"; IconFilename: "{{app}}\\imrryr.ico"
Name: "{{group}}\\Detener Imrryr OS"; Filename: "{{app}}\\Detener Imrryr OS.exe"; IconFilename: "{{app}}\\imrryr.ico"
Name: "{{autodesktop}}\\{{#MyAppName}}"; Filename: "{{app}}\\{{#MyAppExeName}}"; Tasks: desktopicon; IconFilename: "{{app}}\\imrryr.ico"

[Run]
Filename: "{{app}}\\{{#MyAppExeName}}"; Description: "{{cm:LaunchProgram,{{#StringChange(MyAppName, '&', '&&')}}}}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{{app}}\\Detener Imrryr OS.exe"; Flags: runhidden waituntilterminated
"""
    iss_path.write_text(iss_content, encoding="utf-8")
    log(f"Guión de instalador Inno Setup generado: {iss_path.name}")
    return iss_path


def main() -> int:
    ap = argparse.ArgumentParser(description="Compilador de Ejecutables Nativos para Imrryr OS")
    ap.add_argument("--dest", "-d", type=str, default=None, help="Directorio destino de los ejecutables")
    ap.add_argument("--profile", "-p", type=str, default=None, help="Perfil a empaquetar y compilar (ej. pyme o tech)")
    ap.add_argument("--no-standalone", action="store_true", help="No incluir runtime portátil de Python en el paquete")
    ap.add_argument("--skip-installer", action="store_true", help="Omitir compilación del instalador Inno Setup")
    ap.add_argument("--installer-only", action="store_true", help="Solo compilar instalador Inno Setup desde dist/imrryr-os-pkg")
    args = ap.parse_args()

    profile_name = args.profile or "pyme"

    if args.installer_only:
        generar_inno_setup_script(profile_name)
        ok = compilar_inno_setup(profile_name)
        return 0 if ok else 1

    target_dir = Path(args.dest) if args.dest else BIN_DIR

    if args.profile:
        log(f"Empaquetando perfil '{args.profile}' con dependencias autónomas...")
        pkg_script = SCRIPTS_DIR / "package.py"
        cmd_pkg = [get_python_exe(), str(pkg_script), "--profile", args.profile, "--no-zip"]
        if not args.no_standalone:
            cmd_pkg.append("--standalone")

        res_pkg = subprocess.run(cmd_pkg, cwd=str(ROOT))
        if res_pkg.returncode != 0:
            log("ERROR durante el empaquetado base.")
            return 1
        target_dir = DIST_DIR / "imrryr-os-pkg"

    ok = compilar_lanzadores(target_dir)
    if not ok:
        log("Fallo en la compilación de ejecutables.")
        return 1

    generar_inno_setup_script(profile_name)

    if not args.skip_installer and (target_dir == DIST_DIR / "imrryr-os-pkg" or args.profile):
        compilar_inno_setup(profile_name)

    log("Compilación completada con éxito.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
