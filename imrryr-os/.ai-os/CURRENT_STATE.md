# Estado Vivo — Imrryr OS

## Variables Clave
- **Proyecto**: imrryr-os
- **Última iteración**: 2026-08-31 — migración mcp 2.x completada con smoke real
- **CI**: ambos OS en verde (Windows + Ubuntu)
- **Tests**: 80/80 pasando (25 del manifiesto + 1 regresión MCP + 54 previos)
- **Linter**: Ruff sin errores (incluye `.ai-os/`)
- **mcp**: 2.1.1 instalado y verificado end-to-end (stdio: initialize, tools/list 38, tools/call)
- **GROQ_API_KEY**: presente en config/.env — transcripción Groq activa en WhatsApp y voice-bridge

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
Migración mcp 2.x (FastMCP → MCPServer) y rotación de API key antes de producción (aplazada por el usuario).