#!/usr/bin/env python3
"""
navegador_cliente.py — Lanza un navegador para Playwright sin depender de descargar Chromium
============================================================================================
Compartido por navegar_web.py y scraper_tiendas.py (no es una skill: no tiene manifiesto MCP).

Playwright trae su propio Chromium, pero ese binario (~150 MB) hay que bajarlo aparte con
`playwright install chromium` y NO viaja en el paquete de Imrryr OS, así que en el PC de un
cliente "leer una página" fallaba aunque tuviera un navegador instalado. Aquí se usa, por orden:

  1. El Chromium propio de Playwright, si está instalado (el caso de desarrollo).
  2. Cualquier navegador basado en Chromium que el cliente tenga instalado: Chrome, Edge,
     Brave, Vivaldi u Opera. Playwright puede controlarlos por su ruta.

Firefox y Safari no sirven: Playwright los maneja con sus propias versiones modificadas.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path


def log(msg: str) -> None:
    print(f"[navegador_cliente] {msg}", flush=True)


def _rutas_candidatas() -> list[Path]:
    """Ejecutables de navegadores Chromium instalados, en orden de preferencia."""
    candidatas: list[Path] = []
    if os.name == "nt":
        bases = [os.environ.get(v, "") for v in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA")]
        relativas = [
            r"Google\Chrome\Application\chrome.exe",
            r"Microsoft\Edge\Application\msedge.exe",
            r"BraveSoftware\Brave-Browser\Application\brave.exe",
            r"Vivaldi\Application\vivaldi.exe",
            r"Programs\Opera\opera.exe",
            r"Opera\opera.exe",
        ]
        for rel in relativas:
            candidatas += [Path(b) / rel for b in bases if b]
    else:
        candidatas += [
            Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
            Path("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"),
            Path("/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"),
        ]
        for nombre in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "microsoft-edge", "brave-browser"):
            ruta = shutil.which(nombre)
            if ruta:
                candidatas.append(Path(ruta))
    return candidatas


def navegadores_del_cliente() -> list[str]:
    return [str(p) for p in _rutas_candidatas() if p.exists()]


def lanzar_navegador(p, headless: bool = True):
    """Devuelve un Browser de Playwright (`p` es el objeto de sync_playwright()).
    Lanza RuntimeError con un mensaje entendible si no hay ninguno utilizable."""
    try:
        return p.chromium.launch(headless=headless)
    except Exception as e:  # Chromium de Playwright no instalado
        log(f"Chromium propio de Playwright no disponible ({str(e).splitlines()[0][:80]}); busco un navegador instalado")

    for ruta in navegadores_del_cliente():
        try:
            navegador = p.chromium.launch(executable_path=ruta, headless=headless)
            log(f"usando el navegador instalado: {ruta}")
            return navegador
        except Exception as e:
            log(f"no se pudo usar {ruta}: {str(e).splitlines()[0][:80]}")

    raise RuntimeError(
        "No hay un navegador compatible: instala Google Chrome, Microsoft Edge o Brave "
        "(o ejecuta `playwright install chromium`)."
    )
