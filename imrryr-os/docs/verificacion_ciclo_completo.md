# Verificación de un ciclo completo — Imrryr OS

**Fecha:** 12 de agosto de 2026
**Modelo:** `kimi-k2.7-code` vía OpenCode GO (`https://opencode.ai/zen/go/v1`)
**Método:** conversación real por el chat del dashboard (`POST /api/chat`), como
lo haría cualquier usuario. En ningún paso se escribió en la base de datos a
mano: todo lo hizo el agente. La base solo se consultó *después* de cada paso,
para comprobar si lo que el agente dijo haber hecho realmente quedó guardado.

## Resumen

| | |
|---|---|
| Pasos conversacionales | 8 (6 exitosos, 2 fallidos que se corrigieron y se repitieron) |
| Dominios ejercitados | agenda, finanzas, pendientes, compras |
| Datos creados por el agente | 1 evento + 2 avisos, 1 gasto, 1 pendiente, 1 seguimiento |
| Errores encontrados | 4 (todos corregidos; 3 cubiertos con tests) |
| Datos previos del usuario dañados | ninguno |

**Veredicto:** el sistema funciona de punta a punta. Todo lo que el agente dijo
haber hecho quedó realmente guardado y con los valores correctos. El ciclo
destapó un fallo grave que solo aparece en uso prolongado (el sistema se
apagaba solo a los 5 minutos), ya corregido.

---

## Estado de la base antes y después

Snapshot tomado antes de escribir nada y repetido al final:

| tabla | antes | después | delta |
|---|---:|---:|---:|
| eventos | 0 | 1 | +1 |
| avisos_evento | 0 | 2 | +2 |
| pendientes | 0 | 1 | +1 |
| gastos | 1 | 2 | +1 |
| productos_seguimiento | 0 | 1 | +1 |
| uso_ia | 7 | 13 | +6 |
| importaciones | 22 | 23 | +1 |

Los deltas coinciden exactamente con lo pedido por chat. `importaciones +1` es
el sincronizador de correo bancario corriendo solo (importación #26, 0 correos
nuevos), no una consecuencia de la prueba. Se hizo un respaldo previo
(`vault/backups/imrryr_2026-08-12.db`) antes de empezar.

---

## Paso 1 — Agenda: evento con dos avisos a horas libres

> **Yo:** Agéndame dentista el jueves 20 de agosto a las 16:00, y mándame un
> aviso a las 8 de la mañana y otro a las 15:00 ese día.

> **Agente:** Listo, creado evento "dentista" el jueves 20 de agosto a las
> 16:00 con avisos a las 8:00 y 15:00. *(66,2 s)*

**Evidencia en la base:**

```
eventos:        {'id': 4, 'titulo': 'dentista', 'fecha': '2026-08-20',
                 'hora': '16:00', 'duracion_min': 60, 'estado': 'activo'}
avisos_evento:  {'evento_id': 4, 'hora_aviso': '08:00', 'disparado': 0}
                {'evento_id': 4, 'hora_aviso': '15:00', 'disparado': 0}
```

**Decisiones informadas que tomó bien:**

- Resolvió *"el jueves 20 de agosto"* a `2026-08-20`, que efectivamente **es
  jueves** (verificado por calendario). No mezcló el día de la semana con el
  número.
- Guardó **dos** avisos a horas arbitrarias (08:00 y 15:00), que es justo el
  caso para el que se rediseñó la agenda: los avisos no están limitados a
  "inicio del día" y "1 hora antes".
- Asumió 60 minutos de duración por defecto, criterio razonable no especificado.

**Veredicto: correcto.**

---

## Paso 2 — Finanzas: gasto en formato chileno

> **Yo:** Registra un gasto de 12.500 pesos en Copec por bencina, de hoy.

> **Agente:** Gasto registrado: $12.500 en Copec por bencina, categoría
> combustible. *(20,9 s)*

**Evidencia en la base:**

```
{'id': 1, 'comercio': 'AWS',   'monto': 29900.0, 'categoria': 'software',    'fecha': '2026-06-28'}  <- dato previo, intacto
{'id': 9, 'comercio': 'Copec', 'monto': 12500.0, 'categoria': 'combustible', 'fecha': '2026-08-12'}  <- nuevo
```

**Decisiones informadas que tomó bien:**

- Interpretó `12.500` como **doce mil quinientos**, no como 12,5. El punto como
  separador de miles es la convención chilena y la respetó.
- Infirió la categoría `combustible` a partir de "Copec" sin que se la dijeran.
- Resolvió "de hoy" a la fecha real (`2026-08-12`).
- **No tocó el gasto que ya existía.**

**Veredicto: correcto.**

---

