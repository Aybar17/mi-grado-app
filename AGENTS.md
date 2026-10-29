# Trabajo en Mi grado

- El repositorio contiene código y ejemplos ficticios. Las bóvedas configuradas son fuentes externas privadas; no las copies, indexas en Git ni publiques.
- Lee únicamente las fuentes pertinentes a la tarea. El mapa del panel recupera títulos y enlaces; no autoriza una lectura completa de todas las notas.
- `config.local.json` y `runtime/` son locales e ignorados. No añadas sus contenidos con `git add -f`.
- Conserva Markdown como fuente canónica. Un panel generado es reconstruible; generar la página no modifica las fichas ni demuestra aprendizaje.
- Para capturas utiliza el guardado protegido: identificador estable, comparación de huellas, copia de seguridad, comprobación de nota, diario y punto. No sustituyas el contenido editado a mano durante un reintento.
- Los ejemplos no pueden incluir nombres de personas reales, rutas de equipos, conversaciones, resultados académicos ni material docente con derechos de terceros.
- Comprueba `python -m unittest discover -s tests -v` y `python generar_panel.py --demo` antes de proponer cambios. Revisa el conjunto exacto que se va a publicar.
- El servidor escucha solo en `127.0.0.1`. Mantén validación de Host/Origin y límites de peticiones. No lo conviertas en servicio público sin un diseño de acceso y almacenamiento apropiado.
- El código de producción debe ejecutarse desde este checkout. Los lanzadores externos pueden delegar aquí; evita mantener una segunda copia editable del código.
