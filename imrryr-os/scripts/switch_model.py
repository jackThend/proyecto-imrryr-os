#!/usr/bin/env python3
"""
switch_model.py — Utilidad de conmutación agnóstica de modelos (Fase 1.2.11)
============================================================================
Cambia el modelo por defecto del Arnés OpenCode sin tocar código: edita
config/opencode.json y config/.env DEFAULT_MODEL.

Pilar cumplido: Neutralidad de Modelos ("alternar instantáneamente entre
diferentes 'cerebros' comerciales o modelos locales").

Uso:
    python scripts/switch_model.py                 # lista modelos disponibles
    python scripts/switch_model.py gemini-flash    # cambia a gemini-flash
    python scripts/switch_model.py gemini-pro
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# --- rutas (el script vive en imrryr-os/scripts/) ---
ROOT = Path(__file__).resolve().parent.parent
OPENCODE_JSON = ROOT / "config" / "opencode.json"
ENV_FILE = ROOT / "config" / ".env"


def load_provider_models() -> list[str]:
    """Devuelve los modelos definidos en opencode.json (provider imryyr-llm)."""
    if not OPENCODE_JSON.exists():
        return []
    cfg = json.loads(OPENCODE_JSON.read_text(encoding="utf-8"))
    provider = cfg.get("provider", {}).get("imryyr-llm", {})
    return list(provider.get("models", {}).keys())


def update_opencode_json(model: str) -> None:
    cfg = json.loads(OPENCODE_JSON.read_text(encoding="utf-8"))
    full = f"imryyr-llm/{model}"
    cfg["model"] = full
    # si el modelo es flash, úsalo también como small_model (barato para tareas chicas)
    if "flash" in model:
        cfg["small_model"] = full
    OPENCODE_JSON.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")


def update_env_default(model: str) -> None:
    if not ENV_FILE.exists():
        return
    lines = ENV_FILE.read_text(encoding="utf-8").splitlines()
    out = []
    found = False
    for ln in lines:
        if ln.startswith("DEFAULT_MODEL="):
            out.append(f"DEFAULT_MODEL={model}")
            found = True
        else:
            out.append(ln)
    if not found:
        out.append(f"DEFAULT_MODEL={model}")
    ENV_FILE.write_text("\n".join(out) + "\n", encoding="utf-8")


def main() -> int:
    available = load_provider_models()

    if len(sys.argv) < 2:
        print("Modelos disponibles en el gateway Imrryr (imryyr-llm/*):")
        for m in available:
            print(f"  - {m}")
        print("\nUso: python scripts/switch_model.py <modelo>")
        return 0

    target = sys.argv[1].removeprefix("imryyr-llm/")
    if available and target not in available:
        print(f"ERROR: '{target}' no está en opencode.json.")
        print("Modelos válidos: " + ", ".join(available))
        return 1

    update_opencode_json(target)
    update_env_default(target)
    print(f"✓ Modelo por defecto cambiado a: imryyr-llm/{target}")
    print("  - opencode.json actualizado (model + small_model)")
    print("  - .env DEFAULT_MODEL actualizado")
    print("\nReinicia OpenCode (si estaba corriendo) para que tome el cambio.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
