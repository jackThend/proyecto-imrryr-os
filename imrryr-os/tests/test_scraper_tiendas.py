"""Lógica determinista del cotizador de tiendas (skills/scraper_tiendas.py)."""
import scraper_tiendas as st


def test_precio_a_float_formato_chileno():
    assert st._precio_a_float("$ 869.990") == 869990.0
    assert st._precio_a_float("969.990") == 969990.0
    assert st._precio_a_float("$1.299.990") == 1299990.0


def test_precio_a_float_vacio_o_sin_digitos():
    assert st._precio_a_float("") is None
    assert st._precio_a_float("Agotado") is None
    assert st._precio_a_float(None) is None


def test_tienda_desconocida_devuelve_lista_vacia():
    resultado = st.scraper_tiendas("notebook", tiendas="tiendafantasma")
    assert resultado == {"tiendafantasma": []}


def test_fallback_navegador_existe_solo_para_tiendas_verificadas():
    # Solo Ripley demostró funcionar con navegador headless (Paris renderiza
    # "0 productos" incluso en navegador real, MercadoLibre exige token).
    # Si alguien agrega una tienda acá sin verificarla en vivo, este test
    # obliga a mirar dos veces.
    assert set(st._BUSCADORES_NAVEGADOR.keys()) == {"ripley"}


def test_usar_navegador_no_afecta_tiendas_sin_fallback(monkeypatch):
    # Con usar_navegador=True, Falabella debe seguir usando el método rápido.
    llamadas = []
    monkeypatch.setitem(st._BUSCADORES, "falabella", lambda q: llamadas.append(q) or [])
    st.scraper_tiendas("notebook", tiendas="falabella", usar_navegador=True)
    assert llamadas == ["notebook"]
