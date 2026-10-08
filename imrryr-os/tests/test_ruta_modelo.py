"""Ruta de modelo: LiteLLM por defecto, proveedor nativo de OpenCode para Zen gratis.

Contexto: los modelos gratuitos de OpenCode Zen devuelven 403 ("solo se puede
usar desde dentro de OpenCode") cuando llegan por un passthrough OpenAI
compatible como LiteLLM, incluso con clave válida. Solo responden al proveedor
nativo `opencode` (y sin credenciales). Estos tests fijan que esa excepción no
se filtre al resto de proveedores.
"""
import json

import pytest

from config import cuentas_ia
from scripts import sync_agentes


@pytest.fixture
def cuentas(tmp_path, monkeypatch):
    ruta = tmp_path / "cuentas_ia.json"
    monkeypatch.setattr(cuentas_ia, "CUENTAS_PATH", ruta)

    def escribir(lista):
        ruta.write_text(json.dumps({"cuentas": lista}), encoding="utf-8")

    return escribir


def test_sin_cuenta_activa_va_por_litellm(cuentas):
    cuentas([])
    assert cuentas_ia.modelo_para_agente() == {"providerID": "imrryr-llm", "modelID": "imrryr-activo"}


def test_cuenta_normal_va_por_litellm(cuentas):
    cuentas([{"id": "g", "proveedor": "gemini", "modelo": "gemini/gemini-2.5-flash", "activa": True}])
    assert cuentas_ia.modelo_para_agente()["providerID"] == "imrryr-llm"


def test_opencode_go_pagado_sigue_por_litellm(cuentas):
    # GO es de pago y sí funciona por passthrough con su cabecera: no es nativo.
    cuentas([{"id": "go", "proveedor": "opencode_go", "modelo": "kimi-k2.7-code", "activa": True}])
    assert cuentas_ia.modelo_para_agente()["providerID"] == "imrryr-llm"


def test_zen_gratis_sale_por_el_provider_nativo(cuentas):
    cuentas([{"id": "z", "proveedor": "opencode_zen", "modelo": "nemotron-3-ultra-free", "activa": True}])
    assert cuentas_ia.modelo_para_agente() == {"providerID": "opencode", "modelID": "nemotron-3-ultra-free"}


def test_zen_sin_modelo_elegido_usa_el_recomendado(cuentas):
    cuentas([{"id": "z", "proveedor": "opencode_zen", "activa": True}])
    assert cuentas_ia.modelo_para_agente()["modelID"] == cuentas_ia.PROVEEDORES["opencode_zen"]["modelo_base"]


def test_solo_cuenta_la_activa(cuentas):
    cuentas([
        {"id": "z", "proveedor": "opencode_zen", "modelo": "big-pickle", "activa": False},
        {"id": "g", "proveedor": "gemini", "activa": True},
    ])
    assert cuentas_ia.modelo_para_agente()["providerID"] == "imrryr-llm"


def test_zen_no_requiere_key_y_es_nativo():
    prov = cuentas_ia.PROVEEDORES["opencode_zen"]
    assert prov["nativo_opencode"] is True
    assert prov["requiere_key"] is False


def test_es_modelo_gratuito():
    assert cuentas_ia.es_modelo_gratuito("big-pickle")
    assert cuentas_ia.es_modelo_gratuito("nemotron-3-ultra-free")
    assert not cuentas_ia.es_modelo_gratuito("claude-sonnet-5")
    assert not cuentas_ia.es_modelo_gratuito("gpt-5.5")


class _Resp:
    status_code = 200

    def json(self):
        return {"data": [{"id": i} for i in ("big-pickle", "gpt-5.5", "space-bunny-free", "claude-sonnet-5")]}


def test_catalogo_zen_sin_clave_solo_lista_gratuitos(monkeypatch):
    import httpx

    visto = {}

    def falso_get(url, headers=None, timeout=None):
        visto["headers"] = headers
        return _Resp()

    monkeypatch.setattr(httpx, "get", falso_get)
    r = cuentas_ia.listar_modelos_remotos("opencode_zen")
    assert r["ok"] is True
    assert [m["id"] for m in r["modelos"]] == ["big-pickle", "space-bunny-free"]
    assert "Authorization" not in visto["headers"]


