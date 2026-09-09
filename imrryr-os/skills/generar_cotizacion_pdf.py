#!/usr/bin/env python3
"""
generar_cotizacion_pdf.py — Skill: Generación de Cotizaciones y Propuestas en PDF
====================================================================================
Usada por el Agente Comercial (CRM) para compilar presupuestos formales y cotizaciones
con diseño sobrio profesional a partir de los requerimientos de clientes y datos de
proyectos previos recuperados de la memoria de Imrryr OS.
"""
from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
VAULT_DIR = ROOT / "vault" / "cotizaciones"


def _slug(texto: str) -> str:
    s = re.sub(r"[^\w\s-]", "", texto.lower()).strip()
    return re.sub(r"[-\s]+", "_", s)[:30]


def generar_cotizacion_pdf(
    cliente_nombre: str,
    proyecto_titulo: str,
    items: list[dict[str, Any]] | str,
    cliente_email: str = "",
    validez_dias: int = 30,
    notas: str = "",
) -> dict[str, Any]:
    """Genera un archivo PDF formal de cotización comercial guardándolo en vault/cotizaciones/."""
    try:
        import fitz
    except ImportError:
        return {"ok": False, "error": "PyMuPDF (fitz) no está instalado en el entorno"}

    VAULT_DIR.mkdir(parents=True, exist_ok=True)

    # Parsear items si vienen como JSON string
    if isinstance(items, str):
        try:
            items_list = json.loads(items)
        except Exception:
            items_list = [{"descripcion": items, "cantidad": 1, "precio": 0}]
    else:
        items_list = items or []

    if not items_list:
        items_list = [{"descripcion": "Servicios profesionales", "cantidad": 1, "precio": 0}]

    fecha_hoy = datetime.date.today().isoformat()
    nombre_archivo = f"cotizacion_{_slug(cliente_nombre)}_{fecha_hoy}.pdf"
    ruta_salida = VAULT_DIR / nombre_archivo

    doc = fitz.open()
    page = doc.new_page(width=595, height=842)  # A4

    # Encabezado con barra de acento (paleta azul noche Imrryr)
    page.draw_rect(fitz.Rect(50, 45, 545, 48), fill=(0.12, 0.45, 0.72), color=None)

    page.insert_text(fitz.Point(50, 80), "IMRRYR OS — PROPUESTA & COTIZACIÓN", fontsize=15, fontname="helv", color=(0.1, 0.1, 0.15))
    page.insert_text(fitz.Point(50, 96), f"Fecha de emisión: {fecha_hoy}   |   Validez: {validez_dias} días", fontsize=9, fontname="helv", color=(0.4, 0.4, 0.4))

    # Recuadro Cliente y Proyecto
    page.draw_rect(fitz.Rect(50, 115, 545, 185), fill=(0.96, 0.97, 0.98), color=(0.85, 0.88, 0.9))
    page.insert_text(fitz.Point(65, 135), f"Cliente: {cliente_nombre}", fontsize=11, fontname="helv", color=(0.15, 0.15, 0.2))
    if cliente_email:
        page.insert_text(fitz.Point(65, 150), f"Email: {cliente_email}", fontsize=9, fontname="helv", color=(0.35, 0.35, 0.4))
    page.insert_text(fitz.Point(65, 170), f"Proyecto / Servicio: {proyecto_titulo}", fontsize=11, fontname="helv", color=(0.1, 0.35, 0.6))

    # Cabecera de la tabla
    y = 215
    page.draw_rect(fitz.Rect(50, y, 545, y + 22), fill=(0.9, 0.93, 0.96), color=None)
    page.insert_text(fitz.Point(60, y + 15), "Descripción del Item / Servicio", fontsize=10, fontname="helv", color=(0.2, 0.2, 0.25))
    page.insert_text(fitz.Point(360, y + 15), "Cant.", fontsize=10, fontname="helv", color=(0.2, 0.2, 0.25))
    page.insert_text(fitz.Point(420, y + 15), "P. Unitario", fontsize=10, fontname="helv", color=(0.2, 0.2, 0.25))
    page.insert_text(fitz.Point(495, y + 15), "Subtotal", fontsize=10, fontname="helv", color=(0.2, 0.2, 0.25))

    y += 28
    total_general = 0.0

    for item in items_list:
        desc = str(item.get("descripcion", "Item"))[:55]
        cant = float(item.get("cantidad", 1))
        precio = float(item.get("precio", item.get("precio_unitario", 0)))
        subtotal = cant * precio
        total_general += subtotal

        page.insert_text(fitz.Point(60, y + 12), desc, fontsize=9, fontname="helv", color=(0.2, 0.2, 0.2))
        page.insert_text(fitz.Point(365, y + 12), f"{cant:g}", fontsize=9, fontname="helv", color=(0.3, 0.3, 0.3))
        page.insert_text(fitz.Point(420, y + 12), f"${int(precio):,}".replace(",", "."), fontsize=9, fontname="helv", color=(0.3, 0.3, 0.3))
        page.insert_text(fitz.Point(495, y + 12), f"${int(subtotal):,}".replace(",", "."), fontsize=9, fontname="helv", color=(0.15, 0.15, 0.2))

        page.draw_rect(fitz.Rect(50, y + 18, 545, y + 19), fill=(0.92, 0.92, 0.92), color=None)
        y += 24

    # Línea de Total
    y += 10
    page.draw_rect(fitz.Rect(350, y, 545, y + 30), fill=(0.12, 0.45, 0.72), color=None)
    page.insert_text(fitz.Point(365, y + 20), "TOTAL ESTIMADO:", fontsize=11, fontname="helv", color=(1.0, 1.0, 1.0))
    total_formateado = f"${int(total_general):,}".replace(",", ".")
    page.insert_text(fitz.Point(465, y + 20), total_formateado, fontsize=12, fontname="helv", color=(1.0, 1.0, 1.0))

    # Notas al pie y condiciones
    y += 55
    if notas:
        page.insert_text(fitz.Point(50, y), "Condiciones y Observaciones:", fontsize=10, fontname="helv", color=(0.25, 0.25, 0.3))
        y += 16
        for linea in notas.split("\n")[:4]:
            page.insert_text(fitz.Point(50, y), f"• {linea.strip()}", fontsize=8, fontname="helv", color=(0.4, 0.4, 0.4))
            y += 14

    # Pie de página
    page.insert_text(fitz.Point(50, 800), "Documento generado por Imrryr OS — Núcleo Cognitivo Local-First.", fontsize=8, fontname="helv", color=(0.6, 0.6, 0.6))

    doc.save(str(ruta_salida))
    doc.close()

    try:
        ruta_pdf_str = str(ruta_salida.relative_to(ROOT))
    except ValueError:
        ruta_pdf_str = str(ruta_salida)

    return {
        "ok": True,
        "ruta_pdf": ruta_pdf_str,
        "archivo": nombre_archivo,
        "total": total_general,
        "total_formateado": total_formateado,
        "mensaje": f"Cotización generada con éxito para {cliente_nombre}: {total_formateado} (Guardada en vault/cotizaciones/{nombre_archivo})",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Genera cotizaciones en PDF")
    ap.add_argument("--cliente", type=str, required=True)
    ap.add_argument("--proyecto", type=str, required=True)
    ap.add_argument("--items", type=str, required=True, help="JSON array con [{descripcion, cantidad, precio}]")
    ap.add_argument("--email", type=str, default="")
    ap.add_argument("--validez", type=int, default=30)
    ap.add_argument("--notas", type=str, default="")
    args = ap.parse_args()

    res = generar_cotizacion_pdf(
        cliente_nombre=args.cliente,
        proyecto_titulo=args.proyecto,
        items=args.items,
        cliente_email=args.email,
        validez_dias=args.validez,
        notas=args.notas,
    )
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())