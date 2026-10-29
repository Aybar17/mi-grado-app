# Colaborar en Mi grado

Mi grado organiza estudio y conserva intentos en Markdown local. Antes de una función nueva, explica qué tarea del estudiante facilita y cómo comprobarla en una segunda sesión.

## Ejecutar una demo

Necesitas Python 3.11 o posterior. El funcionamiento básico usa su biblioteca estándar.

```text
python escritorio.py --demo
```

La demo crea sus datos ficticios en `runtime/demo`. No uses tus apuntes para enviar pruebas o capturas a una incidencia.

## Comprobar cambios

```text
python -m unittest discover -s tests -v
python generar_panel.py --demo
node tests/frontend.cjs
```

Node solo se necesita para la comprobación de JavaScript. Para el ZIP Windows, consulta [Desarrollo](docs/DESARROLLO.md); se construye en Windows con los componentes de `requirements-build.txt`.

Prueba el recorrido de tu cambio: acción visible, respuesta del servicio, archivo guardado y recuperación después de reiniciar. Incluye teclado y pantalla estrecha si modificas la interfaz. Un botón que muestra éxito no basta como evidencia de guardado.

## Proponer una mejora o comunicar un error

Indica versión, paso, resultado esperado y resultado observado. Usa datos ficticios. No adjuntes perfiles, copias del cuaderno, archivos `.env`, claves, conversaciones o documentos docentes.

Conserva cambios pequeños y explica su propósito, validación y limitaciones. Si afecta al formato Markdown o a las copias, mantén compatibilidad y comprueba recuperación y ediciones manuales. Archivar no debe borrar notas.

El servicio escucha en `127.0.0.1`; mantén sus controles de origen y límites de entrada. No añadas APIs de pago obligatorias. Material disponible, trabajo declarado, entrega confirmada y comprensión demostrada conservan estados distintos.

## Licencia y apertura

El código está abierto bajo la [licencia MIT](LICENSE). Conserva sus avisos al reutilizarlo. La publicación abre la colaboración; las pruebas independientes del piloto siguen pendientes.

## Preparación de la beta

Consulta [la hoja de ruta](docs/HOJA_DE_RUTA.md). Buenos primeros cambios: reproducir una incidencia con datos ficticios, mejorar un paso de la guía o verificar teclado y recuperación. Incluye sistema, navegador y versión; no necesitas Windows para comunicar un error web.