def test_catalogo_de_go_sigue_exigiendo_clave():
    r = cuentas_ia.listar_modelos_remotos("opencode_go")
    assert r["ok"] is False and "API key" in r["error"]


def test_bloque_de_litellm_nunca_lleva_la_clave_real():
    bloque = cuentas_ia._bloque_activo(
        {"proveedor": "opencode_go", "modelo": "kimi-k2.7-code", "api_key": "sk-SECRETO-NO-DEBE-APARECER"}
    )
    assert "sk-SECRETO" not in bloque
    assert "os.environ/IMRRYR_ACTIVE_API_KEY" in bloque
    assert "x-opencode-session" in bloque


def test_activar_cuenta_nativa_no_toca_litellm_pero_si_reinicia_opencode(cuentas, monkeypatch):
    cuentas([{"id": "z", "proveedor": "opencode_zen", "modelo": "big-pickle", "activa": False}])
    llamadas = []
    monkeypatch.setattr(cuentas_ia, "_reiniciar_litellm", lambda: llamadas.append("litellm") or True)
    monkeypatch.setattr(cuentas_ia, "_reiniciar_opencode", lambda: llamadas.append("opencode") or True)
    monkeypatch.setattr(cuentas_ia, "_regenerar_litellm_config", lambda c: llamadas.append("yaml"))
    monkeypatch.setattr(cuentas_ia, "_actualizar_env", lambda k, v: llamadas.append("env"))
    monkeypatch.setattr(cuentas_ia, "_opencode_usa_ruta_nativa", lambda: False)
    # Sin esto el test depende de que haya un opencode instalado: en CI no lo hay y
    # activar_cuenta se niega por "versión desconocida".
    monkeypatch.setattr(cuentas_ia, "version_opencode", lambda: (1, 18, 32))

    assert cuentas_ia.activar_cuenta("z")["ok"] is True
    assert llamadas == ["opencode"]


def test_activar_cuenta_normal_no_reinicia_opencode(cuentas, monkeypatch):
    cuentas([{"id": "g", "proveedor": "gemini", "api_key": "k", "activa": False}])
    llamadas = []
    monkeypatch.setattr(cuentas_ia, "_reiniciar_litellm", lambda: llamadas.append("litellm") or True)
    monkeypatch.setattr(cuentas_ia, "_reiniciar_opencode", lambda: llamadas.append("opencode") or True)
    monkeypatch.setattr(cuentas_ia, "_regenerar_litellm_config", lambda c: llamadas.append("yaml"))
    monkeypatch.setattr(cuentas_ia, "_actualizar_env", lambda k, v: llamadas.append("env"))
    monkeypatch.setattr(cuentas_ia, "_opencode_usa_ruta_nativa", lambda: False)

    cuentas_ia.activar_cuenta("g")
    assert llamadas == ["env", "yaml", "litellm"]


def test_volver_de_nativa_a_normal_reinicia_opencode(cuentas, monkeypatch):
    cuentas([{"id": "g", "proveedor": "gemini", "api_key": "k", "activa": False}])
    llamadas = []
    monkeypatch.setattr(cuentas_ia, "_reiniciar_litellm", lambda: True)
    monkeypatch.setattr(cuentas_ia, "_reiniciar_opencode", lambda: llamadas.append("opencode") or True)
    monkeypatch.setattr(cuentas_ia, "_regenerar_litellm_config", lambda c: None)
    monkeypatch.setattr(cuentas_ia, "_actualizar_env", lambda k, v: None)
    monkeypatch.setattr(cuentas_ia, "_opencode_usa_ruta_nativa", lambda: True)

    cuentas_ia.activar_cuenta("g")
    assert llamadas == ["opencode"]


def test_sync_agentes_apunta_los_agentes_a_la_ruta_activa(monkeypatch):
    monkeypatch.setattr(sync_agentes, "modelo_para_agente", lambda: {"providerID": "opencode", "modelID": "big-pickle"})
    assert sync_agentes._modelo_de_agente({}) == "opencode/big-pickle"
    # un modelo_preferido explícito se respeta y no lo pisa la ruta activa
    assert sync_agentes._modelo_de_agente({"modelo_preferido": "otro-modelo"}) == "imrryr-llm/otro-modelo"


def test_sync_agentes_por_defecto_usa_el_alias_de_litellm(monkeypatch):
    monkeypatch.setattr(sync_agentes, "modelo_para_agente", lambda: {"providerID": "imrryr-llm", "modelID": "imrryr-activo"})
    assert sync_agentes._modelo_de_agente({}) == "imrryr-llm/imrryr-activo"


