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

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import JSONResponse

from api import deps
from api.llm import completar_texto
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
    """Crea o actualiza los metadatos de una reunión.

    Se usa `datos.get(campo)` SIN default (=> None cuando el campo no viene
    en el body) para que guardar_reunion distinga "no me mandaron este campo"
    de "me mandaron explícitamente un valor vacío" — si aquí se pusiera un
    default de "" / "[]" / "{}", cualquier POST parcial (ej. solo cambiar el
    título) borraría en silencio el resto de columnas de la reunión.
    """
    duracion = datos.get("duracion_min")
    return guardar_reunion(
        titulo=datos.get("titulo", ""),
        fecha=datos.get("fecha"),
        duracion_min=int(duracion) if duracion is not None else None,
        participantes=datos.get("participantes"),
        audio_ruta=datos.get("audio_ruta"),
        transcripcion_cruda=datos.get("transcripcion_cruda"),
        resumen_ejecutivo=datos.get("resumen_ejecutivo"),
        conclusiones=datos.get("conclusiones"),
        acuerdos_tareas=datos.get("acuerdos_tareas"),
        mapa_conceptual_json=datos.get("mapa_conceptual_json"),
        reunion_id=datos.get("id"),
    )


async def _extraer_analisis_llm(transcripcion: str, titulo: str) -> dict[str, Any]:
    """Extrae resumen, roles, conclusiones y tareas por persona, filtrando saludos y ruido."""
    prompt = f"""Eres el Agente Especialista de Reuniones y Minutas Ejecutivas de Imrryr OS.
Analiza la siguiente transcripción de una reunión de trabajo titulada "{titulo}".

REGLAS ESTRICTAS DE EXTRACCIÓN:
1. NUNCA tomes saludos, bienvenidas, cortesías ni frases introductorias (ej: "Buenos días equipo", "Hola a todos", "Gracias por venir", "Bienvenidos...") como tareas ni como conclusiones. Esos saludos NO son tareas.
2. Identifica a los participantes mencionados y sus aportes o responsabilidades.
3. Separa y agrupa las tareas por PERSONA ESPECÍFICA (responsable individual). La tarea debe ser la acción concreta que le corresponde a esa persona.
4. Las conclusiones deben ser acuerdos firmes, decisiones estratégicas o hitos aprobados.
5. El resumen ejecutivo debe ser una síntesis coherente de 2 a 3 párrafos de alto nivel con los temas discutidos.

Genera estrictamente un objeto JSON con esta estructura exacta (sin texto ni markdown adicional):
{{
  "resumen_ejecutivo": "Síntesis en 2 a 3 párrafos profesionales con los objetivos y temas abordados.",
  "participantes_roles": [
    {{"nombre": "Nombre de la persona", "rol_o_aporte": "Descripción de su aporte o responsabilidad"}}
  ],
  "conclusiones": "• Acuerdo o decisión clave 1\\n• Acuerdo o decisión clave 2",
  "tareas": [
    {{
      "responsable": "Nombre específico de la persona (ej: Carlos, Sofía, Equipo)",
      "tarea": "Acción concreta y redactada con claridad",
      "fecha_limite": "YYYY-MM-DD o vacía si no se mencionó fecha"
    }}
  ]
}}

Transcripción de la reunión:
{transcripcion[:10000]}
"""
    try:
        contenido = await completar_texto(
            prompt,
            system="Eres un asistente extractor de minutas. Responde ÚNICAMENTE con el objeto JSON solicitado.",
        )
        match = re.search(r"\{.*\}", contenido, re.DOTALL)
        if match:
            parsed = json.loads(match.group(0))
            # Validar que no tenga saludos en tareas
            tareas_limpias = []
            for t in parsed.get("tareas", []):
                t_desc = t.get("tarea", "").strip()
                t_low = t_desc.lower()
                if not any(t_low.startswith(s) for s in ["buenos días", "buenas tardes", "hola", "bienvenidos"]):
                    t["agendada"] = False
                    tareas_limpias.append(t)
            parsed["tareas"] = tareas_limpias
            return parsed
    except Exception:
        pass

    return _extraer_analisis_heuristico(transcripcion, titulo)


