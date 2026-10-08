"""Los skills de navegador no deben exigir descargar Chromium: usan el que tenga el cliente."""
import pytest

from scripts import package
from skills import navegador_cliente


class _Chromium:
    def __init__(self, falla_propio=False, fallan=()):
        self.falla_propio, self.fallan, self.lanzados = falla_propio, set(fallan), []

    def launch(self, headless=True, executable_path=None):
        if executable_path is None and self.falla_propio:
            raise RuntimeError("Executable doesn't exist at ...\nrun playwright install")
        if executable_path in self.fallan:
            raise RuntimeError("no arranca")
        self.lanzados.append(executable_path)
        return f"navegador:{executable_path}"


class _P:
    def __init__(self, **kw):
        self.chromium = _Chromium(**kw)


def test_usa_el_chromium_de_playwright_si_esta_instalado(monkeypatch):
    monkeypatch.setattr(navegador_cliente, "navegadores_del_cliente", lambda: ["C:/chrome.exe"])
    p = _P()
    assert navegador_cliente.lanzar_navegador(p) == "navegador:None"


def test_sin_chromium_de_playwright_usa_el_navegador_del_cliente(monkeypatch):
    """Caso real del paquete: Chromium no viaja, pero el cliente tiene Chrome o Edge."""
    monkeypatch.setattr(navegador_cliente, "navegadores_del_cliente", lambda: ["C:/chrome.exe", "C:/edge.exe"])
    assert navegador_cliente.lanzar_navegador(_P(falla_propio=True)) == "navegador:C:/chrome.exe"


def test_si_el_primer_navegador_no_arranca_prueba_el_siguiente(monkeypatch):
    monkeypatch.setattr(navegador_cliente, "navegadores_del_cliente", lambda: ["C:/chrome.exe", "C:/edge.exe"])
    p = _P(falla_propio=True, fallan={"C:/chrome.exe"})
    assert navegador_cliente.lanzar_navegador(p) == "navegador:C:/edge.exe"


def test_sin_ningun_navegador_el_error_se_entiende(monkeypatch):
    monkeypatch.setattr(navegador_cliente, "navegadores_del_cliente", lambda: [])
    with pytest.raises(RuntimeError, match="Chrome, Microsoft Edge o Brave"):
        navegador_cliente.lanzar_navegador(_P(falla_propio=True))


def test_el_helper_viaja_con_los_skills_que_lo_usan():
    """Si falta en el paquete, navegar_web y scraper_tiendas fallan al instalarse."""
    assert "navegador_cliente.py" in package.CORE_SKILLS
