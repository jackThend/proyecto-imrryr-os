"""API: Finanzas (gastos en SQLite) + importación histórica de correos bancarios."""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter
from fastapi.responses import JSONResponse, Response

from api import deps

router = APIRouter()

QUERY_BANCARIA_DEFECTO = "(compra OR cargo OR transacción OR transaccion OR pago OR abono) (banco OR tarjeta)"
CUENTA_GMAIL_FINANZAS = "gmail_principal"  # Financiero usa una única cuenta Gmail fija (config/gmail_credentials.json)


def _consultar_gastos(desde: str | None = None, hasta: str | None = None, limite: int = 20) -> dict:
    """desde/hasta son fechas ISO (YYYY-MM-DD), inclusivas. Sin ellas, trae todo.

    No hay "reportes congelados": los gastos ya quedan permanentes en SQLite
    apenas se insertan (vía inyectar_gasto), así que filtrar por rango aquí
    siempre es exacto — no hace falta recalcular nada con IA. Reusado tanto
    por /api/finanzas como por /api/finanzas/export."""
    if not deps.DB_PATH.exists():
        return {"gastos": [], "total": 0, "por_categoria": {}, "por_mes": {}, "anios_disponibles": []}

    conn = sqlite3.connect(str(deps.DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        condiciones = []
        params: list = []
        if desde:
            condiciones.append("fecha >= ?")
            params.append(desde)
        if hasta:
            condiciones.append("fecha <= ?")
            params.append(hasta)
        where = f"WHERE {' AND '.join(condiciones)}" if condiciones else ""

        cur = conn.execute(f"SELECT * FROM gastos {where} ORDER BY fecha DESC LIMIT ?", (*params, limite))
        gastos = [dict(row) for row in cur.fetchall()]

        cur = conn.execute(f"SELECT COALESCE(SUM(monto), 0) as total FROM gastos {where}", params)
        total = cur.fetchone()["total"]

        cur = conn.execute(
            f"SELECT categoria, COUNT(*) as count, SUM(monto) as subtotal FROM gastos {where} GROUP BY categoria",
            params,
        )
        por_categoria = {row["categoria"]: {"count": row["count"], "subtotal": row["subtotal"]} for row in cur.fetchall()}

        cur = conn.execute(
            f"SELECT substr(fecha,1,7) as mes, SUM(monto) as subtotal FROM gastos {where} GROUP BY mes ORDER BY mes",
            params,
        )
        por_mes = {row["mes"]: row["subtotal"] for row in cur.fetchall() if row["mes"]}

        cur = conn.execute("SELECT DISTINCT substr(fecha, 1, 4) as anio FROM gastos ORDER BY anio DESC")
        anios_disponibles = [row["anio"] for row in cur.fetchall() if row["anio"]]

        return {"gastos": gastos, "total": total, "por_categoria": por_categoria, "por_mes": por_mes, "anios_disponibles": anios_disponibles}
    finally:
        conn.close()


@router.get("/api/finanzas")
async def get_finanzas(limite: int = 20, desde: str | None = None, hasta: str | None = None):
    return _consultar_gastos(desde, hasta, limite)


@router.get("/api/finanzas/export")
async def exportar_finanzas(desde: str | None = None, hasta: str | None = None):
    import csv
    import io

    datos = _consultar_gastos(desde, hasta, limite=100000)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["fecha", "monto", "comercio", "categoria", "descripcion", "fuente"])
    for g in datos["gastos"]:
        writer.writerow([g["fecha"], g["monto"], g["comercio"], g["categoria"], g.get("descripcion", ""), g.get("fuente", "")])

    nombre = "gastos"
    if desde or hasta:
        nombre += f"_{desde or ''}_{hasta or ''}"
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{nombre}.csv"'},
    )


@router.put("/api/finanzas/gastos/{gasto_id}")
async def editar_gasto_endpoint(gasto_id: int, datos: dict):
    import inyectar_gasto
    return inyectar_gasto.actualizar_gasto(
        gasto_id,
        comercio=datos.get("comercio", ""),
        categoria=datos.get("categoria", ""),
        monto=datos.get("monto") or 0,
        descripcion=datos.get("descripcion", ""),
    )


@router.delete("/api/finanzas/gastos/{gasto_id}")
async def eliminar_gasto_endpoint(gasto_id: int):
    import inyectar_gasto
    return inyectar_gasto.eliminar_gasto(gasto_id)


# ---------------------------------------------------------------------------
# API: Importación histórica de correos bancarios (ver finanzas/importador_historico.py)
# ---------------------------------------------------------------------------
@router.post("/api/finanzas/importar/estimar")
async def estimar_importacion(datos: dict | None = None):
    from finanzas import importador_historico as importador
    query = (datos or {}).get("query") or QUERY_BANCARIA_DEFECTO
    return importador.estimar(query)


@router.post("/api/finanzas/importar/iniciar")
async def iniciar_importacion(datos: dict | None = None):
    from finanzas import importador_historico as importador
    query = (datos or {}).get("query") or QUERY_BANCARIA_DEFECTO
    return importador.iniciar(CUENTA_GMAIL_FINANZAS, query, tipo="historico")


@router.get("/api/finanzas/importar/estado")
async def estado_importacion():
    from finanzas import importador_historico as importador
    estado = importador.obtener_estado(tipo="historico", cuenta_correo_id=CUENTA_GMAIL_FINANZAS)
    return {"importacion": estado}


@router.post("/api/finanzas/importar/cancelar")
async def cancelar_importacion(datos: dict):
    from finanzas import importador_historico as importador
    importacion_id = datos.get("importacion_id")
    if not importacion_id:
        return JSONResponse({"ok": False, "error": "falta 'importacion_id'"}, status_code=400)
    return importador.cancelar(importacion_id)


@router.get("/api/finanzas/importar/informe")
async def informe_importacion():
    from finanzas import importador_historico as importador
    return {"bancos": importador.informe_por_banco()}
