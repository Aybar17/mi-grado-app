# Procedencia

La plantilla y la persistencia se adaptaron de la aplicación local **Mi grado** preparada en sesiones de trabajo del usuario. El módulo `memoria.py` procede del motor de la skill local **cerrar-sesion-memoria** (`scripts/memoria.py`), incorporado como dependencia propia para que la distribución no dependa de una instalación de Codex ni de esa skill.

Esta adaptación elimina rutas y configuración personal, limita la búsqueda de enlaces a las fuentes autorizadas y conserva comparación de huellas, copias, parches concretos e identificadores estables. Los datos y fichas de `examples/demo` se escribieron expresamente como ejemplos sintéticos. No se incorporan bancos del profesor, bóvedas reales, capturas privadas, logs o conversaciones.

El código utiliza la biblioteca estándar de Python y APIs del navegador. No incorpora SDKs comerciales ni requiere servicios de pago. La distribución Windows portable contiene el intérprete oficial Python sin modificar sus binarios, Tcl/Tk y datos horarios de [tzdata](https://pypi.org/project/tzdata/), con sus avisos de licencia en el paquete. Se comprueba la firma del intérprete antes de construirla. La variante experimental [PyInstaller](https://pyinstaller.org/) puede quedar bloqueada por el control de aplicaciones de Windows y no es la descarga recomendada. El conector opcional consulta la API local de [Ollama](https://docs.ollama.com/api/introduction); Ollama y sus modelos no se distribuyen en el ZIP. El propietario eligió la licencia MIT el 13/10/2026. El código de Mi grado y su documentación se distribuyen bajo LICENSE; los componentes de terceros conservan sus propias licencias y avisos.

La copia de la licencia Tcl 8.6.15 procede del [archivo oficial de la versión](https://github.com/tcltk/tcl/blob/core-8-6-15/license.terms); se incluye cuando el intérprete no la trae por separado.

La portada utiliza las familias [DM Sans](https://github.com/google/fonts/tree/main/ofl/dmsans) y [Lora](https://github.com/google/fonts/tree/main/ofl/lora), distribuidas con sus respectivos avisos de la SIL Open Font License en `web/fonts/`. Se sirven desde el propio sitio.
