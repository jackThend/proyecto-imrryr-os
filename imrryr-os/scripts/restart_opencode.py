#!/usr/bin/env python3
"""
restart_opencode.py — Re-sincroniza los agentes y reinicia OpenCode
==============================================================================
OpenCode lee config/opencode.json solo al arrancar. Normalmente cambiar de
cuenta de IA solo toca LiteLLM (todos los agentes apuntan al alias fijo
"imrryr-activo"), pero las cuentas de un proveedor nativo de OpenCode (Zen
gratis, ver config/cuentas_ia.py) salen por otro provider y el modelo de cada
agente cambia: hay que regenerar el bloque "agent" y recargar OpenCode.

Uso:
    python scripts/restart_opencode.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from shutdown import RUN_DIR, kill_pid  # noqa: E402
from startup import OPENCODE_PASSWORD, OPENCODE_PORT, load_env, start_opencode, sync_agentes, wait_opencode  # noqa: E402


def main() -> int:
    env = load_env()
    port = int(env.get("OPENCODE_PORT") or OPENCODE_PORT)
    password = env.get("OPENCODE_SERVER_PASSWORD") or OPENCODE_PASSWORD
    sync_agentes()
    kill_pid("OpenCode", RUN_DIR / "opencode.pid")
    start_opencode(env, port, password)
    ok = wait_opencode(port, password)
    print(f"[restart_opencode] OpenCode {'listo' if ok else 'no respondió a tiempo'} en :{port}", flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
