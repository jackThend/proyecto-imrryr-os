"""API: Reuniones, Minutas y Canvas Conceptual Infinito.

Gestiona transcripciones de audio (en vivo o archivos), análisis de acuerdos
y tareas, persistencia del grafo conceptual y volcado a agenda/pendientes.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any

import httpx
from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import JSONResponse

from api import deps
from skills.gestionar_reuniones import (
    consultar_reuniones,
    generar_mapa_conceptual,
    guardar_reunion,
    volcar_tareas_agenda,
)
from skills.transcribir_audio import transcribir

router = APIRouter()
AUDIO_DIR = deps.ROOT / "vault" / "reuniones"
AUDIO_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/api/reuniones/upload")
async def subir_o_grabar_audio(
    archivo: UploadFile = File(...),
    titulo: str = Form(default=""),
    participantes: str = Form(default=""),
):
    """Sube un archivo de audio (.mp3, .wav, .webm, .ogg) o blob del navegador y lo transcribe."""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        nombre_limpio = Path(archivo.filename or "reunion.webm").name
        nombre_destino = f"{timestamp}_{nombre_limpio}"
        destino = AUDIO_DIR / nombre_destino

        contenido = await archivo.read()
        destino.write_bytes(contenido)

        # Transcribir audio usando Whisper (Groq primario, local fallback)
        texto_transcrito = transcribir(str(destino))

        titulo_final = titulo.strip() or f"Reunión {datetime.now().strftime('%d/%m/%Y %H:%M')}"

        # Guardar registro preliminar en BD
        res_bd = guardar_reunion(
            titulo=titulo_final,
            fecha=date.today().isoformat(),
            participantes=participantes,
            audio_ruta=str(destino),
            transcripcion_cruda=texto_transcrito,
        )

        return {
            "ok": True,
            "reunion_id": res_bd.get("id"),
            "titulo": titulo_final,
            "audio_url": f"/reuniones_audio/{nombre_destino}",
            "transcripcion": texto_transcrito,
        }
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@router.get("/api/reuniones")
async def listar_reuniones(fecha: str = "", query: str = "", limite: int = 50):
    """Obtiene el historial de reuniones."""
    return consultar_reuniones(
        accion="buscar" if query else "listar",
        query=query,
        fecha=fecha,
        limite=limite,
    )


@router.get("/api/reuniones/{reunion_id}")
async def detalle_reunion(reunion_id: int):
    """Obtiene el detalle completo de una reunión con su minuta y mapa conceptual."""
    res = consultar_reuniones(accion="detalle", reunion_id=reunion_id)
    if not res.get("ok"):
        return JSONResponse(res, status_code=404)
    return res


@router.post("/api/reuniones")
async def crear_o_actualizar_reunion(datos: dict[str, Any]):
    """Crea o actualiza los metadatos de una reunión."""
    return guardar_reunion(
        titulo=datos.get("titulo", ""),
        fecha=datos.get("fecha", ""),
        duracion_min=int(datos.get("duracion_min", 0)),
        participantes=datos.get("participantes", ""),
        audio_ruta=datos.get("audio_ruta", ""),
        transcripcion_cruda=datos.get("transcripcion_cruda", ""),
        resumen_ejecutivo=datos.get("resumen_ejecutivo", ""),
        conclusiones=datos.get("conclusiones", ""),
        acuerdos_tareas=datos.get("acuerdos_tareas", "[]"),
        mapa_conceptual_json=datos.get("mapa_conceptual_json", "{}"),
        reunion_id=datos.get("id"),
    )


async def _extraer_analisis_llm(transcripcion: str, titulo: str) -> dict[str, Any]:
    """Intenta procesar la transcripción con LiteLLM/OpenCode o recurre a heurística estructurada."""
    prompt = f"""Eres el Agente de Reuniones de Imrryr OS.
Analiza la siguiente transcripción de una reunión de trabajo titulada "{titulo}".
Genera estrictamente un objeto JSON con la siguiente estructura:
{{
  "resumen_ejecutivo": "Síntesis en 2 a 4 párrafos de alto nivel con los temas discutidos.",
  "conclusiones": "Lista de acuerdos clave, hitos alcanzados y decisiones finales tomadas.",
  "tareas": [
    {{
      "tarea": "Descripción clara de la acción requerida",
      "responsable": "Nombre del asignado o 'Sin asignar'",
      "fecha_limite": "YYYY-MM-DD o vacía si no se mencionó"
    }}
  ]
}}

