#!/usr/bin/env python3
"""
gestionar_reuniones.py — Skill: Gestión de Reuniones y Minutas con Mapa Conceptual
===================================================================================
Registra reuniones transcritas, sintetiza conclusiones y tareas, construye
el grafo inicial del mapa conceptual interactivo y vuelca compromisos en
la Agenda y lista de Pendientes.

Uso:
    python skills/gestionar_reuniones.py --accion consultar
    python skills/gestionar_reuniones.py --accion guardar --titulo "Reunión de Estrategia"
"""
from __future__ import annotations

import argparse
import json
import math
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "vault" / "sqlite" / "imrryr.db"


def log(msg: str) -> None:
    print(f"[reuniones] {msg}", flush=True)


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def guardar_reunion(
    titulo: str,
    fecha: str = "",
    duracion_min: int = 0,
    participantes: str = "",
    audio_ruta: str = "",
    transcripcion_cruda: str = "",
    resumen_ejecutivo: str = "",
    conclusiones: str = "",
    acuerdos_tareas: str | list[dict[str, Any]] = "[]",
    mapa_conceptual_json: str | dict[str, Any] = "{}",
    reunion_id: int | None = None,
) -> dict[str, Any]:
    """Crea o actualiza una reunión en la base de datos de Imrryr OS."""
    if not titulo and not reunion_id:
        return {"ok": False, "error": "Se requiere un título o id de reunión"}

    fecha_final = fecha or date.today().isoformat()

    if isinstance(acuerdos_tareas, list):
        tareas_str = json.dumps(acuerdos_tareas, ensure_ascii=False)
    else:
        tareas_str = acuerdos_tareas or "[]"

    if isinstance(mapa_conceptual_json, dict):
        mapa_str = json.dumps(mapa_conceptual_json, ensure_ascii=False)
    else:
        mapa_str = mapa_conceptual_json or "{}"

    conn = _conn()
    try:
        if reunion_id:
            actualizaciones = []
            params: list[Any] = []
            if titulo:
                actualizaciones.append("titulo = ?")
                params.append(titulo)
            if fecha:
                actualizaciones.append("fecha = ?")
                params.append(fecha)
            if duracion_min:
                actualizaciones.append("duracion_min = ?")
                params.append(duracion_min)
            if participantes:
                actualizaciones.append("participantes = ?")
                params.append(participantes)
            if audio_ruta:
                actualizaciones.append("audio_ruta = ?")
                params.append(audio_ruta)
            if transcripcion_cruda:
                actualizaciones.append("transcripcion_cruda = ?")
                params.append(transcripcion_cruda)
            if resumen_ejecutivo:
                actualizaciones.append("resumen_ejecutivo = ?")
                params.append(resumen_ejecutivo)
            if conclusiones:
                actualizaciones.append("conclusiones = ?")
                params.append(conclusiones)
            if tareas_str != "[]":
                actualizaciones.append("acuerdos_tareas = ?")
                params.append(tareas_str)
            if mapa_str != "{}":
                actualizaciones.append("mapa_conceptual_json = ?")
                params.append(mapa_str)

            actualizaciones.append("updated_at = ?")
            params.append(datetime.now().isoformat())
            params.append(reunion_id)

            sql = f"UPDATE reuniones SET {', '.join(actualizaciones)} WHERE id = ?"
            conn.execute(sql, params)
            conn.commit()
            log(f"Reunión #{reunion_id} actualizada.")
            rid = reunion_id
        else:
            cur = conn.execute(
                """
                INSERT INTO reuniones (
                    titulo, fecha, duracion_min, participantes, audio_ruta,
                    transcripcion_cruda, resumen_ejecutivo, conclusiones,
                    acuerdos_tareas, mapa_conceptual_json, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    titulo,
                    fecha_final,
                    duracion_min,
                    participantes,
                    audio_ruta,
                    transcripcion_cruda,
                    resumen_ejecutivo,
                    conclusiones,
                    tareas_str,
                    mapa_str,
                    datetime.now().isoformat(),
                ),
            )
            conn.commit()
            rid = cur.lastrowid
            log(f"Reunión guardada con ID #{rid}: '{titulo}'")

        return {"ok": True, "id": rid, "titulo": titulo, "fecha": fecha_final}
    except Exception as e:
        log(f"Error guardando reunión: {e}")
        return {"ok": False, "error": str(e)}
    finally:
        conn.close()


def consultar_reuniones(
    accion: str = "listar",
    query: str = "",
    fecha: str = "",
    reunion_id: int | None = None,
    limite: int = 20,
) -> dict[str, Any]:
    """Consulta reuniones en la base de datos: listar, buscar o ver detalle."""
    conn = _conn()
    try:
        if accion == "detalle" or reunion_id is not None:
            if not reunion_id:
                return {"ok": False, "error": "Falta reunion_id para consultar detalle"}
            fila = conn.execute("SELECT * FROM reuniones WHERE id = ?", (reunion_id,)).fetchone()
            if not fila:
                return {"ok": False, "error": f"Reunión #{reunion_id} no encontrada"}
            data = dict(fila)
            try:
                data["acuerdos_tareas"] = json.loads(data.get("acuerdos_tareas") or "[]")
            except Exception:
                pass
            try:
                data["mapa_conceptual_json"] = json.loads(data.get("mapa_conceptual_json") or "{}")
            except Exception:
                pass
            return {"ok": True, "reunion": data}

        if accion == "buscar" and query:
            patron = f"%{query}%"
            filas = conn.execute(
                """
                SELECT id, titulo, fecha, duracion_min, participantes, resumen_ejecutivo, created_at
                FROM reuniones
                WHERE titulo LIKE ? OR resumen_ejecutivo LIKE ? OR conclusiones LIKE ? OR transcripcion_cruda LIKE ?
                ORDER BY fecha DESC LIMIT ?
                """,
                (patron, patron, patron, patron, limite),
            ).fetchall()
            return {"ok": True, "reuniones": [dict(f) for f in filas], "total": len(filas)}

        condiciones = []
        params: list[Any] = []
        if fecha:
            condiciones.append("fecha = ?")
            params.append(fecha)

        where = f"WHERE {' AND '.join(condiciones)}" if condiciones else ""
        params.append(limite)
        filas = conn.execute(
            f"""
            SELECT id, titulo, fecha, duracion_min, participantes, resumen_ejecutivo,
                   conclusiones, created_at, updated_at
            FROM reuniones
            {where}
            ORDER BY fecha DESC, id DESC LIMIT ?
            """,
            params,
        ).fetchall()
        return {"ok": True, "reuniones": [dict(f) for f in filas], "total": len(filas)}
    except Exception as e:
        log(f"Error consultando reuniones: {e}")
        return {"ok": False, "error": str(e)}
    finally:
        conn.close()


def generar_mapa_conceptual(
    reunion_id: int | None = None,
    titulo: str = "",
    resumen: str = "",
    conclusiones: str = "",
    tareas: list[dict[str, Any]] | str = "[]",
) -> dict[str, Any]:
    """Genera la estructura de nodos y conexiones de un mapa conceptual a partir de la minuta."""
    if reunion_id and (not titulo or not resumen):
        conn = _conn()
        try:
            fila = conn.execute("SELECT * FROM reuniones WHERE id = ?", (reunion_id,)).fetchone()
            if fila:
                titulo = titulo or fila["titulo"]
                resumen = resumen or fila["resumen_ejecutivo"]
                conclusiones = conclusiones or fila["conclusiones"]
                if tareas == "[]" or not tareas:
                    try:
                        tareas = json.loads(fila["acuerdos_tareas"] or "[]")
                    except Exception:
                        tareas = []
        finally:
            conn.close()

    titulo_nodo = (titulo or "").strip() or "Reunión Principal"
    nodos: list[dict[str, Any]] = []
    conexiones: list[dict[str, Any]] = []

    # 1. Nodo Central
    root_id = "node-root"
    nodos.append({
        "id": root_id,
        "tipo": "central",
        "texto": titulo_nodo,
        "x": 600,
        "y": 400,
        "ancho": 180,
        "alto": 70,
        "color": "#6366f1",
    })

    # 2. Desglose de Temas Clave del Resumen
    lineas_resumen = [
        line.strip("- *• \t\r\n")
        for line in (resumen or "").split("\n")
        if line.strip("- *• \t\r\n") and len(line.strip("- *• \t\r\n")) > 10
    ]
    if not lineas_resumen and (resumen or "").strip():
        lineas_resumen = [s.strip() for s in resumen.split(".") if len(s.strip()) > 10][:4]

    temas = lineas_resumen[:4]
    radio_temas = 220
    num_temas = len(temas) or 1
    tema_ids = []

    for i, tema_texto in enumerate(temas):
        tid = f"node-tema-{i+1}"
        tema_ids.append(tid)
        angulo = (2 * math.pi / num_temas) * i - (math.pi / 2)
        tx = 600 + int(radio_temas * math.cos(angulo))
        ty = 400 + int(radio_temas * math.sin(angulo))
        nodos.append({
            "id": tid,
            "tipo": "tema",
            "texto": tema_texto[:90],
            "x": tx,
            "y": ty,
            "ancho": 160,
            "alto": 60,
            "color": "#3b82f6",
        })
        conexiones.append({
            "id": f"edge-root-{tid}",
            "desde": root_id,
            "hacia": tid,
            "etiqueta": "tema",
        })

    # 3. Conclusiones y Decisiones
    lineas_concl = [
        line.strip("- *• \t\r\n")
        for line in (conclusiones or "").split("\n")
        if line.strip("- *• \t\r\n") and len(line.strip("- *• \t\r\n")) > 5
    ]
    for j, dec in enumerate(lineas_concl[:3]):
        did = f"node-decision-{j+1}"
        dx = 350 + (j * 250)
        dy = 680
        nodos.append({
            "id": did,
            "tipo": "decision",
            "texto": f"Acuerdo: {dec[:80]}",
            "x": dx,
            "y": dy,
            "ancho": 170,
            "alto": 60,
            "color": "#10b981",
        })
        origen = tema_ids[j % len(tema_ids)] if tema_ids else root_id
        conexiones.append({
            "id": f"edge-dec-{did}",
            "desde": origen,
            "hacia": did,
            "etiqueta": "acuerdo",
        })

    # 4. Tareas y Acciones
    lista_tareas: list[dict[str, Any]] = []
    if isinstance(tareas, str):
        try:
            lista_tareas = json.loads(tareas)
        except Exception:
            lista_tareas = []
    elif isinstance(tareas, list):
        lista_tareas = tareas

    for k, t in enumerate(lista_tareas[:6]):
        kid = f"node-tarea-{k+1}"
        desc = t.get("tarea", "") or str(t)
        resp = t.get("responsable", "")
        texto_t = f"Tarea: {desc[:60]}"
        if resp:
            texto_t += f" ({resp})"
        kx = 200 + (k % 3) * 380
        ky = 120 + (k // 3) * 110
        nodos.append({
            "id": kid,
            "tipo": "tarea",
            "texto": texto_t,
            "x": kx,
            "y": ky,
            "ancho": 170,
            "alto": 55,
            "color": "#f59e0b",
        })
        origen_t = tema_ids[k % len(tema_ids)] if tema_ids else root_id
        conexiones.append({
            "id": f"edge-tar-{kid}",
            "desde": origen_t,
            "hacia": kid,
            "etiqueta": "asigna",
        })

    mapa = {
        "nodos": nodos,
        "conexiones": conexiones,
        "actualizado_at": datetime.now().isoformat(),
    }

    if reunion_id:
        conn = _conn()
        try:
            conn.execute(
                "UPDATE reuniones SET mapa_conceptual_json = ?, updated_at = ? WHERE id = ?",
                (json.dumps(mapa, ensure_ascii=False), datetime.now().isoformat(), reunion_id),
            )
            conn.commit()
            log(f"Mapa conceptual guardado en BD para reunión #{reunion_id}")
        finally:
            conn.close()

    return {"ok": True, "mapa": mapa}


def volcar_tareas_agenda(
    reunion_id: int,
    indices_tareas: list[int] | None = None,
    agendar_en_eventos: bool = True,
    agendar_en_pendientes: bool = True,
) -> dict[str, Any]:
    """Vuelca compromisos acordados en la reunión hacia la tabla eventos y pendientes."""
    conn = _conn()
    try:
        fila = conn.execute("SELECT * FROM reuniones WHERE id = ?", (reunion_id,)).fetchone()
        if not fila:
            return {"ok": False, "error": f"Reunión #{reunion_id} no encontrada"}

        titulo_reunion = fila["titulo"]
        try:
            tareas_raw = json.loads(fila["acuerdos_tareas"] or "[]")
        except Exception:
            tareas_raw = []

        if not tareas_raw:
            return {"ok": True, "mensaje": "No hay tareas definidas en esta reunión", "agendadas": 0}

        import sys
        sys.path.insert(0, str(ROOT / "skills"))
        from agenda import agenda as skill_agenda
        from pendientes import pendientes as skill_pendientes

        eventos_creados = []
        pendientes_creados = []
        tareas_actualizadas = []

        for idx, t in enumerate(tareas_raw):
            if indices_tareas is not None and idx not in indices_tareas:
                tareas_actualizadas.append(t)
                continue

            desc = t.get("tarea", "")
            resp = t.get("responsable", "")
            fecha_limite = t.get("fecha_limite", "")

            # 1. Agregar a Pendientes
            if agendar_en_pendientes and desc:
                prefijo = f"[{resp}] " if resp else ""
                texto_pendiente = f"{prefijo}{desc} (Reunión: {titulo_reunion})"
                r_pen = skill_pendientes(accion="crear", texto=texto_pendiente)
                if r_pen.get("ok"):
                    pendientes_creados.append({"id": r_pen.get("id"), "texto": texto_pendiente})

            # 2. Agregar a Eventos si tiene fecha o si se solicitó explícitamente
            if agendar_en_eventos and desc:
                fecha_evento = fecha_limite or date.today().isoformat()
                titulo_evento = f"Entrega: {desc}"
                if resp:
                    titulo_evento += f" ({resp})"
                r_age = skill_agenda(
                    accion="crear",
                    titulo=titulo_evento,
                    fecha=fecha_evento,
                    hora="10:00",
                    duracion=30,
                    descripcion=f"Compromiso generado en la reunión: {titulo_reunion}",
                )
                if r_age.get("ok"):
                    eventos_creados.append({"id": r_age.get("id"), "titulo": titulo_evento, "fecha": fecha_evento})

            t["agendada"] = True
            tareas_actualizadas.append(t)

        conn.execute(
            "UPDATE reuniones SET acuerdos_tareas = ?, updated_at = ? WHERE id = ?",
            (json.dumps(tareas_actualizadas, ensure_ascii=False), datetime.now().isoformat(), reunion_id),
        )
        conn.commit()

        log(f"Volcado de tareas para reunión #{reunion_id}: {len(pendientes_creados)} pendientes, {len(eventos_creados)} eventos.")
        return {
            "ok": True,
            "reunion_id": reunion_id,
            "pendientes_creados": pendientes_creados,
            "eventos_creados": eventos_creados,
            "total_procesadas": len(pendientes_creados) + len(eventos_creados),
        }
    except Exception as e:
        log(f"Error volcando tareas: {e}")
        return {"ok": False, "error": str(e)}
    finally:
        conn.close()


def main() -> int:
    ap = argparse.ArgumentParser(description="Skill: Gestión de Reuniones")
    ap.add_argument("--accion", choices=["guardar", "consultar", "mapa", "volcar"], default="consultar")
    ap.add_argument("--titulo", default="")
    ap.add_argument("--fecha", default="")
    ap.add_argument("--id", type=int, default=None)
    ap.add_argument("--query", default="")
    args = ap.parse_args()

    if args.accion == "guardar":
        res = guardar_reunion(titulo=args.titulo, fecha=args.fecha, reunion_id=args.id)
    elif args.accion == "mapa":
        res = generar_mapa_conceptual(reunion_id=args.id, titulo=args.titulo)
    elif args.accion == "volcar":
        if not args.id:
            print(json.dumps({"ok": False, "error": "Falta --id"}))
            return 1
        res = volcar_tareas_agenda(reunion_id=args.id)
    else:
        res = consultar_reuniones(accion="buscar" if args.query else "listar", query=args.query, reunion_id=args.id)

    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
