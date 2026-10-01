"""Pruebas unitarias y de integración para el módulo de Reuniones y Canvas Conceptual."""
import json
from datetime import date

import pytest
from fastapi.testclient import TestClient

import agenda
import pendientes
import skills.agenda as agenda_module
import skills.gestionar_reuniones as reuniones_module
import skills.pendientes as pendientes_module


@pytest.fixture(autouse=True)
def _db_aislada(db_temporal, monkeypatch):
    monkeypatch.setattr(reuniones_module, "DB_PATH", db_temporal)
    monkeypatch.setattr(agenda_module, "DB_PATH", db_temporal)
    monkeypatch.setattr(pendientes_module, "DB_PATH", db_temporal)
    monkeypatch.setattr(agenda, "DB_PATH", db_temporal)
    monkeypatch.setattr(pendientes, "DB_PATH", db_temporal)


def test_guardar_y_consultar_reunion():
    r = reuniones_module.guardar_reunion(
        titulo="Lanzamiento Q4",
        fecha=date.today().isoformat(),
        duracion_min=45,
        participantes="Ana, Carlos, Elena",
        transcripcion_cruda="Discutimos las fechas del lanzamiento y asignamos tareas.",
        resumen_ejecutivo="Reunión para alinear el roadmap de producto.",
        conclusiones="Se aprueba fecha de salida para noviembre.",
        acuerdos_tareas=[{"tarea": "Preparar demo", "responsable": "Carlos", "fecha_limite": "2026-11-01"}],
    )
    assert r["ok"] is True
    reunion_id = r["id"]

    # Consultar detalle
    det = reuniones_module.consultar_reuniones(accion="detalle", reunion_id=reunion_id)
    assert det["ok"] is True
    reunion = det["reunion"]
    assert reunion["titulo"] == "Lanzamiento Q4"
    assert len(reunion["acuerdos_tareas"]) == 1
    assert reunion["acuerdos_tareas"][0]["responsable"] == "Carlos"

    # Buscar por palabra clave
    busq = reuniones_module.consultar_reuniones(accion="buscar", query="roadmap")
    assert busq["ok"] is True
    assert busq["total"] >= 1
    assert busq["reuniones"][0]["id"] == reunion_id


def test_generar_mapa_conceptual():
    r = reuniones_module.guardar_reunion(
        titulo="Estrategia Comercial",
        resumen_ejecutivo="• Apertura de nuevos canales digitales.\n• Fortalecimiento de alianzas estratégicas.",
        conclusiones="• Cerrar acuerdo marco con distribuidor.",
        acuerdos_tareas=[{"tarea": "Enviar propuesta comercial", "responsable": "Sofía"}],
    )
    reunion_id = r["id"]

    res_mapa = reuniones_module.generar_mapa_conceptual(reunion_id=reunion_id)
    assert res_mapa["ok"] is True
    mapa = res_mapa["mapa"]
    nodos = mapa["nodos"]
    conexiones = mapa["conexiones"]

    # Verificar nodo raíz y tipos de nodos
    root_nodes = [n for n in nodos if n["tipo"] == "central"]
    assert len(root_nodes) == 1
    assert root_nodes[0]["texto"] == "Estrategia Comercial"

    temas = [n for n in nodos if n["tipo"] == "tema"]
    assert len(temas) >= 1

    decisiones = [n for n in nodos if n["tipo"] == "decision"]
    assert len(decisiones) >= 1

    tareas = [n for n in nodos if n["tipo"] == "tarea"]
    assert len(tareas) >= 1

    # Verificar existencia de conexiones
    assert len(conexiones) >= 3


def test_volcar_tareas_agenda_y_pendientes():
    hoy = date.today().isoformat()
    r = reuniones_module.guardar_reunion(
        titulo="Sprint Planning",
        acuerdos_tareas=[
            {"tarea": "Configurar pipeline CI/CD", "responsable": "Martín", "fecha_limite": hoy},
            {"tarea": "Diseñar mockup de reportes", "responsable": "Laura", "fecha_limite": hoy},
        ],
    )
    reunion_id = r["id"]

    res_volcado = reuniones_module.volcar_tareas_agenda(
        reunion_id=reunion_id,
        agendar_en_eventos=True,
        agendar_en_pendientes=True,
    )
    assert res_volcado["ok"] is True
    assert len(res_volcado["eventos_creados"]) == 2
    assert len(res_volcado["pendientes_creados"]) == 2

    # Verificar que quedaron marcadas como agendadas en la reunión
    det = reuniones_module.consultar_reuniones(accion="detalle", reunion_id=reunion_id)
    tareas_act = det["reunion"]["acuerdos_tareas"]
    assert all(t.get("agendada") is True for t in tareas_act)

    # Verificar en la tabla de pendientes
    pends = pendientes_module._listar()["pendientes"]
    assert any("pipeline CI/CD" in p["texto"] for p in pends)


