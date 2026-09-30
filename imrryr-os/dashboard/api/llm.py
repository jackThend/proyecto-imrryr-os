"""Completado de texto de un solo turno para el propio backend (sin chat).

Existe porque algunos endpoints (ej. la extracción de minutas de Reuniones)
necesitan "pregúntale algo al modelo y dame el texto", y antes hablaban directo
con LiteLLM: eso deja de servir para las cuentas de un proveedor nativo de
OpenCode (Zen gratis), que no pasan por LiteLLM. Acá se decide según la ruta de
la cuenta activa (ver config/cuentas_ia.py::modelo_para_agente).
"""
from __future__ import annotations

import os

import httpx

from api import deps


async def completar_texto(prompt: str, system: str = "", agente: str = "reuniones", timeout: float = 90.0) -> str:
    """Devuelve el texto de la respuesta, o "" si el modelo no respondió."""
    ruta = deps._ruta_modelo()

    if ruta["providerID"] == "imrryr-llm":
        puerto = int(os.environ.get("LITELLM_PORT") or 4000)
        mensajes = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.post(
                f"http://localhost:{puerto}/v1/chat/completions",
                json={"model": ruta["modelID"], "messages": mensajes, "temperature": 0.1},
            )
        if r.status_code != 200:
            return ""
        return r.json()["choices"][0]["message"]["content"] or ""

    # Ruta nativa de OpenCode: una sesión descartable con el agente indicado.
    base = f"http://localhost:{deps._opencode_port()}"
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(
            f"{base}/session", headers=deps._opencode_auth_headers(),
            json={"agent": agente, "model": {"id": ruta["modelID"], "providerID": ruta["providerID"]}},
        )
        r.raise_for_status()
        cuerpo = r.json()
        sid = cuerpo.get("data", {}).get("id") or cuerpo.get("id")
        texto = f"{system}\n\n{prompt}" if system else prompt
        r = await client.post(
            f"{base}/session/{sid}/message", headers=deps._opencode_auth_headers(),
            json={"agent": agente, "model": ruta, "parts": [{"type": "text", "text": texto}]},
        )
        r.raise_for_status()
        return "".join(p.get("text", "") for p in r.json().get("parts", []) if p.get("type") == "text")
