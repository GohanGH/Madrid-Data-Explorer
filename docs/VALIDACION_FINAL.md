# Validación de Madrid Data Explorer 4.0

## Referencia local y ejecución

La auditoría partió de la 3.1.0 local, con los cambios de DATAMAD aún por publicar. Se conservó una copia de los archivos de referencia fuera del árbol de trabajo. La rama `main` y la referencia local `origin/main` apuntaban a `96e2dc9`. La tabla distingue la ejecución inicial de la validación de la 4.0.

| Comprobación | 3.1.0 local | 4.0 local |
| --- | --- | --- |
| `python -m ruff check .` | Correcta | Correcta |
| `python -m pytest -q` en Python 3.11 | 98 aprobadas, 1 omitida | 133 aprobadas, 1 omitida |
| `MDE_RUN_INTEGRATION=1 python -m pytest -q -m integration` | Una prueba registrada en la validación anterior | 1 aprobada, 133 excluidas por el filtro |
| Descubrimiento y trabajo | Búsqueda con consultas validadas, análisis y mapa en apartados propios | Biblioteca general, recetas, versiones, gráficos, mapas y cuaderno unidos por un proyecto activo |
| Archivo de proyecto | Formato v1, resultados por método y tabla | Formato v2, múltiples ejecuciones, originales, figuras, notas e informes. Se abrió un archivo escrito por la 3.1 |
| Dependencias de Python | Python 3.11 en CI | Requisitos conservados, `python -m pip check` sin dependencias rotas |

Las pruebas de interfaz de Streamlit usan los controles del espacio de trabajo. Se actualizaron las comprobaciones que antes abrían rutas predeterminadas y se mantuvieron los resultados históricos, uniones, cartografía, riesgo metodológico, procedencia y persistencia. Los archivos `tests/test_research4.py` y `tests/test_final_workflow.py` recorren las cinco investigaciones. `tests/test_workspace4.py` cubre tablas arbitrarias, recetas, métodos y archivos antiguos. `tests/test_app.py` comprueba, entre otros, que una revisión deja visibles los resultados históricos con una advertencia.

En una prueba adicional del buscador en vivo, la consulta «visitas población atendida bibliotecas públicas municipios» mostró las dos fichas objetivo entre las tres primeras. «paro registrado crecimiento población municipios» mostró el padrón por sexo y el total de paro registrado entre las cinco primeras. La búsqueda habitual y la prueba de integración ejercitan CKAN y la carga de recursos por separado.

## Investigaciones reproducidas

Las preguntas de esta sección son casos de aceptación. Se recorrieron por biblioteca, preparación, combinación, análisis, visualización y descarga. En los cuatro casos de los ámbitos anteriores se eligieron los extractos oficiales locales en **Datos → Catálogo** para reproducir el corte. Para bibliotecas se usaron fichas reales y copias del corte publicado, con la consulta y la descarga oficiales verificadas aparte. Cada caso guardó resultados e informe. La documentación de origen conserva las definiciones, valores y referencias históricas. [Resultados DATAMAD](../RESULTADOS_DATAMAD.md) · [Metadatos de los extractos](../demo_data/sources.json)

