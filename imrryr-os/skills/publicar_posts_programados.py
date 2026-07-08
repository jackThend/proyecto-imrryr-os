#!/usr/bin/env python3
"""
publicar_posts_programados.py — Skill: publica los posts programados vencidos
==================================================================================
100% determinista, sin IA: el scheduler (scripts/scheduler.py) llama a esto
cada minuto. Si un post fue programado con contenido ya redactado (por el
usuario o por el agente al momento de programar), publicarlo no vuelve a
consultar al modelo de lenguaje — solo llama a la Graph API.

No se expone como herramienta del Agente RRSS/Web (no está en
herramientas_permitidas de agentes/agente_rrss_web.yaml): es una tarea de
mantenimiento del sistema, no una acción conversacional. Se registra igual
como skill MCP por si algún agente necesita forzar la publicación manual
de la cola.

Uso:
    python skills/publicar_posts_programados.py
"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from redes_sociales import _cuenta, _publicar_graph_api

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "vault" / "sqlite" / "imrryr.db"


def log(msg: str) -> None:
    print(f"[publicar_posts_programados] {msg}", flush=True)


def publicar_posts_programados() -> dict:
    """Punto de entrada MCP (y llamado por import directo desde el scheduler)."""
    ahora = datetime.now().isoformat(timespec="minutes")
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.execute(
            "SELECT * FROM posts_programados WHERE estado = 'pendiente' AND programado_at <= ?",
            (ahora,),
        )
        vencidos = [dict(row) for row in cur.fetchall()]

        publicados, fallidos = 0, 0
        for post in vencidos:
            cuenta = _cuenta("")
            if not cuenta:
                conn.execute(
                    "UPDATE posts_programados SET estado='fallido', error_detalle=? WHERE id=?",
                    ("no hay cuenta social configurada", post["id"]),
                )
                fallidos += 1
                continue

            resultados = _publicar_graph_api(cuenta, post["contenido"], post.get("media_ruta") or "", post["plataformas"])
            ok_general = any(r.get("ok") for r in resultados.values())
            if ok_general:
                conn.execute(
                    "UPDATE posts_programados SET estado='publicado', publicado_at=datetime('now') WHERE id=?",
                    (post["id"],),
                )
                publicados += 1
                log(f"Post #{post['id']} publicado: {resultados}")
            else:
                errores = "; ".join(f"{k}: {v.get('error','')}" for k, v in resultados.items())
                conn.execute(
                    "UPDATE posts_programados SET estado='fallido', error_detalle=? WHERE id=?",
                    (errores, post["id"]),
                )
                fallidos += 1
                log(f"Post #{post['id']} falló: {errores}")

        conn.commit()
        return {"publicados": publicados, "fallidos": fallidos, "revisados": len(vencidos)}
    finally:
        conn.close()


if __name__ == "__main__":
    print(publicar_posts_programados())
