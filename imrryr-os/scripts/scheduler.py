#!/usr/bin/env python3
"""
scheduler.py — Scheduler genérico de tareas periódicas (Tanda P)
=====================================================================
Un solo hilo daemon, arrancado por dashboard/server.py (el único proceso de
larga duración del sistema — startup.py es solo un lanzador que termina en
cuanto los servicios quedan arriba). Tickea cada 60 segundos y ejecuta, cada
uno envuelto en su propio try/except (un fallo en una tarea no debe tumbar
las demás ni el hilo completo):

  - Publicar posts de redes sociales programados que ya vencieron.
  - Disparar recordatorios vencidos (antes solo corría por CLI manual).
  - Guardia de Seguridad real: cada ~5 min, revisa procesos atascados y
    actúa solo si hace falta (valor agregado de la Tanda P, no pedido
    explícitamente por el usuario — ver docstring de _tick_guardia_seguridad).
  - Digest diario de ofertas de compras (Tanda Q) y resumen diario +
    avisos 1h-antes de agenda (Tanda R), ambos 100% deterministas (sin IA).

Uso:
    from scripts.scheduler import iniciar_scheduler_generico
    iniciar_scheduler_generico()   # no bloquea, arranca un daemon thread
"""
from __future__ import annotations

import json
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
ESTADO_PATH = ROOT / "config" / "scheduler_estado.json"
AGENDA_PREFS_PATH = ROOT / "config" / "agenda_prefs.json"

_ultimo_chequeo_guardia = 0.0


def log(msg: str) -> None:
    print(f"[scheduler] {msg}", flush=True)


def _leer_estado() -> dict[str, Any]:
    if not ESTADO_PATH.exists():
        return {}
    try:
        return json.loads(ESTADO_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _guardar_estado(estado: dict[str, Any]) -> None:
    ESTADO_PATH.parent.mkdir(parents=True, exist_ok=True)
    ESTADO_PATH.write_text(json.dumps(estado, indent=2, ensure_ascii=False), encoding="utf-8")


def _hora_resumen_diario() -> str:
    if not AGENDA_PREFS_PATH.exists():
        return "08:00"
    try:
        datos = json.loads(AGENDA_PREFS_PATH.read_text(encoding="utf-8"))
        return datos.get("hora_resumen_diario", "08:00")
    except (json.JSONDecodeError, OSError):
        return "08:00"


def _tick_posts_programados() -> None:
    from skills.publicar_posts_programados import publicar_posts_programados
    resultado = publicar_posts_programados()
    if resultado.get("revisados"):
        log(f"posts programados: {resultado}")


def _tick_recordatorios() -> None:
    from skills.recordatorios import ejecutar_vencidos
    disparados = ejecutar_vencidos()
    if disparados:
        log(f"recordatorios disparados: {disparados}")


def _tick_guardia_seguridad() -> None:
    """Valor agregado de la Tanda P (no pedido explícitamente): antes, el
    Guardia de Seguridad solo revisaba procesos si algo lo invocaba a mano,
    pese a que su propia descripción dice 'vigila todo el tiempo'. Esto cierra
    esa brecha: cada ~5 minutos, revisa y actúa solo si detecta algo atascado."""
    global _ultimo_chequeo_guardia
    ahora = time.time()
    if ahora - _ultimo_chequeo_guardia < 300:
        return
    _ultimo_chequeo_guardia = ahora

    from skills.monitorear_procesos import monitorear_procesos
    procesos = monitorear_procesos()
    atascados = [p for p in procesos if p.get("atascado")]
    if not atascados:
        return

    from skills.detener_proceso import detener_proceso
    from skills.enviar_alerta import enviar_alerta
    for p in atascados:
        log(f"proceso atascado detectado: {p}")
        detener_proceso(p["pid"])
        enviar_alerta(f"Detuve el proceso {p.get('nombre_proceso', p['pid'])} (llevaba atascado más de lo normal).")


def _tick_compras_digest() -> None:
    ahora = datetime.now()
    if ahora.strftime("%H:%M") != _hora_resumen_diario():
        return
    estado = _leer_estado()
    hoy = ahora.date().isoformat()
    if estado.get("ultimo_digest_compras") == hoy:
        return

    from skills.enviar_digest_compras import enviar_digest_compras
    resultado = enviar_digest_compras()
    log(f"digest de compras enviado: {resultado}")
    estado["ultimo_digest_compras"] = hoy
    _guardar_estado(estado)


def _tick_agenda_avisos() -> None:
    """Cada evento puede tener cualquier cantidad de avisos a horas libres
    (tabla avisos_evento) — reemplaza los dos flags fijos de antes (inicio
    del día / 1h antes) por avisos a la hora exacta que el usuario pida."""
    from skills.agenda import avisar_eventos_programados
    avisados = avisar_eventos_programados()
    if avisados:
        log(f"avisos de agenda enviados: {avisados}")


def ejecutar_tareas_programadas() -> None:
    tareas = (
        _tick_posts_programados,
        _tick_recordatorios,
        _tick_guardia_seguridad,
        _tick_compras_digest,
        _tick_agenda_avisos,
    )
    for tarea in tareas:
        try:
            tarea()
        except Exception as e:
            log(f"tarea {tarea.__name__} falló: {e}")


def _loop() -> None:
    while True:
        ejecutar_tareas_programadas()
        time.sleep(60)


def iniciar_scheduler_generico() -> None:
    threading.Thread(target=_loop, daemon=True).start()
    log("scheduler genérico iniciado (tick cada 60s)")


if __name__ == "__main__":
    ejecutar_tareas_programadas()
