"""Rangos de fecha y avisos de la agenda (skills/agenda.py), contra DB temporal."""
from datetime import date, timedelta

import pytest

import agenda


@pytest.fixture(autouse=True)
def _db_aislada(db_temporal, monkeypatch):
    monkeypatch.setattr(agenda, "DB_PATH", db_temporal)


def test_crear_evento_con_avisos_multiples():
    hoy = date.today().isoformat()
    r = agenda._crear("Médico", hoy, "18:00", 60, "", avisos=["08:00", "17:00"], exportar_ics=False)
    assert r["ok"] is True

    eventos = agenda._que_tengo("hoy", None, None)["eventos"]
    assert len(eventos) == 1
    assert eventos[0]["titulo"] == "Médico"
    assert [a["hora_aviso"] for a in eventos[0]["avisos"]] == ["08:00", "17:00"]


def test_crear_sin_titulo_falla():
    assert agenda._crear("", "2026-01-01", "09:00", 60, "", [], False)["ok"] is False


def test_que_tengo_manana_no_mezcla_con_hoy():
    hoy = date.today()
    manana = (hoy + timedelta(days=1)).isoformat()
    agenda._crear("Solo mañana", manana, "10:00", 60, "", [], False)

    assert agenda._que_tengo("hoy", None, None)["eventos"] == []
    titulos = [e["titulo"] for e in agenda._que_tengo("mañana", None, None)["eventos"]]
    assert titulos == ["Solo mañana"]


def test_que_tengo_semana_incluye_los_7_dias():
    hoy = date.today()
    agenda._crear("En 6 días", (hoy + timedelta(days=6)).isoformat(), "10:00", 60, "", [], False)
    agenda._crear("En 20 días", (hoy + timedelta(days=20)).isoformat(), "10:00", 60, "", [], False)

    titulos = [e["titulo"] for e in agenda._que_tengo("semana", None, None)["eventos"]]
    assert titulos == ["En 6 días"]


def test_que_tengo_mes_usa_mes_pedido():
    agenda._crear("Evento enero", "2027-01-15", "10:00", 60, "", [], False)
    agenda._crear("Evento febrero", "2027-02-15", "10:00", 60, "", [], False)

    titulos = [e["titulo"] for e in agenda._que_tengo("mes", 2027, 1)["eventos"]]
    assert titulos == ["Evento enero"]
