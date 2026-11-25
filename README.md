# Madrid Data Explorer · DATAMAD 2026

Aplicación Streamlit en español para descubrir, combinar y analizar datos abiertos de la Comunidad de Madrid. Incluye tres demostraciones reproducibles con extractos oficiales.

## Explora Madrid con una pregunta

- **Explorar** interpreta preguntas en español y ordena fuentes del catálogo. Para los indicadores validados, abre directamente un mapa, ranking, serie histórica, resumen o cruce.
- **Mapa** colorea los 179 municipios con límites oficiales del IGN. Busca o pulsa hasta seis municipios, cambia indicador, año, colores y clasificación (cuantiles, intervalos iguales o Jenks), consulta su posición y evolución, y descarga el mapa o sus datos.
- **Analizar** reúne preparación, uniones, análisis estadístico, gráficos y asistente opcional. Si una tabla tiene códigos municipales reconocidos, propone el mapa incorporado.
- **Catálogo** conserva la búsqueda CKAN por filtros, la selección múltiple y la importación de archivos.

La portada incluye un buscador central y accesos temáticos a población, economía, empleo, salud, educación, vivienda y transporte. Los informes muestran primero la respuesta, sus indicadores y una visualización con vistas intercambiables. Los filtros y descargas siguen disponibles junto a cada informe. Desde Explorar puedes abrir cinco consultas preparadas con datos oficiales: renta por habitante, envejecimiento, evolución del paro registrado, crecimiento poblacional y relación entre renta y envejecimiento. Los extractos permiten ejecutar esos ejemplos sin credenciales ni consultas CKAN. El padrón cubre 2015–2025. El crecimiento se calcula como variación porcentual entre los extremos con datos para cada municipio.

La recuperación temática funciona con un vocabulario configurable en Python. Un tema, territorio, unidad o año sin análisis validado puede devolver fichas relacionadas para explorar. El catálogo y los recursos Leaflet del mapa necesitan conexión. La selección municipal es compartida por los informes y el mapa dentro de la sesión. Consulta [el diseño 2.0, los códigos y la licencia cartográfica](docs/UX_2.md).

## Estudio estadístico 3.0

En **Analizar → Estudio estadístico**, cada tabla tiene un diagnóstico, un informe exploratorio y recomendaciones revisables de limpieza. Las correcciones crean versiones comparables con el original. El estudio propone análisis por rol de variable y ejecuta los contrastes y regresiones solo al pulsar **Ejecutar análisis**. Puedes descargar datos, resultados, gráficos e informes HTML. El tema oscuro también se aplica a los mapas y las visualizaciones. Consulta [la guía técnica y las limitaciones estadísticas](docs/MDE_3.md).

## Ejecutar en macOS o Linux

Usa Python 3.11 para reproducir la configuración de CI y Community Cloud. Si ya tienes un entorno virtual de otra versión, crea uno nuevo y ajusta la ruta de activación.

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

La aplicación abre en `http://localhost:8501`. La búsqueda oficial requiere Internet. La importación, las demostraciones incluidas y el análisis manual funcionan con archivos locales.

## Flujo de trabajo

1. En **Catálogo**, busca por tema, revisa los metadatos y selecciona uno o varios recursos. Después de la primera búsqueda aparecen los filtros ofrecidos por CKAN. También puedes importar CSV, TSV, XLSX, XLS o JSON tabular.
2. En **Analizar → Preparar y combinar tablas**, revisa las primeras 100 filas, los valores faltantes y los duplicados. Puedes convertir números y fechas, normalizar nombres y categorías, o quitar duplicados mediante una transformación confirmada.
3. En **Combinar tablas**, elige claves equivalentes en el mismo orden. Para datos municipales longitudinales, usa código municipal y periodo si ambos son comparables. Previsualiza, revisa coincidencias y cardinalidad, y confirma para guardar. Las claves reconocidas de Madrid se comparan en formato INE y se muestran los años comunes y las filas perdidas de cada fuente. Las uniones muchos a muchos que multiplicarían filas se bloquean. Puedes encadenar cruces y deshacer la última operación. En **Construir indicador**, guarda una versión nueva con un cociente escalado.
4. En **Analizar → Resultados y gráficos**, selecciona una operación manual o formula una pregunta si la IA está configurada. Los resultados incluyen estadísticas, gráficos cuando corresponden, CSV y un JSON de metodología. Para capas alternativas se puede aportar un GeoJSON municipal WGS84.

## Estudios de ejemplo

En **Explorar → Estudios de ejemplo**, pulsa **Abrir estudio**. Los tres estudios usan datos oficiales y se ejecutan sin claves ni conexión después de instalar la aplicación.

