#!/usr/bin/env python3
"""
startup.py — Orquestador de arranque del backend invisible (Fase 1.3.4)
=====================================================================
"Script de inicio que ejecuta OpenCode en segundo plano (modo headless)."

Secuencia:
  1. Carga config/.env (credenciales locales aisladas).
  2. Arranca el proxy LiteLLM en :4000 (traductor agnóstico).
  3. Espera al healthcheck de LiteLLM.
  4. Arranca `opencode serve` en :4040 (backend headless, sin TUI).
  5. Espera al healthcheck de OpenCode (/api/health con Basic Auth).
  6. Guarda PIDs en .run/ para que shutdown.py los detenga limpiamente.

Pilares cumplidos:
  - Soberanía de datos (todo local, .env aislado).
  - Backend invisible (headless, sin terminal nativa de OpenCode).
  - Motor agnóstico (OpenCode enruta por LiteLLM).

Uso:
    python scripts/startup.py
    python scripts/startup.py --check-only   # solo healthcheck, no arrancar
"""
from __future__ import annotations

import argparse
import base64
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

# --- rutas ---
ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
GATEWAY_DIR = ROOT / "gateway"
DASHBOARD_DIR = ROOT / "dashboard"
RUN_DIR = ROOT / ".run"
ENV_FILE = CONFIG_DIR / ".env"
LITELLM_CONFIG = CONFIG_DIR / "litellm_config.yaml"
OPENCODE_CONFIG = CONFIG_DIR / "opencode.json"

sys.path.insert(0, str(GATEWAY_DIR))

# --- defaults (overrideables desde .env) ---
LITELLM_PORT = 4000
OPENCODE_PORT = 4040
GATEWAY_PORT = 5050
WHATSAPP_LOCAL_PORT = 5051
DASHBOARD_PORT = 3000
OPENCODE_PASSWORD = "imryyr-local-pass"  # local-only; sustituir por .env
HEALTH_TIMEOUT = 60  # segundos máx esperando cada servicio


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def log(msg: str) -> None:
    print(f"[startup] {msg}", flush=True)


def load_env() -> dict[str, str]:
    if not ENV_FILE.exists():
        log(f"ERROR: no existe {ENV_FILE}. Copia config/.env.example y rellénalo.")
        sys.exit(1)
    load_dotenv(ENV_FILE)
    return dict(os.environ)


def basic_auth_header(password: str) -> dict[str, str]:
    token = base64.b64encode(f"opencode:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def sync_agentes() -> None:
    """Escanea /agentes y /skills hacia config/opencode.json antes de arrancar OpenCode."""
    resultado = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "sync_agentes.py")],
        cwd=str(ROOT),
    )
    if resultado.returncode != 0:
        log("ADVERTENCIA: sync_agentes.py falló; los agentes/skills pueden no estar actualizados.")


# --------------------------------------------------------------------------
# Arranque de servicios
# --------------------------------------------------------------------------
def start_litellm(env: dict[str, str], port: int) -> subprocess.Popen:
    """Levanta el proxy LiteLLM en background."""
    log_dir = RUN_DIR / "litellm.log"
    # Forzar UTF-8 para que el banner Unicode de LiteLLM no crashee en Windows
    env = {**env, "PYTHONIOENCODING": "utf-8"}
    # El CLI de litellm (no python -m litellm).
    cmd = [
        sys.executable.replace("python.exe", "litellm.exe"),
        "--config", str(LITELLM_CONFIG),
        "--port", str(port),
    ]
    # fallback si el exe no está junto al python
    litellm_exe = ROOT / ".venv" / "Scripts" / "litellm.exe"
    if litellm_exe.exists():
        cmd[0] = str(litellm_exe)

    log_dir.parent.mkdir(parents=True, exist_ok=True)
    logf = log_dir.open("w", encoding="utf-8")
    proc = subprocess.Popen(
        cmd,
        stdout=logf,
        stderr=subprocess.STDOUT,
        env=env,
        cwd=str(ROOT),
        creationflags=_new_process_group(),
    )
    (RUN_DIR / "litellm.pid").write_text(str(proc.pid), encoding="utf-8")
    log(f"LiteLLM arrancado (PID {proc.pid}) en http://localhost:{port}")
    return proc


def _resolve_executable(name: str) -> str:
    """Resuelve el binario real de 'opencode' (en Windows es un shim .cmd/.ps1)."""
    found = shutil.which(name)
    if found:
        return found
    # fallback típico de npm global en Windows
    for ext in (".cmd", ".ps1", ".exe", ".bat"):
        guess = Path(os.environ.get("APPDATA", "")) / "npm" / f"{name}{ext}"
        if guess.exists():
            return str(guess)
    return name  # último recurso; lanzará FileNotFoundError claro


