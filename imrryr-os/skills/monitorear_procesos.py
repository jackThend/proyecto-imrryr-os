#!/usr/bin/env python3
"""
monitorear_procesos.py — Skill: Observabilidad de procesos (Guardia de Seguridad)
==================================================================================
Observa los procesos de los servicios base (OpenCode, LiteLLM, gateway y el
sidecar de WhatsApp; sus PIDs los deja scripts/startup.py en .run/*.pid) y
reporta su estado.

REGLA CENTRAL — los servicios base NUNCA se marcan como atascados:
    La versión anterior consideraba "atascado" a todo proceso con más de
    timeout_max segundos de vida. Para un demonio eso es su estado normal:
    LiteLLM, OpenCode y el gateway existen precisamente para estar siempre
    arriba. El resultado era que a los 5 minutos el scheduler los daba por
    colgados y los mataba — el sistema se apagaba solo en mitad de una
    conversación (verificado en vivo: se cayeron los tres a la vez).
    Por eso el tiempo de vida ya no decide nada sobre ellos, y `atascado`
    queda reservado para procesos que NO son parte de la infraestructura.

Para lo que el módulo sí promete ("detecta bucles infinitos") se usa una
señal real y no el reloj: consumo de CPU sostenido (`cpu_alto`). Eso el
scheduler lo trata como motivo de ALERTA, nunca de apagado — un modelo
razonando o una importación pesada también consumen CPU, y matar el motor
por estar trabajando sería el mismo error de antes con otro disfraz.

Uso:
    python skills/monitorear_procesos.py
    python skills/monitorear_procesos.py --timeout 300
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PID_DIR = ROOT / ".run"
PROCESOS_RAIZ = ("opencode", "litellm", "gateway", "whatsapp_local")

# % de CPU a partir del cual un proceso se considera "trabajando fuerte".
# No implica que esté roto: es solo la señal que dispara una alerta cuando
# además lleva mucho rato así.
CPU_ALTO_PCT = 85.0


def log(msg: str) -> None:
    print(f"[monitorear_procesos] {msg}", flush=True)


def _leer_pid(nombre: str) -> int | None:
    pid_file = PID_DIR / f"{nombre}.pid"
    if not pid_file.exists():
        return None
    try:
        return int(pid_file.read_text().strip())
    except ValueError:
        return None


def listar_procesos(timeout_segundos: int = 300) -> list[dict]:
    import psutil

    resultado = []
    ahora = time.time()

    for nombre in PROCESOS_RAIZ:
        pid_raiz = _leer_pid(nombre)
        if pid_raiz is None or not psutil.pid_exists(pid_raiz):
            continue
        try:
            proceso_raiz = psutil.Process(pid_raiz)
        except psutil.NoSuchProcess:
            continue

        # Todo el árbol de un servicio declarado ES el servicio: tanto el
        # proceso raíz como sus hijos (en Windows, por ejemplo, OpenCode
        # arranca como cmd.exe -> opencode.exe). Ninguno es "una tarea que se
        # colgó"; son infraestructura que debe seguir viva.
        candidatos = [proceso_raiz, *proceso_raiz.children(recursive=True)]
        for proc in candidatos:
            try:
                segundos_activo = ahora - proc.create_time()
                # cpu_percent() sin intervalo devuelve el uso desde la llamada
                # anterior; en la primera da 0.0, lo cual es aceptable: la
                # alerta exige además tiempo activo, así que nunca dispara en
                # el primer tick.
                cpu = proc.cpu_percent()
                resultado.append({
                    "pid": proc.pid,
                    "nombre_proceso": proc.name(),
                    "cmdline": " ".join(proc.cmdline())[:200],
                    "servicio": nombre,
                    "segundos_activo": round(segundos_activo, 1),
                    "cpu_pct": round(cpu, 1),
                    "es_servicio_base": True,
                    # Un servicio base jamás se marca atascado: llevar horas
                    # arriba es exactamente lo que se espera de él.
                    "atascado": False,
                    # Señal para alertar (no para apagar): trabajando a tope
                    # durante más tiempo del razonable.
                    "cpu_alto": cpu >= CPU_ALTO_PCT and segundos_activo > timeout_segundos,
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

    return resultado


def monitorear_procesos(timeout: int = 300) -> list[dict]:
    """Punto de entrada MCP (nombre = nombre de la skill, ver mcp_server/skills_server.py)."""
    return listar_procesos(timeout)


def main() -> int:
    ap = argparse.ArgumentParser(description="Lista procesos monitoreados y marca los atascados")
    ap.add_argument("--timeout", type=int, default=300, help="Segundos a partir de los cuales un proceso se considera atascado")
    args = ap.parse_args()

    procesos = listar_procesos(args.timeout)
    atascados = [p for p in procesos if p["atascado"]]
    log(f"Procesos monitoreados: {len(procesos)} | Atascados: {len(atascados)}")
    print(json.dumps(procesos, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
