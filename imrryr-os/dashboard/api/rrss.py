"""API: RRSS — posts programados (lectura/alta directa, sin pasar por el LLM)."""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from api import deps

router = APIRouter()


@router.get("/api/rrss/posts")
async def listar_posts_programados():
    conn = sqlite3.connect(str(deps.DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.execute("SELECT * FROM posts_programados ORDER BY programado_at DESC")
        return {"posts": [dict(row) for row in cur.fetchall()]}
    finally:
        conn.close()


@router.post("/api/rrss/posts")
async def crear_post_programado(datos: dict):
    contenido = datos.get("contenido", "")
    plataformas = datos.get("plataformas", "")
    programado_at = datos.get("programado_at", "")
    if not contenido or not plataformas or not programado_at:
        return JSONResponse({"ok": False, "error": "faltan contenido, plataformas o programado_at"}, status_code=400)
    conn = sqlite3.connect(str(deps.DB_PATH))
    try:
        cur = conn.execute(
            "INSERT INTO posts_programados (contenido, media_ruta, plataformas, programado_at) VALUES (?, ?, ?, ?)",
            (contenido, datos.get("media_ruta", ""), plataformas, programado_at),
        )
        conn.commit()
        return {"ok": True, "id": cur.lastrowid}
    finally:
        conn.close()