def start_opencode(env: dict[str, str], port: int, password: str) -> subprocess.Popen:
    """Levanta `opencode serve` headless en background."""
    log_path = RUN_DIR / "opencode.log"
    env = {**env, "OPENCODE_SERVER_PASSWORD": password}

    opencode_bin = _resolve_executable("opencode")
    cmd = [
        opencode_bin, "serve",
        "--port", str(port),
        "--hostname", "127.0.0.1",
    ]
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logf = log_path.open("w", encoding="utf-8")
    proc = subprocess.Popen(
        cmd,
        stdout=logf,
        stderr=subprocess.STDOUT,
        env=env,
        cwd=str(CONFIG_DIR),   # OpenCode lee config/opencode.json desde aquí
        creationflags=_new_process_group(),
    )
    (RUN_DIR / "opencode.pid").write_text(str(proc.pid), encoding="utf-8")
    log(f"OpenCode headless arrancado (PID {proc.pid}) en http://localhost:{port}")
    return proc


def start_gateway(env: dict[str, str], port: int) -> subprocess.Popen:
    """Levanta el gateway de WhatsApp (webhook_server.py) en background."""
    log_path = RUN_DIR / "gateway.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logf = log_path.open("w", encoding="utf-8")
    proc = subprocess.Popen(
        [sys.executable, str(GATEWAY_DIR / "webhook_server.py"), "--port", str(port)],
        stdout=logf,
        stderr=subprocess.STDOUT,
        env={**env, "PYTHONIOENCODING": "utf-8"},
        cwd=str(ROOT),
        creationflags=_new_process_group(),
    )
    (RUN_DIR / "gateway.pid").write_text(str(proc.pid), encoding="utf-8")
    log(f"Gateway WhatsApp arrancado (PID {proc.pid}) en http://localhost:{port}")
    return proc


def start_whatsapp_local(env: dict[str, str], port: int, gateway_port: int) -> subprocess.Popen | None:
    """Levanta el sidecar Node (whatsapp-web.js + QR) si el modo activo es 'local'."""
    sidecar_dir = GATEWAY_DIR / "whatsapp_local"
    if not (sidecar_dir / "node_modules").exists():
        log("ADVERTENCIA: gateway/whatsapp_local/node_modules no existe. Ejecuta 'npm install' ahí primero.")
        return None

    log_path = RUN_DIR / "whatsapp_local.log"
    logf = log_path.open("w", encoding="utf-8")
    proc = subprocess.Popen(
        ["node", "index.js"],
        stdout=logf,
        stderr=subprocess.STDOUT,
        env={**env, "WHATSAPP_LOCAL_PORT": str(port), "GATEWAY_PORT": str(gateway_port)},
        cwd=str(sidecar_dir),
        creationflags=_new_process_group(),
    )
    (RUN_DIR / "whatsapp_local.pid").write_text(str(proc.pid), encoding="utf-8")
    log(f"Sidecar WhatsApp local arrancado (PID {proc.pid}) en http://localhost:{port} (escanea el QR desde el dashboard)")
    return proc


def start_dashboard(env: dict[str, str], port: int) -> subprocess.Popen:
    """Levanta el Dashboard web (dashboard/server.py) en background."""
    log_path = RUN_DIR / "dashboard.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logf = log_path.open("w", encoding="utf-8")
    proc = subprocess.Popen(
        [sys.executable, str(DASHBOARD_DIR / "server.py"), "--port", str(port)],
        stdout=logf,
        stderr=subprocess.STDOUT,
        env={**env, "PYTHONIOENCODING": "utf-8"},
        cwd=str(ROOT),
        creationflags=_new_process_group(),
    )
    (RUN_DIR / "dashboard.pid").write_text(str(proc.pid), encoding="utf-8")
    log(f"Dashboard arrancado (PID {proc.pid}) en http://localhost:{port}")
    return proc


# --------------------------------------------------------------------------
# Healthchecks
# --------------------------------------------------------------------------
def wait_litellm(port: int) -> bool:
    url = f"http://localhost:{port}/health/liveliness"
    return _wait(url, headers={}, name="LiteLLM")


def wait_opencode(port: int, password: str) -> bool:
    url = f"http://localhost:{port}/api/health"
    return _wait(url, headers=basic_auth_header(password), name="OpenCode")


def wait_gateway(port: int) -> bool:
    url = f"http://localhost:{port}/webhook/health"
    return _wait(url, headers={}, name="Gateway")


