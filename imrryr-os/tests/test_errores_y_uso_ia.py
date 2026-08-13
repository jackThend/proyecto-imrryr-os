"""Helpers compartidos de la Tanda X: errores humanizados y contador de uso."""
import httpx

import errores_ia
import uso_ia


def test_conexion_rechazada_menciona_startup():
    msg = errores_ia.humanizar_error_ia(httpx.ConnectError("refused"))
    assert "OpenCode" in msg
    assert "startup" in msg


def test_timeout_menciona_cuota_como_causa_probable():
    msg = errores_ia.humanizar_error_ia(httpx.ReadTimeout("timed out"))
    assert "cuota" in msg.lower()


def test_429_menciona_cuota():
    req = httpx.Request("POST", "http://x")
    e = httpx.HTTPStatusError("429", request=req, response=httpx.Response(429, request=req))
    assert "cuota" in errores_ia.humanizar_error_ia(e).lower()


def test_error_generico_no_expone_stacktrace_pero_si_el_detalle():
    msg = errores_ia.humanizar_error_ia(ValueError("detalle util"))
    assert "detalle util" in msg
    assert "Traceback" not in msg


def test_excepcion_sin_texto_no_deja_el_mensaje_a_medias():
    # Visto en vivo: al caerse OpenCode a mitad de una consulta, la excepción
    # llegaba con str() vacío y el usuario leía "Algo falló hablando con los
    # agentes:" sin ninguna explicación.
    msg = errores_ia.humanizar_error_ia(RuntimeError(""))
    assert msg.rstrip().endswith("RuntimeError")


def test_registrar_y_contar_uso(db_temporal, monkeypatch):
    monkeypatch.setattr(uso_ia, "DB_PATH", db_temporal)
    assert uso_ia.uso_de_hoy()["hoy"] == 0
    uso_ia.registrar_uso("dashboard", "build")
    uso_ia.registrar_uso("whatsapp", "build")
    assert uso_ia.uso_de_hoy() == {"hoy": 2, "limite": uso_ia.LIMITE_GRATUITO}


def test_registrar_uso_nunca_lanza_sin_db(tmp_path, monkeypatch):
    # Si la DB no existe, perder el registro es aceptable; romper el chat no.
    monkeypatch.setattr(uso_ia, "DB_PATH", tmp_path / "no_existe" / "x.db")
    uso_ia.registrar_uso("dashboard")  # no debe lanzar
    assert uso_ia.uso_de_hoy()["hoy"] == 0
