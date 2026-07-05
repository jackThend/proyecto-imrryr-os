# Informe de Entorno — Imrryr OS (Fase 1)

> Generado automáticamente por la subtarea **0.7** del plan atomizado.
> Fecha: 2026-06-22

## Resumen ejecutivo

El entorno del host cumple con los requisitos **mínimos** para ejecutar Fase 1 (Entorno Seguro y Motor Agnóstico). Faltan dos piezas críticas que se instalarán durante esta fase: **Bun** (requerido por OpenCode) y **Ollama** (opcional, solo si se quiere validar el modelo local Qwen).

> ⚠️ **Sin GPU NVIDIA detectada.** Por ello el modelo local **Qwen queda diferido**. La **conmutación agnóstica** del pilar «Neutralidad de Modelos» se validará con **dos modelos de nube** (`gemini-1.5-pro` + `gemini-1.5-flash`) en lugar de nube+local. Esto NO altera el mecanismo: LiteLLM enruta igual ambos casos.

## Inventario detectado

### ✓ Instalado

| Herramienta | Versión | Ruta / Notas |
|---|---|---|
| **Python (default)** | 3.14.0 | `C:\Python314\python.exe` — en PATH |
| Python 3.11 | 3.11 | `AppData\Local\Programs\Python\Python311\python.exe` — **se usará para el venv** (mayor estabilidad de wheels litellm/mcp) |
| Python 3.13 | 3.13 | `AppData\Local\Programs\Python\Python313\python.exe` |
| **Node.js** | v24.11.0 | `C:\Program Files\nodejs\node.exe` |
| **npm** | 11.0.0 | — |
| **Git** | 2.43.0 | `C:\Program Files\Git\...` |

### ✗ Faltante (a instalar en Fase 1)

| Herramienta | Crítico para Fase 1 | Acción planificada |
|---|---|---|
| **Bun** | **Sí** (OpenCode requiere Bun) | Tarea **1.1.2**: `powershell -c "irm bun.sh/install.ps1 \| iex"` |
| **gh CLI** | No (alternativa manual) | Fork manual: `git clone` + `git remote set-url origin <fork>` |
| **Ollama** | No (sin GPU) | Diferido. Qwen no se puede ejecutar. |
| **Docker Desktop** | No (Fase 4) | Fuera de alcance de Fase 1. |
| **GPU NVIDIA** | No | No detectada (`nvidia-smi` no existe). Modelos locales inviables. |

## Decisiones derivadas para el resto de Fase 1

1. **Venv con Python 3.11** (no 3.14): Python 3.14 es demasiado reciente y litellm/mcp/pydantic pueden no tener wheels compilados. Se invocará explícitamente: `py -3.11 -m venv .venv`.
2. **Conmutación agnóstica con 2 modelos de nube** en lugar de nube+local:
   - `gemini-pro` → `gemini/gemini-1.5-pro` (modelo «grande»)
   - `gemini-flash` → `gemini/gemini-1.5-flash` (modelo «ligero»)
   - El config de LiteLLM (`1.2.3`/`1.2.4`) y `opencode.json` (`1.2.8`) se ajustan en consecuencia. Qwen queda comentado y listo para activarse cuando exista GPU + Ollama.
3. **Fork de OpenCode sin gh CLI**: clonar `sst/opencode` y configurar el remote `origin` hacia el fork propio creado manualmente en GitHub.
4. **Sin Docker**: no afecta Fase 1. El Agente Build (Fase 4) es el único que lo requiere.

## Próximos pasos (Subfase 1.1)

- [x] **1.1.1** Clonar `sst/opencode` ✓
- [x] **1.1.2** Instalar Bun 1.3.14 ✓
- [x] **1.1.3** Instalar OpenCode v1.17.9 (binario global) ✓
- [x] **1.1.4** Build N/A (binario precompilado) ✓
- [x] **1.1.5** Smoke test OpenCode ✓ (respondió con `deepseek-v4-flash-free`)
- [x] **1.1.6** Estructura `imrryr-os/` ✓
- [x] **1.1.7** venv Python 3.11.9 ✓
- [x] **1.1.8** `requirements.txt` + install ✓ (litellm[proxy] 1.89.3, mcp 1.28.0)
- [x] **1.1.9** `.env` ✓
- [x] **1.1.10** `.gitignore` ✓
- [x] **1.1.11** `.env.example` ✓

---

## Resultado Subfase 1.2 — Traductor Agnóstico (LiteLLM)

**Estado: ✓ DEMOSTRADO**

- Proxy LiteLLM levanta en `http://localhost:4000` (sin DB/Prisma, modo pass-through).
- Healthcheck HTTP 200.
- **Conmutación agnóstica validada**: `curl … -d '{"model":"gemini-flash",…}'` respondió **"FLASH-OK"** vía LiteLLM → Gemini 2.5-flash.
- API key de Gemini **válida** (errores 404/429, no 403).

**Restricción de free tier detectada:**
- `gemini-2.5-pro` (modelo "Pro" vigente) tiene `limit: 0` en plan gratuito → error 429.
- `gemini-2.5-flash` sí permite uso gratuito y responde correctamente.
- La cuota gratuita por minuto se agota rápido (~15 RPM); tras varios tests, incluso flash cae a 429 temporalmente.

**Implicación:** el mecanismo de Neutralidad de Modelos está construido y probado. Para usar el modelo "grande" (Pro) en producción, se requiere **habilitar facturación** en Google AI Studio o esperar reset de cuota free. La conmutación nube↔local (Gemini↔Qwen) se completa automáticamente cuando exista GPU + Ollama.

**Modelos vigentes disponibles con tu API key** (revisado 2026-06-23):
- `gemini-2.5-flash` ✓ (free tier)
- `gemini-2.5-pro` (requiere billing)
- `gemini-2.0-flash`, `gemini-flash-latest`, `gemini-pro-latest`
- Preview: `gemini-3-pro-preview`, `gemini-3.5-flash`, `gemini-3.1-pro-preview`

---

## Resultado Subfase 1.3 — Encapsulamiento Backend Headless

### Modo headless de OpenCode (1.3.1)
El comando es **`opencode serve`** ("starts a headless opencode server"). No abre TUI. Opciones:
- `--port <N>`: puerto (default 0 = aleatorio)
- `--hostname <H>`: default `127.0.0.1` (local-first)
- Env `OPENCODE_SERVER_PASSWORD`: si no se setea, el servidor queda sin auth (advertencia en log).

### Autenticación (IMPORTANTE)
OpenCode **NO usa Bearer**. Usa **HTTP Basic Auth**:
`Authorization: Basic base64("opencode:<OPENCODE_SERVER_PASSWORD>")`.

### Endpoints clave descubiertos vía `GET /doc` (1.3.3)
Para Fase 1 lo relevante:
- `GET /api/health` ← **healthcheck** oficial
- `GET /api/model` ← lista modelos disponibles
- `GET /api/agent` / `GET /api/skill` ← agentes y skills registrados (para Fase 4/3)
- `GET /api/session` / `POST /api/session` ← gestión de sesiones
- `POST /api/session/{id}/prompt` ← enviar prompt (futuro Dashboard Fase 6)
- `GET /api/event` (SSE) ← stream de eventos en tiempo real (futuro Dashboard)
- `GET /api/fs/read/*` ← lectura de archivos (futuro autodocumentación)
- `GET /doc` ← spec OpenAPI completo (referencia)

Puertos fijos de Imrryr OS:
- **LiteLLM**: `:4000`
- **OpenCode serve**: `:4040`