def wait_dashboard(port: int) -> bool:
    url = f"http://localhost:{port}/api/status"
    return _wait(url, headers={}, name="Dashboard")


def _wait(url: str, headers: dict, name: str) -> bool:
    log(f"Esperando {name} ({url})…")
    deadline = time.time() + HEALTH_TIMEOUT
    last = 0
    while time.time() < deadline:
        try:
            r = httpx.get(url, headers=headers, timeout=3)
            if r.status_code == 200:
                log(f"{name} OK (HTTP 200)")
                return True
            last = r.status_code
        except httpx.HTTPError:
            pass
        time.sleep(1)
    log(f"X {name} NO respondio 200 tras {HEALTH_TIMEOUT}s (ultimo HTTP {last}).")
    return False


# --------------------------------------------------------------------------
# Windows: crear proceso en grupo propio para poder matar el árbol.
# --------------------------------------------------------------------------
def _new_process_group() -> int:
    if os.name == "nt":
        return subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Arranca el backend Imrryr OS (headless).")
    ap.add_argument("--check-only", action="store_true", help="Solo healthcheck, no arrancar procesos.")
    ap.add_argument("--no-browser", action="store_true", help="No abrir el navegador automáticamente al terminar.")
    args = ap.parse_args()

    env = load_env()
    RUN_DIR.mkdir(parents=True, exist_ok=True)

    litellm_port = int(env.get("LITELLM_PORT") or LITELLM_PORT)
    opencode_port = int(env.get("OPENCODE_PORT") or OPENCODE_PORT)
    gateway_port = GATEWAY_PORT
    whatsapp_local_port = int(env.get("WHATSAPP_LOCAL_PORT") or WHATSAPP_LOCAL_PORT)
    dashboard_port = int(env.get("DASHBOARD_PORT") or DASHBOARD_PORT)
    password = env.get("OPENCODE_SERVER_PASSWORD") or OPENCODE_PASSWORD

    if not args.check_only:
        sync_agentes()

    if args.check_only:
        ok = wait_litellm(litellm_port) and wait_opencode(opencode_port, password)
        return 0 if ok else 1

    # 1. LiteLLM
    if not _port_open(litellm_port):
        start_litellm(env, litellm_port)
    else:
        log(f"Puerto {litellm_port} ocupado: asumo LiteLLM ya corriendo.")
    if not wait_litellm(litellm_port):
        return 1

    # 2. OpenCode
    if not _port_open(opencode_port):
        start_opencode(env, opencode_port, password)
    else:
        log(f"Puerto {opencode_port} ocupado: asumo OpenCode ya corriendo.")
    if not wait_opencode(opencode_port, password):
        return 1

    # 3. Gateway WhatsApp (webhook + selector local/cloud)
    if not _port_open(gateway_port):
        start_gateway(env, gateway_port)
    else:
        log(f"Puerto {gateway_port} ocupado: asumo Gateway ya corriendo.")
    wait_gateway(gateway_port)  # no bloqueante: el gateway es opcional para el resto del backend

    # 4. Sidecar WhatsApp local (solo si el modo activo es "local")
    from config import modo_activo  # gateway/config.py

    if modo_activo() == "local":
        if not _port_open(whatsapp_local_port):
            start_whatsapp_local(env, whatsapp_local_port, gateway_port)
        else:
            log(f"Puerto {whatsapp_local_port} ocupado: asumo sidecar WhatsApp local ya corriendo.")
    else:
        log("Modo WhatsApp activo: cloud (sidecar local no se levanta).")

    # 5. Dashboard (la cara visible; sin esto el usuario no tiene forma de usar el sistema)
    if not _port_open(dashboard_port):
        start_dashboard(env, dashboard_port)
    else:
        log(f"Puerto {dashboard_port} ocupado: asumo Dashboard ya corriendo.")
    wait_dashboard(dashboard_port)

    log("=" * 60)
    log("Imrryr OS operativo:")
    log(f"  • Dashboard (abre esto): http://localhost:{dashboard_port}")
    log(f"  • LiteLLM (traductor)  : http://localhost:{litellm_port}")
    log(f"  • OpenCode (motor)     : http://localhost:{opencode_port}")
    log(f"  • Gateway WhatsApp     : http://localhost:{gateway_port}")
    log("  • Para detener         : python scripts/shutdown.py")
    log("=" * 60)

    if not args.no_browser:
        import webbrowser
        webbrowser.open(f"http://localhost:{dashboard_port}")

    return 0


def _port_open(port: int) -> bool:
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.5)
    try:
        return s.connect_ex(("127.0.0.1", port)) == 0
    finally:
        s.close()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        log("Interrumpido.")
        raise SystemExit(130)
