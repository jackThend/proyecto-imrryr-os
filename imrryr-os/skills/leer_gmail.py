#!/usr/bin/env python3
"""
leer_gmail.py — Skill: Lee correos del inbox de Gmail vía Gmail API
=====================================================================
Uso:
    python skills/leer_gmail.py --max-results 5
    python skills/leer_gmail.py --query "subject:banco" --max-results 10

Requiere: credentials.json de Gmail API en config/
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import pickle
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOKEN_FILE = ROOT / "config" / "gmail_token.pickle"
CREDS_FILE = ROOT / "config" / "gmail_credentials.json"
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def log(msg: str) -> None:
    print(f"[leer_gmail] {msg}", flush=True)


def get_service():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
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
                log(f"ERROR: No existe {CREDS_FILE}. Sigue: https://developers.google.com/gmail/api/quickstart/python")
                return None
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)
        with TOKEN_FILE.open("wb") as f:
            pickle.dump(creds, f)

    return build("gmail", "v1", credentials=creds)


def read_emails(max_results: int = 5, query: str = "") -> list[dict]:
    service = get_service()
    if not service:
        return []

    results = service.users().messages().list(userId="me", maxResults=max_results, q=query).execute()
    messages = results.get("messages", [])
    emails = []

    for msg in messages:
        msg_data = service.users().messages().get(userId="me", id=msg["id"], format="full").execute()
        headers = {h["name"]: h["value"] for h in msg_data["payload"].get("headers", [])}

        body = ""
        if "parts" in msg_data["payload"]:
            for part in msg_data["payload"]["parts"]:
                if part.get("mimeType") == "text/plain":
                    data = part["body"].get("data", "")
                    if data:
                        body = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
                    break
        elif msg_data["payload"]["body"].get("data"):
            body = base64.urlsafe_b64decode(msg_data["payload"]["body"]["data"]).decode("utf-8", errors="replace")

        emails.append({
            "id": msg["id"],
            "from": headers.get("From", ""),
            "subject": headers.get("Subject", ""),
            "date": headers.get("Date", ""),
            "snippet": msg_data.get("snippet", ""),
            "body": body[:1000],
        })

    return emails


def main() -> int:
    ap = argparse.ArgumentParser(description="Lee correos de Gmail")
    ap.add_argument("--max-results", type=int, default=5)
    ap.add_argument("--query", type=str, default="")
    args = ap.parse_args()

    emails = read_emails(args.max_results, args.query)
    log(f"Correos encontrados: {len(emails)}")
    for e in emails:
        print(f"  [{e['date']}] {e['from']}: {e['subject']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
