# Madrid Data Explorer · DATAMAD 2026

Aplicación Streamlit para descubrir conjuntos de datos abiertos de la Comunidad de Madrid, cargar y combinar varias tablas, visualizar estadísticas básicas y, opcionalmente, consultar un modelo de IA.

## Funcionalidades

- Búsqueda en el catálogo oficial CKAN (`package_search`).
- Selección y lectura de recursos oficiales CSV, JSON y Excel (hasta 15 MB).
- Carga de hasta ocho tablas en la sesión, con uniones `inner`, `left`, `right` y `outer`.
- Claves simples o compuestas (p. ej., municipio y año), diagnóstico de coincidencias y detección de duplicados.
- Vista previa, faltantes, descriptivos, histogramas y medias por grupo.
- Descarga de la tabla seleccionada en CSV.
- Interpretación opcional con OpenAI; los cálculos los realiza pandas, no la IA.
- Enlaces a los datos originales para comprobar procedencia.

## Requisitos

Python 3.10 o posterior y acceso a Internet. Una clave API de OpenAI es opcional para usar el chat.

## Ejecución local

```bash
git clone <URL-DE-TU-REPOSITORIO>
cd madrid-data-explorer
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Si recibes esta carpeta como ZIP, descomprímela y omite el paso `git clone`. En Windows usa `.venv\Scripts\activate`.

Para habilitar el chat local crea `.streamlit/secrets.toml` (no lo publiques):

```toml
OPENAI_API_KEY = "tu_clave_api"
```

## Despliegue web compartido (Streamlit Community Cloud)

1. Crea un repositorio de GitHub con los archivos de este directorio; **no subas** `secrets.toml`.
2. En [share.streamlit.io](https://share.streamlit.io/), inicia sesión y elige **Create app** desde GitHub.
3. Selecciona el repositorio, rama principal y archivo `app.py`.
4. En **Advanced settings → Secrets** añade `OPENAI_API_KEY = "..."` (sintaxis TOML). Si no tienes clave, omite este paso: búsqueda, carga y estadísticas seguirán funcionando.
5. Despliega. Comparte la URL resultante con tu equipo. Quien tenga acceso a la app podrá consumir cuota de tu API si has habilitado la IA; establece límites de gasto y controla quién accede.

La interfaz corre en Streamlit; no necesitas un servidor propio. La plataforma de alojamiento puede imponer límites o suspender aplicaciones inactivas.

## Pruebas

```bash
python -m pytest -q
python -m compileall -q .
```

## Cómo cruzar dos fuentes sin IA

1. En **Buscar datos**, busca y carga una primera tabla.
2. Busca y carga una segunda tabla; la primera permanece guardada en memoria.
3. En **Combinar datasets**, elige tabla A y tabla B.
4. Selecciona las claves equivalentes, por ejemplo `municipio` en ambas. Para series anuales elige **municipio y año**, en ese orden para A y B.
5. Elige unión `inner` para coincidencias, `left` para conservar A o `outer` para conservar ambas.
6. Pulsa **Ejecutar unión**, revisa el diagnóstico y selecciona la tabla resultante en **Analizar**. También puedes volver a unir el resultado con una tercera tabla.

**Advertencia:** una unión no armoniza automáticamente definiciones, unidades, periodos, códigos territoriales ni variables duplicadas. Comprueba duplicados antes de interpretar resultados. Las uniones que producirían más de 250.000 filas se rechazan para proteger el prototipo. Las tablas quedan en memoria solo durante la sesión de Streamlit.

## Alcance y límites

Esta versión **busca el catálogo**, pero **no descarga todos sus datasets**. Descarga solo los recursos que el usuario elige. No soporta PDF, archivos masivos ni datos geoespaciales. Las uniones entre fuentes son manuales y requieren elegir las claves; no detecta de forma automática qué tablas son compatibles. El chat no ejecuta scripts: explica el resumen estadístico y la muestra que recibe. No se debe interpretar como un modelo de predicción o causalidad.

La política de seguridad solo permite descargar recursos de dominios oficiales de la Comunidad de Madrid y rechaza respuestas redirigidas. Algunas fuentes oficiales externas, formatos complejos o recursos alojados en otros dominios no cargarán: se pueden añadir después de revisar sus destinos.

Los datos públicos no siempre están actualizados, ni tienen la misma unidad geográfica, y pueden contener errores. Verifica la documentación oficial antes de publicar resultados.

## Estructura

- `app.py`: interfaz, búsqueda, análisis, descarga y chat.
- `catalog.py`: conexión CKAN y parsers de recursos.
- `assistant.py`: interpretación opcional con OpenAI.
- `joins.py`: uniones seguras y diagnósticos entre tablas.
- `requirements.txt`: dependencias.
- `.streamlit/config.toml`: presentación.
- `tests/`: pruebas básicas.

Fuente oficial: https://www.comunidad.madrid/datos-abiertos/reutiliza-datos-abiertos-comunidad-madrid
