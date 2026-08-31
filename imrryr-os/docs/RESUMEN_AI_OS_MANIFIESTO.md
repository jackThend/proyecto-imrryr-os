# Resumen de Implementación — AI-OS Master System Manifest

**Ciclo**: 2026-08-30 → 2026-08-31 · **Commits**: `0210605`, `b5b2f84`, `198af00`, `4a77bf8`
**Estado final**: 79/79 tests · ruff limpio · CI verde (Windows + Ubuntu) · RFC de dependencias aplicado

---

## Qué se implementó

### 1. Estructura de memoria viva `.ai-os/` (commit `0210605`)
El manifiesto AI-OS completo, con el workspace de memoria persistente en
archivos locales abiertos (sin bases de datos cerradas):

| Archivo | Propósito |
|---|---|
| `.ai-os/config.json` (v1.1.0) | MCPs, routing de modelos por rol, reglas de contexto, capas de skills, sandbox |
| `.ai-os/PROJECT_SPEC.md` | Mapa conceptual, 6 flujos UX, restricciones local-first |
| `.ai-os/PLAN.md` | Stack, contratos de datos, desglose de tareas con checkboxes |
| `.ai-os/CURRENT_STATE.md` | Estado vivo: variables clave y bloqueos |
| `.ai-os/LOGBOOK.md` | Bitácora incremental (formato canónico del manifiesto) |
| `AGENTS.md` | Wire del manifiesto: 5-phase loop, SDD, reglas de oro |
| `.codebase-memory/` | Índice AST commitado (2120 nodos, 6544 aristas) |

### 2. Módulos funcionales (commit `b5b2f84`)
- **voice-bridge** (`.ai-os/modules/voice-bridge/`): enrutamiento de
  comandos de voz del OS y ciclo completo de turno.
- **meta-harness** (`.ai-os/modules/meta-harness/`): scout determinista
  (PyPI JSON API — breaking changes del stack), análisis de patrones de
  agentes YAML, repos MCP, y sandbox aislado en `.ai-os/sandbox/` con
  variables de entorno mínimas (sin credenciales IMRRYR_/GROQ_/OPENAI_).
- **init-project** (`.ai-os/modules/init-project/`): entrevista
  estructurada CLI que genera PROJECT_SPEC.md y PLAN.md.

### 3. Skills forjadas (capa de gobierno del AI-OS)
En `.ai-os/skills/`, separadas de los 70 skills MCP operativos de `skills/`:
- `ast_navigation.py` — protocolo FETCH: índice ligero de patrones del
  MCP codebase-memory + registro de entidades consultadas por tarea.
- `sdd_protocol.py` — enforcement del SDD: verificación de artefactos,
  desglose de tareas, registro de iteraciones en LOGBOOK (autousada).
- `deterministic_validate.py` — fase VALIDATE: ruff + pytest con
  diagnóstico exacto `archivo:línea: mensaje`, sin volcar salidas.

### 4. Voz: Groq con fallback local (commit `198af00`)
- Decisión del usuario: **Groq (whisper-large-v3) primario,
  faster-whisper local de respaldo**, síntesis con edge-tts.
- El wire al gateway de WhatsApp se hizo **sin tocar
  `webhook_server.py`**: la skill compartida `skills/transcribir_audio.py`
  ahora prueba Groq primero y el gateway la hereda por composición.
- voice-bridge refactorizado para delegar en la misma skill (una sola
  ruta de transcripción en todo el OS, sin duplicación).

### 5. Tests del manifiesto (commit `198af00`)
`tests/test_ai_os.py`: 25 tests herméticos (sdd_protocol,
ast_navigation, deterministic_validate, voice_bridge, meta_harness y
la skill de transcripción). Suite total: **79 tests** (54 previos + 25).

### 6. RFC de breaking changes (commit `4a77bf8`)
Scout detectó 4 cambios de versión mayor. RFC con evidencia
determinista, aprobado por el usuario y aplicado a `requirements.txt`:

| Paquete | Antes | Ahora | Motivo |
|---|---|---|---|
| mcp | `>=1.2.0` | `>=1.2.0,<2` | Techo protector: 2.x elimina `FastMCP` y el pin sin techo ya rompía instalaciones frescas |
| edge-tts | `>=6.1.0` | `>=7.2.8` | Microsoft rompió su API (dic 2025); las 6.x ya no generan audio |
| psutil | `>=6.0.0` | `>=7.2.2,<8` | 7.x validado por la suite; techo por 8.0 en desarrollo |
| pytest | `>=8.0.0` | `>=9.1.1,<10` | 9.1.1 validada por 79/79 tests |

Validación: `pip check` limpio, smoke TTS real, baseline FastMCP OK.
Sin `pip install` necesario (el venv ya estaba en el estado objetivo).

---

## Decisiones técnicas clave (ADR)

1. **El modelo es la CPU, no el sistema** — toda memoria persiste en
   archivos locales (`.md`, `.json`, SQLite); cero dependencias cerradas.
2. **Cómputo determinista sobre inferencia** — el scout usa la API JSON
   de PyPI, no razonamiento del LLM; la validación es ruff + pytest.
3. **Groq primario con fallback local** — baja latencia sin perder el
   modo offline; clave en `config/.env` (`GROQ_API_KEY`).
4. **Skills separadas en dos capas** — `skills/` operativo (sirve al
   usuario) vs `.ai-os/skills/` forjadas (el AI-OS se gobierna a sí mismo).
5. **Wire por composición, no por modificación** — el gateway heredó
   Groq sin cambiar una línea de su código.
6. **Sandbox = subdirectorio aislado** — sin Docker: `.ai-os/sandbox/`
   con env mínimo cumple el manifiesto sin dependencias nuevas.

---

## Pendiente (documentado en `.ai-os/PLAN.md`)

- [ ] Migrar mcp 1.x → 2.x (`FastMCP` → `MCPServer` en
      `mcp_server/skills_server.py`, con smoke del servidor real).
- [ ] Rotar API key y eliminar cualquier rastro antes de producción
      (aplazada por decisión del usuario mientras dure el testing).
- [ ] Verificación final de integridad pre-producción.

## Cómo usar el manifiesto

- Cada sesión de desarrollo sigue el ciclo **PLAN → FETCH → EXECUTE →
  VALIDATE → LOG** (ver `AGENTS.md`).
- Cerrar turno: `python .ai-os/skills/sdd_protocol.py --log --objetivo "..." --entidades ...`
- Validar cambios: `python .ai-os/skills/deterministic_validate.py --archivos <arch>`
- Scout de dependencias: `python .ai-os/modules/meta-harness/meta_harness.py --scout`
- Comando por voz: `python .ai-os/modules/voice-bridge/voice_bridge.py --audio <archivo> --sin-voz`
