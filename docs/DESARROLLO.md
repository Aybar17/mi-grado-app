# Configuración y desarrollo

Para instalar y usar la aplicación, empieza por el [README](../README.md). Este documento describe los archivos y comandos del código fuente.

## Probar la demo

Desde la carpeta del repositorio:

```text
python generar_panel.py --demo
python abrir_panel.py --demo
```

El segundo comando abre `http://127.0.0.1:8770/panel.html` y mantiene el servicio mientras la terminal siga abierta. Para cerrarlo pulsa Ctrl+C. Si el puerto está ocupado, añade `--port 8771`. `--no-browser` permite arrancar sin abrir una ventana.

En Windows, `python launcher_local.py --demo` inicia un servicio separado y abre el panel: puede seguir funcionando al cerrar la terminal. `--no-open` arranca sin abrir el navegador. Comprueba la identidad de la configuración para evitar reutilizar un servicio de otra instalación. Después de reiniciar Windows hay que volver a iniciarlo; no instala arranque automático.

La primera ejecución copia las fichas sintéticas a `runtime/demo/`; no reemplaza ediciones posteriores. Los datos generados, notas de prueba, diarios, copias y registros de recuperación quedan ignorados por Git. La demo usa una clave de almacenamiento propia para separar sus borradores de una instalación personal.

En «Registrar avance» puedes guardar una captura ficticia. El éxito requiere comprobar nota, enlace al diario y punto de guardado. Repetir una petición con el mismo identificador no duplica la nota; cambiar su contenido exige un identificador nuevo. Los registros dañados se muestran como incidencias y no bloquean las demás capturas.

## Configurar datos locales

1. Copia `config.example.json` a `config.local.json`.
2. Configura `vaults.degree`, `vaults.hub` y, opcionalmente, `vaults.projects`. Se leen las fichas académicas seleccionadas, capturas y la nota opcional del horario; las otras notas aportan títulos y enlaces.
3. Copia `examples/demo/panel.json` a la ruta de `panel_file`, fuera de las bóvedas, y sustituye las asignaturas y resúmenes. Cada `note` es una ruta relativa a la bóveda del grado. Los materiales del profesor permanecen externos.
4. Mantén `runtime` fuera de las bóvedas. Ahí se guardan página generada, índices, huellas, registros técnicos y copias. No confundas este directorio técnico con la fuente Markdown.
5. Ejecuta `python abrir_panel.py --config config.local.json`.

Las rutas relativas se resuelven junto al JSON de configuración. También puedes usar rutas absolutas en tu archivo local o la variable `MI_GRADO_CONFIG`. `--demo` siempre elige la configuración ficticia y no usa esa variable ni el archivo local.

Para una instalación existente, `memory_config` puede apuntar a su configuración privada de guardado protegido: reutiliza el estado, copias y registros de recuperación sin reemplazarlos. Debe autorizar las capturas y el diario de los destinos configurados. El mapa opcional `documents` sirve únicamente archivos Markdown elegidos explícitamente, por ejemplo `{"/guia.md": "ruta-local/guia.md"}`; su lector `/guia.html` muestra el contenido escapado. Los documentos permanecen fuera del repositorio. Cambiar la configuración requiere reiniciar el servicio.

Para guardar una declaración desde otra herramienta:

```text
python puente_memoria.py --config config.local.json --capture ruta-a-peticion.json
```

La petición contiene cadenas `id`, `subject`, `kind`, `title`, `date`, `time`, `timezone`, `evidence`, `source`, `details` y `created`. El identificador debe ser estable y `subject` debe coincidir con una asignatura configurada o `general`. Una hora requiere fecha y zona `Europe/Madrid`; horas ambiguas o inexistentes se rechazan. Una declaración no confirma una entrega ni dominio autónomo.

## Revisar un resumen

«Horario de clase» lee la fuente editable `00 Dashboard/Horario de clase.md` de la bóveda del grado. Admite las líneas `Grupo:`, `Periodo:`, `Contraste:`, `Fuente:` (URL) y `Nota:`, y una tabla con columnas `Día | Inicio | Fin | Asignatura | Tipo | Aula`. Los días son de lunes a viernes y las horas usan `HH:mm`. Las filas inválidas se señalan para revisión; sin nota no se inventan clases. El horario muestra clases ordinarias, separado de los bloques de estudio y sin acreditar asistencia.

Las tareas sin día asignado se muestran en «Tareas pendientes». El campo de plan `pendingTasks` conserva sus identificadores, asignatura, título y duración propuesta aunque los días no tengan bloques. Asignar una fecha sigue requiriendo disponibilidad real. Los días se recorren con flechas, teclado o desplazamiento horizontal; las tareas pendientes permanecen visibles fuera del carrusel.

`actualizar_panel.py` admite una revisión explícita con `subjects: [{id, sourceSha, patch}]` y `plan` opcional. `sourceSha` es SHA-256 de la ficha que realmente se leyó. Comprueba de nuevo las fichas antes de guardar, conserva copia y rechaza cambios concurrentes. La generación marca los resúmenes que necesitan revisión; no infiere aprendizaje de una edición.

```text
python actualizar_panel.py --config config.local.json --review revision-local.json
python puente_memoria.py --config config.local.json --refresh
```

## Verificar

```text
python -m unittest discover -s tests -v
node tests/frontend.cjs
node tests/web-core.cjs
python generar_panel.py --demo
```

