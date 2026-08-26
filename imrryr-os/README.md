# Imrryr OS

Sistema operativo personal local-first: un asistente de agentes de IA que corre
completamente en tu computador, con dashboard web propio, gateway de WhatsApp y
bóveda de datos en SQLite que nunca sale del disco.

## Pilares

- **Soberanía de datos** — toda la información vive en `vault/` (SQLite + Chroma).
  Nada se sube a la nube salvo las llamadas al modelo de IA que elijas.
- **Neutralidad de modelos** — todo el sistema habla con el alias `imrryr-activo`,
  que apunta a la cuenta de IA que actives en *Ajustes > Cuentas de IA*.
  Cambiar de proveedor (Gemini, OpenCode GO, Ollama local…) no toca una línea de código.
- **Backend invisible** — OpenCode corre headless como motor; la cara visible es el
  dashboard en `http://localhost:3000`.
- **Carpetas dinámicas** — cada `agentes/*.yaml` se convierte en un subagente real y
  cada `skills/*.py` en una herramienta MCP, escaneados en cada arranque.

## Instalación

### Camino recomendado: instalador universal

Doble clic y listo. Detecta lo que falte (Python, Node.js, Bun, OpenCode), arma el
entorno virtual, instala dependencias y deja accesos directos en el Escritorio.

```powershell
# Windows
powershell -ExecutionPolicy Bypass -File install.ps1
```

```bash
# macOS / Linux
chmod +x install.sh && ./install.sh
```

### Camino manual

1. Python 3.10–3.13 y Node.js instalados.
2. `python -m venv .venv` y activarlo.
3. `pip install -r requirements.txt`
4. `npm install` dentro de `gateway/whatsapp_local/` (solo si usarás WhatsApp local).
5. Copiar `config/.env.example` a `config/.env` y rellenar credenciales.
6. Arrancar: `python scripts/startup.py` (siembra `config/opencode.json` desde su
   plantilla, registra agentes/skills y levanta todos los servicios).

> `config/opencode.json` es un artefacto local generado por `scripts/sync_agentes.py`
> (igual que `.env`): no se commitea porque contiene rutas absolutas de esta máquina.

## Uso diario

| Acción | Comando |
|---|---|
| Arrancar todo | `python scripts/startup.py` |
| Detener todo | `python scripts/shutdown.py` |
| Solo healthcheck | `python scripts/startup.py --check-only` |
| Prueba E2E (requiere servicios arriba) | `python scripts/smoke_test.py` |
| Respaldo manual de la DB | `python scripts/respaldo_db.py` |

Servicios y puertos: Dashboard `:3000`, LiteLLM `:4000`, OpenCode `:4040`,
Gateway WhatsApp `:5050`, sidecar WhatsApp local `:5051`.

El primer chat entra por el dashboard; también hay gateway para hablarle a Imrryr
por WhatsApp (modo local con QR o Cloud API, se elige desde Ajustes).

## Estructura

```
agentes/    YAMLs → un subagente OpenCode por archivo (permisos deny-by-default)
skills/     Herramientas MCP deterministas (agenda, finanzas, scrapers, TTS…)
config/     .env, plantilla opencode.json, cuentas de IA/git/social
dashboard/  FastAPI + SPA (server.py monta los routers de api/)
gateway/    Webhook WhatsApp + sidecar whatsapp-web.js
finanzas/   Importador histórico de correos bancarios
vault/      DB SQLite + memoria vectorial Chroma + respaldos (nunca al repo)
scripts/    startup/shutdown/scheduler/packaging/tests utilitarios
tests/      Suite pytest de la lógica determinista (sin red ni DB real)
```

## Tests y CI

```bash
python -m pytest tests/ -q
```

La suite cubre parsers, agenda, guardia de seguridad, errores de IA y el contrato
HTTP del dashboard (con `TestClient`, hermética). GitHub Actions corre la suite en
cada push (`.github/workflows/ci.yml`).

## Empaquetado

`python scripts/package.py` genera los zips de distribución por perfil
(pyme / tech) en `dist/`.
