"""El Guardia de Seguridad no debe apagar la infraestructura del sistema.

Bug real encontrado probando un ciclo completo: el monitor marcaba como
"atascado" a todo proceso con más de timeout_max segundos de vida. Como
LiteLLM, OpenCode y el gateway son demonios (estar vivos siempre es su
función), a los 5 minutos el scheduler los mataba y el sistema se apagaba
solo en mitad de una conversación. Estos tests fijan la regla para que no
vuelva a pasar.
"""
import monitorear_procesos as mp


class _ProcFalso:
    """Sustituto de psutil.Process con el tiempo de vida y CPU que se quiera."""

    def __init__(self, pid, nombre, segundos_vivo, cpu, ahora):
        self.pid = pid
        self._nombre = nombre
        self._create = ahora - segundos_vivo
        self._cpu = cpu

    def name(self):
        return self._nombre

    def cmdline(self):
        return [self._nombre, "serve"]

    def create_time(self):
        return self._create

    def cpu_percent(self):
        return self._cpu

    def children(self, recursive=False):
        return []


def _preparar(monkeypatch, tmp_path, segundos_vivo, cpu):
    """Deja un .run/litellm.pid falso y un psutil de mentira apuntando a él."""
    import sys
    import time
    import types

    run = tmp_path / ".run"
    run.mkdir()
    (run / "litellm.pid").write_text("4321")
    monkeypatch.setattr(mp, "PID_DIR", run)

    proc = _ProcFalso(4321, "litellm.exe", segundos_vivo, cpu, time.time())
    falso = types.SimpleNamespace(
        pid_exists=lambda pid: True,
        Process=lambda pid: proc,
        NoSuchProcess=Exception,
        AccessDenied=Exception,
    )
    monkeypatch.setitem(sys.modules, "psutil", falso)


def test_servicio_base_nunca_se_marca_atascado(monkeypatch, tmp_path):
    # 10 horas arriba: para un demonio es normal, no un cuelgue.
    _preparar(monkeypatch, tmp_path, segundos_vivo=36_000, cpu=1.0)
    procesos = mp.listar_procesos(timeout_segundos=300)
    assert procesos, "debería reportar el servicio"
    assert procesos[0]["es_servicio_base"] is True
    assert procesos[0]["atascado"] is False


def test_cpu_alta_sostenida_se_señala_pero_no_como_atascado(monkeypatch, tmp_path):
    _preparar(monkeypatch, tmp_path, segundos_vivo=36_000, cpu=99.0)
    p = mp.listar_procesos(timeout_segundos=300)[0]
    assert p["cpu_alto"] is True      # sirve para avisar
    assert p["atascado"] is False     # pero nunca para apagarlo


def test_cpu_alta_recien_arrancado_no_alerta(monkeypatch, tmp_path):
    # Trabajo pesado normal al arrancar no debe generar ruido.
    _preparar(monkeypatch, tmp_path, segundos_vivo=10, cpu=99.0)
    assert mp.listar_procesos(timeout_segundos=300)[0]["cpu_alto"] is False
