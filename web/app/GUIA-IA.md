# Recorrido actualizado en 0.7.0

Consulta **Guía de uso** dentro de la aplicación o descarga [Tu primer día con Mi grado](PRIMER-USO.md). La configuración muestra un paso cada vez y el importador de avances se cierra al guardar. Las tareas permiten duración, detalle, edición y archivo; el horario permite editar clases.

# Elegir tu IA y conectar tus notas

Esta primera versión usa tu chat habitual y sus límites. Mi grado no llama a una API de pago, no pide credenciales y no da por instalada una skill por adjuntar sus instrucciones.

## ChatGPT en iPhone o iPad: recorrido gratuito básico

Desde la 0.5.1, empieza en **Configurar Mi grado**: guarda grado, centro, bóveda e IA. Devuelve la nota de prueba tras guardarla y editarla en Obsidian, y pega en tu chat el mensaje de comprobación de IA. Revisa su JSON y confirma su origen. Estos pasos habilitan el estudio; no crean actividad académica ni autentican la cuenta del proveedor. Los intercambios de cada sesión siguen siendo manuales. Tus notas anteriores y copias permanecen disponibles.

1. Abre [Mi grado](https://mi-grado-piloto.vercel.app/app/) en Safari. Puedes usar Compartir → Añadir a pantalla de inicio. Añade una asignatura de prueba.
2. En Conexiones selecciona una nota .md desde Archivos. Revisa su título y contenido: se añadirá como un tema independiente. Puedes gestionarlo en Mis notas.
3. Descarga INSTRUCCIONES-IA.md. En ChatGPT adjunta ese archivo o pega sus instrucciones al comenzar el chat; utiliza «Sigue estas instrucciones con el contexto Mi grado que voy a darte».
4. En Preparar sesión marca los temas de esa sesión, prepara y revisa el contexto. Solo esos apuntes se incluirán, junto con el último intento de la asignatura. Cópialo o descárgalo y adjúntalo a ese chat. Los textos/archivos que envías se comparten con el proveedor elegido.
5. Estudia y pide «Cierra la sesión y devuelve el JSON de avance para Mi grado». Importa la respuesta en Conexiones, revísala y confirma el guardado.
6. Descarga la nota del registro y guárdala en tu bóveda Obsidian desde Archivos. Para cambiar de dispositivo, descarga también la copia JSON del cuaderno.

En ChatGPT, la distribución instalable de skills para web/móvil utiliza plugins. El paquete Mi grado Obsidian IA es un plugin de instrucciones, sin servidor ni acceso automático a tus archivos. Su instalación/disponibilidad depende de la cuenta y de cómo se comparta; el flujo por instrucciones funciona como alternativa sin exigir esa función. Crear el plugin privado del autor no lo publica ni concede acceso a otras cuentas.

[Documentación oficial de ChatGPT](https://learn.chatgpt.com/docs/build-skills).

## Claude

Si tu cuenta muestra Customize → Skills, activa Code execution and file creation según tu configuración, elige crear/subir skill y carga `mi-grado-obsidian-ia.zip`. La documentación consultada incluye el plan Free; la disponibilidad de la interfaz puede variar por cuenta. La skill cargada trabaja con lo adjuntado al chat, no con tu bóveda local. Si no aparece, adjunta o pega INSTRUCCIONES-IA.md y sigue el mismo intercambio.

[Instrucciones oficiales de Claude](https://support.claude.com/en/articles/12512180-use-skills-in-claude).

## Gemini

En la web, puedes pegar las instrucciones en un chat o en las instrucciones de un Gem y adjuntar la nota/contexto. No lo presentes como una instalación de SKILL.md en Gemini web. Recoge el mismo JSON al cerrar la sesión. No se necesitan API ni recursos contratados por Mi grado.

[Guía oficial de Gems](https://support.google.com/gemini/answer/15146780?hl=es).

## Agentes locales: guardado directo en Obsidian

Extrae el ZIP de la skill. El agente debe tener acceso local a los archivos elegidos; el uso/precio del agente es independiente de Mi grado.

- Codex: copia la carpeta mi-grado-obsidian-ia en `~/.agents/skills/`; puede usarse con `$mi-grado-obsidian-ia`.
- Claude Code: copia esa carpeta en `~/.claude/skills/` y utiliza `/mi-grado-obsidian-ia`.
- Gemini CLI: `gemini skills link RUTA_DE_LA_SKILL --scope user`, luego `/skills reload`. La CLI solicita autorización al activar la skill.

El puente incluido requiere Python 3.11 o posterior y no requiere paquetes externos. Exporta el cuaderno web después de preparar la sesión. Indica al agente ese JSON, la bóveda elegida, la nota concreta y la respuesta revisada. El puente comprueba identidades, genera contexto y guarda un registro nuevo con diario enlazado; un reintento idéntico conserva las ediciones manuales. No se sincroniza continuamente: importa el resultado en la web para actualizar su copia de trabajo.

[Skills Codex](https://learn.chatgpt.com/docs/build-skills), [skills Claude Code](https://code.claude.com/docs/en/skills), [skills Gemini CLI](https://geminicli.com/docs/cli/using-agent-skills/).

## Límites que debes conocer

La PWA guarda una copia de trabajo en el navegador. Exporta Markdown para tu bóveda y JSON para recuperación; borrar los datos del sitio puede borrar esa copia. No hay acceso directo a la bóveda desde Safari, ni sincronización entre dispositivos, ni lectura de conversaciones de tu IA. El modo sin conexión sirve para el cuaderno después de cargar la aplicación, no para el chat externo. El ZIP Windows anterior conserva su funcionamiento y no se convierte en app iOS/Android.

Documentación comprobada el 14/10/2026. La prueba en iPad, iPhone, Android y Mac reales sigue pendiente.

Recorrido actualizado el 15/10/2026 para temas y copias: el primer uso está guiado desde Mi cuaderno. Al actualizar desde la versión anterior, los apuntes existentes se conservan como Apuntes anteriores. Descarga una copia y comprueba que está en Archivos. Una descarga preparada no confirma su guardado en Obsidian.
