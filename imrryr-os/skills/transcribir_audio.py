#!/usr/bin/env python3
"""
transcribir_audio.py — Skill: Transcripción de audio con Whisper
================================================================
Fase 5.2: Toma un archivo .ogg/.mp3/.wav y lo transcribe a texto.

Arquitectura de decisión (2026-08-30):
  - Primario: Groq Whisper (whisper-large-v3) — ultra-baja latencia.
  - Fallback: faster-whisper local (offline) — sin clave o sin red.
Compartida por gateway/webhook_server.py (WhatsApp) y .ai-os/modules/
voice-bridge. La clave se lee de la env GROQ_API_KEY o de config/.env.

Uso:
    python skills/transcribir_audio.py --audio mensaje.ogg
    python skills/transcribir_audio.py --audio voz.wav --modelo tiny
    python skills/transcribir_audio.py --audio voz.wav --motor local
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / "config" / ".env"

GROQ_ENDPOINT = "https://api.groq.com/openai/v1/audio/transcriptions"


def log(msg: str) -> None:
    print(f"[transcribir] {msg}", flush=True)


def _groq_api_key() -> str:
    """Lee GROQ_API_KEY del entorno o de config/.env."""
    key = os.environ.get("GROQ_API_KEY", "")
    if key:
        return key
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            if line.startswith("GROQ_API_KEY="):
                return line.split("=", 1)[1].strip()
    return ""


def transcribir_groq(ruta_audio: str, lenguaje: str = "es") -> str:
    """Transcripción vía Groq. Devuelve '' si no hay clave, archivo o red."""
    key = _groq_api_key()
    if not key:
        log("GROQ_API_KEY no configurada — usando Whisper local")
        return ""
    path = Path(ruta_audio)
    if not path.exists():
        log(f"ERROR: archivo no encontrado: {ruta_audio}")
        return ""
    try:
        import httpx

        response = httpx.post(
            GROQ_ENDPOINT,
            headers={"Authorization": f"Bearer {key}"},
            files={"file": (path.name, path.read_bytes(), "audio/ogg")},
            data={"model": "whisper-large-v3", "language": lenguaje},
            timeout=30.0,
        )
        response.raise_for_status()
        texto = response.json().get("text", "")
        log(f"Transcripcion (Groq): {texto[:100]}...")
        return texto
    except Exception as e:
        log(f"WARN: Groq fallo ({e.__class__.__name__}) — usando Whisper local")
        return ""


def _transcribir_local(ruta_audio: str, modelo: str = "tiny") -> str:
    """Transcripción offline con faster-whisper. Devuelve '' si falla."""
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
        log(f"Transcripcion (local): {texto[:100]}...")
        return texto
    except ImportError:
        log("faster-whisper no instalado. Prueba: pip install faster-whisper")
        return ""


def transcribir(ruta_audio: str, modelo: str = "tiny", motor: str = "auto") -> str:
    """Transcribe un audio. motor: 'auto' (Groq→local), 'local' o 'groq'."""
    if motor in ("auto", "groq"):
        texto = transcribir_groq(ruta_audio)
        if texto:
            return texto
        if motor == "groq":
            return ""
    return _transcribir_local(ruta_audio, modelo)


def transcribir_con_motor(ruta_audio: str, modelo: str = "tiny", motor: str = "auto") -> dict:
    """Igual que transcribir() pero reporta qué motor respondió."""
    if motor in ("auto", "groq"):
        texto = transcribir_groq(ruta_audio)
        if texto:
            return {"texto": texto, "motor": "groq"}
        if motor == "groq":
            return {"texto": "", "motor": "groq"}
    texto = _transcribir_local(ruta_audio, modelo)
    return {"texto": texto, "motor": "faster-whisper-local"}


def transcribir_audio(audio: str, modelo: str = "tiny") -> dict:
    """Punto de entrada MCP (nombre = nombre de la skill, ver mcp_server/skills_server.py)."""
    return {"texto": transcribir(audio, modelo)}


def main() -> int:
    ap = argparse.ArgumentParser(description="Transcribe audio a texto")
    ap.add_argument("--audio", type=str, required=True)
    ap.add_argument("--modelo", type=str, default="tiny", choices=["tiny", "base", "small", "medium"])
    ap.add_argument("--motor", type=str, default="auto", choices=["auto", "groq", "local"])
    args = ap.parse_args()

    texto = transcribir(args.audio, args.modelo, args.motor)
    if texto:
        print(texto)
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())