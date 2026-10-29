# Contrato de intercambio, versión 1

La web prepara una petición y conserva su ID en `requests`. Los identificadores son opacos y pertenecen a un cuaderno y una asignatura; no los regeneres ni cambies de cuaderno.

Respuesta al terminar el trabajo:

```json
{
  "kind": "mi-grado-result",
  "version": 1,
  "notebookId": "book-ejemplo01",
  "subjectId": "subject-ejemplo01",
  "sessionId": "session-ejemplo01",
  "attempt": "Comparé dos distribuciones con una pista.",
  "help": "Recibí ayuda para identificar los valores extremos.",
  "result": "Expliqué el primer caso con ayuda; el segundo queda por comprobar.",
  "nextStep": "Resolver otro caso sin pistas y justificarlo."
}
```

Sustituye los IDs del ejemplo por los del contexto recibido. Los cuatro campos narrativos son cadenas de hasta 12000 caracteres. Mantén desconocidos y límites; no incluyas tokens, contraseñas, mensajes completos o un nivel de dominio inferido. La fecha original la conserva Mi grado, no la inventa la IA.

El cuaderno intercambiable es un JSON `kind: mi-grado-notebook`, con `id`, `label`, `subjects`, `tasks`, `schedule`, `sessions`, `requests` y `settings`. El formato actual es **5**; la web y el puente aceptan los formatos 1–5. La web conserva una copia del formato anterior al migrar. El formato 2 separó temas; el 3 añadió centro y comprobaciones iniciales; el 4 incorporó punto de reanudación, duración/detalle y tipo de clase. El formato 5 conserva la identidad del traslado local y los orígenes de los temas para su actualización revisada. La migración no inventa verificaciones, práctica ni selección antigua de materiales.

Las referencias portables están en `subjects[].references`. Cada petición y registro puede conservar `referenceIds` y `referenceSnapshot`: es la selección original con sus títulos, ubicación e indicaciones, aunque después cambie el material actual. No adjunta el contenido de PDFs ni acredita lectura del enlace. El puente conserva ese material al preparar contexto y guardar la nota. Un mismo ID con un resumen o material histórico distinto no debe sobrescribir el registro anterior.

El JSON de avance sigue en versión 1: copia sus tres identificadores del contexto recibido y devuelve solo los cuatro campos narrativos. La aplicación vincula el avance al material de la petición original; no aceptes material inventado por la IA como si fuera esa selección. El regreso web→local requiere el cuaderno completo y su identidad de salida, revisión de cambios y resolución de conflictos. Un ZIP Windows, una copia ZIP y un JSON de respuesta no son un cuaderno web.

La comprobación inicial de IA usa otro tipo: `mi-grado-connection-result`, versión 1, con `notebookId`, `challenge`, `provider` y `ready: true`. Copia los identificadores del mensaje de configuración; no añadas un registro académico. La web exige revisión y declaración del usuario sobre el origen de la respuesta. No hay firma del proveedor, autenticación de cuenta, prueba de acceso continuo ni permiso para escribir en Obsidian. La nota inicial de Obsidian comprueba un archivo devuelto tras una edición indicada; su carpeta/aplicación de origen no se certifican por el navegador.

Python local devuelve comprobaciones verificables y rutas de sus dos notas. El script no actualiza la bóveda original importada ni envía peticiones a la IA; guarda un registro independiente y un enlace en el diario del cuaderno. Usa Markdown como fuente local legible, sin sobrescribir fichas manuales.
