#!/usr/bin/env python3
"""
escribir_archivo.py — Skill: Escribe un archivo (sandboxed) para el Agente Build
==================================================================================
Misma política de sandbox que leer_archivo.py: solo rutas dentro de
imrryr-os/ o de proyectos declarados en config/proyectos_permitidos.json.

Uso:
    python skills/escribir_archivo.py --ruta docs/notas.md --contenido "hola"
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PROYECTOS = ROOT / "config" / "proyectos_permitidos.json"


def log(msg: str) -> None:
    print(f"[escribir_archivo] {msg}", flush=True)


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


def escribir_archivo(ruta: str, contenido: str, sobrescribir: bool = True) -> dict:
    segura = _ruta_segura(ruta)
    if segura is None:
        return {"ok": False, "error": "Ruta fuera del sandbox permitido (imrryr-os/ o proyectos declarados)"}
    if segura.exists() and not sobrescribir:
        return {"ok": False, "error": "El archivo ya existe y sobrescribir=false"}

    segura.parent.mkdir(parents=True, exist_ok=True)
    segura.write_text(contenido, encoding="utf-8")
    return {"ok": True, "ruta": str(segura), "bytes_escritos": len(contenido.encode("utf-8"))}


def main() -> int:
    ap = argparse.ArgumentParser(description="Escribe un archivo dentro del sandbox del proyecto")
    ap.add_argument("--ruta", type=str, required=True)
    ap.add_argument("--contenido", type=str, required=True)
    ap.add_argument("--no-sobrescribir", action="store_true")
    args = ap.parse_args()

    resultado = escribir_archivo(args.ruta, args.contenido, not args.no_sobrescribir)
    print(json.dumps(resultado, ensure_ascii=True, indent=2))
    return 0 if resultado["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