def test_api_reuniones_endpoints(db_temporal, monkeypatch):
    # El router importa `api.deps` (dashboard/ está en sys.path), que es OTRO objeto de
    # módulo distinto de `dashboard.api.deps`. Parchear solo este último dejaba a
    # DELETE /api/reuniones/{id} apuntando a la base real: en un equipo con datos
    # borraba la reunión #1 de verdad, y en CI fallaba por no existir la carpeta.
    from dashboard.server import app  # añade dashboard/ a sys.path: debe ir antes de `api.deps`

    import api.deps as api_deps
    import dashboard.api.deps as api_deps_pkg

    monkeypatch.setattr(api_deps, "DB_PATH", db_temporal)
    monkeypatch.setattr(api_deps_pkg, "DB_PATH", db_temporal)

    client = TestClient(app)

    # 1. Crear reunión vía POST
    r_post = client.post(
        "/api/reuniones",
        json={
            "titulo": "Reunión de Directorio",
            "fecha": "2026-09-15",
            "participantes": "Director General, Finanzas",
            "resumen_ejecutivo": "Revisión del presupuesto anual.",
            "acuerdos_tareas": json.dumps([{"tarea": "Aprobar balance", "responsable": "Director"}]),
        },
    )
    assert r_post.status_code == 200
    res_crear = r_post.json()
    assert res_crear["ok"] is True
    rid = res_crear["id"]

    # 2. Listar reuniones
    r_list = client.get("/api/reuniones")
    assert r_list.status_code == 200
    assert len(r_list.json()["reuniones"]) >= 1

    # 3. Detalle de reunión
    r_det = client.get(f"/api/reuniones/{rid}")
    assert r_det.status_code == 200
    det = r_det.json()["reunion"]
    assert det["titulo"] == "Reunión de Directorio"

    # 4. Actualizar mapa conceptual en canvas vía PUT
    nuevo_mapa = {
        "nodos": [{"id": "node-1", "tipo": "central", "texto": "Directorio", "x": 100, "y": 100}],
        "conexiones": [],
    }
    r_put = client.put(f"/api/reuniones/{rid}/mapa", json={"mapa": nuevo_mapa})
    assert r_put.status_code == 200

    r_det2 = client.get(f"/api/reuniones/{rid}")
    assert r_det2.json()["reunion"]["mapa_conceptual_json"]["nodos"][0]["texto"] == "Directorio"

    # 5. Agendar tareas vía POST
    r_ag = client.post(f"/api/reuniones/{rid}/agendar-tareas", json={"agendar_en_pendientes": True})
    assert r_ag.status_code == 200
    assert r_ag.json()["ok"] is True

    # 6. Subir imagen para nodo de canvas vía POST
    r_img = client.post(
        f"/api/reuniones/{rid}/imagen",
        files={"archivo": ("diagrama.png", b"\x89PNG\r\n\x1a\nfakeimagecontent", "image/png")},
    )
    assert r_img.status_code == 200
    res_img = r_img.json()
    assert res_img["ok"] is True
    assert "url" in res_img
    assert "/reuniones_audio/imagenes/" in res_img["url"]

    # 7. Eliminar reunión
    r_del = client.delete(f"/api/reuniones/{rid}")
    assert r_del.status_code == 200
    assert r_del.json()["ok"] is True