def _extraer_analisis_heuristico(transcripcion: str, titulo: str = "") -> dict[str, Any]:
    """Heurística estructurada de respaldo (offline / fallback inteligente)."""
    # 1. Separar en oraciones limpias
    oraciones = [
        s.strip()
        for s in re.split(r"[.!?]\s+|\n+", transcripcion)
        if s.strip() and len(s.strip()) > 8
    ]

    # 2. Filtrar saludos y cortesías de la lista de trabajo
    saludos_prefijos = [
        "buenos días", "buenas tardes", "buenas noches", "hola equipo",
        "hola a todos", "bienvenidos", "gracias por asistir", "gracias a todos",
        "en esta reunión vamos a", "estamos reunidos para",
    ]
    oraciones_utiles = [
        s for s in oraciones
        if not any(s.lower().startswith(p) for p in saludos_prefijos)
    ]

    tareas = []
    conclusiones_lista = []
    participantes_set = set()

    # Patrones de asignación de tareas a personas
    patron_persona_tarea = re.compile(
        r"(?P<quien>[A-ZÁÉÍÓÚ][a-záéíóú]+(?:\s+[A-ZÁÉÍÓÚ][a-záéíóú]+)?)\s+"
        r"(?:estará a cargo de|se encargará de|quedará a cargo de|preparará|revisará|enviará|desarrollará|diseñará|realizará|completará|liderará|debe|tiene que)\s+"
        r"(?P<que>.+)",
        re.IGNORECASE,
    )
    patron_tarea_general = re.compile(
        r"(?:queda como tarea pendiente|como tarea pendiente|tarea:\s*)(?:que\s+)?(?P<que>.+)",
        re.IGNORECASE,
    )
    patron_acuerdo = re.compile(
        r"(?:acordamos|aprobamos|decidimos|como acuerdo principal|como conclusión|se acuerda|se aprueba|se decide)\s+(?P<concl>.+)",
        re.IGNORECASE,
    )

    for o in oraciones_utiles:
        # Detectar acuerdos
        m_acuerdo = patron_acuerdo.search(o)
        if m_acuerdo:
            texto_c = m_acuerdo.group("concl").strip()
            conclusiones_lista.append(f"• {texto_c[:120]}")
            continue

        # Detectar tareas por persona
        m_persona = patron_persona_tarea.search(o)
        if m_persona:
            quien = m_persona.group("quien").strip().capitalize()
            que = m_persona.group("que").strip()
            # Limpiar cola de oración
            que = re.sub(r"\s+antes del.*|\s+el próximo.*", "", que, flags=re.IGNORECASE).strip()
            participantes_set.add(quien)
            tareas.append({
                "responsable": quien,
                "tarea": que[:110],
                "fecha_limite": date.today().isoformat(),
                "agendada": False,
            })
            continue

        # Detectar tarea general
        m_gen = patron_tarea_general.search(o)
        if m_gen:
            que_gen = m_gen.group("que").strip()
            tareas.append({
                "responsable": "Equipo",
                "tarea": que_gen[:110],
                "fecha_limite": date.today().isoformat(),
                "agendada": False,
            })
            continue

    if not conclusiones_lista:
        conclusiones_lista = [
            "• Se revisaron y acordaron los objetivos prioritarios del proyecto.",
            "• Se formalizaron los próximos pasos y el plan de entrega.",
        ]

    if not tareas:
        tareas.append({
            "responsable": "Participantes",
            "tarea": "Revisar minuta y validar compromisos de la reunión",
            "fecha_limite": date.today().isoformat(),
            "agendada": False,
        })

    # Resumen ejecutivo coherente
    resumen_candidatos = [o for o in oraciones_utiles if len(o) > 25][:3]
    resumen_texto = " ".join(resumen_candidatos) if resumen_candidatos else transcripcion[:350]

    return {
        "resumen_ejecutivo": resumen_texto,
        "conclusiones": "\n".join(conclusiones_lista),
        "participantes": ", ".join(sorted(participantes_set)) if participantes_set else "",
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


@router.put("/api/reuniones/{reunion_id}/transcripcion")
async def guardar_transcripcion_reunion(reunion_id: int, datos: dict[str, Any]):
    """Actualiza la transcripción cruda o editada por el usuario."""
    transcripcion = datos.get("transcripcion", "")
    return guardar_reunion(
        titulo="",
        transcripcion_cruda=transcripcion,
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


@router.post("/api/reuniones/{reunion_id}/imagen")
async def subir_imagen_canvas(reunion_id: int, archivo: UploadFile = File(...)):
    """Sube una imagen para insertarla como nodo visual en el canvas infinito."""
    try:
        img_dir = AUDIO_DIR / "imagenes"
        img_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        nombre_limpio = Path(archivo.filename or "imagen.png").name
        nombre_destino = f"{timestamp}_{nombre_limpio}"
        destino = img_dir / nombre_destino

        contenido = await archivo.read()
        destino.write_bytes(contenido)

        url_publica = f"/reuniones_audio/imagenes/{nombre_destino}"
        return {"ok": True, "url": url_publica, "nombre": nombre_limpio}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


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
