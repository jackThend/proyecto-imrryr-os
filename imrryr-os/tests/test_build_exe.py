"""El generador del instalador no debe descartar en silencio los arreglos del .iss.

Caso real: el commit 8f181b1 edito imrryr_setup.iss a mano (silenciar el Restart
Manager y detener los servicios antes de instalar), pero build_exe.py regenera
ese archivo desde una plantilla en cada build normal, asi que el siguiente
instalador salio SIN esos arreglos y sin ningun aviso.
"""
from pathlib import Path

from scripts import build_exe


def _generar(tmp_path, monkeypatch):
    monkeypatch.setattr(build_exe, "ROOT", tmp_path)
    monkeypatch.setattr(build_exe, "DIST_DIR", tmp_path / "dist")
    return build_exe.generar_inno_setup_script("pyme").read_text(encoding="utf-8")


def test_el_instalador_no_reinicia_ni_cierra_aplicaciones_por_su_cuenta(tmp_path, monkeypatch):
    iss = _generar(tmp_path, monkeypatch)
    assert "CloseApplications=no" in iss
    assert "RestartApplications=no" in iss


def test_el_instalador_detiene_los_servicios_antes_de_copiar_archivos(tmp_path, monkeypatch):
    iss = _generar(tmp_path, monkeypatch)
    assert "function PrepareToInstall" in iss
    assert "Detener Imrryr OS.exe" in iss.split("[Code]")[1]


def test_el_script_generado_coincide_con_el_versionado(tmp_path, monkeypatch):
    """Si alguien vuelve a editar el .iss a mano, este test obliga a llevar el
    cambio al generador (o el proximo build lo pisaria)."""
    generado = _generar(tmp_path, monkeypatch)
    versionado = (Path(__file__).resolve().parent.parent / "imrryr_setup.iss").read_text(encoding="utf-8")

    def normalizar(texto):
        # las rutas absolutas dependen de la maquina; el resto debe ser identico
        return [l.strip() for l in texto.replace("\r", "").splitlines()
                if l.strip() and not l.startswith(("OutputDir=", "SetupIconFile=", "Source:"))]

    assert normalizar(generado) == normalizar(versionado)

