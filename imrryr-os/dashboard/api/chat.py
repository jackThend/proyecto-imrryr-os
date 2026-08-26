"""API: Chat (usa una sesión real de OpenCode -> acceso a agentes y skills).

OpenCode expone dos familias de endpoints de sesión: `/api/session/...`
(asíncrona: /prompt solo admite el mensaje en una cola y hay que
esperar/consultar aparte) y `/session/...` (síncrona: POST .../message
devuelve la respuesta ya generada). Usamos la segunda porque es la que
realmente usa el CLI de OpenCode (`opencode run`) y no requiere hacer
polling.
"""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from api import deps

router = APIRouter()

# Una sesión de OpenCode por agente (proceso único, usuario único — coherente
# con el modelo local-first de Imrryr OS). Sin esto, hablar con "creativo" y
# luego con "build" en la misma sesión compartida podía confundir el contexto.
_opencode_sessions: dict[str, str] = {}


async def _get_or_create_session(client, agent: str) -> str:
    if agent in _opencode_sessions:
        return _opencode_sessions[agent]

    r = await client.post(
        f"http://localhost:{deps._opencode_port()}/session",
        headers=deps._opencode_auth_headers(),
        json={"agent": agent, "model": {"id": deps._modelo_activo(), "providerID": "imrryr-llm"}},
        timeout=15,
    )
    r.raise_for_status()
    data = r.json()
    sid = data.get("data", {}).get("id") or data.get("id")
    if not sid:
        raise RuntimeError(f"Respuesta inesperada al crear sesión: {data}")
    _opencode_sessions[agent] = sid
    return sid


async def _esperar_texto_final(client, sid: str, intentos: int = 8, espera: float = 1.5) -> str:
    """Cuando el agente encadena llamadas a herramientas (tool -> tool -> texto),
    el POST /session/{id}/message puede devolver antes de que el mensaje final
    con texto exista todavía — la acción de las herramientas ya se ejecutó, solo
    falta que redacte la respuesta. Se sondea la lista de mensajes de la sesión
    unos segundos hasta encontrar el último turno del asistente con texto."""
    import asyncio

    for _ in range(intentos):
        r = await client.get(
            f"http://localhost:{deps._opencode_port()}/session/{sid}/message",
            headers=deps._opencode_auth_headers(),
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
            break  # el más reciente ya se revisó y no tiene texto; esperar y reintentar
        await asyncio.sleep(espera)
    return ""


@router.post("/api/chat")
async def chat(request: Request):
    import httpx

    body = await request.json()
    mensaje = body.get("mensaje", "")
    agente = body.get("agente", "build")

    try:
        async with httpx.AsyncClient() as client:
            sid = await _get_or_create_session(client, agente)
            r = await client.post(
                f"http://localhost:{deps._opencode_port()}/session/{sid}/message",
                headers=deps._opencode_auth_headers(),
                json={
                    "agent": agente,
                    "model": {"providerID": "imrryr-llm", "modelID": deps._modelo_activo()},
                    "parts": [{"type": "text", "text": mensaje}],
                },
                # 300s y no 120: una pregunta que obliga a delegar en varios
                # subagentes encadena varias llamadas al modelo. Medido con
                # kimi-k2.7-code vía OpenCode GO, un resumen de cuatro dominios
                # tardó 108s y una consulta de agenda 123s — con el límite
                # anterior esa última moría por timeout aunque el modelo estaba
                # respondiendo bien.
                timeout=deps.chat_timeout_seconds(),
            )
            r.raise_for_status()
            data = r.json()

            from uso_ia import registrar_uso
            registrar_uso("dashboard", agente)

            respuesta = "".join(p.get("text", "") for p in data.get("parts", []) if p.get("type") == "text")
            if not respuesta:
                respuesta = await _esperar_texto_final(client, sid)

        if not respuesta:
            herramientas = [p.get("tool") for p in data.get("parts", []) if p.get("type") == "tool"]
            respuesta = f"Listo, usé: {', '.join(herramientas)}." if herramientas else "(sin respuesta de texto)"

        return {"respuesta": respuesta, "session_id": sid}
    except Exception as e:
        # La sesión de este agente pudo quedar inválida (ej. OpenCode se reinició); se recrea en el próximo intento.
        _opencode_sessions.pop(agente, None)
        from errores_ia import humanizar_error_ia
        return JSONResponse({"error": humanizar_error_ia(e)}, status_code=500)
