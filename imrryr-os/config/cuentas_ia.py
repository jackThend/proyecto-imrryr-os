#!/usr/bin/env python3
"""
cuentas_ia.py — Cuentas de IA (Motor de IA que usan los agentes)
=====================================================================
Permite guardar más de una cuenta de IA (Gemini, OpenAI, Claude, DeepSeek,
OpenCode GO, Ollama local, u "otro" avanzado) y elegir cuál está activa.

NO existe un modelo por defecto (pilar: Neutralidad de Modelos). Todos los
agentes referencian un único alias estable, `imrryr-activo`, definido en
config/litellm_config.yaml — al activar una cuenta distinta se reescribe SOLO
ese bloque (el resto del archivo queda intacto) y se reinicia el proceso de
LiteLLM para que recargue la configuración (no relee el YAML en caliente en
este modo sin master_key, ver el propio litellm_config.yaml). La cuenta
elegida queda guardada en cuentas_ia.json, así que persiste entre sesiones:
al volver a entrar sigue activa la última que se usó.

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

# proveedor -> (nombre visible, modelo real de LiteLLM por defecto, si requiere API key,
# y opcionalmente api_base fijo del proveedor cuando siempre es el mismo endpoint).
PROVEEDORES = {
    "gemini": {"nombre": "Google Gemini", "modelo_base": "gemini/gemini-2.5-flash", "requiere_key": True},
    "openai": {"nombre": "OpenAI (GPT)", "modelo_base": "openai/gpt-4o-mini", "requiere_key": True},
    "anthropic": {"nombre": "Anthropic (Claude)", "modelo_base": "anthropic/claude-3-5-sonnet-20241022", "requiere_key": True},
    "deepseek": {"nombre": "DeepSeek (IA china)", "modelo_base": "deepseek/deepseek-chat", "requiere_key": True},
    # OpenCode GO: suscripción de OpenCode, compatible con OpenAI. El api_base
    # es siempre el mismo, así que se fija acá y el usuario solo elige el
    # modelo; _bloque_activo le antepone "openai/" para que LiteLLM use su
    # handler OpenAI-compatible contra ese api_base. Los modelos NO están
    # publicados en la web: se consultan en vivo a su endpoint /models con la
    # API key del usuario (ver listar_modelos_remotos()).
    "opencode_go": {"nombre": "OpenCode GO", "modelo_base": "", "requiere_key": True, "api_base": "https://opencode.ai/zen/go/v1"},
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


def obtener_cuenta_activa() -> dict[str, Any] | None:
    """Devuelve la cuenta marcada como activa, con la api_key enmascarada."""
    for c in _leer_todas():
        if c.get("activa"):
            copia = dict(c)
            if copia.get("api_key"):
                copia["api_key"] = "*" * 6
            return copia
    return None


def listar_modelos_remotos(proveedor: str, api_key: str = "", cuenta_id: str = "") -> dict[str, Any]:
    """Consulta en vivo qué modelos ofrece el proveedor (endpoint /models).

    Existe porque proveedores como OpenCode GO no publican su catálogo en la
    web: lo entrega la propia API según la suscripción de cada usuario. Así el
    usuario elige de una lista real en vez de teclear un id a ciegas.

    La api_key puede venir del formulario (cuenta nueva, todavía sin guardar) o
    tomarse de una cuenta ya guardada por su id — así el dashboard nunca
    necesita reenviar un secreto que ya está en disco.
    """
    prov = PROVEEDORES.get(proveedor)
    if not prov:
        return {"ok": False, "error": f"proveedor desconocido: {proveedor}"}
    api_base = prov.get("api_base", "")
    if not api_base:
        return {"ok": False, "error": "este proveedor no expone un catálogo de modelos"}

    if not api_key and cuenta_id:
        for c in _leer_todas():
            if c.get("id") == cuenta_id:
                api_key = c.get("api_key", "")
                break
    if not api_key:
        return {"ok": False, "error": "falta la API key para consultar los modelos"}

    import httpx

    try:
        r = httpx.get(
            f"{api_base}/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=20,
        )
    except httpx.HTTPError as e:
        return {"ok": False, "error": f"no se pudo conectar con el proveedor: {e}"}

    if r.status_code in (401, 403):
        return {"ok": False, "error": "la API key fue rechazada por el proveedor (401/403)"}
    if r.status_code != 200:
        return {"ok": False, "error": f"el proveedor respondió HTTP {r.status_code}"}

    try:
        data = r.json()
    except ValueError:
        return {"ok": False, "error": "el proveedor no devolvió JSON válido"}

    # Formato OpenAI: {"data": [{"id": "...", ...}, ...]}
    modelos = []
    for m in data.get("data", data if isinstance(data, list) else []):
        if isinstance(m, dict) and m.get("id"):
            modelos.append({"id": m["id"], "nombre": m.get("name") or m["id"]})
        elif isinstance(m, str):
            modelos.append({"id": m, "nombre": m})
    return {"ok": True, "modelos": sorted(modelos, key=lambda x: x["id"])}


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
    # OpenCode GO es OpenAI-compatible: el usuario elige solo el id del modelo
    # (ej. "grok-code") y acá le anteponemos "openai/" para que LiteLLM use su
    # handler OpenAI-compatible contra el api_base del gateway.
    if cuenta.get("proveedor") == "opencode_go" and modelo and "/" not in modelo:
        modelo = f"openai/{modelo}"
    # api_base: el de la cuenta manda; si no hay, se usa el fijo del proveedor.
    api_base = cuenta.get("api_base") or prov.get("api_base", "")
    lineas = [
        MARCADOR_INICIO,
        "  - model_name: imrryr-activo\n",
        "    litellm_params:\n",
        f"      model: {modelo}\n",
    ]
    if api_base:
        lineas.append(f"      api_base: {api_base}\n")
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
