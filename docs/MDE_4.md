# Madrid Data Explorer 4.0

Un proyecto activo reúne los datos originales, las versiones que el equipo construye y los resultados que decide conservar. El punto de partida puede ser una búsqueda, un archivo, un proyecto previo o una tabla de trabajo. La misma biblioteca está disponible al preparar, analizar y visualizar.

## Arquitectura

| Capa | Módulos | Responsabilidad |
| --- | --- | --- |
| Navegación y contexto | `app.py`, `workspace_views.py`, `workspace.css`, `workspace_controls.py` | Entrada Streamlit, portada, navegación persistente, tabla activa y controles reutilizables. |
| Acceso a datos | `library_view.py`, `catalog.py`, `discovery.py`, `dataset_cards.py`, `data_tables.py` | CKAN, importaciones en lote, originales, fichas, búsqueda, inspección y filtros de biblioteca. |
| Preparación y versiones | `preparation_view.py`, `transformations.py`, `joins.py`, `workspace_state.py` | Recetas declarativas, vistas previas, cardinalidad, cambios de versión y dependencias. |
| Análisis | `analysis_workspace.py`, `profiling.py`, `statistical_engine.py`, `spatial_stats.py` | Roles, orientación, validación de variables, cálculo, diagnóstico de modelos y vecindad municipal. |
| Visualización | `visualization_view.py`, `visualizations.py`, `map_view.py`, `maps.py`, `territories.py` | Configuración y construcción de figuras, capa municipal, clasificaciones geográficas y exportación. |
| Cuaderno y proyectos | `notebook_view.py`, `reports.py`, `project_view.py`, `projects.py` | Resultados múltiples, edición de informes, archivos originales, tablas Parquet, figuras y registro JSON versionado. |

El diseño usa el panel lateral para el proyecto, la tabla y las herramientas. El área central reserva el ancho para datos y figuras. El análisis y los constructores sitúan juntos sus parámetros y resultados. En pantallas pequeñas se puede plegar el panel y usar el acceso **Home** de la cabecera. El tema oscuro, la escala cromática de gráficos y el relieve del panel siguen la paleta de la aplicación. Las operaciones largas muestran el indicador de carga nativo y el estado de preparación.

## Descubrimiento y biblioteca

La búsqueda literal utiliza CKAN con paginación y facetas. El lenguaje natural combina vocabulario temático, territorio, años y términos de consulta para recuperar y ordenar candidatas. La selección de un año o una cobertura en el formulario se aplica a las fichas recuperadas que sí declaran ese dato. Revisa el contenido tabular cuando la ficha tenga metadatos incompletos. El catálogo permite previsualizar el recurso antes de importarlo y agrupar hasta doce recursos por solicitud. El origen oficial y la descarga se identifican por dominio y URL autorizados.

La biblioteca reconoce tablas originales, transformadas, combinadas y derivadas. Cada tabla incluye dimensiones, variables, clasificación, desglose de calidad, fuente, fecha y cobertura cuando constan. La clave candidata de observación se infiere y se puede contrastar con los datos. El explorador estima descriptivos pertinentes por rol, permite ajustar la clasificación y abre las operaciones de conversión o renombrado con la variable seleccionada. Una revisión oficial compara el SHA‑256 del recurso y crea otra versión previa confirmación.

## Preparación y procedencia

Una receta contiene el identificador de operación, columnas, valores y parámetros explícitos. El motor valida los argumentos y calcula la vista previa al solicitarla. Las operaciones incluyen selección y orden, filtros tipados, recodificación, conversiones regionales, fechas, normalización, códigos INE, marcas por rango intercuartílico, fórmulas con operandos seleccionables, agregaciones, pivotes y series temporales. Para una expresión con varias etapas, guarda resultados intermedios como nuevas variables. La comparación temporal conserva ambos niveles y ambos cambios. Se excluyen denominadores de tasa ausentes o no positivos e iniciales nulos en la variación porcentual.

En las uniones se eligen dos tablas y una o varias claves ordenadas. Las sugerencias usan nombre, rol, tipo y solapamiento de una muestra. La vista previa calcula cardinalidad, claves sin pareja, señales de granularidad y ejemplos. Se normalizan las claves territoriales reconocidas. Las uniones muchos a muchos que multiplicarían observaciones se rechazan. Al encadenar el resultado en otro cruce se conservan sus claves y procedencia.

Cada versión tiene un identificador, una instantánea y los enlaces a sus tablas de origen. El historial muestra parámetros y permite comparar o volver a una versión. Deshacer retira una versión de la biblioteca activa y rehacer la recupera. Se puede reaplicar una receta sobre una tabla compatible. Al confirmar una transformación o unión sobre las mismas entradas se puede guardar una rama o designar una revisión. El cuaderno comprueba si la tabla de un resultado o un antecesor se retiró o recibió una revisión. Los resultados históricos permanecen consultables con su aviso. Para actualizar el análisis, el usuario reconstruye las operaciones pertinentes y ejecuta de nuevo.

