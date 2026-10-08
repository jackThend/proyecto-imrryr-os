#!/usr/bin/env python3
"""
scraper_tiendas.py — Skill: busca un producto en tiendas chilenas
=====================================================================
Cada tienda es una función interna independiente — si una falla (cambio de
markup, bloqueo anti-bot), no debe tumbar la consulta a las otras.

Estado real verificado durante el desarrollo (no todas las tiendas quedaron
igual de confiables — se documenta acá para no sorprender más adelante):
  - Falabella: funciona con el método rápido (httpx). Sirve HTML con los
    resultados ya renderizados en el servidor (data-pod="catalyst-pod"), con
    precio, marca y título en atributos estables. No necesita navegador.
  - MercadoLibre: bloqueado. Tanto pedir la página de listado como su API
    pública de búsqueda (api.mercadolibre.com/sites/MLC/search) devuelven
    403 a peticiones anónimas — MercadoLibre lo cerró detrás de una app/token
    autenticado. Un navegador headless no cambia esto (es un bloqueo de
    cuenta/token, no de JavaScript); queda como best-effort sin importar el
    método.
  - Ripley: httpx directo devuelve 403 (bloqueo anti-bot por fingerprint,
    no un desafío tipo Cloudflare — se verificó que no hay challenge, solo
    rechaza clientes no-navegador). Con Playwright (navegador headless real)
    la página SÍ carga con código 200 y trae los resultados completos
    embebidos en su JSON de Next.js (__NEXT_DATA__ →
    props.pageProps.findabilityProps.data.products) — se probó en vivo y
    trajo 58 productos reales con precio. Por eso Ripley SÍ tiene fallback
    con navegador (usar_navegador=True), y es el método recomendado para
    esta tienda en particular.
  - Paris: su página de búsqueda no trae productos ni siquiera con
    Playwright — se probó en vivo (navegador real, esperando a que la red
    quede en reposo) y la página renderiza "0 de 0 productos". No hay ni
    siquiera un intento de llamada a una API de búsqueda en la red capturada,
    lo que sugiere que su buscador necesita un paso previo (selección de
    tienda/despacho, cookie de sesión, etc.) que un navegador "en frío" no
    dispara. Un navegador headless no resuelve este caso hoy; queda como
    best-effort igual que el método rápido.

Uso:
    python skills/scraper_tiendas.py --producto "notebook" --tiendas falabella,mercadolibre
    python skills/scraper_tiendas.py --producto "notebook" --tiendas ripley --usar-navegador
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


def _buscar_ripley_navegador(query: str) -> list[dict[str, Any]]:
    """Fallback con Playwright — httpx recibe 403 de Ripley, pero un navegador
    headless real sí pasa, y la página trae los productos ya armados en su
    JSON de Next.js (mucho más confiable que parsear selectores CSS)."""
    resultados: list[dict[str, Any]] = []
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log("Ripley (navegador) falló: playwright no está instalado")
        return resultados

    url = f"https://simple.ripley.cl/search/{quote(query)}?source=search"
    try:
        try:
            from navegador_cliente import lanzar_navegador
        except ImportError:
            from skills.navegador_cliente import lanzar_navegador
        with sync_playwright() as p:
            navegador = lanzar_navegador(p)
            try:
                pagina = navegador.new_page(user_agent=HEADERS["User-Agent"])
                pagina.goto(url, wait_until="domcontentloaded", timeout=25000)
                pagina.wait_for_timeout(3000)
                html = pagina.content()
            finally:
                navegador.close()

        m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html, re.S)
        if not m:
            log("Ripley (navegador) falló: no se encontró __NEXT_DATA__ en la página")
            return resultados
        data = json.loads(m.group(1))
        productos = (
            data.get("props", {}).get("pageProps", {})
            .get("findabilityProps", {}).get("data", {}).get("products", [])
        )
        for p in productos:
            sku = p.get("sku", "")
            resultados.append({
                "titulo": p.get("name") or p.get("description") or "",
                "precio": float(p.get("priceNumber") or 0) or None,
                "url": f"https://simple.ripley.cl/p/{sku}" if sku else url,
            })
        resultados = [r for r in resultados if r["precio"]]
    except Exception as e:
        log(f"Ripley (navegador) falló: {e}")
    return resultados


_BUSCADORES = {
    "falabella": _buscar_falabella,
    "mercadolibre": _buscar_mercadolibre,
    "paris": _buscar_paris,
    "ripley": _buscar_ripley,
}

# Tiendas para las que existe un fallback con navegador headless, y que de
# verdad cambia el resultado (Paris/MercadoLibre no mejoran con Playwright —
# ver docstring — así que no tiene sentido pagar el costo de abrir un
# navegador para ellas).
_BUSCADORES_NAVEGADOR = {
    "ripley": _buscar_ripley_navegador,
}


def scraper_tiendas(producto: str, tiendas: str = "mercadolibre,falabella,paris,ripley", usar_navegador: bool = False) -> dict:
    """Punto de entrada MCP. Devuelve {tienda: [ofertas...]} — el fallo de una
    tienda no impide devolver resultados de las demás.

    usar_navegador=True: para las tiendas donde el método rápido (httpx) está
    bloqueado pero SÍ existe un fallback con navegador headless que funciona
    de verdad (hoy solo Ripley), usa ese en vez del método rápido. Es más
    lento (abre un Chromium real) — pensado para ofrecerlo como opción
    cuando el método rápido no trajo resultados, no como default.
    """
    resultado: dict[str, list[dict[str, Any]]] = {}
    for tienda in [t.strip() for t in tiendas.split(",") if t.strip()]:
        if usar_navegador and tienda in _BUSCADORES_NAVEGADOR:
            resultado[tienda] = _BUSCADORES_NAVEGADOR[tienda](producto)
            continue
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
    ap.add_argument("--usar-navegador", action="store_true", dest="usar_navegador")
    args = ap.parse_args()
    print(scraper_tiendas(args.producto, args.tiendas, args.usar_navegador))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
