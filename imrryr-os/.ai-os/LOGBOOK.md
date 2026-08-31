# Bitácora Incremental — Imrryr OS

## [2026-08-26 23:58] Iteración #24
**Objetivo**: Configurar Dependabot para Python, npm y GitHub Actions en el proyecto imrryr-os.

**Entidades Modificadas**:
- `.github/dependabot.yml` -> nuevo archivo de configuración Dependabot
- `.ai-os/config.json` -> actualizado con versión del manifiesto y MCPs

**Diagnósticos de Validación**:
- LSP: 0 errores
- Tests: 54/54 OK
- CI Windows: ✓
- CI Ubuntu: ✓
- Integridad SQLite: ok

**Decisiones Técnicas (ADR)**:
- Dependabot configurado con intervalos semanales (pip, npm) y mensuales (GitHub Actions) para minimizar churn de PRs
- Límite de PRs abiertos: 5 para pip/npm, 3 para GitHub Actions

**Siguiente Paso Pendiente**: Implementar módulos init-project, voice-bridge y meta-harness del manifiesto AI-OS. Crear AGENTS.md que wiree el manifiesto al proyecto.
## [2026-08-30 20:07] Iteración #25
**Objetivo**: Implementar módulos funcionales del manifiesto AI-OS

**Entidades Modificadas**:
- .ai-os/config.json -> model_routing/skills_layers/sandbox
- .ai-os/modules/voice-bridge/voice_bridge.py -> transcribir_groq(), transcribir_local(), sintetizar(), turno_completo()
- .ai-os/modules/meta-harness/meta_harness.py -> scout_stack(), scout_patrones_agentes(), sandbox(), auto_evolve()
- .ai-os/skills/ast_navigation.py -> registrar_consulta(), PATRONES
- .ai-os/skills/sdd_protocol.py -> verificar_spec(), registrar_iteracion(), siguiente_tarea()
- .ai-os/skills/deterministic_validate.py -> lint(), tests(), validar()

**Diagnósticos de Validación**: LSP: 0 errores (ruff) | Tests: 54/54 OK | Sandbox: aislado sin fuga de credenciales

**Decisiones Técnicas (ADR)**: Groq primario con fallback local (decisión usuario); skills forjadas separadas de skills MCP operativas; scout determinista vía PyPI JSON API (cómputo determinista sobre inferencia); sandbox con env mínimo sin IMRRYR_/GROQ_/OPENAI_ vars

**Siguiente Paso Pendiente**: Suite de tests para módulos .ai-os/ y wire voice-bridge al gateway
