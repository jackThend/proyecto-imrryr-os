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
        # Antes este mensaje daba por hecho que el proveedor era Gemini y
        # culpaba a su cuota gratuita. Con otro proveedor activo eso confunde:
        # la causa más común ahí es simplemente una consulta que encadena
        # varias llamadas al modelo (delegar en subagentes) y tarda más.
        return (
            "El modelo tardó demasiado en responder y corté la espera. Suele pasar "
            "con preguntas que obligan a consultar varios agentes a la vez; probar de "
            "nuevo, o preguntar por una cosa a la vez, normalmente funciona. "
            "Si usas una cuenta gratuita (por ejemplo Gemini, con 20 consultas al día), "
            "otra causa probable es que se agotara la cuota: en ese caso el proveedor "
            "deja la petición colgada en vez de avisar, y se renueva cerca de las 4-5 AM. "
            "Puedes cambiar de cuenta en Ajustes > Cuentas de IA."
        )
    # Algunas excepciones (ej. las de httpx al cortarse la conexión con
    # OpenCode) traen str() vacío, y el mensaje quedaba en "Algo falló
    # hablando con los agentes:" sin decir nada. En ese caso al menos se
    # nombra el tipo, que es lo único que hay.
    detalle = str(e).strip() or type(e).__name__
    return f"Algo falló hablando con los agentes: {detalle}"
