#!/usr/bin/env python3
"""
errores_ia.py — Traducción de errores técnicos de la cadena de IA a español claro
==================================================================================
NO es una skill de agente (deliberadamente sin .mcp.json — el auto-discovery
de mcp_server/skills_server.py solo registra archivos con manifiesto). Vive en
skills/ porque es el único directorio presente en el sys.path tanto del
dashboard como del gateway: dentro del gateway, gateway/config.py le hace
sombra al paquete config/ de la raíz, así que ahí `from config.x import ...`
no funcionaría.

La cadena dashboard/WhatsApp → OpenCode → LiteLLM → proveedor de IA puede
fallar en varios eslabones, y cada uno habla en stacktrace. Este módulo es el
único lugar donde se decide qué le decimos al usuario en cada caso — lo usan
tanto el chat del dashboard (dashboard/server.py) como el gateway de WhatsApp
(gateway/webhook_server.py), para que ambos canales cuenten la misma historia.

El caso más importante es la cuota gratuita de Gemini (20 consultas/día para
todo el sistema): cuando se agota, el proveedor no siempre responde 429 — a
veces simplemente deja la petición colgada hasta que vence el timeout. Por
eso el timeout se traduce mencionando la cuota como causa probable, no como
un error genérico de red.
"""
from __future__ import annotations


def humanizar_error_ia(e: Exception) -> str:
    """Devuelve un mensaje en español claro para el usuario final (sin stacktrace)."""
    import httpx

    if isinstance(e, (httpx.ConnectError, httpx.ConnectTimeout)):
        return (
            "No pude hablar con el motor de agentes (OpenCode no está corriendo). "
            "Levanta los servicios con `python scripts/startup.py` y vuelve a intentar."
        )
    if isinstance(e, httpx.HTTPStatusError) and e.response.status_code == 429:
        return (
            "Se agotó la cuota diaria del proveedor de IA. Si usas la cuenta gratuita "
            "de Gemini son 20 consultas al día para todo el sistema; se renuevan cerca "
            "de las 4-5 AM (medianoche en hora del Pacífico). También puedes activar "
            "otra cuenta en Ajustes > Cuentas de IA."
        )
    if isinstance(e, (httpx.ReadTimeout, httpx.WriteTimeout, httpx.PoolTimeout)):
        return (
            "El modelo tardó demasiado en responder y corté la espera. Si usas la "
            "cuenta gratuita de Gemini, lo más probable es que se agotara la cuota "
            "diaria (20 consultas) — en ese caso el proveedor deja la petición "
            "colgada en vez de avisar. Puedes esperar a que se renueve (cerca de las "
            "4-5 AM) o activar otra cuenta en Ajustes > Cuentas de IA."
        )
    return f"Algo falló hablando con los agentes: {e}"
