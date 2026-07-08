#!/usr/bin/env python3
"""
restart_litellm.py — Reinicia LiteLLM para que recargue su configuración
==============================================================================
LiteLLM no relee litellm_config.yaml en caliente en el modo pass-through
que usa Imrryr OS (sin master_key ni DB de tracking, ver el propio archivo
de config). Cuando config/cuentas_ia.py cambia la cuenta de IA activa,
llama a este script para matar el proceso viejo y levantar uno nuevo con
el config ya actualizado.

Uso:
    python scripts/restart_litellm.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from shutdown import RUN_DIR, kill_pid  # noqa: E402
from startup import LITELLM_PORT, load_env, start_litellm, wait_litellm  # noqa: E402


def main() -> int:
    env = load_env()
    port = int(env.get("LITELLM_PORT") or LITELLM_PORT)
    kill_pid("LiteLLM", RUN_DIR / "litellm.pid")
    start_litellm(env, port)
    ok = wait_litellm(port)
    print(f"[restart_litellm] LiteLLM {'listo' if ok else 'no respondió a tiempo'} en :{port}", flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