def test_el_instalador_incluye_ruta_modelo():
    """chat.py, el gateway y sync_agentes la importan: si el paquete no la
    lleva, la app instalada falla al arrancar aunque en desarrollo funcione."""
    from scripts import package

    assert "ruta_modelo.py" in package.CORE_SKILLS


def test_no_activa_zen_si_el_opencode_embebido_es_viejo(cuentas, monkeypatch):
    """Caso real: bin/opencode.exe era 1.17.11 y la capa gratuita exige >=1.18.0,
    así que cada mensaje fallaba con 403 aunque la ruta nativa estuviera bien."""
    cuentas([
        {"id": "g", "proveedor": "gemini", "activa": True},
        {"id": "z", "proveedor": "opencode_zen", "modelo": "big-pickle", "activa": False},
    ])
    monkeypatch.setattr(cuentas_ia, "version_opencode", lambda: (1, 17, 11))
    llamadas = []
    monkeypatch.setattr(cuentas_ia, "_reiniciar_opencode", lambda: llamadas.append("opencode") or True)

    r = cuentas_ia.activar_cuenta("z")
    assert r["ok"] is False and "1.18.0" in r["error"] and "1.17.11" in r["error"]
    assert llamadas == []
    # no se cambió de cuenta: sigue activa la anterior
    assert cuentas_ia.modelo_para_agente()["providerID"] == "imrryr-llm"


def test_activa_zen_con_opencode_reciente(cuentas, monkeypatch):
    cuentas([{"id": "z", "proveedor": "opencode_zen", "activa": False}])
    monkeypatch.setattr(cuentas_ia, "version_opencode", lambda: (1, 18, 32))
    monkeypatch.setattr(cuentas_ia, "_reiniciar_opencode", lambda: True)
    monkeypatch.setattr(cuentas_ia, "_opencode_usa_ruta_nativa", lambda: False)
    assert cuentas_ia.activar_cuenta("z")["ok"] is True


# --- Permisos de los agentes en la ruta nativa (Zen gratis) -------------------
# Verificado en vivo: el servidor de la capa gratuita devuelve 403 si a la
# petición le falta CUALQUIER herramienta nativa (bastó quitar `bash`), y
# OpenCode la quita de la lista cuando su regla es un `deny` general. Por eso en
# la ruta nativa cada herramienta lleva un patrón que nunca coincide: sigue
# listada, pero cualquier uso real queda denegado.

def test_ruta_normal_conserva_deny_liso():
    permisos = sync_agentes._permisos_nativos(False)
    assert permisos["bash"] == "deny" and permisos["read"] == "deny" and permisos["task"] == "deny"


def test_ruta_nativa_mantiene_las_herramientas_listadas_pero_bloqueadas():
    permisos = sync_agentes._permisos_nativos(True)
    for herramienta in sync_agentes.HERRAMIENTAS_CON_PATRON:
        regla = permisos[herramienta]
        assert regla["*"] == "deny", herramienta                      # todo lo real, denegado
        assert list(regla) == ["*", sync_agentes.PATRON_NUNCA], herramienta  # pero no es un deny general puro
    # webfetch/websearch solo aceptan una acción simple (OpenCode rechaza objetos)
    assert permisos["webfetch"] == "deny" and permisos["websearch"] == "deny"


def test_el_patron_que_desbloquea_nunca_puede_coincidir_con_algo_real():
    assert sync_agentes.PATRON_NUNCA.startswith("__") and "/" not in sync_agentes.PATRON_NUNCA


def test_asistente_puede_delegar_con_task_en_ambas_rutas():
    assert sync_agentes._permisos_nativos(True, permitir_task=True)["task"] == "allow"
    assert sync_agentes._permisos_nativos(False, permitir_task=True)["task"] == "allow"


def test_el_prompt_de_herramientas_solo_se_agrega_en_la_ruta_nativa():
    assert sync_agentes._prompt_de_agente("Agenda cosas", False) == {}
    prompt = sync_agentes._prompt_de_agente("Agenda cosas", True)["prompt"]
    assert prompt.startswith("Agenda cosas") and "BLOQUEADAS" in prompt and "imrryr_*" in prompt


