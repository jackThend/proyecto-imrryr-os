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
from fastapi.responses import JSONResponse, StreamingResponse

from api import deps

router = APIRouter()

# Una sesión de OpenCode por agente (proceso único, usuario único — coherente
# con el modelo local-first de Imrryr OS). Sin esto, hablar con "creativo" y
# luego con "build" en la misma sesión compartida podía confundir el contexto.
_opencode_sessions: dict[str, str] = {}


async def _get_or_create_session(client, agent: str) -> str:
    if agent in _opencode_sessions:
        return _opencode_sessions[agent]

    ruta = deps._ruta_modelo()
    r = await client.post(
        f"http://localhost:{deps._opencode_port()}/session",
        headers=deps._opencode_auth_headers(),
        json={"agent": agent, "model": {"id": ruta["modelID"], "providerID": ruta["providerID"]}},
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


def _guardar_mensaje_db(sesion_id: str, agente: str, rol: str, texto: str, herramientas: str | None = None) -> None:
    if not deps.DB_PATH.exists():
        return
    import sqlite3
    try:
        conn = sqlite3.connect(str(deps.DB_PATH))
        conn.execute(
            "INSERT INTO mensajes_chat (sesion_id, agente, rol, texto, herramientas) VALUES (?, ?, ?, ?, ?)",
            (sesion_id, agente, rol, texto, herramientas),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


@router.get("/api/chat/historial/{agente}")
async def get_historial(agente: str, limite: int = 50):
    """Devuelve los últimos mensajes persistidos para el agente especificado."""
    if not deps.DB_PATH.exists():
        return {"mensajes": []}
    import sqlite3
    try:
        conn = sqlite3.connect(str(deps.DB_PATH))
        conn.row_factory = sqlite3.Row
        cur = conn.execute(
            "SELECT rol, texto, herramientas, created_at FROM mensajes_chat WHERE agente = ? ORDER BY id DESC LIMIT ?",
            (agente, limite),
        )
        filas = [dict(r) for r in cur.fetchall()]
        conn.close()
        filas.reverse()
        return {"mensajes": filas}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.delete("/api/chat/historial/{agente}")
async def borrar_historial(agente: str):
    """Borra el historial persistido y resetea la sesión activa con ese agente."""
    if not deps.DB_PATH.exists():
        return {"ok": True}
    import sqlite3
    try:
        conn = sqlite3.connect(str(deps.DB_PATH))
        conn.execute("DELETE FROM mensajes_chat WHERE agente = ?", (agente,))
        conn.commit()
        conn.close()
        _opencode_sessions.pop(agente, None)
        return {"ok": True}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/api/chat")
async def chat(request: Request):
    import httpx

    body = await request.json()
    mensaje = body.get("mensaje", "")
    agente_default = "asistente" if (deps.AGENTES_DIR / "agente_asistente.yaml").exists() else "build"
    agente = body.get("agente") or agente_default

    try:
        async with httpx.AsyncClient() as client:
            sid = await _get_or_create_session(client, agente)
            _guardar_mensaje_db(sid, agente, "user", mensaje)

            r = await client.post(
                f"http://localhost:{deps._opencode_port()}/session/{sid}/message",
                headers=deps._opencode_auth_headers(),
                json={
                    "agent": agente,
                    "model": deps._ruta_modelo(),
                    "parts": [{"type": "text", "text": mensaje}],
                },
                timeout=deps.chat_timeout_seconds(),
            )
            r.raise_for_status()
            data = r.json()

            from uso_ia import registrar_uso
            registrar_uso("dashboard", agente)

            respuesta = "".join(p.get("text", "") for p in data.get("parts", []) if p.get("type") == "text")
            if not respuesta:
                respuesta = await _esperar_texto_final(client, sid)

        herramientas = [p.get("tool") for p in data.get("parts", []) if p.get("type") == "tool"]
        if not respuesta:
            respuesta = f"Listo, usé: {', '.join(herramientas)}." if herramientas else "(sin respuesta de texto)"

        _guardar_mensaje_db(sid, agente, "assistant", respuesta, ", ".join(herramientas) if herramientas else None)

        return {"respuesta": respuesta, "session_id": sid}
    except Exception as e:
        # La sesión de este agente pudo quedar inválida; se recrea en el próximo intento.
        _opencode_sessions.pop(agente, None)
        from errores_ia import humanizar_error_ia
        return JSONResponse({"error": humanizar_error_ia(e)}, status_code=500)


@router.post("/api/chat/stream")
async def chat_stream(request: Request):
    """Endpoint de streaming en tiempo real (SSE) para el dashboard."""
    import asyncio
    import json
    import httpx

    body = await request.json()
    mensaje = body.get("mensaje", "")
    agente_default = "asistente" if (deps.AGENTES_DIR / "agente_asistente.yaml").exists() else "build"
    agente = body.get("agente") or agente_default

    async def event_generator():
        client = httpx.AsyncClient()
        try:
            sid = await _get_or_create_session(client, agente)
            _guardar_mensaje_db(sid, agente, "user", mensaje)

            yield f"data: {json.dumps({'tipo': 'start', 'session_id': sid})}\n\n"

            r = await client.post(
                f"http://localhost:{deps._opencode_port()}/session/{sid}/message",
                headers=deps._opencode_auth_headers(),
                json={
                    "agent": agente,
                    "model": deps._ruta_modelo(),
                    "parts": [{"type": "text", "text": mensaje}],
                },
                timeout=deps.chat_timeout_seconds(),
            )
            r.raise_for_status()
            data = r.json()

            from uso_ia import registrar_uso
            registrar_uso("dashboard", agente)

            herramientas = [p.get("tool") for p in data.get("parts", []) if p.get("type") == "tool" and p.get("tool")]
            for h in herramientas:
                yield f"data: {json.dumps({'tipo': 'tool', 'tool': h})}\n\n"

            respuesta = "".join(p.get("text", "") for p in data.get("parts", []) if p.get("type") == "text")
            if not respuesta:
                for _ in range(8):
                    await asyncio.sleep(1.2)
                    r_msg = await client.get(
                        f"http://localhost:{deps._opencode_port()}/session/{sid}/message",
                        headers=deps._opencode_auth_headers(),
                        params={"order": "desc", "limit": 5},
                        timeout=15,
                    )
                    r_msg.raise_for_status()
                    cuerpo = r_msg.json()
                    mensajes = cuerpo.get("data", []) if isinstance(cuerpo, dict) else cuerpo
                    for msg in mensajes:
                        if msg.get("info", {}).get("role") != "assistant":
                            continue
                        texto = "".join(p.get("text", "") for p in msg.get("parts", []) if p.get("type") == "text")
                        if texto:
                            respuesta = texto
                            break
                    if respuesta:
                        break

            if not respuesta:
                respuesta = f"Listo, usé: {', '.join(herramientas)}." if herramientas else "(sin respuesta de texto)"

            # Transmitir el texto en fragmentos para efecto de escritura fluido
            palabras = respuesta.split(" ")
            buffer = []
            for i, p in enumerate(palabras):
                buffer.append(p)
                if len(buffer) >= 2 or i == len(palabras) - 1:
                    chunk = " ".join(buffer) + (" " if i < len(palabras) - 1 else "")
                    yield f"data: {json.dumps({'tipo': 'token', 'texto': chunk})}\n\n"
                    buffer = []
                    await asyncio.sleep(0.015)

            _guardar_mensaje_db(sid, agente, "assistant", respuesta, ", ".join(herramientas) if herramientas else None)
            yield f"data: {json.dumps({'tipo': 'done', 'respuesta': respuesta, 'session_id': sid})}\n\n"
        except Exception as e:
            _opencode_sessions.pop(agente, None)
            from errores_ia import humanizar_error_ia
            yield f"data: {json.dumps({'tipo': 'error', 'error': humanizar_error_ia(e)})}\n\n"
        finally:
            await client.aclose()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )
