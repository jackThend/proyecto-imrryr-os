#!/usr/bin/env python3
"""
server.py — Servidor del Dashboard de Escritorio (Fase 6)
===========================================================
FastAPI que sirve la interfaz visual y las APIs de datos para los widgets.

Uso:
    python dashboard/server.py              # :3000 por defecto
    python dashboard/server.py --port 3000

Endpoints:
    GET  /                → Dashboard HTML
    GET  /api/widgets     → Lista de widgets disponibles (desde /agentes/*.yaml)
    GET  /api/finanzas    → Datos de gastos (SQLite)
    GET  /api/semillas    → Lista de semillas
    POST /api/chat        → Envía prompt a OpenCode
"""
from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
from pathlib import Path

import uvicorn
import yaml
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / "config" / ".env"
DB_PATH = ROOT / "vault" / "sqlite" / "imrryr.db"
AGENTES_DIR = ROOT / "agentes"
SEMILLAS_DIR = ROOT / "semillas"
STATIC_DIR = Path(__file__).parent / "static"

if ENV_FILE.exists():
    load_dotenv(ENV_FILE)

app = FastAPI(title="Imrryr Dashboard", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Sesión de OpenCode reutilizada por el chat del dashboard (proceso único,
# usuario único — coherente con el modelo local-first de Imrryr OS).
_opencode_session_id: str | None = None


def _opencode_port() -> int:
    return int(os.environ.get("OPENCODE_PORT") or 4040)


def _opencode_password() -> str:
    return os.environ.get("OPENCODE_SERVER_PASSWORD", "imryyr-local-pass")


def _modelo_activo() -> str:
    return os.environ.get("DEFAULT_MODEL", "gemini-flash")


def _opencode_auth_headers() -> dict[str, str]:
    token = base64.b64encode(f"opencode:{_opencode_password()}".encode()).decode()
    return {"Authorization": f"Basic {token}", "Content-Type": "application/json"}


# ---------------------------------------------------------------------------
# HTML Dashboard (single-page app embebida)
# ---------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def dashboard():
    html = (Path(__file__).parent / "dashboard.html").read_text(encoding="utf-8")
    return HTMLResponse(html)


# ---------------------------------------------------------------------------
# API: Widgets dinámicos (lee /agentes/*.yaml)
# ---------------------------------------------------------------------------
@app.get("/api/widgets")
async def list_widgets():
    widgets = []
    if AGENTES_DIR.exists():
        for fpath in sorted(AGENTES_DIR.glob("*.yaml")):
            try:
                data = yaml.safe_load(fpath.read_text(encoding="utf-8"))
                if data and data.get("activo", True):
                    widgets.append({
                        "id": fpath.stem,
                        "nombre": data.get("nombre", fpath.stem),
                        "descripcion": data.get("descripcion", ""),
                        "herramientas": data.get("herramientas_permitidas", []),
                    })
            except Exception as e:
                pass
    return {"widgets": widgets}


# ---------------------------------------------------------------------------
# API: Finanzas (desde SQLite)
# ---------------------------------------------------------------------------
@app.get("/api/finanzas")
async def get_finanzas(limite: int = 20):
    if not DB_PATH.exists():
        return {"gastos": [], "total": 0, "por_categoria": {}}

    import sqlite3
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.execute("SELECT * FROM gastos ORDER BY fecha DESC LIMIT ?", (limite,))
        gastos = [dict(row) for row in cur.fetchall()]

        cur = conn.execute("SELECT COALESCE(SUM(monto), 0) as total FROM gastos")
        total = cur.fetchone()["total"]

        cur = conn.execute("SELECT categoria, COUNT(*) as count, SUM(monto) as subtotal FROM gastos GROUP BY categoria")
        por_categoria = {row["categoria"]: {"count": row["count"], "subtotal": row["subtotal"]} for row in cur.fetchall()}

        return {"gastos": gastos, "total": total, "por_categoria": por_categoria}
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# API: Semillas
# ---------------------------------------------------------------------------
@app.get("/api/semillas")
async def get_semillas():
    semillas = []
    if SEMILLAS_DIR.exists():
        for fpath in sorted(SEMILLAS_DIR.iterdir()):
            if fpath.suffix.lower() in (".md", ".txt"):
                semillas.append({
                    "nombre": fpath.name,
                    "contenido": fpath.read_text(encoding="utf-8", errors="replace")[:500],
                    "modificado": fpath.stat().st_mtime,
                })
    return {"semillas": semillas}


# ---------------------------------------------------------------------------
# API: Chat (usa una sesión real de OpenCode -> acceso a agentes y skills)
#
# OpenCode expone dos familias de endpoints de sesión: `/api/session/...`
# (asíncrona: /prompt solo admite el mensaje en una cola y hay que
# esperar/consultar aparte) y `/session/...` (síncrona: POST .../message
# devuelve la respuesta ya generada). Usamos la segunda porque es la que
# realmente usa el CLI de OpenCode (`opencode run`) y no requiere hacer
# polling.
# ---------------------------------------------------------------------------
async def _get_or_create_session(client, agent: str) -> str:
    global _opencode_session_id
    if _opencode_session_id:
        return _opencode_session_id

    r = await client.post(
        f"http://localhost:{_opencode_port()}/session",
        headers=_opencode_auth_headers(),
        json={"agent": agent, "model": {"id": _modelo_activo(), "providerID": "imryyr-llm"}},
        timeout=15,
    )
    r.raise_for_status()
    data = r.json()
    sid = data.get("data", {}).get("id") or data.get("id")
    if not sid:
        raise RuntimeError(f"Respuesta inesperada al crear sesión: {data}")
    _opencode_session_id = sid
    return sid


@app.post("/api/chat")
async def chat(request: Request):
    global _opencode_session_id
    import httpx

    body = await request.json()
    mensaje = body.get("mensaje", "")
    agente = body.get("agente", "build")

    try:
        async with httpx.AsyncClient() as client:
            sid = await _get_or_create_session(client, agente)
            r = await client.post(
                f"http://localhost:{_opencode_port()}/session/{sid}/message",
                headers=_opencode_auth_headers(),
                json={
                    "agent": agente,
                    "model": {"providerID": "imryyr-llm", "modelID": _modelo_activo()},
                    "parts": [{"type": "text", "text": mensaje}],
                },
                timeout=120,
            )
            r.raise_for_status()
            data = r.json()

        respuesta = "".join(p.get("text", "") for p in data.get("parts", []) if p.get("type") == "text")
        if not respuesta:
            respuesta = json.dumps(data, ensure_ascii=True)[:500]

        return {"respuesta": respuesta, "session_id": sid}
    except Exception as e:
        # La sesión pudo quedar inválida (ej. OpenCode se reinició); se recrea en el próximo intento.
        _opencode_session_id = None
        return JSONResponse({"error": str(e)}, status_code=500)


# ---------------------------------------------------------------------------
# API: Estado del sistema
# ---------------------------------------------------------------------------
@app.get("/api/status")
async def system_status():
    import socket
    servicios = {}
    for name, port in [("litellm", 4000), ("opencode", 4040), ("gateway", 5050)]:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.settimeout(1)
            servicios[name] = s.connect_ex(("127.0.0.1", port)) == 0
        finally:
            s.close()
    return {"servicios": servicios}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    import argparse
    ap = argparse.ArgumentParser(description="Servidor del Dashboard Imrryr OS")
    ap.add_argument("--port", type=int, default=3000)
    args = ap.parse_args()
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="info")


if __name__ == "__main__":
    main()
