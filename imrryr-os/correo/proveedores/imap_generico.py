#!/usr/bin/env python3
"""
imap_generico.py — Conector de correo vía IMAP/SMTP estándar
================================================================
Cubre cualquier proveedor que soporte IMAP con contraseña de aplicación
(correo de hosting propio/página web, Outlook, etc.) — la opción de menor
fricción para "cualquier proveedor" sin necesitar OAuth por cada uno.

La cuenta (dict) debe traer: imap_host, imap_port (default 993), smtp_host,
smtp_port (default 587), usuario, password.

NOTA: no se pudo probar contra un servidor real en esta sesión (no hay
credenciales IMAP disponibles) — revisar contra un servidor real antes de
confiar en él para producción, igual que Gmail en la Fase 3.
"""
from __future__ import annotations

import email
import imaplib
import smtplib
from email.mime.text import MIMEText
from email.utils import parseaddr


def log(msg: str) -> None:
    print(f"[imap_generico] {msg}", flush=True)


def _extraer_cuerpo(msg: email.message.Message) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain" and not part.get("Content-Disposition"):
                payload = part.get_payload(decode=True)
                if payload:
                    return payload.decode(errors="replace")
        return ""
    payload = msg.get_payload(decode=True)
    return payload.decode(errors="replace") if payload else ""


def leer_correo(cuenta: dict, max_resultados: int = 5, query: str = "") -> list[dict]:
    try:
        imap = imaplib.IMAP4_SSL(cuenta["imap_host"], cuenta.get("imap_port", 993))
    except (OSError, imaplib.IMAP4.error) as e:
        log(f"No se pudo conectar a {cuenta.get('imap_host')}: {e}")
        return []
    try:
        imap.login(cuenta["usuario"], cuenta["password"])
        imap.select("INBOX")

        criterio = f'(SUBJECT "{query}")' if query else "ALL"
        _, datos = imap.search(None, criterio)
        ids = datos[0].split()[-max_resultados:] if datos and datos[0] else []

        resultados = []
        for mid in reversed(ids):
            _, msg_datos = imap.fetch(mid, "(RFC822)")
            if not msg_datos or not msg_datos[0]:
                continue
            msg = email.message_from_bytes(msg_datos[0][1])
            resultados.append({
                "id": mid.decode(),
                "remitente": msg.get("From", ""),
                "asunto": msg.get("Subject", ""),
                "fecha": msg.get("Date", ""),
                "cuerpo": _extraer_cuerpo(msg)[:1000],
            })
        return resultados
    except (OSError, imaplib.IMAP4.error) as e:
        log(f"Error leyendo bandeja: {e}")
        return []
    finally:
        try:
            imap.logout()
        except Exception:
            pass


def archivar_correo(cuenta: dict, mensaje_id: str) -> dict:
    try:
        imap = imaplib.IMAP4_SSL(cuenta["imap_host"], cuenta.get("imap_port", 993))
    except (OSError, imaplib.IMAP4.error) as e:
        return {"ok": False, "error": f"no se pudo conectar: {e}"}
    try:
        imap.login(cuenta["usuario"], cuenta["password"])
        imap.select("INBOX")
        mid = mensaje_id.encode()
        imap.store(mid, "+FLAGS", "\\Seen")
        try:
            imap.copy(mid, "Archive")
            imap.store(mid, "+FLAGS", "\\Deleted")
            imap.expunge()
        except Exception as e:
            # No todos los servidores tienen una carpeta "Archive" con ese
            # nombre exacto — al menos queda marcado como leído.
            log(f"No se pudo mover a Archive (queda marcado como leído): {e}")
        return {"ok": True}
    except (OSError, imaplib.IMAP4.error) as e:
        return {"ok": False, "error": f"error de IMAP: {e}"}
    finally:
        try:
            imap.logout()
        except Exception:
            pass


def enviar_correo(cuenta: dict, destinatario: str, asunto: str, cuerpo: str) -> dict:
    """Solo la debe llamar enviar_borrador() (dashboard, tras aprobación humana) — nunca el agente."""
    msg = MIMEText(cuerpo, "plain", "utf-8")
    msg["Subject"] = asunto
    msg["From"] = cuenta["usuario"]
    msg["To"] = destinatario

    try:
        with smtplib.SMTP(cuenta["smtp_host"], cuenta.get("smtp_port", 587)) as smtp:
            smtp.starttls()
            smtp.login(cuenta["usuario"], cuenta["password"])
            smtp.sendmail(cuenta["usuario"], [parseaddr(destinatario)[1] or destinatario], msg.as_string())
        return {"ok": True}
    except (OSError, smtplib.SMTPException) as e:
        return {"ok": False, "error": f"no se pudo enviar: {e}"}
