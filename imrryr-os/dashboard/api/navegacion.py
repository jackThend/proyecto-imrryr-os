"""API: Navegación — último audio TTS y transcripción de voz (Whisper local)."""
from __future__ import annotations

import json
import time
from pathlib import Path

from fastapi import APIRouter, File, UploadFile

from api import deps

router = APIRouter()

ULTIMO_AUDIO_PATH = deps.ROOT / "config" / "ultimo_audio.json"
AUDIOS_TEMP_DIR = deps.ROOT / "vault" / "audios_temp"


@router.get("/api/navegacion/ultimo-audio")
async def get_ultimo_audio():
    if not ULTIMO_AUDIO_PATH.exists():
        return {"url": None}
    return json.loads(ULTIMO_AUDIO_PATH.read_text(encoding="utf-8"))


@router.post("/api/navegacion/transcribir")
async def transcribir_audio_navegacion(archivo: UploadFile = File(...)):
    from skills.transcribir_audio import transcribir

    AUDIOS_TEMP_DIR.mkdir(parents=True, exist_ok=True)
    extension = Path(archivo.filename).suffix or ".webm"
    ruta_temp = AUDIOS_TEMP_DIR / f"grabacion_{int(time.time() * 1000)}{extension}"
    ruta_temp.write_bytes(await archivo.read())
    try:
        texto = transcribir(str(ruta_temp))
        return {"ok": True, "texto": texto}
    finally:
        ruta_temp.unlink(missing_ok=True)
