#!/usr/bin/env python3
"""
redes_sociales.py — Skill: Publica en Instagram/Facebook vía Meta Graph API
===============================================================================
Usa la cuenta social configurada en Ajustes (ver config/cuentas_social.py) —
nunca credenciales hardcodeadas en .env, para que cualquier instalación
conecte su propia app de Meta.

OJO — limitaciones reales de la API, no de este código:
  - Instagram Content Publishing API exige que la imagen sea accesible por una
    URL pública (parámetro image_url) — no admite subir un archivo local en
    crudo. Si `media_ruta` no empieza con http(s)://, publicar en Instagram
    falla con un error explicativo (no silencioso).
  - Instagram no admite post de solo texto (siempre necesita imagen/video).
  - Facebook sí admite tanto solo-texto (POST /{page_id}/feed) como imagen
    subida en crudo desde un archivo local (POST /{page_id}/photos, campo
    'source') o por URL (campo 'url').
  - Publicar contra cuentas que no son admin/tester de la app de Meta requiere
    que esa app haya pasado App Review para pages_manage_posts /
    instagram_content_publish — trámite externo ante Meta, no resoluble acá.

`programar` es el único punto donde puede haber existido una llamada previa a
la IA (para redactar el contenido) — la publicación en sí, al llegar la hora,
la hace `publicar_posts_programados.py` sin volver a consultar al modelo.

Uso:
    python skills/redes_sociales.py --cuenta mi_pagina --accion publicar_ahora --contenido "Hola!"
"""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "vault" / "sqlite" / "imrryr.db"
GRAPH_BASE = "https://graph.facebook.com/v20.0"


def log(msg: str) -> None:
    print(f"[redes_sociales] {msg}", flush=True)


def _cuenta(cuenta_id: str) -> dict[str, Any] | None:
    from config import cuentas_social

    if cuenta_id:
        return cuentas_social.obtener_cuenta(cuenta_id)
    for c in cuentas_social.listar_cuentas():
        if c.get("activa"):
            return c
    return None


def _publicar_facebook(cuenta: dict[str, Any], contenido: str, media_ruta: str) -> dict[str, Any]:
    page_id = cuenta.get("page_id")
    token = cuenta.get("access_token")
    try:
        if media_ruta:
            datos = {"caption": contenido, "access_token": token}
            if media_ruta.startswith(("http://", "https://")):
                datos["url"] = media_ruta
                r = httpx.post(f"{GRAPH_BASE}/{page_id}/photos", data=datos, timeout=30)
            else:
                with open(media_ruta, "rb") as f:
                    r = httpx.post(f"{GRAPH_BASE}/{page_id}/photos", data=datos, files={"source": f}, timeout=30)
        else:
            r = httpx.post(f"{GRAPH_BASE}/{page_id}/feed", data={"message": contenido, "access_token": token}, timeout=30)
        cuerpo = r.json()
        if r.status_code >= 400:
            return {"ok": False, "error": cuerpo.get("error", {}).get("message", str(cuerpo))}
        return {"ok": True, "post_id": cuerpo.get("id", "")}
    except (httpx.HTTPError, OSError) as e:
        return {"ok": False, "error": str(e)}


