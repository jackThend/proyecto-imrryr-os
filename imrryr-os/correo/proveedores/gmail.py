#!/usr/bin/env python3
"""
gmail.py — Conector de Gmail para el Agente Secretario (lectura + archivo + envío)
=====================================================================================
Usa su PROPIO archivo de credenciales/token (gmail_secretario_*), separado del
que usa skills/leer_gmail.py (solo lectura, para el Financiero) — cada agente
pide el consentimiento OAuth con el alcance mínimo que necesita.

El scope de Gmail no permite "crear borrador sin poder enviar": gmail.send
es necesario para que el botón "Enviar" del dashboard funcione. La barrera
de seguridad real no es el scope de OAuth, es que esta función enviar_correo()
NUNCA se expone como tool MCP (ver skills/correo.py) — solo la llama
enviar_borrador(), que solo se ejecuta cuando el humano hace clic en el
dashboard. El agente jamás tiene una herramienta para invocarla directo.

Requiere: config/gmail_secretario_credentials.json (inactivo sin ese archivo,
igual que skills/leer_gmail.py).
"""
from __future__ import annotations

import base64
import pickle
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
TOKEN_FILE = ROOT / "config" / "gmail_secretario_token.pickle"
CREDS_FILE = ROOT / "config" / "gmail_secretario_credentials.json"
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send",
]


def log(msg: str) -> None:
    print(f"[correo.gmail] {msg}", flush=True)


def _get_service():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials  # noqa: F401 (usado al deserializar el pickle)
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    creds = None
    if TOKEN_FILE.exists():
        with TOKEN_FILE.open("rb") as f:
            creds = pickle.load(f)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDS_FILE.exists():
                log(f"ERROR: no existe {CREDS_FILE}. Sigue: https://developers.google.com/gmail/api/quickstart/python")
                return None
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)
        with TOKEN_FILE.open("wb") as f:
            pickle.dump(creds, f)

    return build("gmail", "v1", credentials=creds)


def _extraer_cuerpo(payload: dict) -> str:
    if "parts" in payload:
        for part in payload["parts"]:
            if part.get("mimeType") == "text/plain":
                data = part.get("body", {}).get("data", "")
                if data:
                    return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
        return ""
    data = payload.get("body", {}).get("data", "")
    return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace") if data else ""


def leer_correo(cuenta: dict, max_resultados: int = 5, query: str = "") -> list[dict]:
    service = _get_service()
    if not service:
        return []

    resultados = service.users().messages().list(userId="me", maxResults=max_resultados, q=query).execute()
    mensajes = resultados.get("messages", [])
    correos = []
    for msg in mensajes:
        detalle = service.users().messages().get(userId="me", id=msg["id"], format="full").execute()
        headers = {h["name"]: h["value"] for h in detalle["payload"].get("headers", [])}
        correos.append({
            "id": msg["id"],
            "remitente": headers.get("From", ""),
            "asunto": headers.get("Subject", ""),
            "fecha": headers.get("Date", ""),
            "cuerpo": _extraer_cuerpo(detalle["payload"])[:1000],
        })
    return correos


def archivar_correo(cuenta: dict, mensaje_id: str) -> dict:
    service = _get_service()
    if not service:
        return {"ok": False, "error": "Gmail no configurado (sin credenciales)"}
    # "Archivar" en Gmail = quitar la etiqueta INBOX.
    service.users().messages().modify(userId="me", id=mensaje_id, body={"removeLabelIds": ["INBOX"]}).execute()
    return {"ok": True}


def enviar_correo(cuenta: dict, destinatario: str, asunto: str, cuerpo: str) -> dict:
    """Solo la debe llamar enviar_borrador() (dashboard, tras aprobación humana) — nunca el agente."""
    import email.mime.text

    service = _get_service()
    if not service:
        return {"ok": False, "error": "Gmail no configurado (sin credenciales)"}

    mensaje = email.mime.text.MIMEText(cuerpo)
    mensaje["to"] = destinatario
    mensaje["subject"] = asunto
    crudo = base64.urlsafe_b64encode(mensaje.as_bytes()).decode()
    service.users().messages().send(userId="me", body={"raw": crudo}).execute()
    return {"ok": True}
