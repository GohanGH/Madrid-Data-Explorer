# Guía del equipo · Madrid Data Explorer 4.0

## Abrir la versión local

Instala Python 3.11. En la copia de trabajo de esta sesión, ejecuta estos comandos en una terminal de macOS. Si tienes el repositorio en otra carpeta, ajusta la primera línea.

```bash
cd "$HOME/Downloads/madrid-data-explorer 2"
python3.11 -m venv "$HOME/.venvs/madrid-data-explorer-4"
source "$HOME/.venvs/madrid-data-explorer-4/bin/activate"
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Abre [localhost:8501](http://localhost:8501). Para volver a iniciar la aplicación, activa el mismo entorno y ejecuta las últimas instrucciones desde la carpeta del repositorio. Con otro servicio en ese puerto, usa `python -m streamlit run app.py --server.port 8502`.

## Buscar, importar y preparar

1. Escribe un tema o pregunta en **Home**, o elige una categoría. En **Datos → Catálogo**, puedes buscar por palabras, revisar facetas de CKAN y filtrar por cobertura registrada en la ficha.
2. Marca la casilla junto a cada ficha que quieras importar. Se añade el primer recurso compatible. Si quieres escoger otro o añadir varios, expande la ficha y usa **Recursos para importar**. Puedes seguir buscando, cambiar de página o aplicar filtros. Revisa el lote en **Selección para importar** y pulsa **Importar seleccionados**. Cada lote admite hasta doce recursos. **Recurso → Previsualizar** sigue disponible para revisar un archivo antes de importarlo.

   En **Datos → Importar**, selecciona varios archivos en el mismo campo y pulsa **Importar archivos**. Ambas importaciones muestran el resultado de cada archivo y añaden las tablas válidas a la biblioteca existente. Si un recurso del catálogo falla, queda marcado para reintentar. Los duplicados se indican en el resultado del lote. Los extractos oficiales siguen disponibles en **Datos → Catálogo** sin conexión.
3. En la barra lateral elige la **Tabla activa**. En **Datos → Biblioteca**, usa el encabezado de la cuadrícula para ordenar, **Columnas visibles** para ocultar variables y **Filtrar filas** para aplicar hasta cuatro condiciones. En el panel de una variable puedes revisar frecuencias, distribución o valores distintos, corregir el rol, cambiar el tipo o renombrarla. **Descargar selección (CSV)** exporta las filas y columnas elegidas y **Guardar subconjunto** crea una tabla nueva.
4. En **Preparación → Transformar**, elige herramienta, operación y parámetros. Pulsa **Generar vista previa**, revisa el recuento de filas y después **Confirmar y guardar versión**. Para crear un porcentaje, elige **Crear variables → Construir razón o tasa**, selecciona numerador y denominador y usa escala 100. Una dotación por 10.000 habitantes usa escala 10.000. Revisa los avisos sobre denominadores.
5. En **Preparación → Combinar**, elige dos tablas y las claves de cada una en el mismo orden. Por ejemplo, código municipal y año si cada fila representa un municipio en un año. Revisa la vista previa, incompatibilidades y registros sin pareja. Confirma la granularidad y guarda. Puedes elegir la salida como tabla izquierda para un tercer cruce.
6. En **Historial**, inspecciona parámetros, compara versiones y recupera una anterior para abrir otra rama. Si cambias una operación sobre las mismas entradas, usa **Guardar como → Revisión de…** en su vista previa para señalar en el cuaderno las salidas que dependían de la anterior.

## Analizar y visualizar

1. En **Análisis → Métodos estadísticos**, elige una familia y un método. Selecciona variables, mira cuántos casos están completos y ajusta filtros y parámetros. Por ejemplo, para comparar dos medidas cuantitativas, ejecuta Pearson si te interesa su relación lineal o Spearman si te interesa el orden monotónico. Los resultados se añaden al cuaderno cada vez que pulsas **Ejecutar**.
2. En **Visualización → Gráficos**, elige el tipo, los ejes y los campos disponibles. Para series de varios municipios, selecciona periodo en X y municipio como grupo o color. Indica una agregación si una combinación de claves se repite. Pulsa **Actualizar vista** en los gráficos que lo requieren y **Guardar en Resultados** para conservar la vista.
3. En **Visualización → Mapas**, elige **Coropleta municipal**, el identificador geográfico y el indicador. Filtra a un periodo o agrega con una operación explícita. Puedes ajustar paleta y cortes, consultar el ranking y comparar municipios. **Abrir registros** lleva a la selección en **Datos**. Si tus datos tienen latitud y longitud WGS84, elige puntos o densidad.
4. Para revisar una visualización, selecciónala en **Editar una vista guardada**. Puedes actualizarla o guardar los cambios como otra vista. Utiliza **Resultados → Cuaderno → Anotar y organizar** para ponerle nombre, duplicarla o retirarla.

## Redactar y compartir

- En **Mis proyectos → Proyecto activo**, guarda el nombre, la pregunta y la descripción. En **Resultados → Cuaderno**, puedes guardar también la tabla activa, añadir una interpretación y ordenar los resultados. **Metodología y exportación** contiene la versión, los parámetros, los enlaces a las fuentes y las descargas.
- En **Resultados → Informes**, crea un borrador y añade en orden los resultados, la introducción, los objetivos, la metodología y el resto del texto. Guarda el borrador y descarga el HTML. Para un PDF, abre el HTML y elige **Imprimir → Guardar como PDF**.
- En **Mis proyectos → Proyecto activo**, pulsa **Preparar archivo ZIP** y después **Descargar proyecto (ZIP)**. Si sigues trabajando, genera otra copia para incorporar las modificaciones. Comparte el archivo con tu compañero. Para abrirlo, entra en **Mis proyectos → Abrir**, carga el ZIP y confirma **Restaurar proyecto**. Si hay trabajo activo, guarda una copia antes de sustituirlo. La guía de validación incluye cinco recorridos con datos oficiales. [Investigaciones reproducibles](VALIDACION_FINAL.md#investigaciones-reproducidas)

## Actualizar GitHub y Streamlit después de la revisión

1. En la misma carpeta, ejecuta `git fetch origin` y `git status --short --branch`. Comprueba que la rama y el remoto son los esperados. Si `origin/main` ha avanzado, incorpora esos cambios en una revisión antes de publicar.
2. Revisa `git diff` y prepara los archivos revisados. La siguiente selección abarca el código, la documentación, las pruebas y los activos de esta entrega, incluidos los cambios de 3.1 que estaban pendientes.

   ```bash
   git add -- README.md CHANGELOG.md app.py analysis_workspace.py catalog.py data_tables.py \
     demos.py discovery.py explore_view.py interface.py joins.py library_view.py loading.py map_view.py \
     notebook_view.py preparation_view.py project_view.py projects.py reports.py spatial_stats.py \
     statistical_engine.py territories.py transformations.py visualization_view.py visualizations.py \
     workspace.css workspace_controls.py workspace_state.py workspace_views.py \
     demo_data/build_spatial_assets.py demo_data/madrid_silueta.svg demo_data/vecindad.json \
     docs/GUIA_EQUIPO.md docs/MDE_4.md docs/MEJORAS_FINALES_DATAMAD.md docs/VALIDACION_FINAL.md \
     tests/test_app.py tests/test_datamad.py tests/test_exploration.py tests/test_studio.py \
     tests/test_final_workflow.py tests/test_multiple_import.py tests/test_research4.py tests/test_workspace4.py tests/workbench_helpers.py \
     tests/fixtures/bibliotecas_1916180_2025.csv tests/fixtures/bibliotecas_1928360_2025.csv \
     tests/fixtures/bibliotecas_fuentes.json tests/fixtures/proyecto_31.zip
   git diff --cached --stat
   git diff --cached --check
   git diff --cached
   git commit -m "Madrid Data Explorer 4.0"
   git push origin main
   ```

   Los comandos de commit y push se ejecutan después de la revisión y con `main` como rama revisada. La selección explícita deja fuera archivos locales como `.DS_Store`, el entorno de Python, los secretos y el ZIP de publicación anterior.

3. En la app existente, confirma que Community Cloud sigue el repositorio **GohanGH/Madrid-Data-Explorer**, la rama que publicaste y el archivo **`app.py`**. Espera la actualización de la rama y revisa el arranque en **Manage app**. Si creas una app de prueba, configura esa misma ruta y selecciona Python 3.11 en los ajustes avanzados.
4. En la URL de la revisión, comprueba **Home**, una búsqueda CKAN, una importación, un gráfico y la restauración de un ZIP. Si aparece un error de instalación, copia la primera línea de error de **Manage app** y comprueba la versión de Python y el `requirements.txt` de la rama. La aplicación arranca sin claves para la IA. [Despliegue en Community Cloud](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy) · [Dependencias](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/app-dependencies)
