#!/usr/bin/env python3
"""
semillas.py — Skill: Sistema de Ideas/Proyectos ("Pinterest de ideas")
=========================================================================
Ciclo de vida de una idea: idea -> desarrollada -> proyecto -> archivada.

El "desarrollador de ideas" no es una función aparte: es el propio Agente
Creativo, instruido para expandir una idea corta en una versión detallada
y bien escrita antes de guardarla — por eso crear_semilla recibe tanto el
texto original del usuario (contenido_original) como la versión ya
enriquecida que redactó el agente (contenido/descripcion).

Uso:
    python skills/semillas.py --crear --titulo "Anteojos con IA" --contenido "..." --listar
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "vault" / "sqlite" / "imrryr.db"

ESTADOS_VALIDOS = {"idea", "desarrollada", "proyecto", "archivada"}


def log(msg: str) -> None:
    print(f"[semillas] {msg}", flush=True)


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _fila_semilla(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["etiquetas"] = d["etiquetas"].split(",") if d.get("etiquetas") else []
    return d


def crear_semilla(
    titulo: str,
    contenido: str,
    contenido_original: str = "",
    etiquetas: list[str] | None = None,
    fuente: str = "manual",
) -> dict:
    if not DB_PATH.exists():
        return {"ok": False, "error": "Base de datos no encontrada. Ejecuta: python scripts/init_db.py"}

    etiquetas_str = ",".join(etiquetas) if etiquetas else ""
    conn = _conn()
    try:
        cur = conn.execute(
            "INSERT INTO semillas (titulo, descripcion, contenido_original, etiquetas, fuente, estado, updated_at) "
            "VALUES (?, ?, ?, ?, ?, 'idea', datetime('now'))",
            (titulo, contenido, contenido_original or contenido, etiquetas_str, fuente),
        )
        conn.commit()
        log(f"Idea creada: '{titulo}' (#{cur.lastrowid})")
        return {"ok": True, "id": cur.lastrowid}
    finally:
        conn.close()


def listar_semillas(estado: str = "") -> list[dict]:
    """Incluye 'primer_adjunto' (miniatura) por idea para la vista tipo Pinterest."""
    if not DB_PATH.exists():
        return []
    conn = _conn()
    try:
        query = (
            "SELECT s.*, "
            "(SELECT ruta_archivo FROM adjuntos_semilla a WHERE a.semilla_id = s.id "
            " ORDER BY a.created_at ASC LIMIT 1) AS primer_adjunto "
            "FROM semillas s"
        )
        params: list = []
        if estado:
            query += " WHERE s.estado = ?"
            params.append(estado)
        query += " ORDER BY s.updated_at DESC"
        cur = conn.execute(query, params)
        return [_fila_semilla(row) for row in cur.fetchall()]
    finally:
        conn.close()


def obtener_semilla(id: int) -> dict:
    if not DB_PATH.exists():
        return {"ok": False, "error": "no existe la base de datos"}
    conn = _conn()
    try:
        fila = conn.execute("SELECT * FROM semillas WHERE id = ?", (id,)).fetchone()
        if not fila:
            return {"ok": False, "error": f"no existe la idea #{id}"}
        d = _fila_semilla(fila)
        adjuntos = conn.execute(
            "SELECT * FROM adjuntos_semilla WHERE semilla_id = ? ORDER BY created_at ASC", (id,)
        ).fetchall()
        d["adjuntos"] = [dict(a) for a in adjuntos]
        return d
    finally:
        conn.close()


def actualizar_semilla(
    id: int,
    titulo: str = "",
    contenido: str = "",
    etiquetas: list[str] | None = None,
) -> dict:
    conn = _conn()
    try:
        campos, valores = [], []
        if titulo:
            campos.append("titulo = ?")
            valores.append(titulo)
        if contenido:
            campos.append("descripcion = ?")
            valores.append(contenido)
        if etiquetas is not None:
            campos.append("etiquetas = ?")
            valores.append(",".join(etiquetas))
        if not campos:
            return {"ok": False, "error": "nada para actualizar"}
        campos.append("updated_at = datetime('now')")
        valores.append(id)
        conn.execute(f"UPDATE semillas SET {', '.join(campos)} WHERE id = ?", valores)
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


def cambiar_estado_semilla(id: int, nuevo_estado: str) -> dict:
    if nuevo_estado not in ESTADOS_VALIDOS:
        return {"ok": False, "error": f"estado inválido; usa uno de {sorted(ESTADOS_VALIDOS)}"}

    conn = _conn()
    try:
        fila = conn.execute("SELECT * FROM semillas WHERE id = ?", (id,)).fetchone()
        if not fila:
            return {"ok": False, "error": f"no existe la idea #{id}"}

        proyecto_id = fila["proyecto_id"]
        if nuevo_estado == "proyecto" and not proyecto_id:
            nombre_proyecto = fila["titulo"]
            try:
                cur = conn.execute(
                    "INSERT INTO proyectos (nombre, descripcion, semilla_origen_id) VALUES (?, ?, ?)",
                    (nombre_proyecto, fila["descripcion"], id),
                )
            except sqlite3.IntegrityError:
                # 'nombre' es UNIQUE; si ya existe un proyecto con ese nombre, desambiguar con el id
                cur = conn.execute(
                    "INSERT INTO proyectos (nombre, descripcion, semilla_origen_id) VALUES (?, ?, ?)",
                    (f"{nombre_proyecto} (#{id})", fila["descripcion"], id),
                )
            proyecto_id = cur.lastrowid
            log(f"Proyecto creado desde la idea #{id}: '{nombre_proyecto}' (proyecto #{proyecto_id})")

        conn.execute(
            "UPDATE semillas SET estado = ?, proyecto_id = ?, updated_at = datetime('now') WHERE id = ?",
            (nuevo_estado, proyecto_id, id),
        )
        conn.commit()
        return {"ok": True, "estado": nuevo_estado, "proyecto_id": proyecto_id}
    finally:
        conn.close()


def adjuntar_archivo_semilla(id: int, ruta_archivo: str, tipo: str = "imagen") -> dict:
    conn = _conn()
    try:
        existe = conn.execute("SELECT 1 FROM semillas WHERE id = ?", (id,)).fetchone()
        if not existe:
            return {"ok": False, "error": f"no existe la idea #{id}"}
        conn.execute(
            "INSERT INTO adjuntos_semilla (semilla_id, ruta_archivo, tipo) VALUES (?, ?, ?)",
            (id, ruta_archivo, tipo),
        )
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


# --- Proyectos: funciones planas de apoyo para el dashboard (no son MCP tools) ---
def listar_proyectos(estado: str = "") -> list[dict]:
    if not DB_PATH.exists():
        return []
    conn = _conn()
    try:
        if estado:
            cur = conn.execute("SELECT * FROM proyectos WHERE estado = ? ORDER BY updated_at DESC", (estado,))
        else:
            cur = conn.execute("SELECT * FROM proyectos ORDER BY updated_at DESC")
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def actualizar_proyecto(id: int, descripcion: str = "", estado: str = "", tecnologias: str = "") -> dict:
    conn = _conn()
    try:
        campos, valores = [], []
        if descripcion:
            campos.append("descripcion = ?")
            valores.append(descripcion)
        if estado:
            campos.append("estado = ?")
            valores.append(estado)
        if tecnologias:
            campos.append("tecnologias = ?")
            valores.append(tecnologias)
        if not campos:
            return {"ok": False, "error": "nada para actualizar"}
        campos.append("updated_at = datetime('now')")
        valores.append(id)
        conn.execute(f"UPDATE proyectos SET {', '.join(campos)} WHERE id = ?", valores)
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


def main() -> int:
    ap = argparse.ArgumentParser(description="Gestión de Ideas/Proyectos")
    ap.add_argument("--crear", action="store_true")
    ap.add_argument("--titulo", type=str, default="")
    ap.add_argument("--contenido", type=str, default="")
    ap.add_argument("--etiquetas", type=str, default="", help="separadas por coma")
    ap.add_argument("--listar", action="store_true")
    ap.add_argument("--estado", type=str, default="")
    args = ap.parse_args()

    if args.crear:
        etiquetas = [e.strip() for e in args.etiquetas.split(",") if e.strip()] or None
        print(json.dumps(crear_semilla(args.titulo, args.contenido, etiquetas=etiquetas), ensure_ascii=True))
        return 0

    if args.listar:
        print(json.dumps(listar_semillas(args.estado), ensure_ascii=True, indent=2))
        return 0

    ap.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
