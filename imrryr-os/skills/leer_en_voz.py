#!/usr/bin/env python3
"""
leer_en_voz.py — Skill: Genera audio (TTS) para que el dashboard lo reproduzca
==================================================================================
Envuelve tts_local.text_to_speech() — no duplica la síntesis de voz, solo
decide DÓNDE queda el archivo (dashboard/static/audios/, servible por HTTP
en vez de docs/audios/ que es de uso interno/WhatsApp) y deja registrado
cuál es "el último audio" en config/ultimo_audio.json para que el dashboard
lo encuentre y lo reproduzca automáticamente tras la respuesta del agente.

Uso:
    python skills/leer_en_voz.py --texto "Hola, esto es una prueba"
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from tts_local import text_to_speech

ROOT = Path(__file__).resolve().parent.parent
AUDIOS_DIR = ROOT / "dashboard" / "static" / "audios"
ESTADO_PATH = ROOT / "config" / "ultimo_audio.json"


def log(msg: str) -> None:
    print(f"[leer_en_voz] {msg}", flush=True)


def leer_en_voz(texto: str, voz: str = "es-CL") -> dict:
    """Punto de entrada MCP."""
    if not texto:
        return {"ok": False, "error": "falta 'texto'"}

    AUDIOS_DIR.mkdir(parents=True, exist_ok=True)
    nombre = f"leer_{int(time.time() * 1000)}.mp3"
    ruta = AUDIOS_DIR / nombre

    resultado = text_to_speech(texto, output=str(ruta), voz=voz)
    if not resultado:
        return {"ok": False, "error": "no se pudo generar el audio (¿está instalado edge-tts?)"}

    url = f"/static/audios/{nombre}"
    ESTADO_PATH.parent.mkdir(parents=True, exist_ok=True)
    ESTADO_PATH.write_text(
        json.dumps({"url": url, "texto": texto[:200], "creado_at": time.time()}, ensure_ascii=False),
        encoding="utf-8",
    )
    log(f"Audio listo para el dashboard: {url}")
    return {"ok": True, "url": url}


def main() -> int:
    ap = argparse.ArgumentParser(description="Genera audio TTS para el dashboard")
    ap.add_argument("--texto", type=str, required=True)
    ap.add_argument("--voz", type=str, default="es-CL")
    args = ap.parse_args()

    resultado = leer_en_voz(args.texto, args.voz)
    print(resultado)
    return 0 if resultado.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
