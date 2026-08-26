#!/usr/bin/env python3
"""
server.py — Servidor del Dashboard de Escritorio (Fase 6)
==========================================================
FastAPI que sirve la interfaz visual y las APIs de datos para los widgets.

Uso:
    python dashboard/server.py              # :3000 por defecto
    python dashboard/server.py --port 3000

Los endpoints ya no viven acá: cada dominio tiene su router en dashboard/api/
(core, chat, finanzas, semillas, correo, oportunidades, ajustes, modulos,
agenda, navegacion, compras, rrss). Las rutas HTTP son las mismas de siempre;
ver el docstring de cada módulo para el detalle.
"""
from __future__ import annotations

import sys
from pathlib import Path

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / "config" / ".env"
ADJUNTOS_DIR = ROOT / "semillas" / "adjuntos"
STATIC_DIR = Path(__file__).parent / "static"
FONDOS_DIR = STATIC_DIR / "fondos"

ADJUNTOS_DIR.mkdir(parents=True, exist_ok=True)
FONDOS_DIR.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(Path(__file__).parent))  # para 'from api import ...'
sys.path.insert(0, str(ROOT / "skills"))
sys.path.insert(0, str(ROOT))  # para 'from correo.config import ...'

if ENV_FILE.exists():
    # override=True: el .env manda sobre lo que ya haya en el entorno. Sin
    # esto, una IMRRYR_ACTIVE_API_KEY heredada del shell (o de un arranque
    # anterior) le ganaba a la cuenta de IA que el usuario acaba de activar.
    load_dotenv(ENV_FILE, override=True)

app = FastAPI(title="Imrryr Dashboard", version="0.1.0")
# CORS cerrado al propio origen del panel. Con "*", cualquier sitio web que
# visitaras con el dashboard abierto podría llamar a estas APIs locales
# (enviar correo, publicar en RRSS…) desde tu navegador. Todo el frontend
# usa URLs relativas (mismo origen), así que esto no le afecta.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/adjuntos", StaticFiles(directory=str(ADJUNTOS_DIR)), name="adjuntos")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

from api import ajustes, agenda, chat, compras, core, correo, finanzas, modulos, navegacion, oportunidades, rrss, semillas  # noqa: E402

for _modulo in (core, chat, finanzas, semillas, correo,
                oportunidades, ajustes, modulos, agenda, navegacion, compras, rrss):
    app.include_router(_modulo.router)


# ---------------------------------------------------------------------------
# Schedulers en segundo plano (viven en este proceso porque es el único que
# se queda corriendo mientras el dashboard está abierto)
# ---------------------------------------------------------------------------
def _iniciar_scheduler_finanzas() -> None:
    """Sincroniza correos bancarios nuevos al iniciar el dashboard y cada 24h
    mientras siga corriendo — cubre tanto "cada vez que inicio sesión en
    Imrryr OS" como "todos los días", sin necesitar un scheduler del sistema
    operativo. `startup.py` es un lanzador que termina apenas los servicios
    quedan arriba, así que el hilo vive aquí (ver finanzas/importador_historico.py)."""
    import threading
    import time

    def _loop():
        from finanzas import importador_historico as importador
        while True:
            try:
                importador.sincronizar_diario(finanzas.CUENTA_GMAIL_FINANZAS, finanzas.QUERY_BANCARIA_DEFECTO)
            except Exception as e:
                print(f"[dashboard] sincronización diaria de Finanzas falló: {e}", flush=True)
            time.sleep(24 * 60 * 60)

    threading.Thread(target=_loop, daemon=True).start()


def main():
    import argparse
    ap = argparse.ArgumentParser(description="Servidor del Dashboard Imrryr OS")
    ap.add_argument("--port", type=int, default=3000)
    args = ap.parse_args()
    _iniciar_scheduler_finanzas()
    from scripts.scheduler import iniciar_scheduler_generico
    iniciar_scheduler_generico()
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="info")


if __name__ == "__main__":
    main()
