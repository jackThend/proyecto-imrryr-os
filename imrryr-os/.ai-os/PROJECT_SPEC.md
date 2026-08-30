# AI-OS PROJECT SPEC — Imrryr OS

## Mapa Conceptual

**Imrryr OS** es un sistema operativo personal inteligente construido sobre Python, cuya interfaz principal es el dashboard web (`dashboard/`) y cuya capa de agentes autónomos vive en `skills/` (70 archivos MCP) y `agentes/`.

El OS no es un producto terminado: es un organismo en desarrollo donde cada skill, agente y router es una extensión viva. El manifiesto exige que toda evolución pase por especificación previa.

## Objetivos

1. **Soberanía de datos local-first**: toda la información del usuario (gastos, eventos, compras, audios) reside en SQLite local (`vault/sqlite/imrryr.db`). Cero dependencia de bases de datos cerradas.
2. **Navegación AST obligatoria**: todo inspección de código pasa por `codebase-memory` (Tree-sitter, grafos de llamadas, firmas de tipos). Prohibido inyectar repositorios enteros.
3. **Desarrollo guiado por especificación (SDD)**: ningún código de producción sin `PLAN.md` previo aprobado por el usuario.
4. **Cómputo determinista sobre inferencia**: linters, LSP, compiladores y scripts locales verifican con certeza absoluta lo que el LLM solo puede inferir.
5. **Memory persistente en archivos locales**: `.md`, `.json`, `.db`. El LLM procesa y razona; no almacena.

## Flujos UX Principales

### Flujo 1: Interacción por voz
- Usuario habla → Whisper Local transcribe → comando ejecutado → respuesta sintética hablada (edge-tts)
- Archivos clave: `skills/leer_en_voz.py`, `skills/tts_local.py`

### Flujo 2: Gestión financiera
- Usuario registra gasto → `skills/inyectar_gasto.py` → `finanzas/` → dashboard visualiza (`/api/finanzas`)
- Inclusión de datos históricos: `finanzas/importador_historico.py`

### Flujo 3: Correo y comunicación
- Gmail API → `skills/leer_gmail.py`, `skills/crear_borrador_respuesta.py`, `skills/archivar_correo.py`
- WhatsApp → `gateway/whatsapp_cli.py`, `skills/repo_web.py`

### Flujo 4: Agentes autónomos
- 6 agentes YAML (`agentes/`): financiero, investigador, creativo, CRM, guardia seguridad, build
- Cada agente tiene su skill MCP correspondiente
- Comunicación vía `gateway/webhook_server.py`

### Flujo 5: Dashboard operativo
- FastAPI (`dashboard/server.py`) con 20 rutas REST
- UI distribuida: CSS/JS separados en `dashboard/static/`
- Monitoreo de procesos, agenda, recordatorios, compras

### Flujo 6: Respaldos y persistencia
- Diario automático: `scripts/respaldo_db.py` + scheduler
- Retención 14 días, integridad SQLite verificable
- Repositorio `.gitignore` protege vault/

## Restricciones del Entorno

- **Lenguaje predominante**: Python 90 archivos
- **Framework web**: FastAPI
- **MCP**: protocolo estándar para skills (archivos `.mcp.json` + `.py`)
- **Shell**: PowerShell 5.1 (Windows) / Bash (CI Ubuntu)
- **CI/CD**: GitHub Actions con matrix Windows + Ubuntu
- **Linter**: Ruff (`ruff.toml`, errores reales únicamente)
- **Test framework**: pytest (`tests/test_dashboard_api.py`, 54 tests)
- **Packaging**: `scripts/package.py` genera zips distributivos

## Reglas de Gobernanza (Manifesto)

- [SÍ] Todo cambio de arquitectura actualiza `PLAN.md` antes de codificar
- [SÍ] Toda sesión registra en `LOGBOOK.md`
- [SÍ] Herramientas deterministas locales sobre inferencia del LLM
- [NO] Nombres de variables o dependencias sin consultar el grafo AST
- [NO] Modificaciones directas al núcleo sin sandbox previo
- [NO] Respuestas conversacionales extensas cuando el usuario solicita ejecución directa