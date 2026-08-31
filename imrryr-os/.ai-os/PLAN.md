# AI-OS PLAN — Imrryr OS

## Arquitectura Técnica

### Stack Tecnológico
| Componente | Tecnología | Ubicación |
|---|---|---|
| Lenguaje | Python 3.11+ | `.venv/` |
| Framework web | FastAPI | `dashboard/server.py` |
| API protocolo | MCP | `skills/*.mcp.json` + `.py` |
| Base de datos | SQLite | `vault/sqlite/imrryr.db` |
| Embeddings/vectorial | ChromaDB | `vault/chroma/` |
| Transcripción voz | Whisper Local / faster-whisper | `skills/transcribir_audio.py` |
| Síntesis voz | edge-tts | `skills/tts_local.py` |
| Correo | Google API + google-auth | `skills/leer_gmail.py` |
| Linter | Ruff | `ruff.toml` |
| Tests | pytest | `tests/` |
| Packaging | scripts/package.py | `dist/` |
| CI | GitHub Actions | `.github/workflows/ci.yml` |
| Memoria AST | codebase-memory MCP | index 2120 nodos, 6544 aristas |

### Estructura de Carpetas
```
imrryr-os/
├── .ai-os/                  # Workspace del AI-OS (manifiesto)
│   ├── config.json          # MCPs, modelos, reglas de contexto
│   ├── PROJECT_SPEC.md      # Mapa conceptual y flujos UX
│   ├── PLAN.md              # Este archivo
│   ├── CURRENT_STATE.md     # Estado vivo
│   ├── LOGBOOK.md           # Bitácora histórica
│   ├── skills/              # Skills forjados por el AI-OS
│   └── modules/
│       ├── init-project/    # Asistente de inicio
│       ├── voice-bridge/    # Puente de voz
│       └── meta-harness/    # Scout auto-evolución
├── agentes/                 # Agentes YAML (6)
├── config/                  # Configuración (.env, defaults, opencode.json)
├── dashboard/               # Dashboard web (FastAPI + UI)
│   ├── api/                 # 12 routers, 59 endpoints
│   ├── static/              # CSS/JS extraídos
│   └── server.py            # Entry point
├── gateway/                 # Webhook server (WhatsApp, local, simular)
├── skills/                  # 70 skills MCP originales
├── scripts/                 # Utilidades (startup, package, respaldo, etc.)
├── finanzas/                # Módulo financiero
├── vault/                   # Datos persistentes (gitignored)
│   ├── sqlite/              # Base de datos principal
│   ├── backups/             # Respaldos diarios (14 días retención)
│   └── chroma/              # Embeddings vectoriales
├── tests/                   # 54 tests pytest
├── docs/                    # Documentación
└── profiles/                # Perfiles de empaquetado (pyme, tech)
```

### Contratos de Datos
- **Gastos**: tabla en `vault/sqlite/imrryr.db`, acceso vía `finanzas/`
- **Eventos**: agenda con feriados locales, `skills/agenda.py`
- **Compras**: seguimiento con digest automático, `skills/gestionar_seguimiento_compras.py`
- **Oportunidades/Crm**: `skills/guardar_oportunidad.py`, `skills/cambiar_estado_oportunidad.py`
- **Semillas**: conocimiento base en `semillas/` y `skills/`

### Estrategia de APIs
- **Dashboard**: REST FastAPI con 20 rutas (`/api/finanzas`, `/api/chat`, `/api/gateway/*`)
- **Skills MCP**: protocolo stdio JSON-RPC, archivos `.mcp.json` + implementación `.py`
- **Gateway webhooks**: POST `/webhook/whatsapp`, `/webhook/local`, `/webhook/simular`
- **CORS**: restringido a `localhost:3000`
- **Timeout**: `IMRRYR_CHAT_TIMEOUT_SECONDS` (default 300)

### Estrategia de Tests
- 54 tests hermeticos con `TestClient` (`tests/test_dashboard_api.py`)
- Cobertura: rutas, widgets, estado, validación, endpoints hermeticos, CSS/JS delivery
- CI paralelo: Windows + Ubuntu
- Lint previo obligatorio

### Fases SDD Obligatorias
1. **Constitución** — Ya completada (manifiesto, config.json)
2. **Especificación UX** — `PROJECT_SPEC.md` actualizado
3. **Plan Técnico** — Este archivo
4. **Desglose de Tareas** — Cada iteración registra en `LOGBOOK.md`

## Tareas Pendientes (Desglose)

- [x] Indexar imrryr-os en codebase-memory (AST)
- [x] Crear estructura `.ai-os/`
- [x] Crear `config.json` con MCPs y routing de modelos
- [x] Crear `PROJECT_SPEC.md`
- [x] Crear `PLAN.md`
- [x] Crear `CURRENT_STATE.md`
- [x] Crear `LOGBOOK.md`
- [x] Forjar skills adicionales en `.ai-os/skills/` (ast_navigation, sdd_protocol, deterministic_validate)
- [x] Implementar módulo `voice-bridge` (Groq primario + faster-whisper fallback)
- [x] Implementar módulo `meta-harness` (scout PyPI/agentes/MCPs + sandbox aislado)
- [x] Crear `AGENTS.md` integrando el manifiesto
- [ ] Implementar suite de tests para los módulos del manifiesto
- [ ] Wire del voice-bridge al gateway (entrada de audio por WhatsApp)
- [ ] Rotar API key antes de producción
- [ ] Verificación final de integridad