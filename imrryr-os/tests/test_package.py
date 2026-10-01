"""Lo que es dato o configuracion de una maquina concreta no debe viajar en el paquete."""
from scripts import package


def _ignorados(nombres):
    return package.IGNORE_PATTERNS("config", nombres)


def test_el_paquete_no_lleva_el_opencode_json_de_la_maquina_de_desarrollo():
    """Lleva rutas absolutas del PC que empaqueta y la cuenta de IA que tenia activa.
    En la maquina destino se siembra desde opencode.template.json (sync_agentes.py)."""
    ign = _ignorados(["opencode.json", "opencode.template.json"])
    assert "opencode.json" in ign
    assert "opencode.template.json" not in ign


def test_el_paquete_no_lleva_secretos_ni_cuentas():
    ign = _ignorados([".env", "cuentas_ia.json", "cuentas_social.json", "gmail_token.pickle", "region.json"])
    assert ign == {".env", "cuentas_ia.json", "cuentas_social.json", "gmail_token.pickle", "region.json"}


def test_codebase_memory_solo_se_habilita_si_hay_agente_build(tmp_path, monkeypatch):
    """Solo lo usa el agente build. Sin build (perfil pyme) habilitarlo hace que
    OpenCode descargue el servidor con `uvx` en el primer mensaje del usuario."""
    import shutil

    from scripts import sync_agentes

    monkeypatch.setattr(shutil, "which", lambda _n: "uvx")  # el equipo tiene uv instalado
    monkeypatch.setattr(sync_agentes, "AGENTES_DIR", tmp_path)

    assert sync_agentes.construir_mcp_config()["codebase-memory"]["enabled"] is False

    (tmp_path / "agente_build.yaml").write_text("activo: true\n", encoding="utf-8")
    assert sync_agentes.construir_mcp_config()["codebase-memory"]["enabled"] is True

    (tmp_path / "agente_build.yaml").write_text("activo: false\n", encoding="utf-8")
    assert sync_agentes.construir_mcp_config()["codebase-memory"]["enabled"] is False
