#!/usr/bin/env python3
"""
cuentas_ia.py — Cuentas de IA (Motor de IA que usan los agentes)
=====================================================================
Permite guardar más de una cuenta de IA (Gemini, OpenAI, Claude, DeepSeek,
Ollama local, u "otro" avanzado) y elegir cuál está activa. Todos los
agentes referencian un alias estable (`imrryr-activo`) en
config/litellm_config.yaml — al activar una cuenta distinta, se reescribe
SOLO ese bloque (el resto del archivo, incluyendo comentarios y los alias
gemini-pro/gemini-flash originales, queda intacto) y se reinicia el proceso
de LiteLLM para que recargue la configuración (no relee el YAML en caliente
en este modo sin master_key, ver el propio litellm_config.yaml).

Uso:
    from config.cuentas_ia import listar_cuentas, guardar_cuenta, activar_cuenta
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
CUENTAS_PATH = Path(__file__).resolve().parent / "cuentas_ia.json"
LITELLM_CONFIG_PATH = Path(__file__).resolve().parent / "litellm_config.yaml"
ENV_PATH = Path(__file__).resolve().parent / ".env"

MARCADOR_INICIO = "  # --- IMRRYR-ACTIVO (autogenerado por Cuentas de IA, no editar a mano) ---\n"
MARCADOR_FIN = "  # --- FIN IMRRYR-ACTIVO ---\n"

# proveedor -> (nombre visible, modelo real de LiteLLM por defecto, si requiere API key)
PROVEEDORES = {
    "gemini": {"nombre": "Google Gemini", "modelo_base": "gemini/gemini-2.5-flash", "requiere_key": True},
    "openai": {"nombre": "OpenAI (GPT)", "modelo_base": "openai/gpt-4o-mini", "requiere_key": True},
    "anthropic": {"nombre": "Anthropic (Claude)", "modelo_base": "anthropic/claude-3-5-sonnet-20241022", "requiere_key": True},
    "deepseek": {"nombre": "DeepSeek (IA china)", "modelo_base": "deepseek/deepseek-chat", "requiere_key": True},
    "ollama": {"nombre": "Ollama (local, sin costo)", "modelo_base": "ollama/qwen2.5", "requiere_key": False},
    "otro": {"nombre": "Otro (avanzado)", "modelo_base": "", "requiere_key": True},
}


def log(msg: str) -> None:
    print(f"[cuentas_ia] {msg}", flush=True)


def _leer_todas() -> list[dict[str, Any]]:
    if not CUENTAS_PATH.exists():
        return []
    try:
        data = json.loads(CUENTAS_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    return data.get("cuentas", []) if isinstance(data, dict) else []


def _guardar_todas(cuentas: list[dict[str, Any]]) -> None:
    CUENTAS_PATH.parent.mkdir(parents=True, exist_ok=True)
    CUENTAS_PATH.write_text(json.dumps({"cuentas": cuentas}, indent=2, ensure_ascii=False), encoding="utf-8")


def listar_cuentas() -> list[dict[str, Any]]:
    return _leer_todas()


def cuentas_seguras() -> list[dict[str, Any]]:
    """Copia de listar_cuentas() con 'api_key' enmascarada, para exponer al dashboard."""
    seguras = []
    for cuenta in _leer_todas():
        copia = dict(cuenta)
        if copia.get("api_key"):
            copia["api_key"] = "*" * 6
        seguras.append(copia)
    return seguras


def guardar_cuenta(datos: dict[str, Any]) -> dict[str, Any]:
    """Crea o actualiza (por 'id') una cuenta de IA. No la activa automáticamente."""
    cuenta_id = datos.get("id")
    if not cuenta_id:
        return {"ok": False, "error": "falta 'id'"}
    if datos.get("proveedor") not in PROVEEDORES:
        return {"ok": False, "error": f"proveedor desconocido: {datos.get('proveedor')}"}

    cuentas = _leer_todas()
    for i, cuenta in enumerate(cuentas):
        if cuenta.get("id") == cuenta_id:
            cuentas[i] = {**cuenta, **datos}
            _guardar_todas(cuentas)
            return {"ok": True, "cuenta": cuentas[i]}

    nueva = {"activa": False, **datos}
    cuentas.append(nueva)
    _guardar_todas(cuentas)
    return {"ok": True, "cuenta": nueva}


def quitar_cuenta(cuenta_id: str) -> dict[str, Any]:
    cuentas = _leer_todas()
    restantes = [c for c in cuentas if c.get("id") != cuenta_id]
    if len(restantes) == len(cuentas):
        return {"ok": False, "error": f"no existe la cuenta '{cuenta_id}'"}
    _guardar_todas(restantes)
    return {"ok": True}


def _actualizar_env(clave: str, valor: str) -> None:
    """Actualiza (o agrega) una línea CLAVE=valor en config/.env sin tocar el resto del archivo."""
    lineas = ENV_PATH.read_text(encoding="utf-8").splitlines() if ENV_PATH.exists() else []
    prefijo = f"{clave}="
    encontrada = False
    for i, linea in enumerate(lineas):
        if linea.startswith(prefijo):
            lineas[i] = f"{clave}={valor}"
            encontrada = True
            break
    if not encontrada:
        lineas.append(f"{clave}={valor}")
    ENV_PATH.write_text("\n".join(lineas) + "\n", encoding="utf-8")


def _bloque_activo(cuenta: dict[str, Any]) -> str:
    prov = PROVEEDORES.get(cuenta.get("proveedor", ""), {})
    modelo = cuenta.get("modelo") or prov.get("modelo_base", "")
    lineas = [
        MARCADOR_INICIO,
        "  - model_name: imrryr-activo\n",
        "    litellm_params:\n",
        f"      model: {modelo}\n",
    ]
    if cuenta.get("api_base"):
        lineas.append(f"      api_base: {cuenta['api_base']}\n")
    if prov.get("requiere_key", True):
        lineas.append("      api_key: os.environ/IMRRYR_ACTIVE_API_KEY\n")
    lineas.append(MARCADOR_FIN)
    return "".join(lineas)


def _regenerar_litellm_config(cuenta: dict[str, Any]) -> None:
    texto = LITELLM_CONFIG_PATH.read_text(encoding="utf-8")
    bloque = _bloque_activo(cuenta)
    if MARCADOR_INICIO in texto and MARCADOR_FIN in texto:
        inicio = texto.index(MARCADOR_INICIO)
        fin = texto.index(MARCADOR_FIN) + len(MARCADOR_FIN)
        texto = texto[:inicio] + bloque + texto[fin:]
    else:
        texto = texto.rstrip("\n") + "\n\n" + bloque
    LITELLM_CONFIG_PATH.write_text(texto, encoding="utf-8")


def _reiniciar_litellm() -> bool:
    try:
        resultado = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "restart_litellm.py")],
            cwd=str(ROOT), capture_output=True, text=True, timeout=60,
        )
        if resultado.returncode != 0:
            log(f"restart_litellm.py devolvió error: {resultado.stdout}\n{resultado.stderr}")
        return resultado.returncode == 0
    except Exception as e:
        log(f"No se pudo reiniciar LiteLLM: {e}")
        return False


def activar_cuenta(cuenta_id: str) -> dict[str, Any]:
    """Marca una cuenta como activa, regenera litellm_config.yaml y reinicia LiteLLM."""
    cuentas = _leer_todas()
    activada = None
    for c in cuentas:
        c["activa"] = c.get("id") == cuenta_id
        if c["activa"]:
            activada = c
    if not activada:
        return {"ok": False, "error": f"no existe la cuenta '{cuenta_id}'"}
    _guardar_todas(cuentas)

    _actualizar_env("IMRRYR_ACTIVE_API_KEY", activada.get("api_key", ""))
    _regenerar_litellm_config(activada)
    reiniciado = _reiniciar_litellm()
    log(f"Cuenta activa: {activada.get('nombre')} ({activada.get('proveedor')}) — LiteLLM reiniciado: {reiniciado}")
    return {"ok": True, "cuenta": activada, "litellm_reiniciado": reiniciado}