| Pregunta y selección | Recorrido por las herramientas generales | Resultado reproducido |
| --- | --- | --- |
| **Envejecimiento y centros de atención primaria, 2024** | Importar Censo anual por edad, padrón y recuento de consultorios locales y centros de salud. Filtrar las bandas desde 65 años, agrupar población por código y año, cruzar con el total censado y usar escala 100. Cruzar recuentos con padrón y construir centros por 10.000 habitantes. Unir los dos indicadores y guardar Pearson, Spearman, dispersión y coropleta. | 179 municipios y 422 centros. Pearson **0,600503** y Spearman **0,505204**. Son asociaciones entre municipios. La capacidad y los desplazamientos quedan fuera del indicador. |
| **Evolución del paro registrado, marzo de 2018–2025** | Importar paro y padrón. Agrupar la serie de ocho años por año para obtener totales. Seleccionar Madrid, Getafe y Alcalá de Henares para **Series temporales → Evolución y cambios**. Filtrar paro y padrón a 2025, unir por código y año y guardar el mapa de recuentos por 1.000 residentes. | 1.432 registros municipales en la serie completa y 24 en las tres series seleccionadas. Total **380.051 → 293.817**, cambio **−86.234 (−22,69 %)**. El indicador del mapa usa residentes empadronados como denominador. |
| **Renta municipal y envejecimiento, 2024** | Unir renta disponible bruta por habitante con el porcentaje calculado a partir del Censo por edad. Usar el código y el año. Ejecutar Pearson y una regresión lineal simple, con renta como respuesta. Guardar dispersión, mapa de renta e informe. | 179 pares. Pearson **−0,109310** y R² **0,011949**. La regresión histórica conserva Spearman **−0,151285** como comprobación independiente. El ajuste explica alrededor del 1,2 % de la variación observada. |
| **Crecimiento de la población y cambio del paro, 2018–2025** | Encontrar padrón y paro. En cada tabla, comparar 2018 y 2025 por municipio y guardar cambios. Unir por código municipal y ejecutar Pearson, Spearman y regresión lineal con diagnóstico espacial de residuos. Guardar dispersión, mapa de crecimiento e informe. Descargar el ZIP, iniciar un proyecto vacío y restaurarlo. | 179 pares. Pearson **0,461633**, Spearman **0,439129**, R² **0,213105** y pendiente **2,342589**. Moran de residuos **0,120402**, p exploratoria **0,018** con 999 permutaciones y semilla 42. El ZIP recuperó tablas, método, modelo e informe. |
| **Población con servicio bibliotecario y visitas, 2025** | Buscar bibliotecas públicas en el catálogo e importar en lote los dos CSV. Si se usa el recurso completo, filtrar `Tipo territorio = Municipios` y `Año = 2025` en cada tabla. Renombrar `Valor`, unir por `Código territorio` y `Año`, ejecutar Pearson y Spearman y guardar dispersión, mapa de visitas e informe. | 179 pares con **7.027.647 habitantes atendidos** y **12.457.272 visitas**. Pearson **0,989836** y Spearman **0,967979**. Los archivos de prueba verifican sumas de control para reproducir el corte. |

### Fuentes y sensibilidad del caso de bibliotecas

