#!/usr/bin/env python3
"""
navegar_web.py — Skill: Búsqueda y lectura de páginas web
=============================================================
`buscar`: usa lite.duckduckgo.com/lite/ vía httpx (HTML plano, sin
JavaScript) — es la única variante de DuckDuckGo que respondió con
resultados reales sin bloqueo anti-bot durante el desarrollo (tanto
html.duckduckgo.com como Bing devolvieron 403/páginas vacías a peticiones
simples). No requiere navegador ni API key.

`leer`: abre la URL con Playwright (navegador headless real) y extrae el
texto principal — esto sí hace falta para páginas que renderizan su
contenido por JavaScript, cosa que una petición HTTP simple no puede ver.

Uso:
    python skills/navegar_web.py --accion buscar --query "noticias tecnologia chile"
    python skills/navegar_web.py --accion leer --url "https://www.xataka.com/"
"""
from __future__ import annotations

import argparse
import re
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

import httpx

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
}

_RE_RESULTADO = re.compile(r'<a rel="nofollow" href="([^"]+)"[^>]*>(.*?)</a>')
_RE_TAGS = re.compile(r"<[^<]+?>")


def log(msg: str) -> None:
    print(f"[navegar_web] {msg}", flush=True)


def _limpiar_html(texto: str) -> str:
    return _RE_TAGS.sub("", texto).strip()


def _buscar(query: str, max_resultados: int) -> dict[str, Any]:
    try:
        r = httpx.get(
            "https://lite.duckduckgo.com/lite/", params={"q": query}, headers=HEADERS, timeout=15,
        )
        r.raise_for_status()
        r.encoding = "utf-8"
        texto = r.text

        resultados = []
        for href, titulo_html in _RE_RESULTADO.findall(texto):
            if "uddg=" not in href:
                continue
            url_real = unquote(parse_qs(urlparse(href).query).get("uddg", [""])[0])
            titulo = _limpiar_html(titulo_html)
            if url_real and titulo:
                resultados.append({"titulo": titulo, "url": url_real})
            if len(resultados) >= max_resultados:
                break
        return {"ok": True, "resultados": resultados}
    except httpx.HTTPError as e:
        log(f"búsqueda falló: {e}")
        return {"ok": False, "error": str(e)}


def _leer(url: str, max_caracteres: int) -> dict[str, Any]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {"ok": False, "error": "playwright no está instalado (pip install playwright && playwright install chromium)"}

    try:
        with sync_playwright() as p:
            navegador = p.chromium.launch(headless=True)
            try:
                pagina = navegador.new_page(user_agent=HEADERS["User-Agent"])
                pagina.goto(url, wait_until="domcontentloaded", timeout=20000)
                titulo = pagina.title()
                # Preferir <article>/<main> (contenido real) antes que todo el <body>
                # (que trae menús, publicidad, etc.) — si no existen, cae a body.
                contenido_el = pagina.query_selector("article") or pagina.query_selector("main")
                texto = (contenido_el.inner_text() if contenido_el else pagina.inner_text("body")) or ""
                texto = re.sub(r"\n{3,}", "\n\n", texto).strip()
                return {"ok": True, "titulo": titulo, "texto": texto[:max_caracteres], "url": url}
            finally:
                navegador.close()
    except Exception as e:
        log(f"no se pudo leer {url}: {e}")
        return {"ok": False, "error": str(e)}


def navegar_web(accion: str = "", query: str = "", url: str = "", max_resultados: int = 5, max_caracteres: int = 4000) -> dict:
    """Punto de entrada MCP. accion: buscar | leer"""
    if accion == "buscar":
        if not query:
            return {"ok": False, "error": "falta 'query'"}
        return _buscar(query, max_resultados)
    if accion == "leer":
        if not url:
            return {"ok": False, "error": "falta 'url'"}
        return _leer(url, max_caracteres)
    return {"ok": False, "error": f"acción desconocida: {accion}"}


def main() -> int:
    ap = argparse.ArgumentParser(description="Búsqueda y lectura de páginas web")
    ap.add_argument("--accion", type=str, required=True)
    ap.add_argument("--query", type=str, default="")
    ap.add_argument("--url", type=str, default="")
    ap.add_argument("--max-resultados", type=int, default=5, dest="max_resultados")
    ap.add_argument("--max-caracteres", type=int, default=4000, dest="max_caracteres")
    args = ap.parse_args()

    resultado = navegar_web(
        accion=args.accion, query=args.query, url=args.url,
        max_resultados=args.max_resultados, max_caracteres=args.max_caracteres,
    )
    print(resultado)
    return 0 if resultado.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