## Análisis y visualización

El motor local conserva los descriptivos, frecuencias, pruebas de grupos, asociaciones, regresiones, análisis temporal y diagnóstico espacial. Añade Kendall, Fisher exacta para tablas 2×2, matriz de correlación con N por par, descriptivos agrupados, intervalos y tamaños de efecto en comparaciones compatibles, términos categóricos e interacciones en modelos, ACF, descomposición temporal aditiva y componentes principales. El perfil permite ver roles, casos incompletos y variabilidad. Después de filtrar, el análisis informa de las exclusiones y usa los casos válidos para cada método. Los modelos vigilan colinealidad, convergencia, separación y sobredispersión cuando corresponda. Moran global y el diagnóstico de residuos utilizan vecindad municipal, con número de permutaciones y semilla registrados.

La interpretación distingue exploración, contraste y ajuste. Un análisis ecológico, una asociación o un valor p por sí solos no establecen una causa. La comparabilidad de las definiciones y denominadores exige revisar las fichas de origen.

El constructor combina ejes, métricas, grupos, facetas, paletas, filtros y agregaciones de acuerdo con el tipo de gráfico. Las vistas ligeras se actualizan con sus parámetros. Las densidades, las matrices, los polígonos propios y las vistas de tablas grandes se generan a petición. La coropleta local usa la geometría oficial de los 179 municipios, muestra las ausencias y exige resolución de filas duplicadas antes de colorear. Puede devolver al explorador los registros de los municipios seleccionados. Las coordenadas WGS84 permiten puntos o densidad y una capa municipal opcional. Estas vistas usan un fondo oscuro incrustado con una URL estable para conservar el estilo durante las actualizaciones y mostrar el HTML sin peticiones de teselas. Un GeoJSON WGS84 aportado por el usuario amplía la cobertura a otros polígonos.

## Cuaderno, informes y persistencia

Cada resultado recuerda la tabla y su instantánea, configuración, momento de ejecución, datos, figuras y notas. El usuario puede añadir interpretación, ordenar, duplicar, renombrar y retirar entradas. Un borrador reutiliza los resultados seleccionados y añade contexto, objetivos, metodología, discusión, limitaciones, conclusiones y fuentes. El HTML incluye el código de las figuras, los datos representados, la procedencia y los avisos de revisión. Las tablas del informe muestran hasta 500 filas por resultado. El CSV descarga todos los datos del resultado. El navegador puede imprimir el HTML en PDF.

En **Mis proyectos**, la exportación v2 combina un manifiesto JSON, tablas Parquet y archivos originales. Se validan nombres, referencias, tamaños, tipos y versiones antes de reemplazar el proyecto. Los ZIP v1 de la 3.1 son importables. Las versiones v1 conservan los datos que archivaban, aunque su formato carecía de las cargas originales y del cuaderno completo. La colaboración consiste en compartir y restaurar un archivo. Cada sesión trabaja con su propia copia y el navegador descarga los proyectos al equipo local.

## Límites de diseño

- La importación admite hasta 15 MB, 150.000 filas, 300 columnas y 1,5 millones de celdas por tabla de origen. La sesión admite hasta 30 versiones, 4 millones de celdas y 24 MB acumulados de archivos originales. El ZIP resultante admite 15 MB comprimidos y 96 MB expandidos. El cuaderno admite 48 resultados y 12 borradores por proyecto.
- El explorador presenta las primeras 5.000 filas filtradas. Los gráficos con más de 25.000 puntos usan una selección sistemática visible en la metodología. Los mapas puntuales exigen filtrar a 25.000 o menos. La coropleta municipal, los puntos y la densidad usan WebGL. Los polígonos aportados admiten hasta 5 MB y requieren el GeoJSON para volver a calcular la figura.
- El reuso de una receta se aplica a operaciones compatibles de una tabla. Las concatenaciones y uniones se reconstruyen con sus controles y fuentes. La reproducción de una rama revisada es explícita. Los ZIP no sincronizan ediciones paralelas.
- Moran local, LISA, binomial negativa y clustering quedan pendientes. La exportación de resultados usa CSV y HTML. El PDF se genera con el diálogo de impresión.
- Conservados para comparación y regresión, `demos.py` y `explore_view.py` contienen recorridos históricos. La aplicación arranca por el espacio de investigación general. El alcance y las comprobaciones constan en la [validación](VALIDACION_FINAL.md).
