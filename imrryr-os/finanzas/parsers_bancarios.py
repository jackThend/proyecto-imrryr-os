#!/usr/bin/env python3
"""
parsers_bancarios.py — Extracción determinista de correos bancarios (sin IA)
=====================================================================================
La mayoría de los correos de notificación bancaria (compra, cargo, pago) siguen
un formato muy repetitivo. Extraerlos con reglas (regex) en vez de pedirle a un
LLM que lea cada uno, uno por uno, es lo que hace viable importar cientos o miles
de correos históricos sin agotar la cuota de la IA (ver finanzas/importador_historico.py).

`intentar_extraer()` es deliberadamente conservador: si no encuentra un monto Y
un comercio con confianza razonable, devuelve None — ese correo queda para el
lote que sí se le pide a la IA. Es un punto de partida genérico/heurístico, no
plantillas específicas por banco (no existen muestras reales todavía); en cuanto
haya correos reales de un banco concreto, se puede agregar un caso más preciso
aquí mismo sin tocar el resto del pipeline.

Uso:
    from finanzas.parsers_bancarios import intentar_extraer, detectar_banco
"""
from __future__ import annotations

import re

_PALABRAS_CLAVE_TRANSACCION = (
    "compra", "cargo", "pago", "transacción", "transaccion",
    "compraste", "abono", "retiro", "cobro",
)

_PATRON_MONTO = re.compile(r"\$\s?(\d{1,3}(?:[.,]\d{3})+(?:[.,]\d{2})?|\d+(?:[.,]\d{2})?)")
_PATRON_COMERCIO = re.compile(
    r"(?:en el comercio|en comercio|comercio|establecimiento|en)\s*:?\s*"
    r"([A-ZÁÉÍÓÚÑ0-9][A-ZÁÉÍÓÚÑ0-9 .\-\*&]{2,40})",
)

# Categorías inferibles por nombre de comercio conocido, sin necesitar IA.
_CATEGORIAS_CONOCIDAS: dict[str, str] = {
    "uber": "transporte", "cabify": "transporte", "didi": "transporte",
    "netflix": "suscripciones", "spotify": "suscripciones", "hbo": "suscripciones", "disney": "suscripciones",
    "starbucks": "restaurante", "mcdonald": "restaurante", "burger": "restaurante", "pizza": "restaurante",
    "copec": "combustible", "shell": "combustible", "petrobras": "combustible",
    "jumbo": "supermercado", "lider": "supermercado", "santa isabel": "supermercado", "unimarc": "supermercado",
    "farmacia": "salud", "cruz verde": "salud", "salcobrand": "salud", "ahumada": "salud",
}

# Dominio del remitente -> nombre de banco, para el informe agrupado.
_BANCOS_CONOCIDOS: dict[str, str] = {
    "bancoestado.cl": "BancoEstado", "santander.cl": "Santander", "bci.cl": "BCI",
    "scotiabank.cl": "Scotiabank", "itau.cl": "Itaú", "bancochile.cl": "Banco de Chile",
    "bancofalabella.cl": "Banco Falabella", "security.cl": "Banco Security",
}


def _limpiar_monto(texto: str) -> float | None:
    texto = texto.strip()
    if re.match(r"^\d{1,3}(\.\d{3})+$", texto):
        return float(texto.replace(".", ""))
    if re.match(r"^\d{1,3}(,\d{3})+$", texto):
        return float(texto.replace(",", ""))
    try:
        return float(texto.replace(".", "").replace(",", "."))
    except ValueError:
        return None


def _categoria_por_comercio(comercio: str) -> str:
    comercio_lower = comercio.lower()
    for palabra, categoria in _CATEGORIAS_CONOCIDAS.items():
        if palabra in comercio_lower:
            return categoria
    return "general"


def detectar_banco(remitente: str) -> str:
    remitente_lower = remitente.lower()
    for dominio, nombre in _BANCOS_CONOCIDOS.items():
        if dominio in remitente_lower:
            return nombre
    return ""


def intentar_extraer(asunto: str, cuerpo: str) -> dict | None:
    """Devuelve {monto, comercio, categoria} si logra extraer con confianza
    razonable, o None si el correo debe pasar al lote que revisa la IA."""
    texto = f"{asunto}\n{cuerpo}"
    texto_lower = texto.lower()
    if not any(palabra in texto_lower for palabra in _PALABRAS_CLAVE_TRANSACCION):
        return None

    m_monto = _PATRON_MONTO.search(texto)
    if not m_monto:
        return None
    monto = _limpiar_monto(m_monto.group(1))
    if not monto or monto <= 0:
        return None

    m_comercio = _PATRON_COMERCIO.search(texto)
    if not m_comercio:
        return None
    comercio = re.sub(r"\s+", " ", m_comercio.group(1)).strip(" .-*")
    if len(comercio) < 3:
        return None

    return {
        "monto": monto,
        "comercio": comercio[:60],
        "categoria": _categoria_por_comercio(comercio),
    }
