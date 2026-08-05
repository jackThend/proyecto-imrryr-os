#!/usr/bin/env python3
"""
webhook_server.py — Servidor Webhook para la Pasarela Móvil (Fase 5)
=======================================================================
Punto único de entrada/salida de WhatsApp, sin importar qué conector esté
activo (ver gateway/config.py):

  - Vía Local (whatsapp-web.js + QR, sidecar Node en gateway/whatsapp_local/):
    el sidecar empuja mensajes entrantes a POST /webhook/local y este
    servidor le pide que envíe salientes vía POST a su propio /send.
  - Cloud API oficial de Meta: Meta empuja mensajes a POST /webhook/whatsapp
    y este servidor envía salientes directo a la Graph API.

Uso:
    python gateway/webhook_server.py              # :5050 por defecto
    python gateway/webhook_server.py --port 5050

Endpoints:
    POST /webhook/whatsapp     → Mensajes entrantes (Cloud API de Meta)
    POST /webhook/local        → Mensajes entrantes (sidecar Node local)
    POST /webhook/simular      → Simula un mensaje entrante (CLI/tests)
    GET  /webhook/health       → Healthcheck
    GET  /api/gateway/config   → Config activa (modo + credenciales, token oculto)
    POST /api/gateway/config   → Cambia modo/credenciales
    GET  /api/gateway/qr       → Proxy a la imagen QR del sidecar local
    POST /api/gateway/enviar   → Envía un WhatsApp genérico (usado por skills, ej. enviar_alerta)
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / "config" / ".env"
DB_PATH = ROOT / "vault" / "sqlite" / "imrryr.db"

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "skills"))
from config import guardar_config, leer_config, modo_activo  # noqa: E402

if ENV_FILE.exists():
    load_dotenv(ENV_FILE)

logging.basicConfig(level=logging.INFO, format="[gateway] %(message)s")
log = logging.getLogger("gateway")

LOCAL_SIDECAR_PORT = int(os.environ.get("WHATSAPP_LOCAL_PORT", 5051))
GRAPH_API_VERSION = "v20.0"

app = FastAPI(title="Imrryr Gateway", version="0.2.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def _init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS mensajes_entrantes (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            remitente   TEXT NOT NULL,
            texto       TEXT,
            tipo        TEXT DEFAULT 'texto',
            archivo_url TEXT,
            procesado   INTEGER DEFAULT 0,
            created_at  TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.commit()
    conn.close()


@app.on_event("startup")
async def startup():
    _init_db()
    log.info(f"Gateway webhook iniciado (modo activo: {modo_activo()})")


@app.get("/webhook/health")
async def health():
    return {"status": "ok", "service": "imrryr-gateway", "modo": modo_activo()}


# ---------------------------------------------------------------------------
# Ingesta unificada (cualquier conector entra por acá)
# ---------------------------------------------------------------------------
def _guardar_mensaje(remitente: str, texto: str, tipo: str, archivo_url: str | None) -> None:
    conn = sqlite3.connect(str(DB_PATH))
    try:
        conn.execute(
            "INSERT INTO mensajes_entrantes (remitente, texto, tipo, archivo_url) VALUES (?, ?, ?, ?)",
            (remitente, texto, tipo, archivo_url),
        )
        conn.commit()
    finally:
        conn.close()


def procesar_mensaje_entrante(remitente: str, texto: str, tipo: str = "texto", archivo_url: str | None = None) -> None:
    """Punto único de entrada para cualquier mensaje (Cloud API o sidecar local).

    Si es audio, lo transcribe antes de reenviarlo al agente. Si el usuario
    pide que se lo lean en audio, la respuesta se convierte a voz (TTS) y se
    reenvía como nota de voz en vez de texto.
    """
    texto_final = texto
    if tipo == "audio" and archivo_url:
        texto_final = _transcribir_audio_entrante(archivo_url)

    _guardar_mensaje(remitente, texto_final, tipo, archivo_url)
    log.info(f"Mensaje de {remitente} ({tipo}): {texto_final[:80]}")

    respuesta = _reenviar_a_opencode(texto_final)
    if not respuesta:
        return

    pide_audio = any(frase in texto_final.lower() for frase in ("léelo en audio", "leelo en audio", "léemelo", "leemelo"))
    if pide_audio:
        ruta_audio = _texto_a_audio(respuesta)
        if ruta_audio:
            enviar_mensaje_whatsapp(remitente, tipo="audio", archivo=ruta_audio)
            return

    enviar_mensaje_whatsapp(remitente, respuesta)


@app.post("/webhook/whatsapp")
async def webhook_whatsapp(request: Request):
    """Recibe mensajes desde WhatsApp Cloud API."""
    try:
        body = await request.json()
        log.info(f"Mensaje recibido (Cloud API): {json.dumps(body, ensure_ascii=False)[:300]}")
        entry = body.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})

        for msg in value.get("messages", []):
            from_number = msg.get("from", "desconocido")
            msg_type = msg.get("type", "text")
            if msg_type == "text":
                procesar_mensaje_entrante(from_number, msg.get("text", {}).get("body", ""), "texto")
            elif msg_type in ("audio", "voice"):
                audio_id = msg.get("audio", {}).get("id", "")
                procesar_mensaje_entrante(from_number, "[audio recibido]", "audio", audio_id)

        return {"status": "ok"}
    except Exception as e:
        log.error(f"Error procesando webhook: {e}")
        return {"status": "error", "detail": str(e)}


@app.post("/webhook/local")
async def webhook_local(data: dict[str, Any]):
    """Recibe mensajes desde el sidecar Node local (whatsapp-web.js)."""
    remitente = data.get("from", "desconocido")
    texto = data.get("text", "")
    tipo = data.get("type", "texto")
    archivo = data.get("file")
    procesar_mensaje_entrante(remitente, texto, tipo, archivo)
    return {"status": "ok"}


@app.post("/webhook/simular")
async def simular_mensaje(data: dict[str, Any]):
    """Endpoint para simular mensajes desde CLI o tests (no envía respuesta real)."""
    remitente = data.get("from", "simulador")
    texto = data.get("text", "")
    tipo = data.get("type", "texto")
    procesar_mensaje_entrante(remitente, texto, tipo)
    return {"status": "recibido", "from": remitente, "text": texto}


# ---------------------------------------------------------------------------
# Envío unificado (según el modo activo en gateway_config.json)
# ---------------------------------------------------------------------------
def enviar_mensaje_whatsapp(destinatario: str, texto: str = "", tipo: str = "text", archivo: str | None = None) -> bool:
    if modo_activo() == "cloud":
        return _enviar_cloud(destinatario, texto, tipo, archivo)
    return _enviar_local(destinatario, texto, tipo, archivo)


def _enviar_cloud(destinatario: str, texto: str = "", tipo: str = "text", archivo: str | None = None) -> bool:
    import httpx

    cfg = leer_config()["cloud"]
    if not cfg["phone_number_id"] or not cfg["access_token"]:
        log.warning("Cloud API no configurada (falta phone_number_id o access_token)")
        return False

    base = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{cfg['phone_number_id']}"
    headers = {"Authorization": f"Bearer {cfg['access_token']}"}

    try:
        if tipo == "audio" and archivo:
            with open(archivo, "rb") as f:
                r = httpx.post(
                    f"{base}/media",
                    headers=headers,
                    data={"messaging_product": "whatsapp", "type": "audio/ogg"},
                    files={"file": (Path(archivo).name, f, "audio/ogg")},
                    timeout=30,
                )
            r.raise_for_status()
            media_id = r.json().get("id")
            payload = {"messaging_product": "whatsapp", "to": destinatario, "type": "audio", "audio": {"id": media_id}}
        else:
            payload = {"messaging_product": "whatsapp", "to": destinatario, "type": "text", "text": {"body": texto}}

        r = httpx.post(f"{base}/messages", headers={**headers, "Content-Type": "application/json"}, json=payload, timeout=15)
        r.raise_for_status()
        return True
    except Exception as e:
        log.warning(f"Error enviando por Cloud API: {e}")
        return False


def _enviar_local(destinatario: str, texto: str = "", tipo: str = "text", archivo: str | None = None) -> bool:
    import httpx

    payload: dict[str, Any] = {"to": destinatario, "type": tipo}
    if tipo == "audio" and archivo:
        payload["file"] = archivo
    else:
        payload["text"] = texto

    try:
        r = httpx.post(f"http://localhost:{LOCAL_SIDECAR_PORT}/send", json=payload, timeout=15)
        r.raise_for_status()
        return True
    except Exception as e:
        log.warning(f"Error enviando por el sidecar local (¿está corriendo?): {e}")
        return False


# ---------------------------------------------------------------------------
# Audio: transcripción de entrada y TTS de salida (Fase 5.2/5.3)
# ---------------------------------------------------------------------------
def _transcribir_audio_entrante(referencia: str) -> str:
    """referencia: ruta local (modo local) o media_id de Meta (modo cloud)."""
    import transcribir_audio as _transcribir

    ruta_local = referencia
    if modo_activo() == "cloud":
        ruta_local = _descargar_audio_cloud(referencia)
        if not ruta_local:
            return "[audio recibido: no se pudo descargar]"

    try:
        return _transcribir.transcribir(ruta_local)
    except Exception as e:
        log.warning(f"Error transcribiendo audio: {e}")
        return "[audio recibido: transcripción no disponible]"


def _descargar_audio_cloud(media_id: str) -> str | None:
    import httpx

    cfg = leer_config()["cloud"]
    if not cfg["access_token"]:
        return None
    headers = {"Authorization": f"Bearer {cfg['access_token']}"}
    try:
        r = httpx.get(f"https://graph.facebook.com/{GRAPH_API_VERSION}/{media_id}", headers=headers, timeout=15)
        r.raise_for_status()
        media_url = r.json().get("url")
        if not media_url:
            return None
        r2 = httpx.get(media_url, headers=headers, timeout=30)
        r2.raise_for_status()
        destino = ROOT / ".run" / f"audio_{media_id}.ogg"
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(r2.content)
        return str(destino)
    except Exception as e:
        log.warning(f"Error descargando audio de Cloud API: {e}")
        return None


def _texto_a_audio(texto: str) -> str | None:
    import tts_local as _tts

    try:
        return _tts.text_to_speech(texto)
    except Exception as e:
        log.warning(f"Error generando audio TTS: {e}")
        return None


# ---------------------------------------------------------------------------
# Puente con OpenCode
# ---------------------------------------------------------------------------
def _esperar_texto_final(port: int, headers: dict, sid: str, intentos: int = 8, espera: float = 1.5) -> str:
    """Cuando el agente encadena llamadas a herramientas (tool -> tool -> texto),
    el POST /session/{id}/message puede devolver antes de que el mensaje final
    con texto exista todavía — la acción de las herramientas ya se ejecutó, solo
    falta que redacte la respuesta. Se sondea la sesión unos segundos hasta
    encontrar el último turno del asistente con texto."""
    import time

    import httpx

    for _ in range(intentos):
        r = httpx.get(
            f"http://localhost:{port}/session/{sid}/message",
            headers=headers,
            params={"order": "desc", "limit": 5},
            timeout=15,
        )
        r.raise_for_status()
        cuerpo = r.json()
        mensajes = cuerpo.get("data", []) if isinstance(cuerpo, dict) else cuerpo
        for msg in mensajes:
            if msg.get("info", {}).get("role") != "assistant":
                continue
            texto = "".join(p.get("text", "") for p in msg.get("parts", []) if p.get("type") == "text")
            if texto:
                return texto
            break
        time.sleep(espera)
    return ""


def _reenviar_a_opencode(texto: str) -> str:
    """Reenvía el texto al motor de OpenCode y devuelve la respuesta del agente.

    Usa los endpoints síncronos `/session` + `/session/{id}/message` (no los
    `/api/session/...`, que solo admiten el mensaje en cola y requieren
    polling aparte) — son los mismos que usa `opencode run` internamente.
    """
    import base64
    import httpx

    password = os.environ.get("OPENCODE_SERVER_PASSWORD", "imryyr-local-pass")
    port = int(os.environ.get("OPENCODE_PORT", 4040))
    # Alias estable de LiteLLM que SIEMPRE apunta a la cuenta de IA activa
    # (Ajustes > Cuentas de IA). Antes esto caía a "gemini-flash" por defecto,
    # lo que rompía la neutralidad de modelos: WhatsApp hablaba con Gemini
    # aunque el usuario hubiera elegido otro proveedor. Sin default: si no hay
    # cuenta activa, el sistema lo dice en vez de asumir un proveedor.
    modelo = "imrryr-activo"
    token = base64.b64encode(f"opencode:{password}".encode()).decode()
    headers = {"Authorization": f"Basic {token}", "Content-Type": "application/json"}

    try:
        r = httpx.post(
            f"http://localhost:{port}/session",
            headers=headers,
            json={"agent": "build", "model": {"id": modelo, "providerID": "imryyr-llm"}},
            timeout=15,
        )
        r.raise_for_status()
        sid = r.json().get("data", {}).get("id") or r.json().get("id", "")
        if not sid:
            return ""

        r = httpx.post(
            f"http://localhost:{port}/session/{sid}/message",
            headers=headers,
            json={
                "agent": "build",
                "model": {"providerID": "imryyr-llm", "modelID": modelo},
                "parts": [{"type": "text", "text": f"[WhatsApp] {texto}"}],
            },
            timeout=120,
        )
        r.raise_for_status()
        data = r.json()

        from uso_ia import registrar_uso
        registrar_uso("whatsapp", "build")

        respuesta = "".join(p.get("text", "") for p in data.get("parts", []) if p.get("type") == "text")
        if not respuesta:
            respuesta = _esperar_texto_final(port, headers, sid)
        return respuesta
    except Exception as e:
        log.warning(f"No se pudo reenviar a OpenCode: {e}")
        # Antes se devolvía "" y el usuario de WhatsApp no recibía NADA (la
        # experiencia "parece que se colgó"). Ahora al menos se le explica
        # qué pasó en su idioma, con la cuota de Gemini como causa probable.
        from errores_ia import humanizar_error_ia
        return humanizar_error_ia(e)


# ---------------------------------------------------------------------------
# API: configuración del gateway (selector Local/Cloud desde el dashboard)
# ---------------------------------------------------------------------------
def _ocultar_token(cfg: dict[str, Any]) -> dict[str, Any]:
    cfg = json.loads(json.dumps(cfg))  # copia profunda, nunca mutar el original
    token = cfg["cloud"].get("access_token", "")
    cfg["cloud"]["access_token"] = ("*" * 6 + token[-4:]) if token else ""
    return cfg


@app.get("/api/gateway/config")
async def get_gateway_config():
    return _ocultar_token(leer_config())


@app.post("/api/gateway/config")
async def set_gateway_config(data: dict[str, Any]):
    return _ocultar_token(guardar_config(data))


@app.get("/api/gateway/qr")
async def get_gateway_qr():
    """Proxy a la imagen QR del sidecar local (solo aplica en modo local)."""
    import httpx

    try:
        r = httpx.get(f"http://localhost:{LOCAL_SIDECAR_PORT}/qr", timeout=5)
        r.raise_for_status()
        return Response(content=r.content, media_type="image/png")
    except Exception:
        return JSONResponse({"error": "QR no disponible (¿está corriendo el sidecar local?)"}, status_code=503)


@app.post("/api/gateway/enviar")
async def api_enviar_generico(data: dict[str, Any]):
    """Envío genérico usado por skills que no conocen el modo activo (ej. enviar_alerta)."""
    destinatario = data.get("destinatario") or os.environ.get("WHATSAPP_ADMIN_NUMBER", "")
    texto = data.get("texto", "")
    if not destinatario:
        return JSONResponse({"error": "sin destinatario (configura WHATSAPP_ADMIN_NUMBER en .env)"}, status_code=400)
    ok = enviar_mensaje_whatsapp(destinatario, texto)
    return {"enviado": ok}


def main():
    import argparse
    ap = argparse.ArgumentParser(description="Servidor webhook del gateway")
    ap.add_argument("--port", type=int, default=5050)
    args = ap.parse_args()

    log.info(f"Gateway webhook en http://localhost:{args.port}")
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="info")


if __name__ == "__main__":
    main()
