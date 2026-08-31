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

## [2026-08-30 20:26] Iteración #26
**Objetivo**: Suite de tests del manifiesto y wire Groq al gateway

**Entidades Modificadas**:
- skills/transcribir_audio.py -> transcribir_groq(), transcribir_con_motor(), _groq_api_key()
- .ai-os/modules/voice-bridge/voice_bridge.py -> transcribir() delega en skill compartida
- tests/test_ai_os.py -> 25 tests herméticos (sdd, fetch, lint, routing, versiones, sandbox)

**Diagnósticos de Validación**: LSP: 0 errores (ruff) | Tests: 79/79 OK (54 previos + 25 nuevos)

**Decisiones Técnicas (ADR)**: Wire sin tocar gateway/webhook_server.py: la skill transcribir_audio compartida ahora prueba Groq primero con fallback faster-whisper, heredando el cambio a WhatsApp y voice-bridge a la vez; transcribir() mantiene su firma (compatibilidad MCP); tests importan módulos .ai-os por ruta con importlib y parchean rutas a tmp_path

**Siguiente Paso Pendiente**: Rotación de API key antes de producción (decisión aplazada por el usuario); revisar breaking changes del scout con RFC

## [2026-08-30 22:17] Iteración #27
**Objetivo**: RFC de breaking changes aprobado y pins corregidos en requirements.txt

**Entidades Modificadas**:
- requirements.txt -> mcp>=1.2.0,<2, edge-tts>=7.2.8, psutil>=7.2.2,<8, pytest>=9.1.1,<10
- .ai-os/sandbox/rfc_breaking_changes_20260831.md -> RFC aprobado y aplicado

**Diagnósticos de Validación**: pip check: sin dependencias rotas | ruff: 0 errores | Tests: 79/79 OK | Smoke TTS real (edge-tts 7.2.8): OK 18KB mp3 | FastMCP baseline en mcp 1.28.1: OK

**Decisiones Técnicas (ADR)**: mcp NO se migra ahora: 2.x elimina FastMCP (skills_server.py:34 rompería); techo <2 protector porque el pin sin techo ya rompía installs frescos; edge-tts 7 obligatorio porque Microsoft rompio su API en dic 2025 y las 6.x ya no generan audio; psutil y pytest: codificar la realidad ya validada por la suite + techos <8/<10

**Siguiente Paso Pendiente**: Migración mcp 1.x a 2.x como tarea propia del PLAN; rotación de API key antes de producción
