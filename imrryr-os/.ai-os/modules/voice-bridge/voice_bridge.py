#!/usr/bin/env python3
"""voice-bridge — Módulo de Control por Voz y Streaming (Tanda VII).

Arquitectura de decisión (2026-08-30):
  - Primario: Groq Whisper (whisper-large-v3) — ultra-baja latencia.
  - Fallback: faster-whisper local (skills/transcribir_audio.py) — offline.
  - Síntesis: edge-tts (skills/tts_local.py) — ya instalado.

La clave GROQ_API_KEY se lee de config/.env. Sin clave o sin red,
el fallback local cubre el turno. Cero dependencias nuevas.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
AI_OS = ROOT / ".ai-os"
CONFIG = AI_OS / "config.json"
ENV_FILE = ROOT / "config" / ".env"

SKILLS_DIR = ROOT / "skills"
sys.path.insert(0, str(ROOT))


def log(msg: str) -> None:
    print(f"[voice-bridge] {msg}", flush=True)


def cargar_config() -> dict:
    if CONFIG.exists():
        return json.loads(CONFIG.read_text(encoding="utf-8"))
    return {}


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


def transcribir_groq(ruta_audio: str) -> str:
    """Transcripción vía Groq (OpenAI-compatible). Devuelve '' si falla."""
    key = _groq_api_key()
    if not key:
        log("GROQ_API_KEY no configurada — usando fallback local")
        return ""
    try:
        import httpx

        audio = Path(ruta_audio)
        if not audio.exists():
            log(f"ERROR: archivo no encontrado: {ruta_audio}")
            return ""
        response = httpx.post(
            "https://api.groq.com/openai/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {key}"},
            files={"file": (audio.name, audio.read_bytes(), "audio/ogg")},
            data={"model": "whisper-large-v3", "language": "es"},
            timeout=30.0,
        )
        response.raise_for_status()
        texto = response.json().get("text", "")
        log(f"Transcripción Groq: {texto[:100]}...")
        return texto
    except Exception as e:
        log(f"WARN: Groq falló ({e.__class__.__name__}: {e}) — usando fallback local")
        return ""


def transcribir_local(ruta_audio: str) -> str:
    """Fallback local: delega en skills/transcribir_audio.py (faster-whisper)."""
    from skills.transcribir_audio import transcribir

    texto = transcribir(ruta_audio, modelo="tiny")
    log(f"Transcripción local: {texto[:100]}...")
    return texto


def transcribir(ruta_audio: str) -> dict:
    """Transcribe con Groq; si falla, usa faster-whisper local."""
    texto = transcribir_groq(ruta_audio)
    motor = "groq"
    if not texto:
        texto = transcribir_local(ruta_audio)
        motor = "faster-whisper-local"
    return {"texto": texto, "motor": motor}


def sintetizar(texto: str, salida: str | None = None, voz: str = "es-CL") -> str:
    """Síntesis de voz: delega en skills/tts_local.py (edge-tts → pyttsx3)."""
    from skills.tts_local import text_to_speech

    return text_to_speech(texto, salida, voz)


ACCIONES = {
    "registrar gasto": {"modulo": "skills/inyectar_gasto.py", "tipo": "skill"},
    "ver finanzas": {"ruta": "/api/finanzas", "tipo": "dashboard"},
    "listar tareas": {"modulo": "skills/pendientes.py", "tipo": "skill"},
    "enviar mensaje": {"ruta": "/api/gateway/enviar", "tipo": "gateway"},
    "respaldo": {"modulo": "scripts/respaldo_db.py", "tipo": "script"},
    "estado": {"ruta": "/api/status", "tipo": "dashboard"},
}


def procesar_comando_voz(comando: str) -> dict:
    """Enruta un comando transcrito a la acción del OS correspondiente."""
    comando = comando.lower().strip()
    for keyword, accion in ACCIONES.items():
        if keyword in comando:
            return {"comando": comando, "accion": accion, "status": "enrutado"}
    return {"comando": comando, "accion": None, "status": "sin_match"}


def turno_completo(ruta_audio: str) -> dict:
    """Ciclo completo: transcribir → enrutar → sintetizar confirmación."""
    resultado = transcribir(ruta_audio)
    if not resultado["texto"]:
        return {"status": "sin_transcripcion", "motor": resultado["motor"]}
    enrutado = procesar_comando_voz(resultado["texto"])
    respuesta = "Comando recibido." if enrutado["accion"] else "Comando no reconocido."
    audio_out = sintetizar(respuesta)
    return {
        "status": "completado",
        "motor": resultado["motor"],
        "transcripcion": resultado["texto"],
        "enrutado": enrutado,
        "audio_respuesta": audio_out,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="voice-bridge: comando por voz")
    ap.add_argument("--audio", type=str, required=True, help="Ruta al archivo de audio")
    ap.add_argument("--sin-voz", action="store_true", help="No sintetizar respuesta")
    args = ap.parse_args()

    resultado = turno_completo(args.audio)
    if args.sin_voz:
        resultado.pop("audio_respuesta", None)
    print(json.dumps(resultado, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())