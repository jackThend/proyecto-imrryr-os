#!/usr/bin/env python3
"""
perfil_negocio.py — Skill: Perfil de Negocio (contexto para el Agente Investigador)
======================================================================================
Guarda las características del negocio del usuario (giro, ubicación, tamaño,
y cualquier característica extra que quiera agregar) en un archivo de texto
plano editable, tanto desde el dashboard como por el propio agente. El
Investigador lo consulta para juzgar si un fondo concursable realmente le
sirve, en vez de usar un motor de scoring aparte.

Uso:
    python skills/perfil_negocio.py --ver
    python skills/perfil_negocio.py --set '{"giro": ["tecnologia", "museografia"]}'
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
PERFIL_PATH = ROOT / "config" / "perfil_negocio.json"

DEFAULTS: dict[str, Any] = {
    "nombre_usuario": "",
    "empresas": [],
    "giro": [],
    "ubicacion": {"region": "", "comuna": ""},
    "tamano_empresa": "",
    "caracteristicas_extra": {},
}


def log(msg: str) -> None:
    print(f"[perfil_negocio] {msg}", flush=True)


def leer_perfil_negocio() -> dict[str, Any]:
    if not PERFIL_PATH.exists():
        return json.loads(json.dumps(DEFAULTS))  # copia profunda
    try:
        data = json.loads(PERFIL_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return json.loads(json.dumps(DEFAULTS))

    perfil = json.loads(json.dumps(DEFAULTS))
    for clave in ("nombre_usuario", "empresas", "giro", "tamano_empresa"):
        if clave in data:
            perfil[clave] = data[clave]
    perfil["ubicacion"].update(data.get("ubicacion", {}))
    perfil["caracteristicas_extra"].update(data.get("caracteristicas_extra", {}))
    return perfil


def actualizar_perfil_negocio(datos: dict[str, Any]) -> dict[str, Any]:
    """Fusiona `datos` sobre el perfil actual.
    Soporta nombre_usuario, lista de empresas, giro, tamaño, ubicación y características extra.
    """
    actual = leer_perfil_negocio()
    if "nombre_usuario" in datos:
        actual["nombre_usuario"] = str(datos["nombre_usuario"]).strip()
    if "empresas" in datos:
        actual["empresas"] = datos["empresas"] if isinstance(datos["empresas"], list) else []
    if "giro" in datos:
        actual["giro"] = datos["giro"]
    if "tamano_empresa" in datos:
        actual["tamano_empresa"] = datos["tamano_empresa"]
    if "ubicacion" in datos:
        actual["ubicacion"].update(datos["ubicacion"])
    if "caracteristicas_extra" in datos:
        for clave, valor in datos["caracteristicas_extra"].items():
            if valor is None:
                actual["caracteristicas_extra"].pop(clave, None)
            else:
                actual["caracteristicas_extra"][clave] = valor

    PERFIL_PATH.parent.mkdir(parents=True, exist_ok=True)
    PERFIL_PATH.write_text(json.dumps(actual, indent=2, ensure_ascii=False), encoding="utf-8")

    # Sincronizar hacia memoria_usuario en SQLite para acceso agéntico limpio
    try:
        db_path = ROOT / "vault" / "sqlite" / "imrryr.db"
        if db_path.exists():
            import sqlite3
            conn = sqlite3.connect(str(db_path))
            try:
                if actual.get("nombre_usuario"):
                    conn.execute(
                        "INSERT INTO memoria_usuario (categoria, clave, valor, updated_at) VALUES ('perfil', 'nombre_usuario', ?, datetime('now')) "
                        "ON CONFLICT(clave) DO UPDATE SET valor = excluded.valor, updated_at = datetime('now')",
                        (actual["nombre_usuario"],),
                    )
                if actual.get("empresas"):
                    conn.execute(
                        "INSERT INTO memoria_usuario (categoria, clave, valor, updated_at) VALUES ('perfil', 'empresas', ?, datetime('now')) "
                        "ON CONFLICT(clave) DO UPDATE SET valor = excluded.valor, updated_at = datetime('now')",
                        (json.dumps(actual["empresas"], ensure_ascii=False),),
                    )
                for k, v in actual.get("caracteristicas_extra", {}).items():
                    conn.execute(
                        "INSERT INTO memoria_usuario (categoria, clave, valor, updated_at) VALUES ('preferencia', ?, ?, datetime('now')) "
                        "ON CONFLICT(clave) DO UPDATE SET valor = excluded.valor, updated_at = datetime('now')",
                        (str(k), str(v)),
                    )
                conn.commit()
            finally:
                conn.close()
    except Exception as e:
        log(f"Aviso sync SQLite: {e}")

    return actual


def main() -> int:
    ap = argparse.ArgumentParser(description="Perfil de Negocio del usuario")
    ap.add_argument("--ver", action="store_true")
    ap.add_argument("--set", type=str, default=None, help="JSON con los campos a actualizar")
    args = ap.parse_args()

    if args.set:
        resultado = actualizar_perfil_negocio(json.loads(args.set))
    else:
        resultado = leer_perfil_negocio()

    print(json.dumps(resultado, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
