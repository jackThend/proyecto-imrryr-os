#!/usr/bin/env python3
"""
tts_local.py — Skill: Text-to-Speech local con pyttsx3 o edge-tts
===================================================================
Fase 3.2: Convierte texto a archivo de audio (.mp3/.wav).
Usa edge-tts si está disponible, fallback a pyttsx3.

Uso:
    python skills/tts_local.py --text "Hola, esto es una prueba"
    python skills/tts_local.py --text "Resumen ejecutivo" --output resumen.mp3 --voz "es-CL"
"""
from __future__ import annotations

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AUDIO_DIR = ROOT / "docs" / "audios"

# edge-tts exige el nombre completo de la voz (ej. "es-CL-CatalinaNeural"),
# no el código de locale a secas. Mapeamos los locales documentados en
# skills/tts_local.mcp.json a una voz neural real por defecto.
VOICE_MAP = {
    "es-CL": "es-CL-CatalinaNeural",
    "es-ES": "es-ES-ElviraNeural",
    "es-MX": "es-MX-DaliaNeural",
    "en-US": "en-US-AriaNeural",
}


def log(msg: str) -> None:
    print(f"[tts] {msg}", flush=True)


def _resolver_voz(voz: str) -> str:
    if "Neural" in voz:
        return voz
    return VOICE_MAP.get(voz, VOICE_MAP["es-CL"])


def text_to_speech(texto: str, output: str | None = None, voz: str = "es-CL") -> str:
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)

    if output is None:
        safe = texto.lower().replace(" ", "_")[:20]
        output = str(AUDIO_DIR / f"tts_{safe}.mp3")

    try:
        import edge_tts
        import asyncio

        async def _synthesize():
            communicate = edge_tts.Communicate(texto, _resolver_voz(voz))
            await communicate.save(output)

        asyncio.run(_synthesize())
        log(f"Audio generado: {output} (edge-tts)")
        return output
    except ImportError:
        pass
    except Exception as e:
        log(f"WARN: edge-tts falló ({e}), probando pyttsx3...")

    try:
        import pyttsx3
        engine = pyttsx3.init()
        engine.save_to_file(texto, output)
        engine.runAndWait()
        log(f"Audio generado: {output} (pyttsx3)")
        return output
    except ImportError:
        log("WARN: ni edge-tts ni pyttsx3 instalados. Instala: pip install edge-tts")
        return ""


def main() -> int:
    ap = argparse.ArgumentParser(description="Texto a voz local")
    ap.add_argument("--text", type=str, required=True)
    ap.add_argument("--output", type=str, default=None)
    ap.add_argument("--voz", type=str, default="es-CL")
    args = ap.parse_args()

    output = text_to_speech(args.text, args.output, args.voz)
    if output:
        print(output)
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