## Paso 3 — Pendientes

> **Yo:** Anótame un pendiente: llamar al seguro del auto para renovar la póliza.

> **Agente:** Pendiente guardado (ID 4). *(15,1 s)*

**Evidencia en la base:**

```
{'id': 4, 'texto': 'llamar al seguro del auto para renovar la póliza', 'hecho': 0}
```

Guardó el texto completo sin recortarlo y lo dejó como no hecho.

**Veredicto: correcto.**

---

## Paso 4 — Compras: seguimiento de precio

> **Yo:** Quiero seguir el precio de un notebook Lenovo IdeaPad, avísame si lo
> encuentras bajo 500.000 pesos.

> **Agente:** Seguimiento creado (ID 4). Te avisaré si encuentro el notebook
> Lenovo IdeaPad bajo $500.000. *(20,0 s)*

**Evidencia en la base:**

```
{'id': 4, 'producto': 'notebook Lenovo IdeaPad', 'precio_min': None,
 'precio_max': 500000.0, 'tiendas': 'mercadolibre,falabella,paris,ripley', 'activo': 1}
```

**Decisión informada clave:** mapeó *"bajo 500.000"* a `precio_max`, no a
`precio_min`. Es el error más fácil de cometer aquí y no lo cometió. Al no
especificarse tiendas, activó las cuatro.

**Veredicto: correcto.**

---

## Paso 5 — Consulta cruzada (primer intento: FALLÓ)

> **Yo:** Hazme un resumen: que tengo agendado, cuanto llevo gastado en total,
> que pendientes tengo y que productos estoy siguiendo.

> **Agente:** `Algo falló hablando con los agentes:` *(71,4 s — error)*

Este fallo destapó **el bug más importante de toda la sesión** (detallado más
abajo): el propio Guardia de Seguridad había apagado LiteLLM, OpenCode y el
gateway mientras la consulta estaba en curso.

---

## Paso 6 — Consulta cruzada (repetida tras el arreglo: OK)

> **Agente:**
> **Agenda (esta semana):** Sin eventos.
> **Gastos:** 2 gastos registrados, total **$42.400**.
> **Pendientes:** 1 — llamar al seguro del auto para renovar la póliza.
> **Seguimiento de compras:** 1 producto — *notebook Lenovo IdeaPad*, con
> precio máximo $500.000 en MercadoLibre, Falabella, Paris y Ripley.
> *(107,9 s)*

**Comprobación de cada cifra:**

| Afirmación del agente | Base de datos | ¿Coincide? |
|---|---|---|
| 2 gastos, total $42.400 | 2 registros, suma 42.400 (29.900 + 12.500) | sí |
| 1 pendiente, ese texto | 1 fila, texto idéntico | sí |
| 1 seguimiento, máx $500.000, 4 tiendas | idéntico | sí |
| "Sin eventos" (esta semana) | ventana 12–19 ago; el evento es el 20 | sí, ver nota |

Esto demuestra que la **delegación funciona**: una sola pregunta obligó al
agente principal a consultar cuatro dominios distintos y a componer una
respuesta con datos reales de la base, no inventados.

**Nota sobre "Sin eventos"** — no es un error de datos, pero sí un matiz que
conviene conocer: la pregunta era abierta ("qué tengo agendado") y el agente la
interpretó como *"esta semana"*, que son los próximos 7 días (12→19 de agosto).
El dentista cae el día 20, justo un día fuera de esa ventana. La respuesta es
técnicamente correcta, pero alguien podría leer "sin eventos" y creer que no
tiene nada agendado. **Ya está corregido** — ver el punto 3 de los fallos.

---

## Paso 7 — Confirmación de que el dato sí era alcanzable

> **Yo:** Y el 20 de agosto, tengo algo agendado? con que avisos?

> **Agente:** Sí: **dentista** el 20 de agosto a las **16:00**. Avisos
> programados: **08:00** y **15:00** (ninguno disparado aún). *(33,2 s)*

Recuperó el evento, la hora y **ambos avisos con su estado de disparo**. Queda
descartada cualquier pérdida de datos: lo del paso 6 era solo la ventana de
7 días.

**Veredicto: correcto.**

---

## Fallos encontrados y corregidos

### 1. CRÍTICO — El sistema se apagaba solo cada 5 minutos

**Qué pasaba.** El Guardia de Seguridad consideraba "atascado" a *cualquier*
proceso con más de 300 segundos de vida. Pero LiteLLM, OpenCode y el gateway
son demonios: estar siempre arriba **es su función**. A los 5 minutos de
arrancar, el scheduler los daba por colgados y los mataba.

**Cómo se manifestó.** En mitad del paso 5, con la consulta en curso. Log real:

