#!/usr/bin/env python3
"""
enviar_alerta.py — Skill: Envía una alerta del Guardia de Seguridad
=====================================================================
Registra siempre la alerta en vault/alertas.log. Si el gateway de WhatsApp
(gateway/webhook_server.py) está corriendo, además intenta reenviarla al
celular vía POST http://localhost:5050/api/gateway/enviar (endpoint
introducido junto con el gateway dual local/cloud). Si el gateway no está
activo, se hace fallback silencioso al log local.

Uso:
    python skills/enviar_alerta.py --mensaje "Scraper de fondos atascado 6 min" --nivel warning
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ALERTAS_LOG = ROOT / "vault" / "alertas.log"
GATEWAY_URL = "http://localhost:5050/api/gateway/enviar"


def log(msg: str) -> None:
    print(f"[enviar_alerta] {msg}", flush=True)


def enviar_alerta(mensaje: str, nivel: str = "warning") -> dict:
    ALERTAS_LOG.parent.mkdir(parents=True, exist_ok=True)
    registro = f"[{datetime.now().isoformat(timespec='seconds')}] ({nivel}) {mensaje}\n"
    with ALERTAS_LOG.open("a", encoding="utf-8") as f:
        f.write(registro)

    enviado_whatsapp = False
    try:
        import httpx
        r = httpx.post(GATEWAY_URL, json={"texto": f"[Guardia] {mensaje}"}, timeout=5)
        enviado_whatsapp = r.status_code == 200
    except Exception:
        pass

    return {"registrado": True, "enviado_whatsapp": enviado_whatsapp}


def main() -> int:
    ap = argparse.ArgumentParser(description="Envía/registra una alerta del Guardia de Seguridad")
    ap.add_argument("--mensaje", type=str, required=True)
    ap.add_argument("--nivel", type=str, default="warning", choices=["info", "warning", "critical"])
    args = ap.parse_args()

    resultado = enviar_alerta(args.mensaje, args.nivel)
    log(json.dumps(resultado, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
