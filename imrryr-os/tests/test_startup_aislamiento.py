"""El arranque no debe chocar con lo que el cliente ya tiene en su equipo."""
import http.server
import socket
import threading

import pytest

from scripts import startup


# ---------------------------------------------------------------- entorno de OpenCode
def test_opencode_no_hereda_variables_opencode_del_usuario():
    """Con HOME propio los archivos del usuario quedan fuera, pero una OPENCODE_CONFIG
    definida en su entorno colaba sus MCP e instrucciones dentro de Imrryr."""
    ajeno = {
        "OPENCODE_CONFIG": "C:/usuario/mi_config.json",
        "OPENCODE_CONFIG_DIR": "C:/usuario/dir",
        "OPENCODE_CONFIG_CONTENT": "{}",
        "opencode_permission": "{}",  # Windows no distingue mayúsculas
        "XDG_DATA_HOME": "C:/usuario/datos",
        "PATH": "C:/Windows",
        "GEMINI_API_KEY": "se-conserva",
    }
    env = startup._entorno_opencode(ajeno, "clave-local")
    assert not [k for k in env if k.upper().startswith("OPENCODE_") and k != "OPENCODE_SERVER_PASSWORD"]
    assert env["OPENCODE_SERVER_PASSWORD"] == "clave-local"
    assert "XDG_DATA_HOME" not in env
    # lo demás (PATH, claves de proveedores) sigue llegando
    assert env["PATH"] == "C:/Windows" and env["GEMINI_API_KEY"] == "se-conserva"


def test_opencode_corre_con_home_propio():
    env = startup._entorno_opencode({}, "x")
    assert env["HOME"] == env["USERPROFILE"] == str(startup.OPENCODE_HOME)
    assert env["XDG_CONFIG_HOME"].startswith(str(startup.OPENCODE_HOME))


# ---------------------------------------------------------------- puertos
class _Servidor:
    """Servidor HTTP local mínimo que responde `codigo` a cualquier GET."""

    def __init__(self, codigo):
        class H(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(codigo)
                self.end_headers()

            def log_message(self, *a):
                pass

        self.srv = http.server.HTTPServer(("127.0.0.1", 0), H)
        self.puerto = self.srv.server_address[1]
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def cerrar(self):
        self.srv.shutdown()
        self.srv.server_close()


@pytest.fixture
def servidor():
    creados = []

    def crear(codigo):
        s = _Servidor(codigo)
        creados.append(s)
        return s

    yield crear
    for s in creados:
        s.cerrar()


def _puerto_libre():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def test_puerto_ocupado_por_otro_programa_se_detecta(servidor, tmp_path, monkeypatch):
    monkeypatch.setattr(startup, "RUN_DIR", tmp_path)
    otro = servidor(404)  # p. ej. una app de desarrollo cualquiera en el 3000
    url = f"http://localhost:{otro.puerto}/api/status"
    assert startup.puertos_ajenos([("dashboard", otro.puerto, url, {})]) == [("dashboard", otro.puerto)]


def test_puerto_con_nuestro_servicio_ya_corriendo_no_es_un_conflicto(servidor, tmp_path, monkeypatch):
    """Doble clic en el icono con la app ya abierta: debe reutilizar, no fallar."""
    monkeypatch.setattr(startup, "RUN_DIR", tmp_path)
    nuestro = servidor(200)
    url = f"http://localhost:{nuestro.puerto}/api/status"
    assert startup.puertos_ajenos([("dashboard", nuestro.puerto, url, {})]) == []


def test_segundo_clic_durante_el_arranque_no_se_toma_por_conflicto(servidor, tmp_path, monkeypatch):
    """Nuestro proceso ya escucha pero aun no responde sano: su PID registrado lo delata."""
    import os

    monkeypatch.setattr(startup, "RUN_DIR", tmp_path)
    arrancando = servidor(503)
    (tmp_path / "dashboard.pid").write_text(str(os.getpid()), encoding="utf-8")  # un PID vivo
    url = f"http://localhost:{arrancando.puerto}/api/status"
    assert startup.puertos_ajenos([("dashboard", arrancando.puerto, url, {})]) == []


def test_puerto_libre_no_es_un_conflicto(tmp_path, monkeypatch):
    monkeypatch.setattr(startup, "RUN_DIR", tmp_path)
    libre = _puerto_libre()
    assert startup.puertos_ajenos([("dashboard", libre, f"http://localhost:{libre}/api/status", {})]) == []


# ---------------------------------------------------------------- esperas de arranque
def test_el_limite_de_espera_cubre_una_primera_arrancada_lenta():
    """Medido: LiteLLM tardo 104 s en la primera apertura tras instalar. Con 120 s de
    limite un equipo algo mas lento fallaba la primera vez."""
    assert startup.HEALTH_TIMEOUT >= 240


def test_si_el_servicio_muere_no_se_espera_todo_el_plazo(monkeypatch):
    import time

    class Muerto:
        returncode = 1

        def poll(self):
            return 1

    monkeypatch.setattr(startup.httpx, "get", lambda *a, **k: (_ for _ in ()).throw(startup.httpx.ConnectError("x")))
    t0 = time.time()
    assert startup._wait("http://localhost:1/x", {}, "Prueba", proc=Muerto()) is False
    assert time.time() - t0 < 5
