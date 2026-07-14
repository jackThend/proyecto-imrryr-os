"""Parser determinista de correos bancarios (finanzas/parsers_bancarios.py).

Es la pieza que permite importar miles de correos históricos sin gastar cuota
de IA — si una regex se rompe en silencio, la importación empieza a mandarle
todo al LLM (lento y caro) o a perder gastos. Estos tests fijan el contrato.
"""
from finanzas.parsers_bancarios import _limpiar_monto, detectar_banco, intentar_extraer


def test_extrae_compra_tipica_chilena():
    resultado = intentar_extraer(
        "Notificación de compra",
        "Te informamos que se realizó una compra por $45.990 en el comercio JUMBO MAIPU con tu tarjeta.",
    )
    assert resultado is not None
    assert resultado["monto"] == 45990.0
    assert "JUMBO" in resultado["comercio"]
    assert resultado["categoria"] == "supermercado"


def test_categoria_inferida_por_comercio():
    resultado = intentar_extraer(
        "Cargo en tu cuenta",
        "Cargo por $12.500 en el comercio UBER TRIP SANTIAGO.",
    )
    assert resultado is not None
    assert resultado["categoria"] == "transporte"


def test_correo_sin_palabras_de_transaccion_se_descarta():
    # Un correo promocional con montos NO debe convertirse en gasto.
    assert intentar_extraer("Aprovecha", "Productos desde $9.990 en nuestro sitio") is None


def test_correo_sin_monto_se_descarta():
    assert intentar_extraer("Compra realizada", "Compraste en el comercio JUMBO") is None


def test_correo_sin_comercio_se_descarta():
    assert intentar_extraer("Aviso", "Se registró un cargo por $10.000.") is None


def test_limpiar_monto_formatos():
    assert _limpiar_monto("45.990") == 45990.0        # miles con punto (Chile)
    assert _limpiar_monto("1.234.567") == 1234567.0
    assert _limpiar_monto("45,990") == 45990.0        # miles con coma
    assert _limpiar_monto("no-numerico") is None


def test_detectar_banco():
    assert detectar_banco("notificaciones@bancoestado.cl") == "BancoEstado"
    assert detectar_banco("alerta@SANTANDER.CL") == "Santander"
    assert detectar_banco("alguien@gmail.com") == ""
