# Empieza con Mi grado

La preparación 0.9 permite usar el cuaderno sin Obsidian ni IA. El enlace publicado sigue en 0.7.1 hasta una entrega posterior; consulta la versión visible.

## Web 0.9

1. Abre Plan de estudio y pulsa Añadir mi asignatura. Basta el nombre; los apuntes son opcionales.
2. En Mis tareas añade una tarea. Para un examen elige tipo Examen, fecha vigente y si la has contrastado. Un cambio propuesto no sustituye la fecha.
3. Indica tus minutos de hoy en el plan. Prepara un ejercicio o ve a Registrar avance y escribe intento, ayuda, resultado y próximo paso.
4. Cierra y vuelve a abrir el navegador: consulta el avance. En Copias descarga JSON y comprueba que está en Descargas. Markdown sirve para leer o llevarlo a tus notas.
5. Si quieres preparar varios días, abre Preparar un examen con mi disponibilidad en Mis tareas. Elige cada día en el calendario, indica sus minutos y pulsa Añadir día. Con 0 marcas un día en que no puedes estudiar. Puedes cambiar o quitar días; los borradores de cada examen se conservan por separado mientras la pestaña siga abierta. Revisa la propuesta y pulsa Añadir estos bloques. Volver a proponer requiere revisar de nuevo.

No necesitas aportar un tema para organizar o registrar un intento. Para resolver un ejercicio con IA, aporta su enunciado real. El programa no lo ha leído por guardar su nombre.

## Conexiones opcionales

En Configurar Mi grado puedes indicar grado/FP, centro y bóveda. Para comprobar Obsidian necesitas indicar el nombre de la bóveda y devolver la nota de prueba editada. Para comprobar la IA sigue su intercambio separado; no requiere Obsidian ni una bóveda. No se verifican por usar el cuaderno y no son autenticación de proveedor. Cambiar bóveda o proveedor invalida la comprobación correspondiente.

## Windows

Extrae el ZIP completo y abre Abrir Mi grado.cmd; no necesitas instalar Python. La carpeta de apuntes y el perfil son independientes del paquete. Para actualizar, cierra el programa, conserva una copia y extrae la entrega nueva en otra carpeta. Copias restaura en un cuaderno separado; el original se conserva.

Desde código se necesita Python 3.11 o posterior: `python escritorio.py --demo` para datos ficticios, `python escritorio.py` para configurar tus apuntes. La web no equivale a un acceso directo a tus carpetas.

## Recuperación

Si aparece Guardado pendiente, conserva el texto y reintenta. No borres el navegador para resolver un fallo. Al restaurar JSON se conserva el cuaderno anterior; las conexiones se vuelven a verificar en ese dispositivo, pero no bloquean el estudio básico.

Las versiones antiguas pueden omitir los nuevos metadatos de examen al reexportar. Conserva una copia original y usa esta entrega o posterior para el recorrido de ida y vuelta con tipos de examen y propuestas de cambio.

## Evitar sobrecarga al preparar un examen

Indica el tiempo total que todavía puedes dedicar a estudiar ese día, incluyendo los bloques pendientes del plan. Si ya has estudiado hoy, indica el tiempo que te queda. La propuesta descuenta las tareas pendientes ya planificadas de tus asignaturas activas; no vuelve a añadir el tiempo ocupado. Si una tarea no tiene duración estimada, ese día queda por revisar. Los días sobrecargados se señalan sin borrar tus tareas. Marcar una tarea como realizada o archivada cambia el plan declarado, no demuestra aprendizaje. Los cambios siguen necesitando revisión antes de guardarse.
