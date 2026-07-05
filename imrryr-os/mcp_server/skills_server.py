#!/usr/bin/env python3
"""
skills_server.py — Servidor MCP local que expone las skills de Imrryr OS
==========================================================================
Puente entre las skills atómicas de Python (imrryr-os/skills/*.py) y el
motor de OpenCode: cada skill se registra aquí como una tool MCP real,
invocable por los agentes según los permisos declarados en
config/opencode.json (agent.<nombre>.permission.skill).

Cada tool de este archivo corresponde 1:1 con un nombre de skill usado en
agentes/*.yaml (herramientas_permitidas) y con su manifiesto
skills/<nombre>.mcp.json.

Se registra en config/opencode.json bajo la clave "mcp" (esto lo hace
scripts/sync_agentes.py automáticamente). No se ejecuta a mano: lo arranca
OpenCode como subproceso stdio.
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "skills"))

from mcp.server.fastmcp import FastMCP  # noqa: E402

import consultar_memoria_vectorial as _rag  # noqa: E402
import crear_evento as _evento  # noqa: E402
import detener_proceso as _detener  # noqa: E402
import enviar_alerta as _alerta  # noqa: E402
import escribir_archivo as _escribir  # noqa: E402
import ejecutar_script as _ejecutar  # noqa: E402
import inyectar_gasto as _gasto  # noqa: E402
import leer_archivo as _leer  # noqa: E402
import leer_gmail as _gmail  # noqa: E402
import monitorear_procesos as _procesos  # noqa: E402
import recordatorios as _recordatorios  # noqa: E402
import scraper_fondos as _scraper  # noqa: E402
import tts_local as _tts  # noqa: E402
import transcribir_audio as _transcribir  # noqa: E402

mcp = FastMCP("imrryr")


@mcp.tool()
def inyectar_gasto(monto: float, comercio: str, categoria: str = "general", descripcion: str = "") -> dict:
    """Inserta un gasto en la base SQLite (Agente Financiero)."""
    return {"id": _gasto.insertar_gasto(monto, comercio, categoria, descripcion)}


@mcp.tool()
def leer_gmail(max_results: int = 5, query: str = "") -> list[dict]:
    """Lee correos de Gmail. Requiere config/gmail_credentials.json (inactivo sin credenciales)."""
    return _gmail.read_emails(max_results, query)


@mcp.tool()
def scraper_fondos(fuente: str | None = None) -> dict:
    """Busca fondos concursables en Sercotec/Corfo (Agente Investigador)."""
    return _scraper.buscar_fondos(fuente)


@mcp.tool()
def crear_evento(titulo: str, fecha: str | None = None, hora: str = "09:00", duracion: int = 60, descripcion: str = "") -> dict:
    """Genera un evento .ics de calendario (Agente Creativo/CRM)."""
    fecha_obj = date.fromisoformat(fecha) if fecha else date.today()
    ruta = _evento.generar_ics(titulo, fecha_obj, hora, duracion, False, descripcion)
    return {"archivo": ruta}


@mcp.tool()
def tts_local(text: str, voz: str = "es-CL") -> dict:
    """Convierte texto a un archivo de audio (TTS local)."""
    return {"archivo": _tts.text_to_speech(text, None, voz)}


@mcp.tool()
def transcribir_audio(audio: str, modelo: str = "tiny") -> dict:
    """Transcribe un archivo de audio a texto (Whisper local)."""
    return {"texto": _transcribir.transcribir(audio, modelo)}


@mcp.tool()
def recordatorios(crear: str | None = None, cuando: str | None = None, ejecutar: bool = False, listar: bool = False) -> dict:
    """Crea, lista o dispara recordatorios pendientes."""
    if crear and cuando:
        return {"creado": _recordatorios.crear_recordatorio(crear, cuando)}
    if ejecutar:
        return {"disparados": _recordatorios.ejecutar_vencidos()}
    if listar:
        return {"pendientes": _recordatorios.listar_pendientes()}
    return {"error": "especifica crear+cuando, ejecutar=true o listar=true"}


@mcp.tool()
def consultar_memoria_vectorial(query: str, n: int = 5) -> list[dict]:
    """Busca fragmentos relevantes en la memoria vectorial ChromaDB (Agente CRM)."""
    return _rag.consultar(query, n)


@mcp.tool()
def monitorear_procesos(timeout: int = 300) -> list[dict]:
    """Lista procesos monitoreados y marca los atascados (Guardia de Seguridad)."""
    return _procesos.listar_procesos(timeout)


@mcp.tool()
def detener_proceso(pid: int, forzar: bool = False) -> dict:
    """Detiene un proceso por PID (Guardia de Seguridad)."""
    return _detener.detener_proceso(pid, forzar)


@mcp.tool()
def enviar_alerta(mensaje: str, nivel: str = "warning") -> dict:
    """Registra y reenvía una alerta (Guardia de Seguridad)."""
    return _alerta.enviar_alerta(mensaje, nivel)


@mcp.tool()
def leer_archivo(ruta: str, max_chars: int = 5000) -> dict:
    """Lee un archivo dentro del sandbox del proyecto (Agente Build)."""
    return _leer.leer_archivo(ruta, max_chars)


@mcp.tool()
def escribir_archivo(ruta: str, contenido: str, sobrescribir: bool = True) -> dict:
    """Escribe un archivo dentro del sandbox del proyecto (Agente Build)."""
    return _escribir.escribir_archivo(ruta, contenido, sobrescribir)


@mcp.tool()
def ejecutar_script(script: str, args: list[str] | None = None, timeout: int = 60) -> dict:
    """Ejecuta un script Python dentro de scripts/ o skills/, sandboxed (Agente Build)."""
    return _ejecutar.ejecutar_script(script, args, timeout)


if __name__ == "__main__":
    mcp.run()
