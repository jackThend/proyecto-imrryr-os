#!/usr/bin/env python3
"""
repo_web.py — Skill: Administra el repositorio de GitHub del sitio web del usuario
=====================================================================================
Clona/actualiza un repo, lee/edita un archivo de texto y hace commit+push a
la rama activa. Usa la cuenta de GitHub configurada en Ajustes (ver
config/cuentas_git.py) — nunca credenciales hardcodeadas en .env, para que
cualquier instalación configure su propio repo.

El token se inyecta en la URL remota solo durante la operación de red
(clone/pull/push) y se limpia de `.git/config` apenas termina, para no
dejarlo en texto plano en reposo más tiempo del necesario.

Uso:
    python skills/repo_web.py --cuenta mi_sitio --accion commit_push --mensaje "actualiza precio"
"""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent


def log(msg: str) -> None:
    print(f"[repo_web] {msg}", flush=True)


def _cuenta(cuenta_id: str) -> dict[str, Any] | None:
    from config import cuentas_git

    if cuenta_id:
        return cuentas_git.obtener_cuenta(cuenta_id)
    for c in cuentas_git.listar_cuentas():
        if c.get("activa"):
            return c
    return None


def _url_autenticada(repo_url: str, token: str) -> str:
    if token and repo_url.startswith("https://"):
        return repo_url.replace("https://", f"https://{token}@", 1)
    return repo_url


def _run_git(args: list[str], cwd: str | None = None) -> tuple[bool, str]:
    try:
        r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=60)
        salida = (r.stdout or "") + (r.stderr or "")
        return r.returncode == 0, salida.strip()
    except (OSError, subprocess.SubprocessError) as e:
        return False, str(e)


def _clonar_o_actualizar(cuenta: dict[str, Any]) -> dict[str, Any]:
    ruta = Path(cuenta["ruta_local"])
    url_auth = _url_autenticada(cuenta["repo_url"], cuenta.get("token", ""))
    rama = cuenta.get("rama", "main")

    if not (ruta / ".git").exists():
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ok, salida = _run_git(["clone", "--branch", rama, url_auth, str(ruta)])
        return {"ok": ok, "detalle": "clonado" if ok else salida}

    _run_git(["remote", "set-url", "origin", url_auth], cwd=str(ruta))
    ok, salida = _run_git(["pull", "origin", rama], cwd=str(ruta))
    _run_git(["remote", "set-url", "origin", cuenta["repo_url"]], cwd=str(ruta))
    return {"ok": ok, "detalle": "actualizado" if ok else salida}


def _leer_archivo(cuenta: dict[str, Any], archivo: str) -> dict[str, Any]:
    ruta_archivo = Path(cuenta["ruta_local"]) / archivo
    if not ruta_archivo.exists():
        return {"ok": False, "error": f"no existe {archivo} en el repo"}
    return {"ok": True, "contenido": ruta_archivo.read_text(encoding="utf-8")}


def _editar_archivo(cuenta: dict[str, Any], archivo: str, contenido_nuevo: str, buscar: str, reemplazar_por: str) -> dict[str, Any]:
    ruta_archivo = Path(cuenta["ruta_local"]) / archivo
    if not ruta_archivo.exists() and not contenido_nuevo:
        return {"ok": False, "error": f"no existe {archivo} en el repo"}

    if contenido_nuevo:
        ruta_archivo.parent.mkdir(parents=True, exist_ok=True)
        ruta_archivo.write_text(contenido_nuevo, encoding="utf-8")
        return {"ok": True, "detalle": f"{archivo} reemplazado por completo"}

    if buscar:
        texto = ruta_archivo.read_text(encoding="utf-8")
        if buscar not in texto:
            return {"ok": False, "error": f"no se encontró el texto a reemplazar en {archivo}"}
        ruta_archivo.write_text(texto.replace(buscar, reemplazar_por), encoding="utf-8")
        return {"ok": True, "detalle": f"reemplazo hecho en {archivo}"}

    return {"ok": False, "error": "especifica contenido_nuevo o buscar/reemplazar_por"}


def _commit_push(cuenta: dict[str, Any], mensaje_commit: str) -> dict[str, Any]:
    ruta = str(Path(cuenta["ruta_local"]))
    rama = cuenta.get("rama", "main")
    mensaje = mensaje_commit or "Actualización vía Imrryr OS"

    _run_git(["add", "-A"], cwd=ruta)
    ok_commit, salida_commit = _run_git(["commit", "-m", mensaje], cwd=ruta)
    if not ok_commit and "nothing to commit" not in salida_commit.lower():
        return {"ok": False, "error": salida_commit}

    url_auth = _url_autenticada(cuenta["repo_url"], cuenta.get("token", ""))
    _run_git(["remote", "set-url", "origin", url_auth], cwd=ruta)
    ok_push, salida_push = _run_git(["push", "origin", rama], cwd=ruta)
    _run_git(["remote", "set-url", "origin", cuenta["repo_url"]], cwd=ruta)
    if not ok_push:
        return {"ok": False, "error": salida_push}

    ok_hash, commit_hash = _run_git(["rev-parse", "HEAD"], cwd=ruta)
    return {"ok": True, "commit_hash": commit_hash if ok_hash else "", "mensaje": mensaje}


def repo_web(
    cuenta_id: str = "",
    accion: str = "",
    archivo: str = "",
    contenido_nuevo: str = "",
    buscar: str = "",
    reemplazar_por: str = "",
    mensaje_commit: str = "",
) -> dict:
    """Punto de entrada MCP (nombre = nombre de la skill, ver mcp_server/skills_server.py).
    accion: clonar_o_actualizar | leer_archivo | editar_archivo | commit_push"""
    cuenta = _cuenta(cuenta_id)
    if not cuenta:
        return {"ok": False, "error": "no hay cuenta de GitHub configurada (ver Ajustes > GitHub)"}

    if accion == "clonar_o_actualizar":
        return _clonar_o_actualizar(cuenta)
    if accion == "leer_archivo":
        return _leer_archivo(cuenta, archivo)
    if accion == "editar_archivo":
        return _editar_archivo(cuenta, archivo, contenido_nuevo, buscar, reemplazar_por)
    if accion == "commit_push":
        return _commit_push(cuenta, mensaje_commit)
    return {"ok": False, "error": f"acción desconocida: {accion}"}


def main() -> int:
    ap = argparse.ArgumentParser(description="Administra el repo de GitHub del sitio web")
    ap.add_argument("--cuenta", type=str, default="", dest="cuenta_id")
    ap.add_argument("--accion", type=str, required=True)
    ap.add_argument("--archivo", type=str, default="")
    ap.add_argument("--contenido-nuevo", type=str, default="", dest="contenido_nuevo")
    ap.add_argument("--buscar", type=str, default="")
    ap.add_argument("--reemplazar-por", type=str, default="", dest="reemplazar_por")
    ap.add_argument("--mensaje", type=str, default="", dest="mensaje_commit")
    args = ap.parse_args()

    resultado = repo_web(
        cuenta_id=args.cuenta_id, accion=args.accion, archivo=args.archivo,
        contenido_nuevo=args.contenido_nuevo, buscar=args.buscar,
        reemplazar_por=args.reemplazar_por, mensaje_commit=args.mensaje_commit,
    )
    print(resultado)
    return 0 if resultado.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