def test_extraccion_heuristica_ignora_saludos_y_extrae_responsables():
    from dashboard.api.reuniones import _extraer_analisis_heuristico

    transcripcion = (
        "Buenos días equipo, muchas gracias por conectarse hoy a esta sesión. "
        "En primer lugar, revisamos el avance del proyecto principal. "
        "Carlos debe preparar el informe técnico de arquitectura antes del viernes. "
        "Sofía se encargará de revisar las cotizaciones de los proveedores. "
        "Acordamos cerrar el diseño de la interfaz antes de fin de mes. "
        "Saludos cordiales y que tengan una excelente semana."
    )

    analisis = _extraer_analisis_heuristico(transcripcion)
    tareas = analisis["tareas"]
    resumen = analisis["resumen_ejecutivo"]

    # Verificar que los saludos no son tareas
    for t in tareas:
        desc = t["tarea"].lower()
        assert not desc.startswith("buenos días")
        assert not desc.startswith("saludos cordiales")
        assert not desc.startswith("muchas gracias")

    # Verificar que se detectaron responsables específicos
    responsables = [t["responsable"] for t in tareas]
    assert "Carlos" in responsables or any("Carlos" in t["tarea"] for t in tareas)
    assert "Sofía" in responsables or any("Sofía" in t["tarea"] for t in tareas)

    # Verificar resumen ejecutivo
    assert "avance del proyecto" in resumen.lower()


def test_actualizar_reunion_permite_vaciar_campos_explicitamente():
    """Bug real: guardar_reunion usaba `if campo:` para decidir si tocar una
    columna en el UPDATE, así que "" y 0 se confundían con "no enviado". El
    usuario que borraba el cuadro de Transcripción Cruda y pulsaba "Guardar"
    recibía un toast de éxito, pero el texto viejo seguía en la base de datos
    intacto. Ahora el centinela de "no tocar" es None, no el valor vacío."""
    r = reuniones_module.guardar_reunion(
        titulo="Reunión con campos a vaciar",
        transcripcion_cruda="Texto original a borrar",
        resumen_ejecutivo="Resumen viejo",
        conclusiones="Conclusión vieja",
    )
    rid = r["id"]

    # El usuario borra por completo la transcripción y guarda (como hace el
    # botón "Guardar Transcripción" -> PUT /api/reuniones/{id}/transcripcion).
    reuniones_module.guardar_reunion(titulo="", transcripcion_cruda="", reunion_id=rid)
    det = reuniones_module.consultar_reuniones(accion="detalle", reunion_id=rid)
    assert det["reunion"]["transcripcion_cruda"] == ""

    # Vaciar resumen y conclusiones a la vez debe respetarse igual.
    reuniones_module.guardar_reunion(titulo="", resumen_ejecutivo="", conclusiones="", reunion_id=rid)
    det2 = reuniones_module.consultar_reuniones(accion="detalle", reunion_id=rid)
    assert det2["reunion"]["resumen_ejecutivo"] == ""
    assert det2["reunion"]["conclusiones"] == ""


def test_actualizar_solo_un_campo_no_borra_los_demas():
    """Contraparte del fix anterior: un update parcial (solo el mapa, como
    hace PUT /mapa) NO debe arrastrar los demás campos a vacío."""
    r = reuniones_module.guardar_reunion(
        titulo="Reunión con mapa aparte",
        transcripcion_cruda="Esta transcripción no debe desaparecer",
    )
    rid = r["id"]

    reuniones_module.guardar_reunion(
        titulo="", mapa_conceptual_json={"nodos": [], "conexiones": []}, reunion_id=rid,
    )
    det = reuniones_module.consultar_reuniones(accion="detalle", reunion_id=rid)
    assert det["reunion"]["transcripcion_cruda"] == "Esta transcripción no debe desaparecer"


def test_mapa_conceptual_agrupa_por_persona_y_curvas_bezier():
    r = reuniones_module.guardar_reunion(
        titulo="Comité de Innovación",
        resumen_ejecutivo="Avance de prototipos de IA para automatización.",
        conclusiones="Lanzar piloto con clientes clave.",
        acuerdos_tareas=[
            {"tarea": "Desarrollar prototipo", "responsable": "Carlos"},
            {"tarea": "Preparar contrato piloto", "responsable": "Sofía"},
        ],
    )
    rid = r["id"]

    res = reuniones_module.generar_mapa_conceptual(reunion_id=rid)
    assert res["ok"] is True
    mapa = res["mapa"]
    nodos = mapa["nodos"]
    conexiones = mapa["conexiones"]

    # Nodos persona
    personas = [n for n in nodos if n["tipo"] == "persona"]
    assert len(personas) == 2
    nombres_persona = [p["texto"] for p in personas]
    assert any("Carlos" in np for np in nombres_persona)
    assert any("Sofía" in np for np in nombres_persona)

    # Conexiones con curvas bezier
    assert any(c.get("curva") == "bezier" for c in conexiones)

