# Estado Vivo — Imrryr OS

_Actualizado: 2026-09-29. Este archivo lo muestra la Vista Código del dashboard; se mantiene corto y con datos verificables. El historial de cambios vive en `git log`._

## Salud del proyecto
- **Tests**: 119 pasando · **Linter (ruff)**: sin advertencias.
- **Agentes**: 13 (`agentes/*.yaml`) · **Skills**: 35 scripts con 46 manifiestos MCP · **Dashboard**: 14 routers, ~93 endpoints.
- **Servicios**: dashboard `:3000`, LiteLLM `:4000`, OpenCode `:4040`, gateway WhatsApp `:5050`, sidecar `:5051`.
- **Base de datos**: SQLite única (`vault/sqlite/imrryr.db`) con respaldo diario automático (14 días).

## Capa de IA (Ajustes > Cuentas de IA)
Una instalación nueva arranca con **OpenCode Zen (gratis)** ya activo, sin que el usuario cree ninguna cuenta (`config/cuentas_ia.py::asegurar_cuenta_inicial`, llamada desde `scripts/startup.py`). Solo actúa si no existe `config/cuentas_ia.json`: nunca pisa ni re-siembra cuentas del usuario. El modelo es el primero disponible de `MODELOS_GRATIS_PREFERIDOS`; hoy `mimo-v2.6-flash-free`, elegido por prueba real (ver abajo).

| Proveedor | Ruta | Estado |
|---|---|---|
| Gemini, OpenAI, Anthropic, DeepSeek, Ollama, "otro" | LiteLLM (alias `imrryr-activo`) | Funciona (Gemini free: 20 consultas/día) |
| OpenCode GO (de pago) | LiteLLM + cabecera `x-opencode-session` | Requiere suscripción activa: hoy devuelve 403 (externo al código) |
| **OpenCode Zen (gratis)** | **Proveedor nativo de OpenCode, sin LiteLLM** | Funciona; por defecto `mimo-v2.6-flash-free`. Prueba 2026-10-08 de los 13 modelos gratuitos con herramientas reales (4 tareas + reunión con volcado, comprobado en la base): mimo 4/4 y sin duplicados; nemotron-3.5-lightning 4/4 pero lento y duplica; big-pickle 3/4 y el más lento; 4 modelos fallan de inmediato. Los modelos gratuitos rotan, por eso hay lista de reserva |

Detalles de la ruta nativa (por qué es distinta):
- El servidor gratuito rechaza (403) cualquier petición que no venga de OpenCode, por eso no puede pasar por LiteLLM.
- Exige OpenCode **≥ 1.18.0** (el binario embebido `bin/opencode.exe` es el que se usa) y el juego **completo** de herramientas nativas en cada petición.
- Para no perder seguridad, en esta ruta las herramientas nativas quedan listadas pero bloqueadas con un patrón que nunca coincide (`scripts/sync_agentes.py`), y cada agente lleva un prompt que le dice qué puede usar. Verificado con un intento de inyección: no se creó ningún archivo.
- Activar la cuenta re-sincroniza agentes y reinicia OpenCode; se niega con motivo si la versión es menor.

## Módulos
- **Verificados con uso real el 2026-10-08**, cada agente en una copia aparte con base vacía y el modelo gratuito por defecto (chat por OpenCode + comprobación directa del dato guardado): Agenda, Asistente (memoria), Financiero, Creativo, Investigador, Reuniones, Compras (seguimiento de producto y precios reales de Falabella), RRSS (post programado), Secretario (borrador), Navegación (lectura web real y audio MP3), Guardia (alerta en `alertas.log`) y CRM (cotización PDF). 14 de 14.
- **No verificados porque exigen cuentas reales del usuario**: leer correo (Gmail/IMAP), publicar en Instagram/Facebook, hacer push a GitHub y WhatsApp.
- **Navegador**: Navegación y Ripley usan el Chromium de Playwright si existe y, si no, el Chrome/Edge/Brave que tenga instalado el cliente (`skills/navegador_cliente.py`). Verificado leyendo páginas y 48 productos de Ripley sin Chromium de Playwright. Paris y MercadoLibre siguen sin funcionar.
- **Agentes opcionales**: ambos perfiles (`pyme`, `tech`) empaquetan Agenda, Compras, Navegación, RRSS y Secretario **desactivados** (`agentes_opcionales` en `profiles/*.yaml`, con sus herramientas). Se activan con un clic en Módulos, que reinicia OpenCode (~40 s) y recarga el panel. Instaladores: `Imrryr_OS_Setup_pyme.exe` e `Imrryr_OS_Setup_tech.exe` en la raíz del repo local (no versionados); comparten identidad y carpeta de instalación, no pensados para convivir en un mismo PC.
- **Pestañas del panel**: el panel oculta las de agentes que no vienen en el perfil instalado (`/api/agentes-disponibles`). Antes pyme mostraba Agenda, Compras, Correo, RRSS, Navegación y Código y respondían error 500.
- **Guardia de Seguridad**: solo avisa; nunca detiene servicios base (un bug anterior los mataba a los 5 min).

## Empaquetado
- Perfiles `pyme` y `tech` (`profiles/*.yaml`); instalador con `python scripts/build_exe.py --profile pyme` (PyInstaller para los lanzadores + Inno Setup + runtime portátil).
- Las skills se empaquetan por lista blanca: una skill nueva compartida entre procesos debe ir en `CORE_SKILLS` de `scripts/package.py` (hay un test que lo vigila para `ruta_modelo`).

## Pendiente
1. **Rotar la API key de OpenCode GO** antes de distribuir (su valor quedó visible en una sesión de trabajo; decisión del usuario: aplazada).
2. Reactivar la suscripción de OpenCode GO si se quiere usar (o seguir con Zen gratis / Gemini).
3. Verificar con cuentas reales lo que hoy no se pudo: leer correo, publicar en redes, push a GitHub y WhatsApp.
4. **CI de GitHub funcionando** (Windows + Ubuntu, repo público desde 2026-09-30). Los 6 PRs de Dependabot se fusionaron tras probarlos en un entorno limpio; falta solo confirmar Express 5 con WhatsApp real (en local, las rutas HTTP del sidecar responden igual que con Express 4).
