# Mejoras finales de Madrid Data Explorer · 3.1.0

## 1. Auditoría y conservación

El repositorio ya separaba búsqueda CKAN y recuperación temática, importación y preparación tabular, uniones, análisis, informes y mapas. Se inspeccionaron los módulos, los activos cartográficos, la configuración de Streamlit y la suite antes de editar. La referencia fue **85 pruebas aprobadas y una omitida** por ser optativa de catálogo en vivo. La sesión ya versionaba las derivaciones y recordaba ciertas preferencias. Los extractos oficiales y la capa municipal existente eran la base de los tres estudios reproducibles.

Los cambios locales previos en `.DS_Store` y el ZIP de publicación se conservaron. El trabajo nuevo queda en el árbol local para revisión.

## 2. Home e indicador de carga

**Antes.** Explorar conservaba la última pregunta. Volver desde el mapa o el análisis abría esa pregunta o el último estudio. Las operaciones de importación, búsqueda y planificación usaban `st.spinner`. El repositorio carecía de una animación de personas. Streamlit administra su indicador de ejecución en el marco de la aplicación y Community Cloud administra la espera anterior al arranque. La URL publicada devolvió una redirección a acceso durante la comprobación, por lo que no se pudo confirmar visualmente cuál de esas dos superficies mostraba la animación descrita. [Interfaz de Streamlit](https://docs.streamlit.io/develop/concepts/architecture/app-chrome) · [Hibernación en Community Cloud](https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app#app-hibernation)

**Después.** `interface.home` selecciona Explorar y limpia la pregunta y el estudio que ocupaban la portada. Conserva el espacio analítico. Home se muestra con un icono de casa en la barra flexible de navegación. `loading.loading` coloca una silueta junto a la operación que antes usaba el spinner. La silueta SVG tiene fondo transparente, gira 360° y desactiva la animación si el sistema solicita movimiento reducido. El estado accesible se limpia al terminar o si la operación falla. La posición y el tamaño de los indicadores propios corresponden a los controles locales. Las dimensiones y posición exactas del indicador del alojamiento quedan fuera de ese control.

**Archivos.** `interface.py`, `loading.py`, `app.py`, `explore_view.py`, `demo_data/build_spatial_assets.py`, `demo_data/madrid_silueta.svg`. El generador disuelve los polígonos del IGN y simplifica el contorno exterior. El SVG de unos 6 KB se sirve desde el propio repositorio.

## 3. Buscador general y preparación

**Antes.** El motor consultaba por temas y ofrecía resultados automáticos para un repertorio acotado. La coincidencia de palabras genéricas podía favorecer fuentes relacionadas al ordenar una pregunta de varios indicadores. Las tablas de series se podían analizar, pero conseguir dos cambios comparables por municipio requería una transformación manual fuera del flujo.

**Después.** `interpret` amplía sinónimos temáticos, reconoce alias municipales, intervalos explícitos, límites abiertos y expresiones de años recientes. `retrieve` consulta CKAN en paralelo, descarta coincidencias solo geográficas y destaca fuentes distintas por tema con preferencia por términos canónicos en el título. `render_candidates` distingue respuesta automática, necesidad de combinación, coincidencias relacionadas y ausencia de evidencia suficiente. Los enlaces de los extractos oficiales y la descarga de CKAN conservan la misma trazabilidad. Las sugerencias de claves se basan en las columnas leídas y las de unión se comprueban sobre las tablas.

`data_tables.transform` añade el filtro reversible de valores. `data_tables.period_change` construye una observación por entidad y conserva los registros incompletos como ausentes en el resultado porcentual. Normaliza códigos municipales reconocidos, impide duplicados del par entidad–periodo, calcula cambios absolutos y requiere base positiva para porcentajes. La comparación registra periodo, variable, fórmula y ausencias. Los metadatos y el historial de ambas tablas acompañan a la unión. Los controles de periodos y variables descartan selecciones que quedan fuera de sus nuevas opciones.

**Archivos.** `discovery.py`, `explore_view.py`, `territories.py`, `data_tables.py`, `app.py`, `analysis_workspace.py` y `interface.py`. El cliente existente en `catalog.py` conserva sus límites y validación de fuentes. `assistant.py` sigue siendo opcional.

## 4. Investigación nueva y verificable

La [guía del equipo](GUIA_EQUIPO.md#investigación-reproducible--crecimiento-poblacional-y-paro-registrado) describe el recorrido por widgets. Las fuentes son los extractos municipales verificados de padrón total y total de paro registrado. Se usan los extremos 2018 y 2025 comunes, y se calcula `100 × (final − inicial) / inicial` para cada fuente antes de cruzarlas por INE. Se obtiene una unión uno a uno con **179 pares completos**, sin pérdidas. La fecha de referencia del padrón es 1 de enero y la del paro 31 de marzo. [Padrón municipal](https://datos.comunidad.madrid/dataset/padron_por_sexo) · [Paro registrado municipal](https://datos.comunidad.madrid/dataset/302038)

| Resultado | Estimación |
| --- | --- |
| Pearson | r = **0,461633**, IC 95 % [0,337835; 0,569729], p = 7,82 × 10⁻¹¹ |
| Spearman | ρ = **0,439129**, p = 7,79 × 10⁻¹⁰ |
| Regresión lineal simple | Pendiente **2,342589**, IC HC3 [0,274894; 4,410284], p = 0,02638, R² = **0,213105** |
| Moran del crecimiento | I = **0,254490**, p = 0,001 |
| Moran del cambio del paro | I = **0,197528**, p = 0,002 |
| Moran de residuos | I = **0,120402**, p exploratorio = 0,018 |

Las p de Moran usan 999 permutaciones y semilla 42. Los cambios del paro son variaciones del número de personas registradas. La asociación lineal positiva puede coexistir con descensos absolutos del paro. El modelo describe diferencias entre municipios y no establece causas. Los efectos de escala, los denominadores pequeños, el contexto de 2020 y la dependencia espacial limitan la inferencia convencional. HC3 ajusta por heterocedasticidad y no corrige la dependencia espacial.

El estudio se ejecuta a partir de herramientas generales. El recorrido automatizado ejercita el buscador, la importación de los extractos, el diagnóstico, la comparación temporal, la unión, los análisis y las descargas, además de la reapertura del proyecto. La consulta real a CKAN se verifica por separado para que la prueba de interfaz sea reproducible sin red.

## 5. Persistencia del proyecto

**Antes.** Se descargaban tablas o informes individuales. La sesión del navegador era el único lugar donde convivían las tablas, el historial y los análisis.

**Después.** `save_project` y `load_project` escriben o leen un ZIP con `manifest.json` de versión 1, tablas Parquet y figuras Plotly representadas en JSON. `remember_result` retiene el último resultado de cada método por tabla con un máximo total de 30. `projects_panel` ofrece Guardar, Abrir y Cerrar. La restauración valida el archivo antes de reemplazar el espacio. Se conservan tipos, códigos textuales, fechas, metadatos, linaje, resultados estadísticos, selección municipal y ajustes de las principales vistas con clave explícita. Las figuras guardadas y los informes se vuelven a exportar desde **Resultados guardados**.

El formato utiliza datos y metadatos declarativos y carece de pickle. Las rutas válidas se enumeran, el ZIP se lee en memoria y se comprueban duplicados, tamaños comprimidos y expandidos, columnas, celdas y versión. Se aplican los límites de 15 MB comprimidos, 96 MB expandidos, 12 tablas y 4 millones de celdas por grupo presupuestado. El ZIP contiene el contenido tabular importado y sus versiones, no una copia byte a byte de los Excel o CSV recibidos. La restauración requiere el mismo esquema de proyecto y una versión compatible de la aplicación. Las vistas de catálogo, importaciones pendientes y otros controles transitorios quedan fuera del archivo.

**Archivos.** `projects.py`, `project_view.py`, `interface.py`, `app.py`, `analysis_workspace.py`, `demos.py`. PyArrow ya estaba en producción.

## 6. Estadística espacial

`build_spatial_assets.py` calcula la lista de contigüidad reina de los 179 polígonos simplificados del IGN. Una intersección de fronteras en punto o tramo, o un solape residual de simplificación, forma un par. El grafo de la capa actual contiene **468 pares**, cubre los 179 códigos y registra el hash del GeoJSON. `municipal_edges` verifica esa correspondencia. El grafo no pretende representar tiempos de viaje ni accesibilidad.

`moran` obtiene la submatriz de municipios observados, excluye códigos inválidos, faltantes y municipios sin vecinos en esa selección y estandariza los pesos por fila. Rechaza el grano duplicado, menos de cuatro municipios conectados o variación nula. La prueba bilateral permuta los valores sobre el grafo fijo, compara la distancia al valor esperado `−1/(n−1)` y aplica la corrección de Monte Carlo `(extremos + 1)/(permutaciones + 1)`. El dispersograma muestra indicador estandarizado frente al promedio vecinal y la pendiente de Moran. Las regresiones lineales pueden aplicar el mismo diagnóstico a los residuos completos que entraron en el ajuste. Su prueba se interpreta como exploratoria, pues los residuos ajustados pueden no ser intercambiables.

**Archivos.** `spatial_stats.py`, `statistical_engine.py`, `analysis_workspace.py`, `demo_data/build_spatial_assets.py`, `demo_data/vecindad.json`. El cálculo en producción usa NumPy y pandas existentes. Para regenerar los activos tras cambiar la geometría, instala `requirements-dev.txt` y ejecuta `python demo_data/build_spatial_assets.py`.

**Pendiente.** Moran local, corrección por comparaciones múltiples, clústeres significativos y mapas LISA. El diagnóstico global disponible no asigna significación a municipios concretos.

## 7. Experiencia, pruebas y despliegue

Las herramientas se añadieron a la navegación y a los paneles existentes. Se conserva el modo oscuro y la portada. Los controles complejos se agrupan en expansores. El HTML de informes, gráficos y mapas se construye al descargar para evitar generar el mismo documento en cada interacción.

La [matriz de validación](VALIDACION_FINAL.md) registra pruebas de estado, consultas, comparaciones, uniones, persistencia, estadísticas espaciales e invariantes de los tres estudios. El servidor local se comprobó con el comando de Streamlit. El navegador de pruebas agotó el tiempo de acceso, por lo que queda pendiente la revisión visual en móvil y en la app desplegada. La versión publicada solo cambiará tras la revisión y el envío del equipo a GitHub.
