"""Tests de los módulos del manifiesto AI-OS (.ai-os/) y de la skill
transcribir_audio compartida por gateway y voice-bridge.

Herméticos por diseño (ver conftest.py): nada de red, servicios vivos ni
modelos de IA. Se cubre la lógica determinista — parsing de versiones,
enrutamiento de comandos, registro de bitácoras y el runner de lint.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
AI_OS = ROOT / ".ai-os"


def _cargar(nombre: str, ruta: Path):
    """Carga un módulo del repo por ruta (no son paquetes importables)."""
    spec = importlib.util.spec_from_file_location(nombre, ruta)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[nombre] = mod
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# sdd_protocol — enforcement SDD + bitácora
# ---------------------------------------------------------------------------
@pytest.fixture
def sdd(tmp_path, monkeypatch):
    mod = _cargar("sdd_protocol_test", AI_OS / "skills" / "sdd_protocol.py")
    monkeypatch.setattr(mod, "AI_OS", tmp_path)
    monkeypatch.setattr(mod, "SPEC", tmp_path / "PROJECT_SPEC.md")
    monkeypatch.setattr(mod, "PLAN", tmp_path / "PLAN.md")
    monkeypatch.setattr(mod, "LOGBOOK", tmp_path / "LOGBOOK.md")
    return mod


def test_verificar_spec_ok_cuando_existen(sdd):
    sdd.SPEC.write_text("# spec", encoding="utf-8")
    sdd.PLAN.write_text("# plan", encoding="utf-8")
    assert sdd.verificar_spec()["ok"] is True


def test_verificar_spec_falla_si_falta(sdd):
    resultado = sdd.verificar_spec()
    assert resultado["ok"] is False
    assert set(resultado["faltantes"]) == {"PROJECT_SPEC.md", "PLAN.md"}


def test_listar_tareas_y_siguiente(sdd):
    sdd.PLAN.write_text(
        "# PLAN\n## Tareas\n- [x] hecha uno\n- [ ] pendiente dos\n- [ ] pendiente tres\n",
        encoding="utf-8",
    )
    tareas = sdd.listar_tareas()
    assert [t["tarea"] for t in tareas] == ["hecha uno", "pendiente dos", "pendiente tres"]
    assert tareas[0]["hecha"] is True
    assert sdd.siguiente_tarea()["tarea"] == "pendiente dos"


def test_registrar_iteracion_numera_incremental(sdd):
    sdd.LOGBOOK.write_text("## [2026-01-01 00:00] Iteración #7\n", encoding="utf-8")
    n = sdd.registrar_iteracion("objetivo", ["a.py -> f()"], "LSP: 0", "ADR", "siguiente")
    assert n == 8
    contenido = sdd.LOGBOOK.read_text(encoding="utf-8")
    assert "Iteración #8" in contenido and "objetivo" in contenido and "a.py -> f()" in contenido


# ---------------------------------------------------------------------------
# ast_navigation — protocolo FETCH
# ---------------------------------------------------------------------------
def test_fetch_registra_y_consulta_por_tarea(tmp_path, monkeypatch):
    mod = _cargar("ast_nav_test", AI_OS / "skills" / "ast_navigation.py")
    registro = tmp_path / "fetch_log.json"
    monkeypatch.setattr(mod, "REGISTRO", registro)

    mod.registrar_consulta("tarea-A", "trace_path", ["mod.f", "mod.g"])
    mod.registrar_consulta("tarea-B", "search_graph", ["mod.h"])

    assert len(mod.entidades_de_tarea("tarea-A")) == 1
    assert mod.entidades_de_tarea("tarea-A")[0]["entidades"] == ["mod.f", "mod.g"]
    assert mod.entidades_de_tarea("tarea-B")[0]["patron"] == "search_graph"
    assert mod.entidades_de_tarea("inexistente") == []


def test_patrones_cubren_mcp_codebase_memory():
    mod = _cargar("ast_nav_patrones", AI_OS / "skills" / "ast_navigation.py")
    esperados = {"search_graph", "trace_path", "get_code_snippet", "query_graph", "get_architecture"}
    assert esperados.issubset(set(mod.PATRONES))


# ---------------------------------------------------------------------------
# deterministic_validate — ruff determinista
# ---------------------------------------------------------------------------
def test_lint_detecta_f401(tmp_path):
    mod = _cargar("dval_bad", AI_OS / "skills" / "deterministic_validate.py")
    malo = tmp_path / "malo.py"
    malo.write_text("import json\n", encoding="utf-8")
    resultado = mod.lint([str(malo)])
    assert resultado["ok"] is False
    assert any("F401" in e for e in resultado["errores"])


def test_lint_pasa_archivo_limpio(tmp_path):
    mod = _cargar("dval_ok", AI_OS / "skills" / "deterministic_validate.py")
    limpio = tmp_path / "limpio.py"
    limpio.write_text("x = 1\n", encoding="utf-8")
    assert mod.lint([str(limpio)])["ok"] is True


def test_lint_sin_errores_en_ai_os():
    """Autolint: los propios módulos del manifiesto están limpios."""
    mod = _cargar("dval_self", AI_OS / "skills" / "deterministic_validate.py")
    archivos = [str(p) for p in sorted(AI_OS.rglob("*.py"))]
    resultado = mod.lint(archivos)
    assert resultado["ok"] is True, resultado["errores"]


# ---------------------------------------------------------------------------
# voice_bridge — enrutamiento determinista
# ---------------------------------------------------------------------------
@pytest.fixture
def vb():
    return _cargar("vb_test", AI_OS / "modules" / "voice-bridge" / "voice_bridge.py")


def test_comando_enrutado_a_skill_existente(vb):
    r = vb.procesar_comando_voz("Registrar gasto 50 en comida")
    assert r["status"] == "enrutado"
    assert (ROOT / r["accion"]["modulo"]).exists()


def test_comando_insensible_a_mayusculas(vb):
    assert vb.procesar_comando_voz("ESTADO DEL SISTEMA")["status"] == "enrutado"


def test_comando_sin_match(vb):
    r = vb.procesar_comando_voz("ponme musica de los 80")
    assert r == {"comando": "ponme musica de los 80", "accion": None, "status": "sin_match"}


def test_todas_las_acciones_apuntan_a_archivos_reales(vb):
    for accion in vb.ACCIONES.values():
        if accion["tipo"] in ("skill", "script"):
            assert (ROOT / accion["modulo"]).exists(), accion["modulo"]


# ---------------------------------------------------------------------------
# meta_harness — versiones, parsing y RFC
# ---------------------------------------------------------------------------
@pytest.fixture
def mh(tmp_path, monkeypatch):
    mod = _cargar("mh_test", AI_OS / "modules" / "meta-harness" / "meta_harness.py")
    monkeypatch.setattr(mod, "REQUIREMENTS", tmp_path / "requirements.txt")
    monkeypatch.setattr(mod, "AGENTES_DIR", tmp_path / "agentes")
    return mod


@pytest.mark.parametrize(
    "actual,reciente,esperado",
    [
        ("1.2.0", "2.1.1", True),   # major up
        ("2.0.0", "2.1.1", False),  # minor up
        ("9.1.1", "9.1.1", False),  # igual
        ("abc", "1.0", False),      # basura
        ("1.0", "", False),         # vacía
    ],
)
def test_version_mayor(mh, actual, reciente, esperado):
    assert mh._version_mayor(actual, reciente) is esperado


def test_parsear_requirements(mh, tmp_path):
    mh.REQUIREMENTS.write_text(
        "# comentario\nlitellm[proxy]>=1.52.0\nfastapi>=0.115.0\n\npytest>=8.0.0\n",
        encoding="utf-8",
    )
    deps = dict(mh._parsear_requirements())
    assert deps["litellm"] == "1.52.0"
    assert deps["fastapi"] == "0.115.0"
    assert deps["pytest"] == "8.0.0"


def test_generar_rfc_lista_breaking(mh):
    scout = {"stack": {"breaking_changes": [{"paquete": "mcp", "pin_actual": ">=1.2.0", "ultima_pypi": "2.1.1", "nota": "n"}]}}
    rfc = mh.generar_rfc(scout)
    assert "mcp" in rfc and "2.1.1" in rfc and "Aprobación Requerida" in rfc


def test_sandbox_devuelve_error_si_no_existe_script(mh, tmp_path):
    r = mh.sandbox(str(tmp_path / "fantasma.py"))
    assert r["ok"] is False and "no encontrado" in r["error"]


# ---------------------------------------------------------------------------
# skills/transcribir_audio — rutas herméticas (sin red, sin modelo)
# ---------------------------------------------------------------------------
def test_transcribir_archivo_inexistente_devuelve_vacio():
    mod = _cargar("ta_test", ROOT / "skills" / "transcribir_audio.py")
    assert mod.transcribir(str(ROOT / "vault" / "fantasma.ogg"), motor="local") == ""


def test_transcribir_groq_sin_clave_no_llama_red(monkeypatch):
    mod = _cargar("ta_nokey", ROOT / "skills" / "transcribir_audio.py")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    assert mod._groq_api_key() == ""
    assert mod.transcribir_groq("archivo-que-no-existe.ogg") == ""


def test_groq_api_key_lee_entorno(monkeypatch):
    mod = _cargar("ta_env", ROOT / "skills" / "transcribir_audio.py")
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test_123")
    assert mod._groq_api_key() == "gsk_test_123"


def test_transcribir_con_motor_reporta_local_en_fallback(monkeypatch):
    mod = _cargar("ta_motor", ROOT / "skills" / "transcribir_audio.py")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    r = mod.transcribir_con_motor("archivo-que-no-existe.ogg")
    assert r == {"texto": "", "motor": "faster-whisper-local"}