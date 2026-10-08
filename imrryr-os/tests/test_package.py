"""Lo que es dato o configuracion de una maquina concreta no debe viajar en el paquete."""
import pytest

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


# ---------------------------------------------------------------- agentes opcionales
OPCIONALES = {"agente_agenda.yaml", "agente_compras.yaml", "agente_navegacion.yaml",
              "agente_rrss_web.yaml", "agente_secretario.yaml"}


def test_los_opcionales_viajan_desactivados_y_los_del_perfil_siguen_activos(tmp_path, monkeypatch):
    """El panel de Módulos solo activa agentes que ya están en la carpeta: por eso viajan,
    pero apagados. Si salieran activos, el perfil dejaría de ser lo que el usuario eligio."""
    import yaml

    monkeypatch.setattr(package, "PKG_DIR", tmp_path)
    package.copy_agents(["agente_asistente.yaml"], ["agente_agenda.yaml"])
    agenda = yaml.safe_load((tmp_path / "agentes" / "agente_agenda.yaml").read_text(encoding="utf-8"))
    asistente = yaml.safe_load((tmp_path / "agentes" / "agente_asistente.yaml").read_text(encoding="utf-8"))
    assert agenda["activo"] is False and agenda["herramientas_permitidas"]  # apagado, pero entero
    assert asistente.get("activo", True) is True


@pytest.mark.parametrize("perfil", ["pyme", "tech"])
def test_ambos_perfiles_declaran_los_cinco_opcionales(perfil):
    assert set(package.load_profile(perfil)["agentes_opcionales"]) == OPCIONALES


@pytest.mark.parametrize("perfil", ["pyme", "tech"])
def test_activar_un_opcional_no_exige_instalar_nada_mas(perfil):
    """Las herramientas de los opcionales entran al paquete aunque el agente viaje apagado."""
    scripts, manifiestos = package.resolve_profile_skills(package.load_profile(perfil))
    for skill in ("agenda.py", "scraper_tiendas.py", "gestionar_seguimiento_compras.py", "navegar_web.py",
                  "leer_en_voz.py", "repo_web.py", "redes_sociales.py", "secretario.py", "navegador_cliente.py"):
        assert skill in scripts, skill
    for manifiesto in ("scraper_tiendas.mcp.json", "navegar_web.mcp.json", "redes_sociales.mcp.json", "leer_correo.mcp.json"):
        assert manifiesto in manifiestos, manifiesto


def test_el_perfil_pyme_sigue_sin_build():
    assert "agente_build.yaml" not in package.load_profile("pyme")["agentes"] + package.load_profile("pyme")["agentes_opcionales"]
