# AGENTS.md — Imrryr OS

Guía para quien desarrolla este repositorio (persona o agente de código). Los agentes
de negocio (agenda, finanzas, reuniones...) **no** se rigen por este archivo: su
comportamiento y sus permisos salen de `agentes/*.yaml` y de `scripts/sync_agentes.py`.

## Qué es
Sistema multiagente local-first sobre OpenCode, con dashboard (FastAPI), skills MCP,
gateway de WhatsApp y una base SQLite única. Estado vivo y pendientes: `.ai-os/CURRENT_STATE.md`.

## Cómo se trabaja aquí
- **Verificar antes de dar algo por hecho.** Un test verde no basta para un cambio que toca
  IA, empaquetado o datos: probarlo de verdad (levantar servicios, conversar por chat,
  comprobar el resultado directo en SQLite) es el estándar de este proyecto.
- **Tests y lint**: `python -m pytest tests/ -q` y `python -m ruff check .` deben quedar limpios.
  Todo bug corregido lleva un test de regresión.
- **Secretos**: nunca en archivos versionados. Las claves viven en `config/.env` y
  `config/cuentas_*.json` (ignorados); `litellm_config.yaml` solo referencia `os.environ/...`.
- **Datos del usuario**: hacer `python scripts/respaldo_db.py` antes de cualquier prueba que escriba en la base,
  y limpiar los datos de prueba al terminar.
- **Commits**: uno por cambio con sentido, mensaje que explique el *porqué*.

## Piezas que sorprenden (léelas antes de tocar)
- **Ruta del modelo**: por defecto todo pasa por LiteLLM (alias `imrryr-activo`). La única excepción es
  OpenCode Zen gratis, que sale por el proveedor nativo de OpenCode. La decisión vive en
  `config/cuentas_ia.py::modelo_para_agente` y se consume vía `skills/ruta_modelo.py`
  (en el gateway `config` está sombreado por `gateway/config.py`, por eso el helper en `skills/`).
- **Permisos de agentes**: `scripts/sync_agentes.py` regenera el bloque `agent` de `config/opencode.json`
  en cada arranque. No editarlo a mano.
- **OpenCode aislado**: Imrryr arranca OpenCode con su propio HOME (`.opencode_home/`) para no heredar
  la configuración personal de quien desarrolla. Usa el binario de `bin/` (hoy ≥ 1.18).
- **Guardia de Seguridad**: los servicios base nunca se marcan como atascados ni se detienen.
- **Empaquetado**: las skills entran por lista blanca (`CORE_SKILLS` en `scripts/package.py`). Una skill
  compartida entre procesos que falte ahí rompe la app instalada aunque en desarrollo funcione.
- **Nueva skill**: `skills/x.py` con una función pública llamada igual que la skill + `skills/x.mcp.json`
  (el servidor MCP la descubre solo). Los helpers sin manifiesto (`errores_ia`, `uso_ia`, `ruta_modelo`) no son skills.

## `.ai-os/`
Contiene módulos con código y tests propios (`voice-bridge`, `meta-harness`, `init-project`, skills forjadas),
más `CURRENT_STATE.md` (lo muestra el dashboard). `PROJECT_SPEC.md`, `PLAN.md` y `LOGBOOK.md` son
histórico del proceso anterior (especificación primero + bitácora por sesión): ya no son obligatorios.
Si una decisión de arquitectura merece constancia, se puede añadir con `python .ai-os/skills/sdd_protocol.py`;
el registro cotidiano es `git log`.
