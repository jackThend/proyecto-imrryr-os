#!/usr/bin/env python3
"""voice-bridge — Módulo de Control por Voz y Streaming (Tanda VII).

Arquitectura de decisión (2026-08-30):
  - La transcripción vive en skills/transcribir_audio.py (Groq primario,
    faster-whisper fallback): este módulo delega, no duplica.
  - La síntesis vive en skills/tts_local.py (edge-tts → pyttsx3).
  - Este módulo aporta el enrutamiento de comandos del OS y el ciclo
    completo de un turno de voz (transcribir → enrutar → confirmar).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
AI_OS = ROOT / ".ai-os"
CONFIG = AI_OS / "config.json"

sys.path.insert(0, str(ROOT))


def log(msg: str) -> None:
    print(f"[voice-bridge] {msg}", flush=True)


def cargar_config() -> dict:
    if CONFIG.exists():
        return json.loads(CONFIG.read_text(encoding="utf-8"))
    return {}


def transcribir(ruta_audio: str) -> dict:
    """Delega en la skill compartida (Groq → faster-whisper local)."""
    from skills.transcribir_audio import transcribir_con_motor

    resultado = transcribir_con_motor(ruta_audio)
    log(f"Transcripción ({resultado['motor']}): {resultado['texto'][:100]}...")
    return resultado


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


def turno_completo(ruta_audio: str, sintetizar_respuesta: bool = True) -> dict:
    """Ciclo completo: transcribir → enrutar → sintetizar confirmación."""
    resultado = transcribir(ruta_audio)
    if not resultado["texto"]:
        return {"status": "sin_transcripcion", "motor": resultado["motor"]}
    enrutado = procesar_comando_voz(resultado["texto"])
    respuesta = "Comando recibido." if enrutado["accion"] else "Comando no reconocido."
    audio_out = sintetizar(respuesta) if sintetizar_respuesta else ""
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

    resultado = turno_completo(args.audio, sintetizar_respuesta=not args.sin_voz)
    print(json.dumps(resultado, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())