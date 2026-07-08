#!/usr/bin/env python3
"""
transcribir_audio.py — Skill: Transcripción local de audio con Whisper
=======================================================================
Fase 5.2: Toma un archivo .ogg/.mp3/.wav y lo transcribe a texto
usando el modelo whisper.cpp o faster-whisper.

Uso:
    python skills/transcribir_audio.py --audio mensaje.ogg
    python skills/transcribir_audio.py --audio voz.wav --modelo tiny
"""
from __future__ import annotations

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def log(msg: str) -> None:
    print(f"[transcribir] {msg}", flush=True)


def transcribir(ruta_audio: str, modelo: str = "tiny") -> str:
    path = Path(ruta_audio)
    if not path.exists():
        log(f"ERROR: archivo no encontrado: {ruta_audio}")
        return ""

    try:
        from faster_whisper import WhisperModel

        log(f"Cargando modelo whisper-{modelo}...")
        model = WhisperModel(modelo, device="cpu", compute_type="int8")
        segments, info = model.transcribe(str(path), language="es")
        log(f"Detectado idioma: {info.language} ({info.language_probability:.2%})")

        texto = " ".join(seg.text for seg in segments)
        log(f"Transcripcion: {texto[:100]}...")
        return texto
    except ImportError:
        log("faster-whisper no instalado. Prueba: pip install faster-whisper")
        log("Fallback: devolviendo marcador de transcripcion.")
        return f"[transcripcion_pendiente:{path.name}]"


def transcribir_audio(audio: str, modelo: str = "tiny") -> dict:
    """Punto de entrada MCP (nombre = nombre de la skill, ver mcp_server/skills_server.py)."""
    return {"texto": transcribir(audio, modelo)}


def main() -> int:
    ap = argparse.ArgumentParser(description="Transcribe audio a texto")
    ap.add_argument("--audio", type=str, required=True)
    ap.add_argument("--modelo", type=str, default="tiny", choices=["tiny", "base", "small", "medium"])
    args = ap.parse_args()

    texto = transcribir(args.audio, args.modelo)
    if texto:
        print(texto)
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
