# Guía de instalación de Imrryr OS (para usuarios no técnicos)

## Antes de empezar
- Necesitas un PC con **Windows 10 u 11** y conexión a internet.
- Reserva unos **1 GB libres** en el disco.
- **No necesitas ser administrador ni instalar nada más.** El programa lleva todo incluido.

## 1. Instalar
1. Haz **doble clic** en `Imrryr_OS_Setup_pyme.exe`.
2. Es probable que Windows muestre una pantalla azul: **"Windows protegió su PC"**. Es normal, porque el programa aún no tiene firma digital. Pulsa **"Más información"** y luego **"Ejecutar de todos modos"**.
3. El asistente está en español. Pulsa **Siguiente** en cada paso y deja marcada la opción **"Crear un icono en el escritorio"**.
4. Al terminar, deja marcada **"Iniciar Imrryr OS"** y pulsa **Finalizar**.

## 2. Primera vez que se abre
- Espera **hasta 3 minutos** la primera vez (después, entre 1 y 2). Los servicios internos se están encendiendo y no verás nada mientras tanto: es normal. La ventana aparece sola cuando todo está listo. **No cierres ni vuelvas a abrir.**
- Se abrirá una ventana con el panel de Imrryr OS. Funciona como una aplicación normal, con su propio icono.
- Si aparece un cuadro de error, **sácale una foto o captura** y mándala a quien te dio el programa.

## 3. Elegir la inteligencia artificial
Sin este paso los asistentes no pueden responder.
1. En el menú, entra a **Ajustes** y luego a **Cuentas de IA**.
2. Elige **"OpenCode Zen (gratis)"**. No pide clave ni tarjeta. Déjalo con el modelo que viene seleccionado y pulsa **Activar**.
3. Espera unos segundos a que confirme.

Con la opción gratuita las respuestas pueden tardar desde 2 segundos hasta **un par de minutos**, porque ese servicio lo comparte mucha gente. No significa que esté roto. Si necesitas respuestas más rápidas o estables, puedes usar una cuenta propia de **Gemini** u otro proveedor desde el mismo lugar.

## 4. Probar que funciona
Entra al chat del **Asistente** y escribe algo simple, por ejemplo: *"Agrega a mis pendientes: llamar al contador"*. Luego revisa la sección **Pendientes**: debería aparecer ahí.

## Uso diario
- **Abrir**: icono **Imrryr OS** del escritorio.
- **Cerrar bien**: busca **"Detener Imrryr OS"** en el menú Inicio y ábrelo. No basta con cerrar la ventana, porque los servicios siguen funcionando de fondo.
- **Desinstalar**: *Configuración de Windows → Aplicaciones → Imrryr OS → Desinstalar*.

## Si algo falla
| Síntoma | Qué hacer |
|---|---|
| La ventana no aparece tras 5 minutos | Abre **"Detener Imrryr OS"**, espera 10 segundos y abre de nuevo **"Imrryr OS"** |
| Aparece "Otro programa del equipo está usando el puerto..." | Imrryr OS necesita ciertos puertos de tu PC (3000, 4000 y 4040) y otro programa los ocupa. Cierra ese programa y vuelve a abrir Imrryr OS. Si no puedes, pide ayuda técnica: se cambia el puerto en `config\.env` |
| El antivirus bloquea o borra archivos | Agrega la carpeta de instalación como excepción (ver abajo) y reinstala |
| Los asistentes no responden | Revisa que el paso 3 esté hecho y que haya internet |
| Nada de lo anterior | Manda a quien te dio el programa el archivo `vault\logs\launcher.log`, dentro de la carpeta de instalación |

La carpeta de instalación es `C:\Users\TU_USUARIO\AppData\Local\Programs\Imrryr OS`. Para abrirla, pega esa ruta en el Explorador de archivos cambiando `TU_USUARIO` por el tuyo.

## Lo que esta versión no trae listo
- **WhatsApp**: **no funciona al instalar y no se puede arreglar desde la aplicación.** El paquete no incluye sus componentes (hay que instalar Node y un paso extra por línea de comandos). Si lo necesitan, requiere ayuda técnica. El resto del programa funciona sin WhatsApp.
- **Correo y Compras**: necesitan configuración propia (cuentas, permisos). No se probaron recientemente en un uso real, así que avisa si algo falla.