# ---------------------------------------------------------------- cuenta inicial
def _catalogo(*ids):
    return lambda proveedor: {"ok": True, "modelos": [{"id": i, "nombre": i} for i in ids]}


def test_instalacion_nueva_arranca_con_zen_gratis_activo(cuentas, monkeypatch):
    """Sin archivo de cuentas (instalación nueva) queda activa la capa gratuita, que no
    pide clave: antes el usuario tenía que crear una cuenta y el formulario lo llevaba a Gemini."""
    monkeypatch.setattr(cuentas_ia, "version_opencode", lambda: (1, 18, 32))
    monkeypatch.setattr(cuentas_ia, "listar_modelos_remotos", _catalogo(*cuentas_ia.MODELOS_GRATIS_PREFERIDOS, "otro-free"))
    assert cuentas_ia.asegurar_cuenta_inicial() is True
    lista = cuentas_ia.listar_cuentas()
    assert len(lista) == 1 and lista[0]["activa"] is True
    assert lista[0]["proveedor"] == "opencode_zen"
    assert lista[0]["modelo"] == cuentas_ia.MODELOS_GRATIS_PREFERIDOS[0] == "mimo-v2.6-flash-free"
    assert "api_key" not in lista[0]
    # y los agentes salen por el proveedor nativo de OpenCode, no por LiteLLM
    assert cuentas_ia.modelo_para_agente() == {"providerID": "opencode", "modelID": "mimo-v2.6-flash-free"}


def test_si_el_mejor_modelo_gratis_ya_no_esta_se_usa_el_siguiente(cuentas, monkeypatch):
    """Los modelos gratuitos rotan: no se puede dejar una cuenta apuntando a uno que ya no existe."""
    monkeypatch.setattr(cuentas_ia, "version_opencode", lambda: (1, 18, 32))
    monkeypatch.setattr(cuentas_ia, "listar_modelos_remotos", _catalogo("big-pickle", "nemotron-3.5-lightning-free", "x-free"))
    cuentas_ia.asegurar_cuenta_inicial()
    assert cuentas_ia.listar_cuentas()[0]["modelo"] == "nemotron-3.5-lightning-free"


def test_sin_red_se_usa_el_modelo_preferido(cuentas, monkeypatch):
    monkeypatch.setattr(cuentas_ia, "version_opencode", lambda: (1, 18, 32))
    monkeypatch.setattr(cuentas_ia, "listar_modelos_remotos", lambda p: {"ok": False, "error": "sin red"})
    cuentas_ia.asegurar_cuenta_inicial()
    assert cuentas_ia.listar_cuentas()[0]["modelo"] == "mimo-v2.6-flash-free"


def test_no_pisa_las_cuentas_que_el_usuario_ya_tiene(cuentas, monkeypatch):
    monkeypatch.setattr(cuentas_ia, "version_opencode", lambda: (1, 18, 32))
    cuentas([{"id": "g", "proveedor": "gemini", "modelo": "gemini/gemini-2.5-flash", "activa": True}])
    assert cuentas_ia.asegurar_cuenta_inicial() is False
    assert [c["id"] for c in cuentas_ia.listar_cuentas()] == ["g"]


def test_si_el_usuario_vacio_sus_cuentas_no_se_vuelve_a_sembrar(cuentas, monkeypatch):
    """Archivo presente pero sin cuentas = decisión del usuario, no una instalación nueva."""
    monkeypatch.setattr(cuentas_ia, "version_opencode", lambda: (1, 18, 32))
    cuentas([])
    assert cuentas_ia.asegurar_cuenta_inicial() is False
    assert cuentas_ia.listar_cuentas() == []


@pytest.mark.parametrize("version", [None, (1, 17, 11)])
def test_no_activa_una_cuenta_rota_si_el_opencode_es_demasiado_viejo(cuentas, monkeypatch, version):
    monkeypatch.setattr(cuentas_ia, "version_opencode", lambda: version)
    assert cuentas_ia.asegurar_cuenta_inicial() is False
    assert cuentas_ia.listar_cuentas() == []


def test_zen_es_el_primer_proveedor_del_formulario():
    """El formulario deja seleccionado el primero: con Gemini ahí, quien quería OpenCode
    guardaba su cuenta como Gemini (caso real)."""
    assert next(iter(cuentas_ia.PROVEEDORES)) == "opencode_zen"
