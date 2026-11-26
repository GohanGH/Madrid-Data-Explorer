# Registro de cambios

## Madrid Data Explorer 4.0 — 26 de noviembre de 2026

### Importación por lotes

- **Datos → Catálogo** permite marcar varias fichas y elegir más de un recurso por ficha. La selección del proyecto activo se conserva al cambiar la búsqueda, la página o los filtros. **Importar seleccionados** incorpora el lote a la biblioteca existente.
- La importación del catálogo y de archivos locales muestra el progreso y el resultado de cada elemento. El lote continúa si uno falla y los recursos fallidos del catálogo quedan seleccionados para reintentar. Los recursos ya registrados por URL y los archivos locales idénticos del mismo formato se omiten como duplicados.

### Interfaz y arquitectura

- Siete espacios de trabajo con proyecto activo y biblioteca persistentes. Home abre el catálogo, la importación y la gestión de proyectos. Los recorridos históricos se conservan como regresiones y documentación técnica.
- Catálogo con búsqueda literal y temática, previsualización, importación múltiple y acceso al archivo oficial. La biblioteca incluye perfiles por variable, filtros, subconjuntos, conservación del original y revisiones de fuente.
- Preparación visual mediante recetas tipadas. Cada confirmación crea una versión con parámetros y dependencias. El historial permite comparar, deshacer, rehacer, reaplicar y guardar ramas o revisiones.

### Nuevas funcionalidades y correcciones

- Uniones encadenadas con sugerencias de claves, cardinalidad, muestras de registros sin pareja y confirmación de granularidad. Se conserva la protección frente a cruces que multiplican observaciones.
- Análisis configurable por tabla y filtro. Se incorporan Kendall, Fisher 2×2, matrices de correlación con N, descriptivos agrupados, tamaños de efecto, términos categóricos, interacciones, autocorrelación temporal, descomposición y componentes principales.
- Constructores de gráficos y mapas para tablas arbitrarias. Se conservan el mapa municipal oficial, los cortes de color y Moran global. Se añaden puntos y densidad WGS84 y el retorno del mapa a los registros.
- Cuaderno con resultados múltiples, anotaciones, organización, metodología y avisos de revisión. Constructor de informes HTML autocontenidos y persistencia de borradores, figuras y archivos originales.

### Compatibilidad, dependencias y límites

- Continúan Python 3.11 como referencia y `app.py` como entrada. NumPy se declara como dependencia directa de los módulos de análisis y visualización.
- Los accesos predeterminados de 3.1 salen de la navegación. El lector 4.0 abre los proyectos ZIP v1 y guarda en formato v2. Para compartir archivos v2, ambos miembros del equipo necesitan 4.0.
- El PDF se obtiene al imprimir el HTML en el navegador. LISA, Moran local, regresión binomial negativa y clustering quedan pendientes. Las revisiones identifican resultados históricos y se recalculan de forma explícita. [Arquitectura y límites](docs/MDE_4.md) · [Validación](docs/VALIDACION_FINAL.md)

## 3.1.0 — 26 de noviembre de 2026

### Funciones y experiencia

- **Home** vuelve a la portada original. Las tablas, el historial reversible y los resultados siguen disponibles en la misma sesión.
- Las operaciones de carga controladas por la aplicación muestran una silueta giratoria de la Comunidad de Madrid, derivada del GeoJSON del IGN. El indicador respeta la preferencia de movimiento reducido.
- El buscador amplía vocabulario y periodos, diversifica fuentes por tema y explica si puede responder, requiere un cruce, solo encontró fuentes relacionadas o carece de datos suficientes.
- La preparación permite conservar valores de una categoría y comparar dos periodos por entidad. La comparación guarda los niveles inicial y final, el cambio absoluto y la variación porcentual como una tabla derivada.
- **Mis proyectos** guarda y abre archivos ZIP portátiles con tablas Parquet, configuración JSON, procedencia y resultados. Los informes y figuras del espacio de análisis se preparan al descargarlos.
- El motor general ofrece Moran global con permutaciones reproducibles, descarga de pares vecinos y diagnóstico exploratorio de residuos en regresiones lineales. La regresión lineal simple incluye una figura del ajuste.

### Correcciones y compatibilidad

- Las preferencias que pierden validez después de cambiar un filtro se descartan antes de mostrar su selector. Las tablas combinadas conservan los metadatos de ambas fuentes.
- Los estudios originales conservan sus extractos, definiciones y resultados. Se mantiene la configuración de dependencias de producción. La generación de activos cartográficos usa Shapely, ya incluido entre las dependencias de desarrollo.
- El formato de proyecto empieza en la versión 1. La importación de datos y las descargas anteriores siguen disponibles.
- El ZIP conserva el último resultado por método y tabla, con un máximo de 30. Los ZIP de hasta 15 MB tienen límites de expansión y de tamaño de tabla. Moran es global. Moran local y mapas LISA quedan pendientes.
- La animación de espera del alojamiento queda fuera del control del código de la aplicación. Consulta la [validación](docs/VALIDACION_FINAL.md) para conocer el alcance de las pruebas.
