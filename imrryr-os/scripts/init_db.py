#!/usr/bin/env python3
"""
init_db.py — Inicializa la Memoria Relacional (SQLite)
=======================================================
Fase 2.3: Crea la base de datos SQLite con el esquema de Gastos.

Uso:
    python scripts/init_db.py
    python scripts/init_db.py --reset   # borra y recrea tablas
"""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_DIR = ROOT / "vault" / "sqlite"
DB_PATH = DB_DIR / "imrryr.db"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS gastos (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha           TEXT    NOT NULL,            -- ISO 8601: 2026-06-28
    monto           REAL    NOT NULL,
    comercio        TEXT    NOT NULL,
    categoria       TEXT    NOT NULL DEFAULT 'general',
    descripcion     TEXT,
    fuente          TEXT    DEFAULT 'manual',    -- manual, gmail, webhook
    fuente_id       TEXT,                        -- ID del correo/transacción de origen (evita duplicados al reprocesar)
    created_at      TEXT    DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS proyectos (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre            TEXT    NOT NULL UNIQUE,
    descripcion       TEXT,
    estado            TEXT    DEFAULT 'activo',     -- activo, pausado, completado
    tecnologias       TEXT,                         -- comma-separated
    semilla_origen_id INTEGER,                       -- de qué idea nació (trazabilidad)
    created_at        TEXT    DEFAULT (datetime('now')),
    updated_at        TEXT    DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS semillas (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    titulo             TEXT    NOT NULL,
    descripcion        TEXT,                         -- versión desarrollada/enriquecida
    contenido_original TEXT,                         -- lo que el usuario mandó tal cual (antes de desarrollarla)
    etiquetas          TEXT,                         -- comma-separated tags
    estado             TEXT    DEFAULT 'idea',        -- idea, desarrollada, proyecto, archivada
    proyecto_id        INTEGER,                       -- se llena cuando estado pasa a 'proyecto'
    fuente             TEXT    DEFAULT 'manual',      -- manual, whatsapp, web
    created_at         TEXT    DEFAULT (datetime('now')),
    updated_at         TEXT    DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS adjuntos_semilla (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    semilla_id   INTEGER NOT NULL,
    ruta_archivo TEXT    NOT NULL,
    tipo         TEXT    DEFAULT 'imagen',
    created_at   TEXT    DEFAULT (datetime('now')),
    FOREIGN KEY (semilla_id) REFERENCES semillas(id)
);

CREATE TABLE IF NOT EXISTS oportunidades_fondos (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    fuente          TEXT    NOT NULL,             -- sercotec, corfo, etc.
    hallazgo        TEXT    NOT NULL,
    monto_estimado  TEXT,
    fecha_cierre    TEXT,
    relevancia_nota TEXT,                         -- por qué le sirve o no al negocio (lo llena el agente)
    estado          TEXT    DEFAULT 'nueva',      -- nueva, revisada, descartada, postulada
    created_at      TEXT    DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS borradores_pendientes (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    cuenta_id           TEXT    NOT NULL,
    destinatario        TEXT    NOT NULL,
    asunto              TEXT,
    cuerpo              TEXT    NOT NULL,
    mensaje_id_original TEXT,                          -- a qué correo responde, si aplica
    estado              TEXT    DEFAULT 'pendiente',   -- pendiente, enviado, descartado
    created_at          TEXT    DEFAULT (datetime('now')),
    updated_at          TEXT    DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS importaciones (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo            TEXT    NOT NULL,                 -- historico, diario
    cuenta_correo_id TEXT   NOT NULL,
    estado          TEXT    DEFAULT 'pendiente',       -- pendiente, en_progreso, pausada_cuota, completada
    query_gmail     TEXT,
    cursor_pagina   TEXT,                              -- nextPageToken donde quedó (reanudación)
    marca_agua      TEXT,                              -- fecha del último correo procesado (sync diario)
    total_estimado  INTEGER DEFAULT 0,
    procesados      INTEGER DEFAULT 0,
    agregados       INTEGER DEFAULT 0,
    iniciado_at     TEXT    DEFAULT (datetime('now')),
    actualizado_at  TEXT    DEFAULT (datetime('now')),
    completado_at   TEXT
);

CREATE TABLE IF NOT EXISTS posts_programados (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    contenido       TEXT    NOT NULL,             -- texto del post
    media_ruta      TEXT,                         -- ruta local a imagen/video, o NULL si es solo texto
    plataformas     TEXT    NOT NULL,             -- comma-separated: instagram,facebook
    programado_at   TEXT    NOT NULL,             -- ISO 8601, cuándo debe publicarse
    estado          TEXT    DEFAULT 'pendiente',  -- pendiente, publicado, fallido, cancelado
    error_detalle   TEXT,                         -- si estado=fallido, por qué
    publicado_at    TEXT,
    created_at      TEXT    DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS productos_seguimiento (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    producto        TEXT    NOT NULL,             -- término de búsqueda, ej. "audífonos sony wh-1000xm5"
    precio_min      REAL,                         -- opcional, rango objetivo
    precio_max      REAL,
    tiendas         TEXT    NOT NULL DEFAULT 'mercadolibre,falabella,paris,ripley',  -- comma-separated
    activo          INTEGER DEFAULT 1,
    ultimo_chequeo  TEXT,                         -- ISO 8601, cuándo se revisó por última vez
    created_at      TEXT    DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS ofertas_encontradas (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    seguimiento_id        INTEGER NOT NULL,
    tienda                TEXT    NOT NULL,
    titulo                TEXT    NOT NULL,
    precio                REAL    NOT NULL,
    url                   TEXT    NOT NULL,
    encontrado_at         TEXT    DEFAULT (datetime('now')),
    FOREIGN KEY (seguimiento_id) REFERENCES productos_seguimiento(id)
);

CREATE TABLE IF NOT EXISTS eventos (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    titulo              TEXT    NOT NULL,
    descripcion         TEXT,
    fecha               TEXT    NOT NULL,           -- ISO 8601: 2026-07-09
    hora                TEXT    DEFAULT '09:00',
    duracion_min        INTEGER DEFAULT 60,
    todo_dia            INTEGER DEFAULT 0,
    ics_generado        TEXT,                        -- ruta al .ics si se exportó (opcional)
    estado              TEXT    DEFAULT 'activo',    -- activo, cancelado, realizado
    created_at          TEXT    DEFAULT (datetime('now')),
    updated_at          TEXT    DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS avisos_evento (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    evento_id       INTEGER NOT NULL,
    hora_aviso      TEXT    NOT NULL,             -- HH:MM, hora del día en que se envía el aviso
    disparado       INTEGER DEFAULT 0,
    FOREIGN KEY (evento_id) REFERENCES eventos(id)
);

CREATE TABLE IF NOT EXISTS pendientes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    texto       TEXT    NOT NULL,
    hecho       INTEGER DEFAULT 0,
    created_at  TEXT    DEFAULT (datetime('now'))
);

-- Registro de turnos de conversación con IA (Tanda X). Es un proxy del gasto
-- de cuota: un turno con herramientas puede costar varias llamadas reales a
-- la API del proveedor, así que el contador subestima — sirve para orientar
-- ("vas 15 de ~20 hoy"), no como medidor exacto.
CREATE TABLE IF NOT EXISTS uso_ia (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha            TEXT    NOT NULL,
    canal            TEXT    NOT NULL,
    agente           TEXT    DEFAULT '',
    proveedor        TEXT    DEFAULT '',
    modelo           TEXT    DEFAULT '',
    tokens_estimados INTEGER DEFAULT 0,
    latencia_ms      INTEGER DEFAULT 0,
    created_at       TEXT    DEFAULT (datetime('now'))
);

-- Persistencia del historial de chat por agente (evita pérdida de contexto al recargar F5)
CREATE TABLE IF NOT EXISTS sesiones_chat (
    id          TEXT PRIMARY KEY,
    agente      TEXT NOT NULL,
    titulo      TEXT,
    created_at  TEXT DEFAULT (datetime('now')),
    updated_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS mensajes_chat (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    sesion_id    TEXT,
    agente       TEXT NOT NULL,
    rol          TEXT NOT NULL,           -- user, assistant, system
    texto        TEXT NOT NULL,
    herramientas TEXT,                    -- comma-separated o lista de herramientas usadas
    created_at   TEXT DEFAULT (datetime('now'))
);

-- Memoria jerárquica de preferencias y hechos clave del usuario (estilo Mem0 / Letta)
CREATE TABLE IF NOT EXISTS memoria_usuario (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    categoria   TEXT NOT NULL,            -- perfil, preferencia, hecho, regla
    clave       TEXT NOT NULL UNIQUE,
    valor       TEXT NOT NULL,
    fuente      TEXT DEFAULT 'chat',
    updated_at  TEXT DEFAULT (datetime('now'))
);

-- Human-in-the-loop (HITL) para autorizaciones críticas de agentes
CREATE TABLE IF NOT EXISTS solicitudes_hitl (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    agente          TEXT NOT NULL,
    accion          TEXT NOT NULL,
    parametros      TEXT NOT NULL DEFAULT '{}',
    resumen_humano  TEXT NOT NULL,
    estado          TEXT DEFAULT 'pendiente', -- 'pendiente', 'aprobado', 'rechazado'
    creado_at       TEXT DEFAULT (datetime('now')),
    resuelto_at     TEXT
);

-- RAG Híbrido: tabla FTS5 de texto completo para búsqueda léxica BM25
CREATE VIRTUAL TABLE IF NOT EXISTS documentos_fts USING fts5(
    chunk_id UNINDEXED,
    archivo,
    fuente,
    texto
);

CREATE INDEX IF NOT EXISTS idx_gastos_fecha ON gastos(fecha);
CREATE INDEX IF NOT EXISTS idx_gastos_categoria ON gastos(categoria);
CREATE INDEX IF NOT EXISTS idx_proyectos_estado ON proyectos(estado);
CREATE INDEX IF NOT EXISTS idx_semillas_estado ON semillas(estado);
CREATE INDEX IF NOT EXISTS idx_oportunidades_estado ON oportunidades_fondos(estado);
CREATE INDEX IF NOT EXISTS idx_adjuntos_semilla_id ON adjuntos_semilla(semilla_id);
CREATE INDEX IF NOT EXISTS idx_borradores_estado ON borradores_pendientes(estado);
CREATE INDEX IF NOT EXISTS idx_importaciones_tipo_cuenta ON importaciones(tipo, cuenta_correo_id);
CREATE INDEX IF NOT EXISTS idx_posts_estado_fecha ON posts_programados(estado, programado_at);
CREATE INDEX IF NOT EXISTS idx_prodseg_activo ON productos_seguimiento(activo);
CREATE INDEX IF NOT EXISTS idx_ofertas_seguimiento ON ofertas_encontradas(seguimiento_id);
CREATE INDEX IF NOT EXISTS idx_eventos_fecha ON eventos(fecha);
CREATE INDEX IF NOT EXISTS idx_eventos_estado ON eventos(estado);
CREATE INDEX IF NOT EXISTS idx_avisos_evento_id ON avisos_evento(evento_id);
CREATE INDEX IF NOT EXISTS idx_avisos_disparado ON avisos_evento(disparado);
CREATE INDEX IF NOT EXISTS idx_pendientes_hecho ON pendientes(hecho);
CREATE INDEX IF NOT EXISTS idx_uso_ia_fecha ON uso_ia(fecha);
CREATE INDEX IF NOT EXISTS idx_mensajes_chat_agente ON mensajes_chat(agente);
CREATE INDEX IF NOT EXISTS idx_mensajes_chat_sesion ON mensajes_chat(sesion_id);
CREATE INDEX IF NOT EXISTS idx_memoria_categoria ON memoria_usuario(categoria);
CREATE INDEX IF NOT EXISTS idx_hitl_estado ON solicitudes_hitl(estado);
CREATE INDEX IF NOT EXISTS idx_hitl_agente ON solicitudes_hitl(agente);
"""


def log(msg: str) -> None:
    print(f"[db] {msg}", flush=True)


def _migrar_gastos_fuente_id(conn: sqlite3.Connection) -> None:
    """Agrega fuente_id a bases de datos creadas antes de esta columna existir."""
    columnas = [row[1] for row in conn.execute("PRAGMA table_info(gastos)").fetchall()]
    if "fuente_id" not in columnas:
        conn.execute("ALTER TABLE gastos ADD COLUMN fuente_id TEXT")
        log("Migración: columna fuente_id agregada a gastos")
    if "banco" not in columnas:
        conn.execute("ALTER TABLE gastos ADD COLUMN banco TEXT")
        log("Migración: columna banco agregada a gastos")
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_gastos_fuente_id ON gastos(fuente_id)")


def _migrar_semillas_ideas(conn: sqlite3.Connection) -> None:
    """Agrega las columnas del sistema de Ideas/Proyectos a bases creadas antes de que existieran."""
    columnas = [row[1] for row in conn.execute("PRAGMA table_info(semillas)").fetchall()]
    if "contenido_original" not in columnas:
        conn.execute("ALTER TABLE semillas ADD COLUMN contenido_original TEXT")
        log("Migración: columna contenido_original agregada a semillas")
    if "proyecto_id" not in columnas:
        conn.execute("ALTER TABLE semillas ADD COLUMN proyecto_id INTEGER")
        log("Migración: columna proyecto_id agregada a semillas")
    if "updated_at" not in columnas:
        conn.execute("ALTER TABLE semillas ADD COLUMN updated_at TEXT")
        log("Migración: columna updated_at agregada a semillas")

    columnas_proyectos = [row[1] for row in conn.execute("PRAGMA table_info(proyectos)").fetchall()]
    if "semilla_origen_id" not in columnas_proyectos:
        conn.execute("ALTER TABLE proyectos ADD COLUMN semilla_origen_id INTEGER")
        log("Migración: columna semilla_origen_id agregada a proyectos")


def _migrar_uso_ia(conn: sqlite3.Connection) -> None:
    """Agrega columnas de telemetría agéntica y presupuesto a uso_ia."""
    columnas = [row[1] for row in conn.execute("PRAGMA table_info(uso_ia)").fetchall()]
    if "proveedor" not in columnas:
        conn.execute("ALTER TABLE uso_ia ADD COLUMN proveedor TEXT DEFAULT ''")
        log("Migración: columna proveedor agregada a uso_ia")
    if "modelo" not in columnas:
        conn.execute("ALTER TABLE uso_ia ADD COLUMN modelo TEXT DEFAULT ''")
        log("Migración: columna modelo agregada a uso_ia")
    if "tokens_estimados" not in columnas:
        conn.execute("ALTER TABLE uso_ia ADD COLUMN tokens_estimados INTEGER DEFAULT 0")
        log("Migración: columna tokens_estimados agregada a uso_ia")
    if "latencia_ms" not in columnas:
        conn.execute("ALTER TABLE uso_ia ADD COLUMN latencia_ms INTEGER DEFAULT 0")
        log("Migración: columna latencia_ms agregada a uso_ia")


def main() -> int:
    ap = argparse.ArgumentParser(description="Inicializa la base de datos SQLite")
    ap.add_argument("--reset", action="store_true", help="Borrar y recrear tablas")
    args = ap.parse_args()

    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")

    if args.reset:
        conn.executescript(
            "DROP TABLE IF EXISTS gastos; DROP TABLE IF EXISTS proyectos; "
            "DROP TABLE IF EXISTS semillas; DROP TABLE IF EXISTS oportunidades_fondos; "
            "DROP TABLE IF EXISTS adjuntos_semilla; DROP TABLE IF EXISTS borradores_pendientes; "
            "DROP TABLE IF EXISTS importaciones; DROP TABLE IF EXISTS posts_programados; "
            "DROP TABLE IF EXISTS ofertas_encontradas; DROP TABLE IF EXISTS productos_seguimiento; "
            "DROP TABLE IF EXISTS avisos_evento; DROP TABLE IF EXISTS eventos; "
            "DROP TABLE IF EXISTS pendientes; DROP TABLE IF EXISTS uso_ia;"
        )
        log("Tablas eliminadas.")

    conn.executescript(SCHEMA_SQL)
    _migrar_gastos_fuente_id(conn)
    _migrar_semillas_ideas(conn)
    _migrar_uso_ia(conn)
    conn.commit()

    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
    tables = [row[0] for row in cur.fetchall()]
    log(f"BD inicializada: {DB_PATH}")
    log(f"Tablas: {', '.join(tables)}")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
