"""Tests de la API del dashboard (dashboard/server.py + dashboard/api/).

Cubren el CONTRATO HTTP sin depender de servicios vivos ni tocar la DB del
usuario: validaciones que cortan antes del I/O, valores por defecto cuando
faltan archivos de config, y el camino de error humanizado del chat.
Todo lo que podría escribir en disco se redirige a tmp_path vía monkeypatch.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
# El paquete api/ vive junto a server.py; server.py también inserta estas
# rutas, pero importarlo exige resolver 'server' primero.
sys.path.insert(0, str(ROOT / "dashboard"))

pytest.importorskip("fastapi.testclient")

from fastapi.testclient import TestClient  # noqa: E402
from server import app  # noqa: E402


@pytest.fixture(scope="module")
def cliente():
    return TestClient(app)


# ---------------------------------------------------------------------------
# Contrato de rutas: el HTML llama por nombre exacto; si una ruta cambia o
# desaparece en un refactor (como el split en routers), este test lo grita.
# ---------------------------------------------------------------------------
RUTAS_CRITICAS = {
    "/", "/api/chat", "/api/status", "/api/widgets", "/api/uso-ia",
    "/api/finanzas", "/api/finanzas/export",
    "/api/finanzas/importar/estado", "/api/finanzas/importar/informe",
    "/api/semillas", "/api/proyectos",
    "/api/correo/cuentas", "/api/correo/borradores",
    "/api/oportunidades", "/api/perfil-negocio",
    "/api/agenda/eventos", "/api/pendientes",
    "/api/compras/seguimientos", "/api/compras/prefs",
    "/api/navegacion/ultimo-audio",
    "/api/ajustes/cuentas-ia", "/api/ajustes/fondo",
    "/api/modulos", "/api/modulos/password-estado",
    "/api/rrss/posts", "/api/respaldos",
}


def test_rutas_criticas_existen():
    expuestas = set(app.openapi()["paths"].keys())
    faltantes = RUTAS_CRITICAS - expuestas
    assert not faltantes, f"rutas que desaparecieron del dashboard: {sorted(faltantes)}"


def test_el_html_del_dashboard_se_sirve(cliente):
    r = cliente.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "__IMRRYR_CHAT_TIMEOUT_MS__" not in r.text
    assert "/static/dashboard.js" in r.text


def test_css_del_dashboard_se_sirve(cliente):
    r = cliente.get("/static/dashboard.css")
    assert r.status_code == 200
    assert "text/css" in r.headers["content-type"]
    assert ":root" in r.text


def test_javascript_del_dashboard_se_sirve(cliente):
    r = cliente.get("/static/dashboard.js")
    assert r.status_code == 200
    assert "javascript" in r.headers["content-type"]
    assert "enviarChatGenerico" in r.text
    assert "AbortSignal.timeout(window.IMRRYR_CONFIG.chatTimeoutMs)" in r.text
    assert "__IMRRYR_CHAT_TIMEOUT_MS__" not in r.text


def test_html_inyecta_timeout_configurado(cliente, monkeypatch):
    monkeypatch.setenv("IMRRYR_CHAT_TIMEOUT_SECONDS", "123")
    r = cliente.get("/")
    assert r.status_code == 200
    assert "chatTimeoutMs: Number('123000')" in r.text


# ---------------------------------------------------------------------------
# Widgets: lectura directa de /agentes/*.yaml (sin DB ni red)
# ---------------------------------------------------------------------------
def test_widgets_lista_los_agentes_yaml(cliente):
    r = cliente.get("/api/widgets")
    assert r.status_code == 200
    ids = [w["id"] for w in r.json()["widgets"]]
    assert len(ids) >= 10, f"se esperaban ~11 agentes, llegaron {len(ids)}"
    assert "agente_build" in ids  # el agente primario debe ser visible como widget


def test_widgets_traen_nombre_y_herramientas(cliente):
    r = cliente.get("/api/widgets")
    for w in r.json()["widgets"]:
        assert w["nombre"], f"widget {w['id']} sin nombre"
        assert isinstance(w["herramientas"], list)


# ---------------------------------------------------------------------------
# Estado del sistema: formato estable, sin importar qué puertos estén arriba
# ---------------------------------------------------------------------------
def test_status_reporta_los_tres_servicios(cliente):
    r = cliente.get("/api/status")
    assert r.status_code == 200
    servicios = r.json()["servicios"]
    assert set(servicios.keys()) == {"litellm", "opencode", "gateway"}
    assert all(isinstance(v, bool) for v in servicios.values())


# ---------------------------------------------------------------------------
# Validaciones que cortan ANTES de tocar disco/red (seguras en cualquier máquina)
# ---------------------------------------------------------------------------
def test_semilla_sin_titulo_o_contenido_rechaza_400(cliente):
    r = cliente.post("/api/semillas", json={"titulo": "", "contenido": ""})
    assert r.status_code == 400


def test_oportunidad_sin_estado_rechaza_400(cliente):
    r = cliente.post("/api/oportunidades/1/estado", json={"estado": ""})
    assert r.status_code == 400


def test_post_rrss_sin_campos_obligatorios_rechaza_400(cliente):
    r = cliente.post("/api/rrss/posts", json={"contenido": "hola"})
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# Valores por defecto cuando falta la config local (redirigida a tmp_path)
# ---------------------------------------------------------------------------
def test_compras_prefs_vacias_si_no_hay_archivo(cliente, tmp_path, monkeypatch):
    import api.compras as compras
    monkeypatch.setattr(compras, "COMPRAS_PREFS_PATH", tmp_path / "no_existe.json")
    r = cliente.get("/api/compras/prefs")
    assert r.status_code == 200
    assert r.json() == {"cuenta_correo_id": "", "destinatario": ""}


def test_ultimo_audio_none_si_no_hay_registro(cliente, tmp_path, monkeypatch):
    import api.navegacion as navegacion
    monkeypatch.setattr(navegacion, "ULTIMO_AUDIO_PATH", tmp_path / "no_existe.json")
    r = cliente.get("/api/navegacion/ultimo-audio")
    assert r.status_code == 200
    assert r.json() == {"url": None}


def test_finanzas_devuelve_estructura_vacia_sin_db(cliente, tmp_path, monkeypatch):
    import api.deps as deps
    monkeypatch.setattr(deps, "DB_PATH", tmp_path / "no_existe.db")
    r = cliente.get("/api/finanzas")
    assert r.status_code == 200
    datos = r.json()
    assert datos["gastos"] == [] and datos["total"] == 0
    assert datos["por_categoria"] == {} and datos["por_mes"] == {}


def test_correo_bandeja_sin_cuenta_no_consulta_nada(cliente):
    r = cliente.get("/api/correo/bandeja")
    assert r.status_code == 200
    assert r.json() == {"correos": []}


# ---------------------------------------------------------------------------
# Módulos: la barrera de contraseña responde bien sin config real
# ---------------------------------------------------------------------------
def test_configurar_password_rechaza_si_ya_existe(cliente, tmp_path, monkeypatch):
    import config.admin_modulos as admin_modulos
    existente = tmp_path / "admin_modulos.json"
    existente.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(admin_modulos, "RUTA", existente)
    r = cliente.post("/api/modulos/configurar-password", json={"password": "12345"})
    assert r.status_code == 400


def test_configurar_password_corta_da_error_claro(cliente, tmp_path, monkeypatch):
    import config.admin_modulos as admin_modulos
    monkeypatch.setattr(admin_modulos, "RUTA", tmp_path / "no_existe.json")
    r = cliente.post("/api/modulos/configurar-password", json={"password": "12"})
    assert r.status_code == 200
    assert r.json()["ok"] is False
    assert not (tmp_path / "no_existe.json").exists(), "no debe escribir nada con password inválida"


def test_verificar_password_sin_config_da_false(cliente, tmp_path, monkeypatch):
    import config.admin_modulos as admin_modulos
    monkeypatch.setattr(admin_modulos, "RUTA", tmp_path / "no_existe.json")
    r = cliente.post("/api/modulos/verificar-password", json={"password": "lo_que_sea"})
    assert r.status_code == 200
    assert r.json() == {"ok": False}


# ---------------------------------------------------------------------------
# Chat: con OpenCode caído, el error llega humanizado (nunca un str() vacío)
# ---------------------------------------------------------------------------
def test_chat_con_opencode_caido_error_humanizado(cliente, monkeypatch):
    import httpx

    # Sin red real: cualquier POST async falla como conexión rechazada,
    # determinista y al instante (TestClient usa httpx síncrono, no se afecta).
    def _conexion_rechazada(*args, **kwargs):
        raise httpx.ConnectError("[WinError] conexión rechazada (simulada)")

    monkeypatch.setattr("httpx.AsyncClient.post", _conexion_rechazada)
    r = cliente.post("/api/chat", json={"mensaje": "ping", "agente": "build"})
    assert r.status_code == 500
    cuerpo = r.json()
    assert cuerpo.get("error"), "el mensaje de error no puede venir vacío"


def test_agentes_disponibles_solo_lista_los_que_existen_y_estan_activos(cliente, tmp_path, monkeypatch):
    """Cada perfil empaqueta solo parte de los agentes. El panel oculta las pestañas de los demás:
    antes mostraba Agenda, Compras, Código... y al escribirles el servidor respondia 500."""
    import api.deps as deps
    (tmp_path / "agente_agenda.yaml").write_text("nombre: Agenda\n", encoding="utf-8")
    (tmp_path / "agente_compras.yaml").write_text("nombre: Compras\nactivo: false\n", encoding="utf-8")
    (tmp_path / "guardia_seguridad.yaml").write_text("nombre: Guardia\nactivo: true\n", encoding="utf-8")
    (tmp_path / "roto.yaml").write_text(": : no es yaml :\n  - [", encoding="utf-8")
    monkeypatch.setattr(deps, "AGENTES_DIR", tmp_path)
    r = cliente.get("/api/agentes-disponibles")
    assert r.status_code == 200
    assert r.json() == {"agentes": ["agenda", "guardia_seguridad"]}


def test_activar_y_desactivar_un_modulo_cambia_que_agentes_hay(cliente, tmp_path, monkeypatch):
    """Los opcionales viajan desactivados; activarlos desde Módulos debe dejarlos disponibles y
    pedir el reinicio de OpenCode (que lee su config solo al arrancar)."""
    import api.deps as deps
    from api import modulos

    (tmp_path / "agente_agenda.yaml").write_text("nombre: Agenda\nactivo: false\n", encoding="utf-8")
    monkeypatch.setattr(deps, "AGENTES_DIR", tmp_path)
    reinicios = []
    monkeypatch.setattr(modulos, "_sincronizar_agentes", lambda: reinicios.append(1) or True)

    assert cliente.get("/api/agentes-disponibles").json() == {"agentes": []}
    r = cliente.post("/api/modulos/agente_agenda/activar")
    assert r.status_code == 200 and r.json() == {"ok": True, "opencode_reiniciado": True}
    assert cliente.get("/api/agentes-disponibles").json() == {"agentes": ["agenda"]}

    r = cliente.post("/api/modulos/agente_agenda/desactivar")
    assert r.json()["ok"] is True
    assert cliente.get("/api/agentes-disponibles").json() == {"agentes": []}
    assert len(reinicios) == 2


def test_activar_un_modulo_inexistente_responde_404(cliente, tmp_path, monkeypatch):
    import api.deps as deps
    monkeypatch.setattr(deps, "AGENTES_DIR", tmp_path)
    assert cliente.post("/api/modulos/agente_que_no_existe/activar").status_code == 404