def _publicar_instagram(cuenta: dict[str, Any], contenido: str, media_ruta: str) -> dict[str, Any]:
    ig_id = cuenta.get("ig_business_id")
    token = cuenta.get("access_token")
    if not ig_id:
        return {"ok": False, "error": "esta cuenta no tiene ig_business_id configurado"}
    if not media_ruta.startswith(("http://", "https://")):
        return {"ok": False, "error": "Instagram exige una imagen en una URL pública (image_url) — no admite un archivo local ni post de solo texto"}
    try:
        r1 = httpx.post(
            f"{GRAPH_BASE}/{ig_id}/media",
            data={"image_url": media_ruta, "caption": contenido, "access_token": token},
            timeout=30,
        )
        cuerpo1 = r1.json()
        if r1.status_code >= 400:
            return {"ok": False, "error": cuerpo1.get("error", {}).get("message", str(cuerpo1))}
        container_id = cuerpo1.get("id")

        r2 = httpx.post(
            f"{GRAPH_BASE}/{ig_id}/media_publish",
            data={"creation_id": container_id, "access_token": token},
            timeout=30,
        )
        cuerpo2 = r2.json()
        if r2.status_code >= 400:
            return {"ok": False, "error": cuerpo2.get("error", {}).get("message", str(cuerpo2))}
        return {"ok": True, "post_id": cuerpo2.get("id", "")}
    except (httpx.HTTPError, OSError) as e:
        return {"ok": False, "error": str(e)}


def _publicar_graph_api(cuenta: dict[str, Any], contenido: str, media_ruta: str, plataformas: str) -> dict[str, Any]:
    """Publica en cada plataforma pedida; el fallo de una no impide el intento en las demás.
    Reusada tal cual por publicar_posts_programados.py (el scheduler)."""
    resultados: dict[str, Any] = {}
    for plataforma in [p.strip() for p in plataformas.split(",") if p.strip()]:
        if plataforma == "facebook":
            resultados["facebook"] = _publicar_facebook(cuenta, contenido, media_ruta)
        elif plataforma == "instagram":
            resultados["instagram"] = _publicar_instagram(cuenta, contenido, media_ruta)
        else:
            resultados[plataforma] = {"ok": False, "error": f"plataforma no soportada: {plataforma}"}
    return resultados


def _programar(cuenta_id: str, contenido: str, media_ruta: str, plataformas: str, programado_at: str) -> dict[str, Any]:
    if not programado_at:
        return {"ok": False, "error": "falta programado_at (ISO 8601)"}
    conn = sqlite3.connect(str(DB_PATH))
    try:
        cur = conn.execute(
            "INSERT INTO posts_programados (contenido, media_ruta, plataformas, programado_at) VALUES (?, ?, ?, ?)",
            (contenido, media_ruta, plataformas, programado_at),
        )
        conn.commit()
        log(f"Post programado #{cur.lastrowid} para {programado_at}")
        return {"ok": True, "id": cur.lastrowid}
    finally:
        conn.close()


def redes_sociales(
    cuenta_id: str = "",
    accion: str = "",
    contenido: str = "",
    media_ruta: str = "",
    plataformas: str = "instagram,facebook",
    programado_at: str = "",
) -> dict:
    """Punto de entrada MCP. accion: publicar_ahora | programar"""
    if accion == "programar":
        return _programar(cuenta_id, contenido, media_ruta, plataformas, programado_at)

    if accion == "publicar_ahora":
        cuenta = _cuenta(cuenta_id)
        if not cuenta:
            return {"ok": False, "error": "no hay cuenta social configurada (ver Ajustes > Redes sociales)"}
        return _publicar_graph_api(cuenta, contenido, media_ruta, plataformas)

    return {"ok": False, "error": f"acción desconocida: {accion}"}


def main() -> int:
    ap = argparse.ArgumentParser(description="Publica en Instagram/Facebook")
    ap.add_argument("--cuenta", type=str, default="", dest="cuenta_id")
    ap.add_argument("--accion", type=str, required=True)
    ap.add_argument("--contenido", type=str, default="")
    ap.add_argument("--media", type=str, default="", dest="media_ruta")
    ap.add_argument("--plataformas", type=str, default="instagram,facebook")
    ap.add_argument("--programado-at", type=str, default="", dest="programado_at")
    args = ap.parse_args()

    resultado = redes_sociales(
        cuenta_id=args.cuenta_id, accion=args.accion, contenido=args.contenido,
        media_ruta=args.media_ruta, plataformas=args.plataformas, programado_at=args.programado_at,
    )
    print(resultado)
    return 0 if resultado.get("ok", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
