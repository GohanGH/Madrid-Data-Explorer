# Resultados DATAMAD 2026

Los resultados corresponden a la selección inicial de **Explorar → Estudios de ejemplo**. La aplicación reconstruye las tablas, calcula los estadísticos y genera el informe con los filtros elegidos. Los estudios se pueden ejecutar sin conexión con los extractos y las geometrías del repositorio.

## 1. Envejecimiento y centros sanitarios

**Pregunta.** ¿Cómo se asocia el porcentaje de población de 65 años y más con la disponibilidad relativa de centros municipales de atención primaria?

**Datos de 2024.** Se sumaron los grupos de edad desde 65–69 hasta 100 años y más del Censo anual y se dividieron por el total censado municipal a 1 de enero. Para los centros se cruzaron los recuentos de consultorios locales y centros de salud con la población empadronada a 1 de enero y se aplicó la escala por 10.000 habitantes. Los dos indicadores calculados coinciden con los publicados hasta su precisión de dos decimales. El cruce secuencial por código INE y año cubre los 179 municipios, con **422 centros** en la definición seleccionada. [Censo anual por edad](https://datos.comunidad.madrid/dataset/poblacion_censada_por_edad_nacionalidad_y_sexo) · [Envejecimiento publicado](https://datos.comunidad.madrid/dataset/grado_envejecimiento_por_edad) · [Centros sanitarios](https://datos.comunidad.madrid/dataset/centros_sanitarios_por_tipo) · [Padrón por sexo](https://datos.comunidad.madrid/dataset/padron_por_sexo)

| Método | Municipios | Coeficiente | IC 95 % | Valor p |
| --- | ---: | ---: | --- | ---: |
| Pearson | 179 | 0,600503 | [0,497663; 0,686693] | 6,39 × 10⁻¹⁹ |
| Spearman | 179 | 0,505204 | — | 5,51 × 10⁻¹³ |

Pearson reproduce el **0,60** del guion al redondear a dos decimales. Spearman también muestra una asociación positiva por rangos. El denominador pequeño de algunos municipios puede producir valores elevados por habitante incluso con un único centro. El indicador mide la disponibilidad administrativa relativa de los establecimientos seleccionados. La capacidad, los horarios, los desplazamientos y la atención en municipios vecinos quedan fuera del estudio. Los coeficientes describen asociaciones territoriales y sus valores p e intervalos presuponen independencia entre municipios, un supuesto que puede verse afectado por la proximidad geográfica.

## 2. Evolución del paro registrado

**Pregunta.** ¿Cómo cambió el paro registrado y qué municipios presentan los mayores cambios?

**Datos.** 1.432 observaciones, una por municipio y año. Los recuentos corresponden al **31 de marzo** de cada año de 2018 a 2025. Para cada municipio se calcula el cambio absoluto entre los extremos seleccionados y se divide ese cambio por el recuento del primer año cuando es positivo. La serie conserva los recuentos y fechas de referencia originales. [Total paro registrado](https://datos.comunidad.madrid/dataset/302038)

La suma de los 179 municipios pasó de **380.051 a 293.817 personas** entre marzo de 2018 y marzo de 2025, una caída de **86.234 personas (−22,69 %)**.

| Municipio | Marzo 2018 | Marzo 2025 | Cambio en personas | Cambio porcentual |
| --- | ---: | ---: | ---: | ---: |
| Madrid, mayor descenso absoluto | 179.406 | 140.249 | −39.157 | −21,83 % |
| Fuenlabrada | 14.417 | 9.632 | −4.785 | −33,19 % |
| Móstoles | 14.099 | 9.776 | −4.323 | −30,66 % |
| Alcalá de Henares | 13.410 | 10.061 | −3.349 | −24,97 % |
| Alcorcón | 10.157 | 7.389 | −2.768 | −27,25 % |
| Navacerrada, mayor aumento absoluto | 101 | 127 | +26 | +25,74 % |
| Berzosa del Lozoya, mayor descenso relativo | 15 | 3 | −12 | −80,00 % |
| Robregordo, mayor aumento relativo | 1 | 6 | +5 | +500,00 % |

Los porcentajes son variaciones del recuento inicial. La población activa queda fuera de ese denominador. Una base pequeña puede producir una variación relativa elevada. La fuente indica que las medidas adoptadas en 2020 pudieron afectar al registro y a su comparabilidad.

## 3. Renta y envejecimiento

**Pregunta.** ¿Cómo se relaciona la renta disponible bruta por habitante con la proporción de población de 65 años y más?

**Datos de 2024.** Cruce por código INE y año de la renta municipal y el porcentaje construido con los grupos de edad del Censo anual. La población de 65 años y más oscila entre el 7,38 % en Arroyomolinos y el 50,00 % en La Acebeda. La renta oscila entre 13.995 € por habitante en Cenicientos y 47.217 € en Pozuelo de Alarcón. Hubo 179 pares completos en esta selección. Los valores ausentes de otras selecciones se conservan y se excluyen del cálculo por pares. [Indicador de renta municipal](https://datos.comunidad.madrid/dataset/irpf_indicador_renta) · [Censo anual por edad](https://datos.comunidad.madrid/dataset/poblacion_censada_por_edad_nacionalidad_y_sexo)

| Método | Municipios | Coeficiente | IC 95 % | Valor p |
| --- | ---: | ---: | --- | ---: |
| Pearson | 179 | −0,109310 | [−0,251943; 0,037971] | 0,1452 |
| Spearman | 179 | −0,151285 | — | 0,0432 |

| Regresión OLS con errores HC3 | Coeficiente | IC 95 % | Valor p |
| --- | ---: | --- | ---: |
| Intercepto, EUR por habitante | 22.382,74 | [20.389,30; 24.376,18] | 2,47 × 10⁻¹⁰⁷ |
| Pendiente, EUR por habitante por punto porcentual | −92,75 | [−188,53; 3,04] | 0,0577 |

**R² = 0,01195.** El ajuste lineal explica aproximadamente el 1,2 % de la variación local observada en renta. Pearson y la pendiente tienen intervalos que incluyen cero y Spearman describe una asociación débil en rangos. El intercepto corresponde a un porcentaje de 0 % fuera del rango observado. El ajuste concede el mismo peso a cada municipio. HC3 permite heterocedasticidad. La dependencia espacial, la influencia de valores extremos y las posibles variables omitidas siguen condicionando la interpretación. El modelo describe asociaciones municipales y carece de interpretación causal.

## Procedencia y reproducción

- Los seis CSV tabulares de la Comunidad de Madrid se verificaron el **25 de noviembre de 2026**. Los extractos tabulares anteriores del repositorio coinciden con los regenerados desde esas descargas. Los extractos nuevos conservan los recuentos sanitarios y censales seleccionados. [URLs directas, licencias, unidades y periodos](demo_data/sources.json)
- La capa contiene las 179 unidades municipales del IGN/CNIG obtenidas el **18 de noviembre de 2026**, simplificadas para visualización. Se verificó el servicio WFS el **25 de noviembre de 2026**. Obra derivada de BDLJE CC BY 4.0 ign.es. [Servicio WFS del IGN](https://www.ign.es/wfs-inspire/unidades-administrativas?SERVICE=WFS&REQUEST=GetCapabilities)
- En cada estudio, **Datos y preparación** muestra los diagnósticos, las transformaciones y la cobertura de cada unión. Los códigos originales de cuatro cifras se conservan como texto y los cruces usan su equivalencia INE de cinco cifras. En **Resultados** se pueden cambiar las variables, métodos, periodos o municipios según el estudio.
- **Descargas** ofrece el informe HTML autocontenido, la vista activa, las tablas combinada y filtrada, un ZIP con los extractos previos a la limpieza, las tablas limpias y la cartografía, y un ZIP de resultados con parámetros y procedencia. El informe HTML incluye estilos de impresión para guardarlo como PDF desde el navegador.
