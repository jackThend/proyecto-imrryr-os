#!/usr/bin/env python3
"""
smoke_test.py - Prueba E2E de Fase 1 (1.3.8)
==============================================
Verifica que toda la cadena funciona de extremo a extremo:

  OpenCode serve (:4040)
      -> config/opencode.json (provider imrryr-llm)
      -> LiteLLM (:4000)
      -> Gemini API (gemini-2.5-flash)

Flujo:
  1. Verifica que ambos servicios estén vivos (healthcheck).
  2. Crea una sesión en OpenCode.
  3. Envía un prompt ("responde solo: PONG").
  4. Confirma que la respuesta llega enroutada vía LiteLLM.
  5. NO detiene los servicios (los deja para uso real); usar shutdown.py.

Requisitos: LiteLLM y OpenCode deben estar corriendo (python scripts/startup.py).

Uso:
    python scripts/smoke_test.py
"""
from __future__ import annotations

import base64
import os
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / "config" / ".env"

LITELLM_PORT = 4000
OPENCODE_PORT = 4040
OPENCODE_PASSWORD = "imrryr-local-pass"


def log(msg: str) -> None:
    print(f"[smoke] {msg}", flush=True)


def basic_auth(password: str) -> dict[str, str]:
    token = base64.b64encode(f"opencode:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}", "Content-Type": "application/json"}


def check_services(port_llm: int, port_oc: int, password: str) -> bool:
    """Healthcheck de los dos servicios."""
    log("1/3 - Healthchecks…")
    try:
        r = httpx.get(f"http://localhost:{port_llm}/health/liveliness", timeout=5)
        assert r.status_code == 200, f"LiteLLM HTTP {r.status_code}"
        log(f"   V LiteLLM  HTTP {r.status_code}")
    except Exception as e:
        log(f"   X LiteLLM no responde: {e}")
        log("   Arranca con: python scripts/startup.py")
        return False

    try:
        r = httpx.get(f"http://localhost:{port_oc}/api/health",
                      headers=basic_auth(password), timeout=5)
        assert r.status_code == 200, f"OpenCode HTTP {r.status_code}"
        log(f"   V OpenCode HTTP {r.status_code}")
    except Exception as e:
        log(f"   X OpenCode no responde: {e}")
        return False
    return True


def create_session(port_oc: int, password: str, model: str) -> str:
    """Crea una sesión en OpenCode y devuelve su ID."""
    log("2/3 - Creando sesión en OpenCode…")
    r = httpx.post(
        f"http://localhost:{port_oc}/session",
        headers=basic_auth(password),
        json={"agent": "build", "model": {"id": model, "providerID": "imrryr-llm"}},
        timeout=15,
    )
    r.raise_for_status()
    data = r.json()
    # OpenCode devuelve { data: { id: ... } } o { id: ... }
    sid = (data.get("data", {}).get("id") or data.get("id"))
    if not sid:
        raise RuntimeError(f"Respuesta inesperada al crear sesión: {data}")
    log(f"   V Sesión {sid}")
    return sid


def send_prompt(port_oc: int, password: str, sid: str, model: str, message: str) -> str:
    """Envía un prompt (endpoint síncrono /session/{id}/message) y devuelve el texto de respuesta."""
    log("3/3 - Enviando prompt (OpenCode -> LiteLLM -> Gemini)…")
    r = httpx.post(
        f"http://localhost:{port_oc}/session/{sid}/message",
        headers=basic_auth(password),
        json={
            "agent": "build",
            "model": {"providerID": "imrryr-llm", "modelID": model},
            "parts": [{"type": "text", "text": message}],
        },
        timeout=120,
    )
    r.raise_for_status()
    data = r.json()
    respuesta = "".join(p.get("text", "") for p in data.get("parts", []) if p.get("type") == "text")
    if not respuesta:
        raise RuntimeError(f"Sin texto de respuesta en parts: {str(data)[:300]}")
    return respuesta


def main() -> int:
    if ENV_FILE.exists():
        load_dotenv(ENV_FILE)
    port_llm = int(os.environ.get("LITELLM_PORT", LITELLM_PORT))
    port_oc = int(os.environ.get("OPENCODE_PORT") or OPENCODE_PORT)
    password = os.environ.get("OPENCODE_SERVER_PASSWORD", OPENCODE_PASSWORD)
    # Alias de la cuenta de IA activa; sin default de proveedor concreto.
    model = "imrryr-activo"

    log("=== Smoke test E2E Fase 1 - Imrryr OS ===")
    if not check_services(port_llm, port_oc, password):
        return 1

    try:
        sid = create_session(port_oc, password, model)
        reply = send_prompt(port_oc, password, sid, model,
                            "Responde únicamente con la palabra: PONG")
        log(f"   V Respuesta recibida: «{reply.strip()[:80]}»")
    except Exception as e:
        log(f"   X Falló la llamada E2E: {e}")
        return 1

    ok = "PONG" in reply.upper()
    log("=" * 60)
    log("VVV E2E OK - Cadena completa operativa:" if ok else "⚠ Respuesta inesperada.")
    log(f"     OpenCode(:{port_oc}) -> LiteLLM(:{port_llm}) -> Gemini")
    log("=" * 60)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
