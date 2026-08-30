# AGENTS.md — Imrryr OS (AI-OS Master Manifest)

## Protocolo de Operación

Este espacio de trabajo opera bajo el **AI-OS Master System Manifest**. Antes de tomar cualquier acción, consulta la estructura `.ai-os/`.

### Principios Fundamentales
1. **El Modelo es la CPU, no el Sistema**: el LLM procesa y razona; no almacena memoria volátil.
2. **La Ventana de Contexto es RAM**: recurso finito. Mantenerla limpia cada turno.
3. **El Harness Local es el Disco**: memoria persistente en `.md`, `.json`, SQLite. Cero bases de datos cerradas.
4. **Cómputo Determinista sobre Inferencia**: nunca uses razonamiento del LLM para lo que un compilador, linter, LSP o script local puede verificar.

### Navegación Estructural por Grafos (AST)
- **Prohibido** inyectar repositorios o archivos enteros para inspección de código.
- Usa `codebase-memory` MCP para consultar el AST (Tree-sitter), grafos de llamadas y firmas de tipos.
- Lee solo las líneas de las entidades afectadas una vez identificadas en el subgrafo.

### Progressive Tool Disclosure
- El contexto inicial expone solo el índice ligero de herramientas.
- La documentación técnica completa se inyecta solo al invocar activamente una herramienta o skill.

### Diagnósticos Locales (LSP / IDE Feedback Loop)
- No adivinar errores de sintaxis o variables inexistentes.
- Tras aplicar un cambio, consultar `ruff` y el LSP local. Si hay errores, inyectar solo el archivo, línea y mensaje exacto.

## SDD — Desarrollo Guiado por Especificación

**Ningún código de producción sin artefacto de especificación aprobado.**

Fases obligatorias:
1. **Constitución** — Reglas de gobernanza, calidad y restricciones. ✓ Completada (manifiesto).
2. **Especificación UX** (`PROJECT_SPEC.md`) — Definición funcional sin mencionar librerías.
3. **Plan Técnico** (`PLAN.md`) — Stack, contratos de datos, estructura, estrategia de APIs.
4. **Desglose de Tareas** — Unidades atómicas y comprobables.

## Ciclo de Ejecución (5-Phase Loop)

En cada interacción de modificación o desarrollo:
1. **PLAN** — Lee la tarea en `PLAN.md` o el requerimiento solicitado.
2. **FETCH** — Consulta el subgrafo AST para obtener dependencias y firmas exactas.
3. **EXECUTE** — Aplica el cambio mediante diffs atómicos y limpios.
4. **VALIDATE** — Ejecuta `ruff` y el LSP para confirmar 0 errores de sintaxis y tipos.
5. **LOG** — Actualiza `LOGBOOK.md` y `CURRENT_STATE.md` antes de cerrar el turno.

## Estructura del Workspace `.ai-os/`

| Archivo | Propósito |
|---|---|
| `.ai-os/config.json` | MCPs asignados, modelos por rol |
| `.ai-os/PROJECT_SPEC.md` | Mapa conceptual, objetivos, flujos UX |
| `.ai-os/PLAN.md` | Arquitectura técnica, stack, tareas |
| `.ai-os/CURRENT_STATE.md` | Estado vivo, variables clave, bloqueo activo |
| `.ai-os/LOGBOOK.md` | Bitácora histórica incremental |
| `.ai-os/skills/` | Skills forjadas y extensiones locales |
| `.ai-os/modules/` | Módulos del sistema |

### Formato de LOGBOOK.md
Cada iteración:
```
[YYYY-MM-DD HH:MM] Iteración #[ID]
Objetivo: Descripción concisa.
Entidades Modificadas: ruta/archivo.ext -> función().
Diagnósticos: LSP: 0 errores | Tests: OK
Decisiones Técnicas: Justificación de cambios.
Siguiente Paso: Próxima tarea según PLAN.md.
```

## Módulos del Sistema
- **`/init-project`** (`modules/init-project/`): Entrevista estructurada para nuevos proyectos. Genera PROJECT_SPEC.md y PLAN.md.
- **`/voice-bridge`** (`modules/voice-bridge/`): Comandos por voz vía Whisper, respuestas sintetizadas con edge-tts.
- **`/meta-harness`** (`modules/meta-harness/`): Trend scout, RFC generado, sandbox con aprobación humana requerida.

## Model Routing
- **Arquitecto/Planificador**: Modelos flagship → especificaciones y contratos.
- **Constructor/Ejecutor**: Modelos eficientes (DeepSeek, Gemini Flash, Haiku) → diffs y refactorización.
- **Streaming de Voz**: Ultra-baja latencia (Groq, Whisper Local) → transcripción y síntesis.
- **Auditor/Reviewer**: Razonamiento crítico aislado → validación de regresiones y auditoría de seguridad pre-producción.

## Reglas de Oro (LEDGER INMUTABLE)
- [SÍ] Todo cambio de arquitectura actualiza `PLAN.md` antes de codificar.
- [SÍ] Toda sesión concluye registrando en `LOGBOOK.md`.
- [SÍ] Prioriza herramientas deterministas locales sobre inferencia del LLM.
- [NO] No asumas nombres de variables ni dependencias: consúltalas en el grafo AST.
- [NO] No modifiques el núcleo sin validación previa en sandbox.
- [NO] No generes respuestas conversacionales extensas cuando el usuario solicita ejecución directa.

## Integración con el Proyecto Existente
- **Skills MCP**: `skills/*.py` + `skills/*.mcp.json` son las skills operativas del OS.
- **Dashboard**: FastAPI con 20 rutas en `dashboard/api/`.
- **Agentes**: 6 agentes YAML en `agentes/`.
- **Gateway**: Webhooks en `gateway/webhook_server.py`.
- **Tests**: `tests/test_dashboard_api.py` (54 tests).
- **CI**: GitHub Actions matrix Windows + Ubuntu.
- **Packaging**: `scripts/package.py` genera zips distributivos.
- **Backup**: `scripts/respaldo_db.py` + scheduler diario (14 días retención).