| Estudio | Análisis inicial |
| --- | --- |
| Envejecimiento y centros sanitarios | Censo, recuentos de atención primaria y padrón de 2024. Calcula ambos indicadores, cruza por municipio y año y ejecuta Pearson y Spearman. |
| Evolución del desempleo | Recuentos municipales a 31 de marzo de 2018–2025. Compara series, recuentos y cambios absolutos y porcentuales. |
| Renta y envejecimiento | Renta disponible bruta por habitante y porcentaje censal de población de 65 años y más en 2024. Calcula Pearson, Spearman y OLS lineal con intervalos HC3. |

En **Resultados**, cambia los filtros o métodos y usa **Vista** para alternar entre los gráficos y mapas. En **Datos y preparación**, abre las fuentes, el diagnóstico, la limpieza y la auditoría de uniones. En **Descargas**, guarda los datos y el informe o incorpora la tabla combinada a **Analizar**. El informe HTML incrusta los gráficos y mapas. Ábrelo en el navegador para guardarlo como PDF con el diálogo de impresión.

### Recorrido de 90 segundos ante el jurado

1. **0–15 s.** Abre **Envejecimiento y centros sanitarios**. Muestra el resultado de Pearson y la dispersión.
2. **15–40 s.** En **Datos y preparación**, abre **Datos y fuentes** y **Unión**. Señala el padrón, el recuento, el censo y el cruce por INE y año.
3. **40–65 s.** Vuelve a **Resultados** y elige **Mapa Y** para mostrar los centros por 10.000 habitantes. Selecciona municipios si quieres comparar sus valores.
4. **65–90 s.** Abre **Descargas** y descarga el informe HTML. Los mismos controles están disponibles en los estudios de paro registrado y renta.

### Reproducir el corte oficial

Los extractos de `demo_data/` son el corte que usa la aplicación. Conservan los códigos publicados con sus ceros iniciales. Las fuentes tabulares se verificaron el 25 de noviembre de 2026. Las geometrías se obtuvieron del WFS del IGN el 18 de noviembre de 2026. Los mapas de los estudios se dibujan con la capa local y sin un mapa base remoto. [Resultados, referencias y limitaciones](RESULTADOS_DATAMAD.md) · [Metadatos de las fuentes](demo_data/sources.json)

Para comparar el corte con una descarga oficial posterior, genera extractos en otra carpeta.

```bash
python demo_data/build.py --output nuevos-extractos --save-raw csv-originales
```

Para regenerar desde descargas conservadas, usa `--local carpeta-csv` en lugar de `--save-raw`. Usa `mde-<clave>.csv` con las claves de `demo_data/sources.json` y `mde-paro.csv` para la serie de paro. Para reconstruir la geometría, `python demo_data/build_geometry.py` acepta las páginas GeoJSON del servicio WFS y valida que haya 179 municipios.

## IA opcional

Configura `OPENAI_API_KEY` como variable de entorno o en `.streamlit/secrets.toml`. `MDE_AI_MODEL` selecciona el modelo y `MDE_AI_BASE_URL` permite un proveedor compatible con la API Responses y respuestas JSON. [.env.example](.env.example) enumera las variables, que deben exportarse en el entorno para que la aplicación las lea. La aplicación comparte con el proveedor la pregunta y el esquema de hasta 100 columnas. Cada petición ejecuta una operación sobre la tabla activa y respeta los filtros aplicados en la interfaz.

## Pruebas

```bash
python -m pip install -r requirements-dev.txt
python -m ruff check .
python -m pytest -q
python -m pip check
```

Las pruebas habituales no requieren Internet ni credenciales. Para verificar CKAN y una descarga real ejecuta `MDE_RUN_INTEGRATION=1 python -m pytest -q -m integration`. CI instala las dependencias en Python 3.11 y ejecuta Ruff y pytest. Consulta la [arquitectura y sus límites](docs/ARCHITECTURE.md) para ver responsabilidades y decisiones.

## Desplegar en Streamlit Community Cloud

1. Publica en GitHub una rama que contenga estos archivos. Mantén fuera del repositorio los secretos y el entorno virtual.
2. En [Streamlit Community Cloud](https://share.streamlit.io/), crea una aplicación desde esa rama. Selecciona `app.py` y Python 3.11 en los ajustes avanzados.
3. Configura `OPENAI_API_KEY` en **Secrets** si vas a activar la IA y limita el gasto del proveedor para una app pública. Puedes desplegar sin clave.
4. Verifica en la URL que carguen Inicio, una demostración y una búsqueda oficial.

La capa municipal incorporada usa límites actuales simplificados. Los mapas de otras capas dependen del GeoJSON aportado y de sus códigos. Para comparar fuentes, comprueba definiciones, unidades y denominadores antes de interpretar un resultado. Los recursos alojados fuera de los dominios admitidos pueden incorporarse mediante importación manual.
