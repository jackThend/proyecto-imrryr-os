"""Parsing de resultados de búsqueda (skills/navegar_web.py).

El buscador depende del formato HTML de lite.duckduckgo.com (links envueltos
en //duckduckgo.com/l/?uddg=<url-real-urlencoded>). Este test fija el contrato
de parsing con una respuesta enlatada — si DuckDuckGo cambia el formato, el
test de parsing sigue en verde (eso se detecta en vivo), pero si ALGUIEN
rompe el unwrap/regex al editar el código, esto lo pesca al tiro.
"""
import httpx

import navegar_web as nw

_HTML_DDG_LITE = """
<html><body><table>
<tr><td>
  <a rel="nofollow" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.xataka.com%2Fnoticia-uno&rut=abc123" class='result-link'>Primera <b>noticia</b> de tecnología</a>
</td></tr>
<tr><td>
  <a rel="nofollow" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Ffayerwayer.com%2Fsegunda&rut=def456" class='result-link'>Segunda noticia</a>
</td></tr>
<tr><td>
  <a rel="nofollow" href="https://duckduckgo.com/ads/sin-uddg" class='result-link'>Un anuncio que no debe aparecer</a>
</td></tr>
</table></body></html>
"""


class _RespuestaFalsa:
    text = _HTML_DDG_LITE
    encoding = "utf-8"

    def raise_for_status(self):
        pass


def test_buscar_desenvuelve_urls_reales(monkeypatch):
    monkeypatch.setattr(httpx, "get", lambda *a, **kw: _RespuestaFalsa())
    r = nw._buscar("noticias tecnologia", max_resultados=5)
    assert r["ok"] is True
    urls = [x["url"] for x in r["resultados"]]
    assert urls == ["https://www.xataka.com/noticia-uno", "https://fayerwayer.com/segunda"]


def test_buscar_limpia_html_del_titulo(monkeypatch):
    monkeypatch.setattr(httpx, "get", lambda *a, **kw: _RespuestaFalsa())
    r = nw._buscar("x", max_resultados=5)
    assert r["resultados"][0]["titulo"] == "Primera noticia de tecnología"


def test_buscar_respeta_max_resultados(monkeypatch):
    monkeypatch.setattr(httpx, "get", lambda *a, **kw: _RespuestaFalsa())
    r = nw._buscar("x", max_resultados=1)
    assert len(r["resultados"]) == 1


def test_accion_desconocida():
    assert nw.navegar_web(accion="volar")["ok"] is False


def test_buscar_sin_query():
    assert nw.navegar_web(accion="buscar")["ok"] is False