Las pruebas usan carpetas temporales y datos ficticios: arranque HTTP, rutas permitidas, protección de origen, guardado completo, reintento, edición manual, conflicto de petición, metadatos dañados, huellas de revisión, configuración nueva, reanudación y conectores sin servicios de pago. GitHub Actions ejecuta la batería en Windows y Ubuntu al recibir cambios.

## Sesiones, objetivos y equipo

«Preparar sesión» conserva un borrador por asignatura y selecciona materiales por su referencia estable. «Registrar intento de esta sesión» lleva asignatura, material, ejercicio y punto de partida a la captura; completa qué intentaste y qué ayuda recibiste antes de guardar. Una entrega registrada con fecha, hora y enlace tiene prioridad en el inicio cuando queda a tres días o menos; la referencia conserva su alcance y necesita contraste si hubo cambios.

En «Proyecto y horizonte», «Objetivos» deriva sus campos de `30 Áreas/Objetivos/Objetivos.md` en la bóveda central. Puedes configurar `goals_file` dentro de esa bóveda. Las casillas describen hitos declarados; no calculan dominio académico.

«Equipo IA» muestra registros locales de roles, trabajo, críticas, instrucciones y alcance de memoria desde `equipo.local.json` en el directorio de ejecución. Es un registro de encargos, no un equipo ejecutándose permanentemente. La demo no inventa ejecuciones ni consumo. Los contadores, cuando existen, distinguen entrada, caché y salida; no son una factura de ChatGPT. La guía de modelos y su calculadora de API muestran recomendaciones y escenarios etiquetados, con fecha y fuentes oficiales. No llaman a una API.

## Una sola versión del código

El checkout versionado debe ser la fuente de código editable. La instalación personal mantiene fuera del repositorio su configuración y datos. Un acceso directo o lanzador antiguo puede delegar a `abrir_panel.py` en este checkout con `--config` apuntando al archivo privado. Tras validar la migración, los lanzadores históricos se conservan solo como delegación o copia de recuperación; no se mantienen dos versiones editables.

Antes de conectar una instalación existente: copia recuperable del código/configuración, prueba con copia de datos, confirma nota/diario/recuperación y después cambia el lanzador y reinicia el servicio. Este repositorio no realiza esa migración automáticamente ni altera una instalación viva.

## Alcance

Servicio local por instalación. No ofrece autenticación multiusuario, acceso remoto, sincronización de chats, sincronización automática con plataformas docentes, automatizaciones o envío a personas. La preparación de contexto funciona sin llamar a un modelo; la consulta a Ollama local es opcional y explícita. Las capturas siguen siendo declaraciones pendientes de contraste. Consulta `ATTRIBUTION.md` para la procedencia y condiciones pendientes de redistribución.

## Construir la aplicación Windows

Usa un entorno de construcción separado en Windows. Instala `requirements-build.txt` y ejecuta:

```text
python -m pip install -r requirements-build.txt
python empaquetar_windows.py --version 0.9.0-rc.3
```

El ZIP y su SHA-256 quedan en `output/windows`, ignorado por Git. La lista de recursos está en `Mi grado.spec`; la configuración y las bóvedas no se añaden al paquete. Las zonas horarias se incluyen en la aplicación. Ollama y sus modelos se instalan por separado si el usuario decide utilizarlos.


## Gestión y recuperación del cuaderno

`gestion.py` valida cambios de asignaturas y controla huellas antes de escribir; el plan y horario son fuentes Markdown. `gestion-ui.js` presenta los formularios de Mi cuaderno. Las asignaturas archivadas conservan identidad, fichas y capturas. Las tareas propias se guardan en el bloque `mi-grado:plan`; el resto del texto de esa nota se conserva.

`copias.py` crea un ZIP con manifiesto y huellas, solo de fichas seleccionadas, plan, horario, capturas y diarios vinculados. La restauración valida rutas y límites, crea un perfil independiente y comprueba los registros del guardado; no sobrescribe el cuaderno abierto. Incluye nombres de bóveda distintos para que los enlaces recuperados no apunten al original. No incluye adjuntos, otras áreas ni borradores del navegador.

Las rutas `/api/manage/subject`, `/api/manage/task`, `/api/manage/schedule` y `/api/backup/*` usan los controles de Host/Origin existentes. La descarga de copia es GET; vista previa y restauración aceptan JSON hasta 45 MB para un ZIP de hasta 32 MB codificado en base64. No habilitan acceso remoto ni servicios de pago.

Las pruebas `test_management.py` y `test_backups.py` usan carpetas temporales y datos ficticios para comprobar conflicto de ediciones, conservación de notas, tareas vencidas, archivos alterados y guardado tras restaurar. La verificación visible y del paquete Windows sigue siendo distinta de una prueba en otro ordenador.


## Construcción portable Windows

`python empaquetar_windows.py --version 0.9.0-rc.3` construye por defecto el formato portable: intérprete oficial de la instalación Python utilizada, stdlib sin site-packages ajenos, Tcl/Tk, tzdata y una lista explícita de módulos y recursos de Mi grado. Comprueba la firma Authenticode del intérprete y su arranque aislado. El lanzador es Abrir Mi grado.cmd; no registra Python, no crea permisos adicionales y no modifica controles de Windows. Se usa Python x64 con Tk y tzdata disponibles en el entorno de construcción.

`--experimental-exe` conserva la construcción de PyInstaller, que fue bloqueada por el control de aplicaciones en este equipo. No distribuir esa variante como validada.
