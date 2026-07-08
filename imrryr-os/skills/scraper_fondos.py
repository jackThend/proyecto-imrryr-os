#!/usr/bin/env python3
"""
scraper_fondos.py — Skill: Busca fondos concursables en Sercotec y Corfo
========================================================================
Uso:
    python skills/scraper_fondos.py
    python skills/scraper_fondos.py --fuente sercotec
"""
from __future__ import annotations

import argparse
import re
from datetime import date
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parent.parent

FUENTES = {
    "sercotec": {
        "url": "https://www.sercotec.cl/",
        "selector": "convocatorias",
    },
    "corfo": {
        "url": "https://www.corfo.cl/sites/cpp/convocatorias",
        "selector": "convocatorias",
    },
}


def log(msg: str) -> None:
    print(f"[scraper] {msg}", flush=True)


def scrape_url(url: str) -> list[dict[str, Any]]:
    resultados = []
    try:
        r = httpx.get(url, timeout=30, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()

        # Búsqueda simple de patrones de convocatorias/fondos
        text = r.text
        patrones = [
            r"(?:Fondo|Convocatoria|Concurso)\s*[:\-]?\s*([^.<]+)",
            r"(?:Monto|Financiamiento)\s*[:\-]?\s*\$?([\d.]+)",
            r"(?:Cierre|Postulación|Plazo)\s*[:\-]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
        ]

        for patron in patrones:
            matches = re.findall(patron, text, re.IGNORECASE)
            for m in matches[:5]:
                resultados.append({"hallazgo": m.strip(), "fuente": url, "fecha": date.today().isoformat()})
    except Exception as e:
        log(f"Error scraping {url}: {e}")

    return resultados


def buscar_fondos(fuente: str | None = None) -> dict[str, list[dict[str, Any]]]:
    fuentes = {fuente: FUENTES[fuente]} if fuente else FUENTES
    return {nombre: scrape_url(cfg["url"]) for nombre, cfg in fuentes.items()}


def scraper_fondos(fuente: str | None = None) -> dict:
    """Punto de entrada MCP (nombre = nombre de la skill, ver mcp_server/skills_server.py)."""
    return buscar_fondos(fuente)


def main() -> int:
    ap = argparse.ArgumentParser(description="Busca fondos concursables")
    ap.add_argument("--fuente", choices=list(FUENTES.keys()), help="Fuente específica")
    args = ap.parse_args()

    resultados_por_fuente = buscar_fondos(args.fuente)

    for nombre, resultados in resultados_por_fuente.items():
        log(f"Scrapeando {nombre}...")
        log(f"  {len(resultados)} hallazgos en {nombre}")
        for r in resultados[:3]:
            print(f"  - {r['hallazgo']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
