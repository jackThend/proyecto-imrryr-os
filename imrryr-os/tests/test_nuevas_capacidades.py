"""Tests herméticos y de integración local para las capacidades aprobadas AI-OS 2026:
- Memoria de usuario manipulable y multi-empresa (skills/perfil_negocio.py y skills/memoria_perfil.py)
- Generador de cotizaciones en PDF (skills/generar_cotizacion_pdf.py)
- Sistema Human-in-the-Loop HITL (skills/confirmacion_hitl.py)
- RAG Híbrido RRF (skills/consultar_memoria_vectorial.py)
- Telemetría de Tokens, Presupuesto y Observabilidad (skills/uso_ia.py)
- Sandbox de ejecución de scripts (skills/ejecutar_script.py)
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "skills"))


def test_memoria_perfil(tmp_path, monkeypatch):
    from skills import memoria_perfil

    db_test = tmp_path / "test_imrryr.db"
    monkeypatch.setattr(memoria_perfil, "DB_PATH", db_test)

    # Guardar hecho con clave, valor, categoría
    res = memoria_perfil.guardar_hecho_memoria(
        clave="tema_color",
        valor="oscuro minimalista",
        categoria="preferencia",
    )
    assert res["ok"] is True

    # Consultar
    res_query = memoria_perfil.consultar_memoria_usuario(categoria="preferencia")
    assert len(res_query) == 1
    assert res_query[0]["clave"] == "tema_color"
    assert res_query[0]["valor"] == "oscuro minimalista"


def test_perfil_usuario_y_empresas(tmp_path, monkeypatch):
    from skills import perfil_negocio

    perfil_file = tmp_path / "perfil_test.json"
    monkeypatch.setattr(perfil_negocio, "PERFIL_PATH", perfil_file)

    datos = {
        "nombre_usuario": "Carlos",
        "empresas": [
            {"nombre": "Estudio Museográfico", "descripcion": "Diseño y montaje de exhibiciones"},
            {"nombre": "Consultora Imrryr", "descripcion": "Software y automatización"},
        ],
        "giro": ["tecnologia", "cultura"],
        "caracteristicas_extra": {"facturacion": "exenta de IVA"},
    }
    actualizado = perfil_negocio.actualizar_perfil_negocio(datos)
    assert actualizado["nombre_usuario"] == "Carlos"
    assert len(actualizado["empresas"]) == 2
    assert actualizado["empresas"][0]["nombre"] == "Estudio Museográfico"

    # Verificar lectura
    leido = perfil_negocio.leer_perfil_negocio()
    assert leido["nombre_usuario"] == "Carlos"
    assert len(leido["empresas"]) == 2


def test_cotizacion_pdf(tmp_path, monkeypatch):
    from skills import generar_cotizacion_pdf

    monkeypatch.setattr(generar_cotizacion_pdf, "VAULT_DIR", tmp_path)

    items = [
        {"descripcion": "Diseño de Arquitectura de IA", "cantidad": 1, "precio_unitario": 800000},
        {"descripcion": "Desarrollo de Subagentes MCP", "cantidad": 2, "precio_unitario": 500000},
    ]
    res = generar_cotizacion_pdf.generar_cotizacion_pdf(
        cliente_nombre="Empresa Demo SpA",
        proyecto_titulo="Implementación AI-OS",
        items=items,
        cliente_email="contacto@demo.cl",
        validez_dias=15,
        notas="Incluye soporte 30 días",
    )

    assert res["ok"] is True
    assert res["total"] == 1800000.0
    assert Path(res["ruta_pdf"]).exists()
    assert Path(res["ruta_pdf"]).stat().st_size > 1000


def test_confirmacion_hitl(tmp_path, monkeypatch):
    from skills import confirmacion_hitl

    db_test = tmp_path / "test_hitl.db"
    conn = sqlite3.connect(str(db_test))
    conn.execute(
        """
        CREATE TABLE solicitudes_hitl (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agente TEXT NOT NULL,
            accion TEXT NOT NULL,
            parametros TEXT NOT NULL DEFAULT '{}',
            resumen_humano TEXT NOT NULL,
            estado TEXT DEFAULT 'pendiente',
            creado_at TEXT DEFAULT (datetime('now')),
            resuelto_at TEXT
        )
        """
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(confirmacion_hitl, "DB_PATH", db_test)

    # 1. Solicitar autorización
    res = confirmacion_hitl.solicitar_autorizacion_humana(
        agente="build",
        accion="ejecutar_script",
        resumen_humano="Ejecutar script de limpieza",
        parametros={"script": "clean.py"},
    )
    assert res["ok"] is True
    assert res["requiere_aprobacion"] is True
    sid = res["solicitud_id"]

    # 2. Listar pendientes
    pendientes = confirmacion_hitl.listar_solicitudes_pendientes()
    assert len(pendientes) == 1
    assert pendientes[0]["id"] == sid
    assert pendientes[0]["agente"] == "build"

    # 3. Resolver
    res_resolv = confirmacion_hitl.resolver_solicitud(sid, "aprobado")
    assert res_resolv["ok"] is True
    assert res_resolv["nuevo_estado"] == "aprobado"

    # 4. Verificar ya no está en pendientes
    assert len(confirmacion_hitl.listar_solicitudes_pendientes()) == 0


def test_telemetria_observabilidad(tmp_path, monkeypatch):
    from skills import uso_ia

    db_test = tmp_path / "test_telemetria.db"
    conn = sqlite3.connect(str(db_test))
    conn.execute(
        """
        CREATE TABLE uso_ia (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT NOT NULL,
            canal TEXT NOT NULL,
            agente TEXT DEFAULT '',
            proveedor TEXT DEFAULT '',
            modelo TEXT DEFAULT '',
            tokens_estimados INTEGER DEFAULT 0,
            latencia_ms INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        )
        """
    )
    conn.commit()
    conn.close()

    config_test = tmp_path / "presupuesto_test.json"
    monkeypatch.setattr(uso_ia, "DB_PATH", db_test)
    monkeypatch.setattr(uso_ia, "PRESUPUESTO_PATH", config_test)

    # Registrar uso
    uso_ia.registrar_uso("dashboard", "asistente", "Google Gemini", "gemini-2.5-flash", 150, 800)
    uso_ia.registrar_uso("whatsapp", "crm", "Google Gemini", "gemini-2.5-flash", 200, 1200)

    # Guardar presupuesto
    res_presup = uso_ia.guardar_limite_diario(50)
    assert res_presup["ok"] is True
    assert uso_ia.obtener_limite_diario() == 50

    # Consultar telemetría
    telemetria = uso_ia.uso_de_hoy(incluir_detalles=True)
    assert telemetria["hoy"] == 2
    assert telemetria["limite"] == 50
    assert telemetria["por_canal"]["dashboard"] == 1
    assert telemetria["por_canal"]["whatsapp"] == 1
    assert telemetria["por_agente"]["asistente"] == 1
    assert telemetria["por_agente"]["crm"] == 1
    assert telemetria["tokens_estimados"] == 350


def test_sandbox_ejecutar_script(monkeypatch):
    from skills import ejecutar_script

    # Crear script temporal en scripts/
    script_path = ROOT / "scripts" / "_test_sandbox_tmp.py"
    try:
        script_path.write_text(
            "import os\nprint('KEY_EXISTS:', 'OPENCODE_SERVER_PASSWORD' in os.environ)\n",
            encoding="utf-8",
        )

        monkeypatch.setenv("OPENCODE_SERVER_PASSWORD", "secreto123")
        monkeypatch.setenv("GEMINI_API_KEY", "gemini_secret")

        res = ejecutar_script.ejecutar_script("scripts/_test_sandbox_tmp.py")
        assert res["ok"] is True
        assert "KEY_EXISTS: False" in res["stdout"]
    finally:
        if script_path.exists():
            script_path.unlink()


def test_hybrid_rag_query():
    from skills.consultar_memoria_vectorial import consultar

    res = consultar("sistema operativo", n_resultados=2)
    assert isinstance(res, list)
    if res:
        assert "texto" in res[0]
        assert "relevancia" in res[0]
        assert "tipo_recuperacion" in res[0]