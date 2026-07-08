#!/usr/bin/env python3
"""
scraper_tiendas.py — Skill: busca un producto en tiendas chilenas
=====================================================================
Cada tienda es una función interna independiente — si una falla (cambio de
markup, bloqueo anti-bot), no debe tumbar la consulta a las otras.

Estado real verificado durante el desarrollo (no todas las tiendas quedaron
igual de confiables — se documenta acá para no sorprender más adelante):
  - Falabella: funciona. Sirve HTML con los resultados ya renderizados en el
    servidor (data-pod="catalyst-pod"), con precio, marca y título en
    atributos estables.
  - MercadoLibre: bloqueado. Tanto pedir la página de listado como su API
    pública de búsqueda (api.mercadolibre.com/sites/MLC/search) devuelven
    403 a peticiones anónimas — MercadoLibre lo cerró detrás de una app/token
    autenticado. Sin credenciales de su Developer Program esto no funciona;
    queda como best-effort (devuelve lista vacía) hasta que se agregue esa
    integración.
  - Paris: su página de búsqueda es una SPA que renderiza los productos por
    JavaScript en el cliente — el HTML que llega por HTTP no trae productos
    todavía ("Has visto 0 de 0 productos"). Scrapearlo de verdad requeriría
    un navegador headless (Playwright), que este proyecto no usa hoy. Queda
    como best-effort.
  - Ripley: devuelve 403 (bloqueo anti-bot) incluso con headers de navegador
    real. Queda como best-effort.

Uso:
    python skills/scraper_tiendas.py --producto "notebook" --tiendas falabella,mercadolibre
"""
from __future__ import annotations

import argparse
import json
import re
from typing import Any
from urllib.parse import quote

import httpx
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "es-CL,es;q=0.9",
}


def log(msg: str) -> None:
    print(f"[scraper_tiendas] {msg}", flush=True)


def _precio_a_float(texto: str) -> float | None:
    """Precios chilenos usan '.' como separador de miles: '869.990' -> 869990.0"""
    limpio = re.sub(r"[^\d]", "", texto or "")
    return float(limpio) if limpio else None


def _buscar_falabella(query: str) -> list[dict[str, Any]]:
    resultados: list[dict[str, Any]] = []
    try:
        url = f"https://www.falabella.com/falabella-cl/search?Ntt={quote(query)}"
        r = httpx.get(url, headers=HEADERS, timeout=20, follow_redirects=True)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        for pod in soup.select('a[data-pod="catalyst-pod"]'):
            data_key = pod.get("data-key", "")
            marca_el = pod.select_one(".pod-title.title-rebrand")
            titulo_el = pod.select_one(".pod-subTitle.subTitle-rebrand")
            precio_el = pod.select_one("li[data-internet-price]") or pod.select_one("li[data-cmr-price]")
            if not titulo_el or not precio_el:
                continue
            precio = _precio_a_float(precio_el.get_text())
            if precio is None:
                continue
            marca = marca_el.get_text(strip=True) if marca_el else ""
            titulo = titulo_el.get_text(strip=True)
            resultados.append({
                "titulo": f"{marca} {titulo}".strip(),
                "precio": precio,
                "url": f"https://www.falabella.com/falabella-cl/product/{data_key}" if data_key else url,
            })
    except (httpx.HTTPError, OSError) as e:
        log(f"Falabella falló: {e}")
    return resultados


def _buscar_mercadolibre(query: str) -> list[dict[str, Any]]:
    resultados: list[dict[str, Any]] = []
    try:
        r = httpx.get(
            "https://api.mercadolibre.com/sites/MLC/search",
            params={"q": query}, headers=HEADERS, timeout=20,
        )
        if r.status_code != 200:
            log(f"MercadoLibre devolvió {r.status_code} (requiere app/token autenticado — ver docstring)")
            return resultados
        for item in r.json().get("results", []):
            resultados.append({
                "titulo": item.get("title", ""),
                "precio": float(item.get("price", 0)),
                "url": item.get("permalink", ""),
            })
    except (httpx.HTTPError, OSError, json.JSONDecodeError) as e:
        log(f"MercadoLibre falló: {e}")
    return resultados


def _buscar_paris(query: str) -> list[dict[str, Any]]:
    resultados: list[dict[str, Any]] = []
    try:
        url = f"https://www.paris.cl/search/?text={quote(query)}"
        r = httpx.get(url, headers=HEADERS, timeout=20, follow_redirects=True)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        for card in soup.select('[data-testid="product-list-grid"] [data-testid="product-card"]'):
            titulo_el = card.select_one('[data-testid="product-title"]')
            precio_el = card.select_one('[data-testid="product-price"]')
            link_el = card.select_one("a[href]")
            if not titulo_el or not precio_el:
                continue
            precio = _precio_a_float(precio_el.get_text())
            if precio is None:
                continue
            resultados.append({
                "titulo": titulo_el.get_text(strip=True),
                "precio": precio,
                "url": ("https://www.paris.cl" + link_el["href"]) if link_el else url,
            })
    except (httpx.HTTPError, OSError) as e:
        log(f"Paris falló: {e}")
    return resultados


def _buscar_ripley(query: str) -> list[dict[str, Any]]:
    resultados: list[dict[str, Any]] = []
    try:
        url = f"https://simple.ripley.cl/search/{quote(query)}?source=search"
        r = httpx.get(url, headers=HEADERS, timeout=20, follow_redirects=True)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        for card in soup.select(".catalog-product-item"):
            titulo_el = card.select_one(".catalog-product-details__name")
            precio_el = card.select_one(".catalog-prices__offer-price")
            link_el = card.select_one("a[href]")
            if not titulo_el or not precio_el:
                continue
            precio = _precio_a_float(precio_el.get_text())
            if precio is None:
                continue
            resultados.append({
                "titulo": titulo_el.get_text(strip=True),
                "precio": precio,
                "url": ("https://simple.ripley.cl" + link_el["href"]) if link_el else url,
            })
    except (httpx.HTTPError, OSError) as e:
        log(f"Ripley falló: {e}")
    return resultados


_BUSCADORES = {
    "falabella": _buscar_falabella,
    "mercadolibre": _buscar_mercadolibre,
    "paris": _buscar_paris,
    "ripley": _buscar_ripley,
}


def scraper_tiendas(producto: str, tiendas: str = "mercadolibre,falabella,paris,ripley") -> dict:
    """Punto de entrada MCP. Devuelve {tienda: [ofertas...]} — el fallo de una
    tienda no impide devolver resultados de las demás."""
    resultado: dict[str, list[dict[str, Any]]] = {}
    for tienda in [t.strip() for t in tiendas.split(",") if t.strip()]:
        buscador = _BUSCADORES.get(tienda)
        if not buscador:
            resultado[tienda] = []
            continue
        resultado[tienda] = buscador(producto)
    return resultado


def main() -> int:
    ap = argparse.ArgumentParser(description="Busca un producto en tiendas chilenas")
    ap.add_argument("--producto", type=str, required=True)
    ap.add_argument("--tiendas", type=str, default="mercadolibre,falabella,paris,ripley")
    args = ap.parse_args()
    print(scraper_tiendas(args.producto, args.tiendas))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