Los CSV se consultaron el 26 de noviembre de 2026. Las fichas atribuyen los datos a la Estadística de Bibliotecas de la Consejería de Cultura, Turismo y Deporte y declaran licencia Creative Commons Attribution. La población atendida es la población que dispone de una biblioteca pública o un punto de servicio móvil en el territorio. Las visitas son recuentos de actividad. Las extracciones conservaron las siete columnas y las 179 filas municipales de 2025 de cada CSV, incluidos 79 municipios con cero en ambas medidas. [Población atendida](https://datos.comunidad.madrid/dataset/1916180) · [Visitas](https://datos.comunidad.madrid/dataset/1928360) · [Origen, corte y sumas SHA‑256](../tests/fixtures/bibliotecas_fuentes.json)

Excluyendo Madrid capital mediante un filtro, la comprobación de sensibilidad deja 178 pares y da Pearson **0,788980** y Spearman **0,967385**. Es una asociación entre dos recuentos municipales, sensible al tamaño de los municipios. En particular, Madrid reúne 3.506.730 de los habitantes atendidos y 5.244.335 de las visitas. Los agregados geográficos y los periodos anteriores de Madrid requieren verificar definiciones y cobertura.

## Rendimiento y arranque

Se inició `python -m streamlit run app.py` en el puerto local 8504. El punto de salud `/_stcore/health` respondió `ok`. Se usó un lote sintético de 100.000 filas y cuatro columnas para medir una ejecución en frío de preparación y figuras en el equipo de desarrollo. Se observaron **0,012 s** para agrupar en 100 categorías, **3,088 s** para unir 100.000 pares uno a uno y **0,374 s** para construir la dispersión con 25.000 marcas. Son tiempos locales del motor. El renderizado y la red añaden su propio coste. Los límites de memoria y las operaciones que se ejecutan a petición constan en la [arquitectura](MDE_4.md#límites-de-diseño).

## Comprobación en navegador

Chrome automatizado con Playwright abrió la aplicación local a **1440 × 1000**. Se importó un CSV oficial, se abrió la biblioteca, se dibujó la coropleta municipal y se guardó en el cuaderno. Se descargó un informe con la coropleta y texto escrito durante la sesión. El HTML se abrió con el acceso HTTP y HTTPS deshabilitado y se imprimió a un PDF local. A **390 × 844** se comprobó la portada, el regreso a Home y la biblioteca con sus métricas en dos columnas. Se verificó el renderizado de la cuadrícula de datos y la ausencia de desbordamiento horizontal en ambos tamaños. La comprobación de navegador llevó a corregir la descarga diferida y la reaplicación del estilo del mapa durante cambios de vista.

## Estado de las funcionalidades

| Funcionalidad | Estado | Alcance comprobado |
| --- | --- | --- |
| Home, navegación y contexto persistentes | Verificada | Siete secciones, importación y retorno a Home con proyecto activo en AppTest. |
| Catálogo, importación, originales, biblioteca y perfiles | Verificada | Búsqueda viva, previsualización, lote, archivo local, códigos con ceros, filtros y aviso por actualización de recurso. |
| Transformaciones, uniones e historial | Verificada | Recetas y cálculo arbitrario, confirmación, varias uniones, comparación de versiones, ramas, revisión, deshacer y rehacer. |
| Estadística general, temporal y espacial | Verificada | Regresiones numéricas, datos arbitrarios, casos completos, diagnósticos, PCA y Moran con semilla fija. |
| Constructor de gráficos | Verificada | Once tipos de gráfico calculados con datos cambiantes y uso de dispersión y serie en los recorridos. |
| Mapa oficial y constructor de puntos | Verificada | Coropleta de 179 municipios, ausencia explícita, agregación optativa, coordenadas WGS84, densidad y capa municipal en el motor. |
| GeoJSON aportado y edición de sus mapas | Parcial | Se verifica el motor de códigos y geometría. La edición requiere aportar de nuevo el archivo y el renderizado de esta variante no se revisó en navegador. |
| Cuaderno e informes HTML | Verificada | Resultados múltiples, trazabilidad, marcas de revisión, anotaciones e informes con datos y figuras. |
| Proyectos v1 y v2 | Verificada | Apertura de un ZIP 3.1, ida y vuelta completa, restauración y rechazo de esquemas incompatibles. |
| Asistente opcional | Parcial | Se verifica con respuesta controlada que propone un plan y espera la ejecución. El proveedor real queda sin verificar. |
| Community Cloud para 4.0 | Pendiente | Probada en Python 3.11 local con los requisitos del repositorio. La publicación y comprobación del alojamiento requieren la revisión previa. |
| Moran local, LISA, binomial negativa y clustering | Pendiente | El alcance avanzado actual incluye Moran global, PCA y marcado de valores extremos. |

## Inventario para revisión

Se crearon `library_view.py`, `notebook_view.py`, `preparation_view.py`, `project_view.py`, `transformations.py`, `visualization_view.py`, `visualizations.py`, `workspace.css`, `workspace_controls.py`, `workspace_state.py` y `workspace_views.py`. Se actualizaron la entrada `app.py`, los módulos `analysis_workspace.py`, `catalog.py`, `discovery.py`, `interface.py`, `joins.py`, `projects.py`, `reports.py`, `statistical_engine.py` y `territories.py`, además de cuatro pruebas adaptadas y los recorridos en `tests/test_final_workflow.py`. Se incorporaron `tests/test_research4.py`, `tests/test_workspace4.py`, `tests/workbench_helpers.py` y los cuatro archivos de prueba en `tests/fixtures/`.

Quedan preservados los cambios 3.1 preexistentes en preparación histórica, demos, mapas, indicador de espera, análisis espacial y activos del IGN. La guía de publicación enumera los archivos de revisión. [Guía del equipo](GUIA_EQUIPO.md#actualizar-github-y-streamlit-después-de-la-revisión) · [Registro de cambios](../CHANGELOG.md)
