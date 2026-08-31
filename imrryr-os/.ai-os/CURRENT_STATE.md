# Estado Vivo — Imrryr OS

## Variables Clave
- **Proyecto**: imrryr-os
- **Última iteración**: 2026-08-30 — módulos del manifiesto funcionales
- **CI**: ambos OS en verde (Windows + Ubuntu)
- **Tests**: 54/54 pasando
- **Linter**: Ruff sin errores (incluye `.ai-os/`)
- **Codebase-memory**: indexado, 2120 nodos, 6544 aristas
- **GROQ_API_KEY**: presente en config/.env — voice-bridge en modo Groq activo

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

## Hallazgos del Scout (meta-harness, 2026-08-30)
Breaking changes mayores pendientes de sandbox+changelog:
- mcp >=1.2.0 → 2.1.1 (impacta mcp_server/skills_server.py)
- edge-tts >=6.1.0 → 7.2.8 (impacta skills/tts_local.py)
- psutil >=6.0.0 → 7.2.2 (impacta guardia de seguridad)
- pytest >=8.0.0 → 9.1.1 (impacta CI)
Ninguno actualizado: requieren RFC aprobado primero.

## Siguiente Paso Pendiente
Suite de tests para los módulos `.ai-os/` y wire del voice-bridge al gateway.