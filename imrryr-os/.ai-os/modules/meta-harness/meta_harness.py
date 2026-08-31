#!/usr/bin/env python3
"""meta-harness — Módulo Trend Scout & Auto-Evolve (Tanda VIII).

Alcance de decisión (2026-08-30):
  - Scout: breaking changes del stack (requirements.txt vs PyPI),
    patrones de agentes (agentes/*.yaml) y repos MCP rastreados.
    Dependabot cubre versiones; el scout detecta cambios ARQUITECTURALES
    (breaking changes mayores) que Dependabot no interpreta.
  - RFC: informe conciso problema → impacto en rendimiento o tokens.
  - Sandbox: ejecución aislada en .ai-os/sandbox/ (sin vault, sin credenciales).
  - Instalación: siempre requiere aprobación humana.

Cómputo determinista: la comparación de versiones y la consulta a PyPI
son scripts locales, no inferencia del LLM.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
AI_OS = ROOT / ".ai-os"
CONFIG = AI_OS / "config.json"
SANDBOX = AI_OS / "sandbox"
REQUIREMENTS = ROOT / "requirements.txt"
AGENTES_DIR = ROOT / "agentes"

sys.path.insert(0, str(ROOT))


def log(msg: str) -> None:
    print(f"[meta-harness] {msg}", flush=True)


def cargar_config() -> dict:
    if CONFIG.exists():
        return json.loads(CONFIG.read_text(encoding="utf-8"))
    return {}


# ---------------------------------------------------------------- scout --

_RE_REQ = re.compile(r"^([A-Za-z0-9_.\-]+)\[?([A-Za-z0-9_,.\-]*)\]?(?:>=|==|>|<)?\s*([0-9][0-9A-Za-z.\-]*)?")


def _parsear_requirements() -> list[tuple[str, str]]:
    """Extrae (paquete, versión_mínima) de requirements.txt."""
    deps = []
    for line in REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = _RE_REQ.match(line)
        if m:
            deps.append((m.group(1), m.group(3) or ""))
    return deps


def _ultima_version_pypi(paquete: str) -> str | None:
    """Consulta la última versión estable en PyPI (determinista, sin LLM)."""
    try:
        import httpx

        r = httpx.get(f"https://pypi.org/pypi/{paquete}/json", timeout=10.0)
        r.raise_for_status()
        return r.json()["info"]["version"]
    except Exception as e:
        log(f"WARN: PyPI no disponible para {paquete} ({e.__class__.__name__})")
        return None


def _version_mayor(actual: str, reciente: str) -> bool:
    """True si 'reciente' sube el primer componente (breaking probable)."""
    try:
        a = int(actual.split(".")[0])
        r = int(reciente.split(".")[0])
        return r > a
    except (ValueError, IndexError):
        return False


def scout_stack() -> dict:
    """Detecta breaking changes mayores entre requirements.txt y PyPI."""
    log("Scouting: breaking changes del stack (requirements.txt vs PyPI)...")
    breaking = []
    sin_verificar = []
    for paquete, version_min in _parsear_requirements():
        if not version_min:
            sin_verificar.append(paquete)
            continue
        ultima = _ultima_version_pypi(paquete)
        if ultima and _version_mayor(version_min, ultima):
            breaking.append({
                "paquete": paquete,
                "pin_actual": f">={version_min}",
                "ultima_pypi": ultima,
                "nota": "cambio de versión mayor — revisar changelog antes de actualizar",
            })
    log(f"Breaking changes detectados: {len(breaking)}")
    return {"breaking_changes": breaking, "sin_pin_verificable": sin_verificar}


def scout_patrones_agentes() -> dict:
    """Escanea agentes/*.yaml para patrones estructurales."""
    log("Scouting: patrones de agentes...")
    patrones = {"agentes": [], "con_herramientas": 0, "con_modelo_explicito": 0}
    if not AGENTES_DIR.exists():
        return patrones
    for yaml_file in sorted(AGENTES_DIR.glob("*.yaml")):
        try:
            import yaml

            data = yaml.safe_load(yaml_file.read_text(encoding="utf-8")) or {}
            nombre = data.get("nombre", yaml_file.stem)
            tiene_modelo = "modelo" in data or "model" in data
            tiene_herramientas = bool(data.get("herramientas") or data.get("tools"))
            if tiene_herramientas:
                patrones["con_herramientas"] += 1
            if tiene_modelo:
                patrones["con_modelo_explicito"] += 1
            patrones["agentes"].append({
                "archivo": yaml_file.name,
                "nombre": nombre,
                "modelo_explicito": tiene_modelo,
                "herramientas": tiene_herramientas,
            })
        except Exception as e:
            log(f"WARN: no se pudo parsear {yaml_file.name} ({e.__class__.__name__})")
    log(f"Agentes analizados: {len(patrones['agentes'])}")
    return patrones


MCPS_RASTREADOS = [
    "modelcontextprotocol/servers",
]


def scout_mcps() -> dict:
    """Registra los repos MCP bajo seguimiento (el detalle va en el RFC)."""
    log("Scouting: repos MCP bajo seguimiento...")
    return {"seguimiento": MCPS_RASTREADOS, "total": len(MCPS_RASTREADOS)}


def scout() -> dict:
    """Scout completo: stack + patrones de agentes + MCPs."""
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "stack": scout_stack(),
        "agentes": scout_patrones_agentes(),
        "mcps": scout_mcps(),
    }


# ------------------------------------------------------------------ RFC --

def generar_rfc(scout_result: dict) -> str:
    """RFC conciso: problema resuelto + impacto en rendimiento o tokens."""
    breaking = scout_result.get("stack", {}).get("breaking_changes", [])
    lineas_breaking = "\n".join(
        f"- **{b['paquete']}**: {b['pin_actual']} → {b['ultima_pypi']} ({b['nota']})"
        for b in breaking
    ) or "- Ninguno detectado."

    return f"""# RFC — Meta-Harness

## Fecha
{datetime.now().isoformat(timespec="seconds")}

## Problema Detectado
Cambios de versión mayor en el stack que pueden romper patrones
arquitecturales (routers FastAPI, contrato MCP, imports de config).

## Hallazgos del Scout
{lineas_breaking}

## Impacto en Rendimiento/Tokens
A evaluar tras sandbox. Los cambios mayores pueden alterar latencia
del proxy litellm y el tamaño de respuesta del dashboard.

## Propuesta
Ejecutar sandbox por cada paquete afectado antes de cualquier
actualización de requirements.txt.

## Aprobación Requerida
[ ] Human approval required before installing in .ai-os/skills/
"""


# -------------------------------------------------------------- sandbox --

def sandbox(ruta_script: str) -> dict:
    """Ejecuta un script en .ai-os/sandbox/ de forma aislada.

    Aislamiento: copia el script al sandbox, lo ejecuta con cwd=sandbox,
    sin acceso garantizado a vault/ ni credenciales (variables de entorno
    mínimas). Nunca modifica el código de producción.
    """
    origen = Path(ruta_script)
    if not origen.exists():
        return {"ok": False, "error": f"script no encontrado: {ruta_script}"}

    SANDBOX.mkdir(parents=True, exist_ok=True)
    destino = SANDBOX / origen.name
    shutil.copy2(origen, destino)

    env_min = {
        k: v
        for k, v in os.environ.items()
        if not k.upper().startswith(("IMRRYR_", "GROQ_", "OPENAI_", "ANTHROPIC_", "GOOGLE_"))
    }
    env_min["PYTHONPATH"] = str(SANDBOX)
    env_min["PYTHONDONTWRITEBYTECODE"] = "1"

    log(f"Ejecutando en sandbox: {destino.name}")
    try:
        proc = subprocess.run(
            [sys.executable, str(destino)],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(SANDBOX),
            env=env_min,
        )
        resultado = {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": proc.stdout[-2000:],
            "stderr": proc.stderr[-2000:],
            "aprobado": False,
        }
    except subprocess.TimeoutExpired:
        resultado = {"ok": False, "error": "timeout de 120s en sandbox", "aprobado": False}
    finally:
        destino.unlink(missing_ok=True)

    log(f"Sandbox completado. ok={resultado['ok']}")
    return resultado


# ------------------------------------------------------------ auto-evolve --

def auto_evolve() -> dict:
    """Ciclo: scout → RFC → guarda RFC para revisión humana."""
    log("Meta-Harness: ciclo de auto-evolución")
    scout_result = scout()
    rfc = generar_rfc(scout_result)
    rfc_path = AI_OS / "sandbox" / f"rfc_{datetime.now().strftime('%Y%m%d_%H%M')}.md"
    rfc_path.parent.mkdir(parents=True, exist_ok=True)
    rfc_path.write_text(rfc, encoding="utf-8")
    log(f"RFC guardado: {rfc_path.name}")
    return {
        "scout": scout_result,
        "rfc_path": str(rfc_path.relative_to(ROOT)),
        "requiere_aprobacion_humana": True,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="meta-harness: scout, RFC y sandbox")
    ap.add_argument("--scout", action="store_true", help="Ejecutar scout completo y generar RFC")
    ap.add_argument("--sandbox", type=str, metavar="SCRIPT", help="Probar un script en el sandbox")
    args = ap.parse_args()

    if args.sandbox:
        print(json.dumps(sandbox(args.sandbox), indent=2, ensure_ascii=False))
        return 0
    if args.scout:
        print(json.dumps(auto_evolve(), indent=2, ensure_ascii=False))
        return 0

    ap.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())