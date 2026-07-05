#!/usr/bin/env python3
"""
leer_archivo.py — Skill: Lee un archivo (sandboxed) para el Agente Build
==========================================================================
Restringido a rutas dentro de imrryr-os/ y, opcionalmente, a proyectos
declarados en config/proyectos_permitidos.json (lista JSON de rutas
absolutas). Evita path traversal (../../..) fuera del sandbox.

Uso:
    python skills/leer_archivo.py --ruta scripts/startup.py
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PROYECTOS = ROOT / "config" / "proyectos_permitidos.json"


def log(msg: str) -> None:
    print(f"[leer_archivo] {msg}", flush=True)


def _raices_permitidas() -> list[Path]:
    raices = [ROOT]
    if CONFIG_PROYECTOS.exists():
        try:
            extra = json.loads(CONFIG_PROYECTOS.read_text(encoding="utf-8"))
            raices += [Path(p).resolve() for p in extra]
        except Exception:
            pass
    return raices


def _ruta_segura(ruta_str: str) -> Path | None:
    candidata = Path(ruta_str)
    if not candidata.is_absolute():
        candidata = ROOT / candidata
    candidata = candidata.resolve()
    for raiz in _raices_permitidas():
        try:
            candidata.relative_to(raiz)
            return candidata
        except ValueError:
            continue
    return None


def leer_archivo(ruta: str, max_chars: int = 5000) -> dict:
    segura = _ruta_segura(ruta)
    if segura is None:
        return {"ok": False, "error": "Ruta fuera del sandbox permitido (imrryr-os/ o proyectos declarados)"}
    if not segura.exists() or not segura.is_file():
        return {"ok": False, "error": "El archivo no existe"}

    contenido = segura.read_text(encoding="utf-8", errors="replace")
    truncado = len(contenido) > max_chars
    return {"ok": True, "ruta": str(segura), "contenido": contenido[:max_chars], "truncado": truncado}


def main() -> int:
    ap = argparse.ArgumentParser(description="Lee un archivo dentro del sandbox del proyecto")
    ap.add_argument("--ruta", type=str, required=True)
    ap.add_argument("--max-chars", type=int, default=5000)
    args = ap.parse_args()

    resultado = leer_archivo(args.ruta, args.max_chars)
    print(json.dumps(resultado, ensure_ascii=True, indent=2))
    return 0 if resultado["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