Transcripción de la reunión:
{transcripcion[:8000]}
"""
    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            r = await client.post(
                "http://localhost:4000/v1/chat/completions",
                json={
                    "model": "imrryr-activo",
                    "messages": [
                        {"role": "system", "content": "Responde solo con el JSON requerido, sin markdown adicional."},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.2,
                },
            )
            if r.status_code == 200:
                data = r.json()
                contenido = data["choices"][0]["message"]["content"]
                # Extraer JSON limpio
                match = re.search(r"\{.*\}", contenido, re.DOTALL)
                if match:
                    return json.loads(match.group(0))
    except Exception:
        pass

    # Heurística local de respaldo (si el LLM no está activo o no respondió a tiempo)
    parrafos = [p.strip() for p in transcripcion.split("\n") if len(p.strip()) > 20]
    resumen = "\n\n".join(parrafos[:3]) if parrafos else transcripcion[:300]
    conclusiones = "• Se revisaron los objetivos principales discutidos.\n• Se definieron próximos pasos y acuerdos de equipo."
    tareas = []

    # Extraer posibles líneas con compromisos o tareas
    for p in parrafos:
        p_low = p.lower()
        if any(w in p_low for w in ["acuerdo", "tarea", "hacer", "pendiente", "compromiso", "entregar", "revisar"]):
            partes = p.split(":")
            responsable = partes[0].strip() if len(partes) > 1 else "Equipo"
            desc = partes[1].strip() if len(partes) > 1 else p
            tareas.append({
                "tarea": desc[:100],
                "responsable": responsable[:30],
                "fecha_limite": date.today().isoformat(),
                "agendada": False,
            })
            if len(tareas) >= 5:
                break

    if not tareas:
        tareas.append({
            "tarea": "Revisar minuta y validar compromisos",
            "responsable": "Participantes",
            "fecha_limite": date.today().isoformat(),
            "agendada": False,
        })

    return {
        "resumen_ejecutivo": resumen,
        "conclusiones": conclusiones,
        "tareas": tareas,
    }


@router.post("/api/reuniones/{reunion_id}/procesar")
async def procesar_reunion(reunion_id: int):
    """Procesa la transcripción cruda con el Agente para generar resumen, acuerdos y mapa conceptual."""
    det = consultar_reuniones(accion="detalle", reunion_id=reunion_id)
    if not det.get("ok"):
        return JSONResponse(det, status_code=404)

    reunion = det["reunion"]
    transcripcion = reunion.get("transcripcion_cruda") or ""
    if not transcripcion.strip():
        return JSONResponse({"ok": False, "error": "La reunión no tiene transcripción que procesar"}, status_code=400)

    # 1. Extraer minuta estructurada
    analisis = await _extraer_analisis_llm(transcripcion, reunion.get("titulo", "Reunión"))
    resumen = analisis.get("resumen_ejecutivo", "")
    conclusiones = analisis.get("conclusiones", "")
    tareas = analisis.get("tareas", [])

    # 2. Generar grafo de mapa conceptual
    res_mapa = generar_mapa_conceptual(
        reunion_id=reunion_id,
        titulo=reunion.get("titulo", ""),
        resumen=resumen,
        conclusiones=conclusiones,
        tareas=tareas,
    )

    # 3. Guardar todo en la reunión
    guardar_reunion(
        titulo=reunion.get("titulo", ""),
        resumen_ejecutivo=resumen,
        conclusiones=conclusiones,
        acuerdos_tareas=tareas,
        mapa_conceptual_json=res_mapa.get("mapa", {}),
        reunion_id=reunion_id,
    )

    return consultar_reuniones(accion="detalle", reunion_id=reunion_id)


@router.put("/api/reuniones/{reunion_id}/mapa")
async def guardar_mapa_canvas(reunion_id: int, datos: dict[str, Any]):
    """Guarda las modificaciones interactivas del mapa conceptual hechas en el canvas infinito."""
    mapa = datos.get("mapa") or {}
    return guardar_reunion(
        titulo="",
        mapa_conceptual_json=mapa,
        reunion_id=reunion_id,
    )


@router.post("/api/reuniones/{reunion_id}/agendar-tareas")
async def agendar_tareas_reunion(reunion_id: int, datos: dict[str, Any]):
    """Vuelca las tareas seleccionadas a la Agenda (eventos) y/o lista de Pendientes."""
    indices = datos.get("indices")
    agendar_eventos = bool(datos.get("agendar_en_eventos", True))
    agendar_pendientes = bool(datos.get("agendar_en_pendientes", True))
    return volcar_tareas_agenda(
        reunion_id=reunion_id,
        indices_tareas=indices,
        agendar_en_eventos=agendar_eventos,
        agendar_en_pendientes=agendar_pendientes,
    )


@router.delete("/api/reuniones/{reunion_id}")
async def eliminar_reunion(reunion_id: int):
    """Elimina una reunión de la base de datos."""
    import sqlite3
    conn = sqlite3.connect(str(deps.DB_PATH))
    try:
        conn.execute("DELETE FROM reuniones WHERE id = ?", (reunion_id,))
        conn.commit()
        return {"ok": True, "reunion_id": reunion_id}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)
    finally:
        conn.close()
