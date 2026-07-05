#!/usr/bin/env python3
"""
whatsapp_cli.py — Cliente de línea de comandos para la Pasarela Móvil
======================================================================
Fase 5.1: Envía mensajes simulados al gateway y prueba la integración.

Uso:
    python gateway/whatsapp_cli.py --to "+56912345678" --text "Hola, recuerda comprar leche"
    python gateway/whatsapp_cli.py --audio "ruta/del/audio.ogg"
    python gateway/whatsapp_cli.py --listen   # modo escucha
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
GATEWAY_URL = "http://localhost:5050"


def log(msg: str) -> None:
    print(f"[wsp] {msg}", flush=True)


def enviar_texto(texto: str, destino: str = "simulador") -> dict:
    r = httpx.post(
        f"{GATEWAY_URL}/webhook/simular",
        json={"from": destino, "text": texto, "type": "texto"},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


def enviar_audio(ruta_audio: str, destino: str = "simulador") -> dict:
    r = httpx.post(
        f"{GATEWAY_URL}/webhook/simular",
        json={"from": destino, "text": f"[audio:{ruta_audio}]", "type": "audio"},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


def modo_escucha():
    """Modo interactivo: lee comandos desde stdin y los envía."""
    log("Modo escucha activo. Escribe mensajes (Ctrl+C para salir):")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            resp = enviar_texto(line)
            log(f"Enviado: {resp}")
        except Exception as e:
            log(f"Error: {e}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Cliente de la pasarela WhatsApp")
    ap.add_argument("--text", type=str, help="Texto a enviar")
    ap.add_argument("--to", type=str, default="simulador", help="Destinatario")
    ap.add_argument("--audio", type=str, help="Ruta de archivo de audio")
    ap.add_argument("--listen", action="store_true", help="Modo escucha interactivo")
    args = ap.parse_args()

    if args.listen:
        modo_escucha()
        return 0

    if args.audio:
        resp = enviar_audio(args.audio, args.to)
    elif args.text:
        resp = enviar_texto(args.text, args.to)
    else:
        ap.print_help()
        return 1

    log(json.dumps(resp, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
