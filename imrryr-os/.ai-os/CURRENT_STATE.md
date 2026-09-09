# Estado Vivo — Imrryr OS

## Variables Clave
- **Proyecto**: imrryr-os
- **Última iteración**: 2026-09-08 — Transformación de Agente Build (OpenCode nativo + AST Graph MCP + Vista Código)
- **CI / Tests**: 87/87 pasando (100% verde)
- **Linter**: Ruff sin errores (0 advertencias)
- **Agente Programador**: Permisos completos nativos de OpenCode habilitados (bash, edit, read, glob, ast-graph). Vista dedicada en Dashboard.
- **Compilación Nativa**: Lanzadores ejecutables compilados con PyInstaller (Iniciar Imrryr OS.exe / Detener Imrryr OS.exe) + guion Inno Setup.
- **Servicios**: dashboard (:3000), litellm (:4000), opencode (:4040), gateway (:5050), whatsapp_local (:5051)
- **Zips Distributables**: regenerados y validados en entorno sandbox limpio (pyme + tech)

## Estado de Módulos del Manifiesto
- **config.json**: v1.1.0 con decisiones del usuario (Groq primario/local fallback, skills separadas, CLI, scout stack+agentes+MCPs, sandbox subdirectorio, modelos sugeridos) ✓
- **PROJECT_SPEC.md**: completo ✓
- **PLAN.md**: actualizado con progreso real ✓
- **LOGBOOK.md**: iteración #25 registrada ✓
- **voice-bridge**: FUNCIONAL — Groq (whisper-large-v3) primario, faster-whisper local fallback, edge-tts síntesis ✓
- **meta-harness**: FUNCIONAL — scout PyPI detectó 4 breaking changes (mcp 2.x, edge-tts 7.x, psutil 7.x, pytest 9.x), 11 agentes analizados, sandbox aislado verificado sin fuga de credenciales ✓
- **init-project**: CLI con entrevista estructurada ✓
- **Skills forjadas**: ast_navigation (protocolo FETCH + registro), sdd_protocol (enforcement SDD + LOGBOOK), deterministic_validate (ruff + pytest, diagnóstico exacto) ✓

## Bloqueo Activo
- **API key**: rotación pendiente antes de producción (decisión del usuario: aplazada)

## Hallazgos del Scout (meta-harness) — RESUELTOS 2026-08-31
RFC aprobado y aplicado: pins corregidos en requirements.txt.
- mcp: `>=1.2.0,<2` (techo protector; migración 2.x abierta en PLAN)
- edge-tts: `>=7.2.8` (6.x rota contra la API actual de Microsoft)
- psutil: `>=7.2.2,<8`
- pytest: `>=9.1.1,<10`
Validación: pip check limpio, ruff limpio, suite 79/79, smoke TTS real OK.

## Siguiente Paso Pendiente
Única tarea restante del PLAN: rotar API key antes de producción (aplazada por decisión del usuario).