```
[scheduler] proceso atascado detectado: {'pid': 21096, 'nombre_proceso': 'opencode.exe', ... 'segundos_activo': 307.4, 'atascado': True}
[scheduler] proceso atascado detectado: {'pid': 13036, 'nombre_proceso': 'litellm.exe', ... 'segundos_activo': 456.1, 'atascado': True}
INFO: "POST /api/chat HTTP/1.1" 500 Internal Server Error
```

Comprobación posterior de puertos: **LiteLLM, OpenCode y Gateway caídos**; solo
sobrevivía el dashboard, porque es el proceso que hospeda al propio Guardia.

**Por qué no se había visto antes.** Todas las pruebas anteriores duraban menos
de 5 minutos, así que el temporizador nunca llegaba a cumplirse.

**Arreglo** (`skills/monitorear_procesos.py` y `scripts/scheduler.py`):

- Los servicios base **nunca** se marcan como atascados, sin importar cuánto
  lleven vivos. El tiempo de vida deja de ser un criterio de fallo para ellos.
- Todo el árbol de procesos de un servicio se reconoce como infraestructura
  (en Windows OpenCode arranca como `cmd.exe` → `opencode.exe`; antes se
  mataban los dos).
- Para lo que el módulo sí promete —detectar bucles infinitos— se usa una señal
  real: CPU alta **sostenida**. Y eso genera un **aviso**, nunca un apagado:
  un modelo razonando también consume CPU, y apagar el motor por estar
  trabajando sería el mismo error con otro disfraz.
- Doble seguro en el scheduler: aunque algo marcara mal un servicio base, ahí
  se filtra antes de ejecutar cualquier cierre.

**Tests que lo fijan** (`tests/test_guardia_seguridad.py`): un servicio con
10 horas de vida no puede marcarse atascado; CPU al 99 % sostenida avisa pero
no apaga; CPU alta recién arrancado no genera ruido.

### 2. MENOR — Mensajes de error que no decían nada

El fallo del paso 5 llegó al usuario como `Algo falló hablando con los
agentes:` — sin explicación. La causa: excepciones cuyo `str()` viene vacío.
Ahora, cuando no hay texto, al menos se nombra el tipo de excepción. Cubierto
con un test.

---

### 3. La agenda respondía "sin eventos" ocultando la cita siguiente (aplicado)

Era la mejora sugerida tras el paso 6, aprobada y ya implementada. Cuando la
ventana consultada sale vacía, `agenda(accion="que_tengo")` devuelve ahora
también `proximo_evento` con la siguiente actividad, y el agente tiene
instrucción explícita de mencionarla en vez de responder un "no tienes nada"
a secas.

**Comprobado en vivo con la misma pregunta que antes fallaba:**

> **Yo:** Que tengo agendado?
>
> **Agente:** Esta semana no tienes nada agendado. Lo más próximo es
> **dentista el jueves 20 de agosto a las 16:00**. *(72,1 s)*

Cubierto por tres tests (`tests/test_agenda.py`): que una ventana vacía ofrece
el próximo evento con sus avisos; que sin ningún evento el campo llega nulo; y
que cuando sí hay eventos en la ventana no se añade ruido.

### 4. El chat cortaba respuestas correctas a los 120 segundos

Al probar la mejora anterior, el primer intento murió por timeout a los 123,4 s
— el modelo estaba respondiendo bien, pero tanto el navegador como el servidor
cortaban a los 120 s. Las mediciones reales de esta sesión (66 s, 72 s, 108 s,
123 s) dejan claro que ese límite quedaba corto para preguntas que obligan a
delegar en varios subagentes.

Subido a 300 s en los tres puntos que participan: `dashboard/server.py`,
`dashboard/dashboard.html` (el `AbortSignal` del navegador, que cortaba por su
cuenta aunque el servidor esperara) y `gateway/webhook_server.py`, para que
WhatsApp no sufra lo mismo.

Además, el mensaje de timeout daba por hecho que el proveedor era Gemini y
culpaba a su cuota gratuita; con OpenCode GO activo eso despistaba. Ahora
menciona primero la causa más probable (consulta que encadena varias llamadas)
y deja la cuota como segunda opción.

---

## Cómo reproducir esta verificación

```bash
python scripts/startup.py          # levanta todo
python -m pytest tests/ -q         # 32 tests de la lógica determinista
```

Luego, desde http://localhost:3000, escribir en el chat del inicio las mismas
frases de los pasos 1 a 7 y contrastar con la base:

```bash
python -c "import sqlite3; c=sqlite3.connect('vault/sqlite/imrryr.db'); print(c.execute('SELECT * FROM eventos').fetchall())"
```
