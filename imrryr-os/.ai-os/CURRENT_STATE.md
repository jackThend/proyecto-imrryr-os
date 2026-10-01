# Estado Vivo — Imrryr OS

_Actualizado: 2026-09-29. Este archivo lo muestra la Vista Código del dashboard; se mantiene corto y con datos verificables. El historial de cambios vive en `git log`._

## Salud del proyecto
- **Tests**: 119 pasando · **Linter (ruff)**: sin advertencias.
- **Agentes**: 13 (`agentes/*.yaml`) · **Skills**: 35 scripts con 46 manifiestos MCP · **Dashboard**: 14 routers, ~93 endpoints.
- **Servicios**: dashboard `:3000`, LiteLLM `:4000`, OpenCode `:4040`, gateway WhatsApp `:5050`, sidecar `:5051`.
- **Base de datos**: SQLite única (`vault/sqlite/imrryr.db`) con respaldo diario automático (14 días).

## Capa de IA (Ajustes > Cuentas de IA)
Sin modelo por defecto: el sistema usa la cuenta que el usuario activa.

| Proveedor | Ruta | Estado |
|---|---|---|
| Gemini, OpenAI, Anthropic, DeepSeek, Ollama, "otro" | LiteLLM (alias `imrryr-activo`) | Funciona (Gemini free: 20 consultas/día) |
| OpenCode GO (de pago) | LiteLLM + cabecera `x-opencode-session` | Requiere suscripción activa: hoy devuelve 403 (externo al código) |
| **OpenCode Zen (gratis)** | **Proveedor nativo de OpenCode, sin LiteLLM** | Funciona con `big-pickle` (verificado con escritura real en la base) |

Detalles de la ruta nativa (por qué es distinta):
- El servidor gratuito rechaza (403) cualquier petición que no venga de OpenCode, por eso no puede pasar por LiteLLM.
- Exige OpenCode **≥ 1.18.0** (el binario embebido `bin/opencode.exe` es el que se usa) y el juego **completo** de herramientas nativas en cada petición.
- Para no perder seguridad, en esta ruta las herramientas nativas quedan listadas pero bloqueadas con un patrón que nunca coincide (`scripts/sync_agentes.py`), y cada agente lleva un prompt que le dice qué puede usar. Verificado con un intento de inyección: no se creó ningún archivo.
- Activar la cuenta re-sincroniza agentes y reinicia OpenCode; se niega con motivo si la versión es menor.

## Módulos
- **Verificados con uso real** (conversación por chat + comprobación directa en SQLite): Agenda, Pendientes, Finanzas, Reuniones (incluye edición de transcripción, mapa conceptual, volcado a agenda/pendientes).
- **Con tests y sin verificación en vivo reciente**: Compras (Falabella por HTTP; Ripley solo con navegador; Paris y MercadoLibre no funcionan), RRSS/Web, Correo/Secretario, CRM, Navegación por voz.
- **Guardia de Seguridad**: solo avisa; nunca detiene servicios base (un bug anterior los mataba a los 5 min).

## Empaquetado
- Perfiles `pyme` y `tech` (`profiles/*.yaml`); instalador con `python scripts/build_exe.py --profile pyme` (PyInstaller para los lanzadores + Inno Setup + runtime portátil).
- Las skills se empaquetan por lista blanca: una skill nueva compartida entre procesos debe ir en `CORE_SKILLS` de `scripts/package.py` (hay un test que lo vigila para `ruta_modelo`).

## Pendiente
1. **Rotar la API key de OpenCode GO** antes de distribuir (su valor quedó visible en una sesión de trabajo; decisión del usuario: aplazada).
2. Reactivar la suscripción de OpenCode GO si se quiere usar (o seguir con Zen gratis / Gemini).
3. Verificación en vivo de los módulos "sin verificación reciente" (Compras, RRSS, Correo, CRM, Navegación).
4. **CI de GitHub funcionando** (Windows + Ubuntu, repo público desde 2026-09-30). Los 6 PRs de Dependabot se fusionaron tras probarlos en un entorno limpio; falta solo confirmar Express 5 con WhatsApp real (en local, las rutas HTTP del sidecar responden igual que con Express 4).
