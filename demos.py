"""Estudios reproducibles con los extractos municipales del repositorio."""
import json
from functools import lru_cache
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from data_tables import csv_export, describe_table, ratio_indicator, read_table
from interface import validate_selection
from joins import join_preview
from projects import remember_result
from reports import html_report
from statistical_engine import association, numeric_values, regression, temporal
from territories import (
    AGE,
    DATA,
    HEALTH,
    JOBS,
    POP,
    RENT,
    boundaries,
    normalize_code,
    official_codes,
    source_metadata,
)

KEYS = ["Código territorio", "Año"]
CODE, YEAR = KEYS
TOWN = "Territorio"
COUNT = "centros_atencion_primaria_recuento"
CENSUS = "censo_anual_por_edad"
AGE_SHARE = "Población de 65 años y más calculada (%)"
DEMO_NAMES = ["Renta y envejecimiento", "Evolución del desempleo", "Envejecimiento y centros sanitarios"]
SOURCES = {DEMO_NAMES[0]: (CENSUS, AGE, RENT), DEMO_NAMES[1]: (JOBS,),
           DEMO_NAMES[2]: (CENSUS, AGE, COUNT, POP, HEALTH)}
QUESTIONS = {
    DEMO_NAMES[0]: "¿Qué relación existe entre la renta municipal por habitante y el peso demográfico de la población de 65 años y más?",
    DEMO_NAMES[1]: "¿Cómo ha evolucionado el paro registrado y qué municipios presentan mayores cambios?",
    DEMO_NAMES[2]: "¿Existe una asociación entre el envejecimiento municipal y la disponibilidad relativa de centros de atención primaria?",
}
LIMITS = {
    DEMO_NAMES[0]: "La renta es el indicador de renta disponible bruta per cápita. El secreto estadístico genera ausencias. Cada municipio pesa igual y el análisis municipal no permite inferir efectos individuales ni causales.",
    DEMO_NAMES[1]: "Recuentos a 31 de marzo de cada año. Los cambios comparan el mismo mes. La fuente advierte que las medidas de 2020 pueden afectar la comparabilidad. Los recuentos dependen del tamaño de cada municipio y la tasa oficial requeriría población activa.",
    DEMO_NAMES[2]: "El recuento municipal incluye consultorios locales y centros de salud. El indicador por habitante puede ser alto en municipios pequeños. Capacidad, horarios, desplazamientos y cobertura asistencial quedan fuera del indicador. La asociación municipal carece de interpretación causal.",
}
RATE = "Centros calculados por 10.000 habitantes"
ABS = "Variación (personas)"
PCT = "Variación (%)"
IGN = "https://www.ign.es/wfs-inspire/unidades-administrativas?SERVICE=WFS&REQUEST=GetCapabilities"


@lru_cache
def raw_source(key):
    return (DATA / f"{key}.csv").read_bytes()


def census_indicators(frame):
    key = [*KEYS, TOWN, "INE"]
    if frame.duplicated([*key, "Edad"]).any():
        raise ValueError("Hay grupos de edad repetidos por municipio y año.")
    metric = "Población censada (personas)"
    wide = frame.pivot(index=key, columns="Edad", values=metric)
    bands = [f"De {age}-{age + 4} años" for age in range(0, 100, 5)] + ["De 100 y más años"]
    if set(wide.columns) != {"Total", *bands} or wide.isna().any().any():
        raise ValueError("Faltan recuentos censales en los grupos de edad esperados.")
    total = wide["Total"]
    if total.le(0).any() or not wide[bands].sum(axis=1).eq(total).all():
        raise ValueError("Los grupos censales deben sumar la población total positiva.")
    older = wide[bands[13:]].sum(axis=1)
    return pd.DataFrame({
        metric: total, "Población de 65 años y más (personas)": older, AGE_SHARE: 100 * older / total,
    }).reset_index()


def prepare_study(name):
    clean, history, diagnostics = {}, [], {}
    for key in SOURCES[name]:
        raw = read_table(raw_source(key), "csv")
        if list(raw.columns[:3]) != [*KEYS, TOWN] or raw.shape[1] != (5 if key == CENSUS else 4):
            raise ValueError(f"Esquema inesperado en {key}.")
        diagnostics[key] = describe_table(raw)
        df = raw.drop_duplicates().copy()
        df["INE"] = df[CODE].map(lambda value: normalize_code(value, "Almudena")).astype("string")
        grain = ["INE", YEAR, "Edad"] if key == CENSUS else ["INE", YEAR]
        if df["INE"].isna().any() or df.duplicated(grain).any():
            raise ValueError(f"{key} contiene claves municipales inválidas o repetidas.")
        if not df["INE"].map(lambda code: official_codes()[code][1]).eq(df[TOWN]).all():
            raise ValueError(f"{key} contiene nombres incompatibles con el padrón.")
        metric = raw.columns[-1]
        values = numeric_values(df[metric])
        invalid = (df[metric].notna() & values.isna()) | values.lt(0).fillna(False)
        if key == AGE:
            invalid |= values.gt(100).fillna(False)
        if key in {POP, COUNT, JOBS, CENSUS}:
            invalid |= values.mod(1).ne(0).fillna(False)
        if key == POP:
            invalid |= values.eq(0).fillna(False)
        if invalid.any():
            raise ValueError(f"{key} contiene valores inválidos para {metric}.")
        df[metric] = values
        clean[key] = df
        history.append({"fuente": key, "duplicados exactos retirados": len(raw) - len(df),
                        "ausencias conservadas": int(df[metric].isna().sum()),
                        "normalización": "Código Almudena validado contra el padrón y convertido a INE",
                        "unidad y variable": metric, "años": [int(y) for y in sorted(df[YEAR].unique())]})

    first, *others = clean
    combined = census_indicators(clean[first]) if first == CENSUS else clean[first]
    if first == CENSUS:
        history.append({"indicador": AGE_SHARE, "fórmula": "100 × suma de grupos de 65 años y más / total del censo",
                        "validación": "La suma de todos los grupos de edad coincide con el total municipal."})
    joins = []
    for key in others:
        right = clean[key]
        # The padrón has its own historical series. Match the years of the study.
        right = right[right[YEAR].isin(combined[YEAR])].drop(columns=[CODE, TOWN])
        combined, info = join_preview(combined, right, ["INE", YEAR], ["INE", YEAR], "left")
        joins.append({"fuente": key, "tipo": "left", **info})
    if name == DEMO_NAMES[2]:
        combined, missing = ratio_indicator(combined, RATE, "Centros de atención primaria (número)",
                                            "Población (personas)", 10_000)
        history.append({"indicador": RATE, "fórmula": "10.000 × centros de atención primaria / población empadronada", "ausencias": missing})
    return combined, clean, history, joins, diagnostics


def demo_table(name):
    """Compatibility entry point for the guided question about rent."""
    df, _, _, joins, _ = prepare_study(name)
    if name != DEMO_NAMES[2]:
        df = (df[[*KEYS, TOWN, "Población de 65 años y más (%)", "Renta per cápita (EUR)"]]
              if name == DEMO_NAMES[0] else df.drop(columns="INE"))
    return df, (joins[-1] if name == DEMO_NAMES[0] else {"uniones": joins} if joins else {})


def employment(frame, years):
    start, end = years
    metric = frame.columns[3]
    subset = frame[frame[YEAR].between(start, end)]
    endpoints = subset.pivot(index=["INE", TOWN], columns=YEAR, values=metric)
    ranking = endpoints.reindex(columns=[start, end]).copy()
    if start == end:
        raise ValueError("Elige dos años distintos para calcular cambios.")
    ranking[ABS] = ranking[end] - ranking[start]
    ranking[PCT] = 100 * ranking[ABS] / ranking[start].where(ranking[start].gt(0))
    return ranking.rename(columns=str).reset_index()


def study_map(frame, variable, title):
    geo = boundaries()
    codes = list(official_codes())
    index = frame.set_index("INE")[variable].reindex(codes)
    values = [None if pd.isna(value) else float(value) for value in index]
    names = [official_codes()[c][1] for c in codes]
    common = {"geojson": geo, "marker_line_width": .6, "marker_line_color": "#8997a5"}
    fig = go.Figure(go.Choroplethmap(
        **common, locations=codes, z=[0] * len(codes), text=names,
        colorscale=[[0, "#303A46"], [1, "#303A46"]], showscale=False,
        hovertemplate="%{text} · %{location}<br>Sin datos en la selección<extra></extra>",
    ))
    observed = [(code, value, name) for code, value, name in zip(codes, values, names) if value is not None]
    if observed:
        locations, z, labels = zip(*observed)
        fig.add_trace(go.Choroplethmap(
            **common, locations=locations, z=z, text=labels, colorscale="Viridis",
            colorbar_title=variable, hovertemplate="%{text} · %{location}<br>%{z:,.3f}<extra></extra>",
        ))
    fig.update_layout(title=title, map_style="white-bg", map_center={"lat": 40.52, "lon": -3.77},
                      map_zoom=7.1, height=540, margin={"l": 0, "r": 0, "b": 0, "t": 55},
                      template="plotly_dark")
    fig.add_annotation(text="Límites IGN/CNIG · BDLJE CC BY 4.0", x=0, y=0, xref="paper", yref="paper",
                       showarrow=False, bgcolor="#161B22")
    return fig


def source_records(name):
    catalog = source_metadata()
    unique = dict.fromkeys(HEALTH if key == COUNT else key for key in SOURCES[name])
    return [catalog[key] for key in unique] + [
        {"title": "Límites municipales · IGN/CNIG", "url": IGN, "license": "CC BY 4.0",
         "cobertura": "179 municipios, GeoJSON simplificado en grados",
         "referencia": "Límites actuales descargados el 18 de noviembre de 2026",
         "unidad": "coordenadas en grados", "consulta": "2026-11-25"}
    ]


def data_bundle(clean):
    output = BytesIO()
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        for key, frame in clean.items():
            archive.writestr(f"extractos_originales/{key}.csv", raw_source(key))
            archive.writestr(f"tablas_limpias/{key}.csv", csv_export(frame))
        archive.writestr("cartografia/municipios.geojson", (DATA / "municipios.geojson").read_bytes())
    return output.getvalue()


def employment_view(frame, tag):
    from map_view import value_text

    figures, tables, notes, parameters = {}, {}, [LIMITS[DEMO_NAMES[1]]], {}
    names = sorted(frame[TOWN].unique())
    default = [town for town in ("Alcalá de Henares", "Alcorcón", "Móstoles") if town in names]
    years = sorted(map(int, frame[YEAR].unique()))
    start, end = st.select_slider("Intervalo de años", options=years, value=(years[0], years[-1]), key=f"{tag}_years")
    if start == end:
        st.info("Elige dos años distintos para calcular cambios.")
        return
    towns = st.multiselect("Municipios de la serie", names, default=default, max_selections=30, key=f"{tag}_towns")
    subset = frame[frame[YEAR].between(start, end)]
    metric = frame.columns[3]
    ranking = employment(subset, (start, end))
    rank_by = st.selectbox("Orden del ranking", [ABS, PCT], key=f"{tag}_rank")
    descending = st.radio("Sentido del ranking", ["Mayores descensos", "Mayores aumentos"], horizontal=True,
                          key=f"{tag}_direction") == "Mayores aumentos"
    tables["Ranking municipal"] = ranking.sort_values(rank_by, ascending=not descending)
    if towns:
        try:
            series = temporal(subset[subset[TOWN].isin(towns)], YEAR, metric, "Año", TOWN)
            figures["Evolución"] = series.figure
            tables["Serie detallada"] = series.table
            notes.extend(series.notes)
        except ValueError as exc:
            st.warning(str(exc))
            notes.append(str(exc))
    map_metric = st.selectbox("Indicador del mapa", [metric, ABS, PCT], key=f"{tag}_map")
    map_years = sorted(map(int, subset[YEAR].unique()), reverse=True)
    validate_selection(f"{tag}_mapyear", map_years)
    map_year = st.selectbox("Año del recuento en el mapa", map_years,
                            key=f"{tag}_mapyear", disabled=map_metric != metric)
    mapped = subset[subset[YEAR].eq(map_year)] if map_metric == metric else ranking
    figures["Mapa municipal"] = study_map(mapped, map_metric, f"{map_metric} · {map_year if map_metric == metric else f'{start}–{end}'}")
    ranked = tables["Ranking municipal"].dropna(subset=[rank_by])
    summary = f"Faltan observaciones comparables para el ranking de marzo de {start} a marzo de {end}."
    if not ranked.empty:
        town, change = ranked.iloc[0][[TOWN, rank_by]]
        unit = "personas" if rank_by == ABS else "%"
        summary = (f"Entre marzo de {start} y marzo de {end}, {town} encabeza el ranking seleccionado "
                   f"({value_text(change, unit, decimals=0 if rank_by == ABS else 2)}).")
    paired = ranking.dropna(subset=[str(start), str(end)])
    if not paired.empty:
        begin, finish = paired[[str(start), str(end)]].sum()
        summary += (f" La suma en {len(paired)} municipios con ambos años pasó "
                    f"de {value_text(begin, 'personas')} a {value_text(finish, 'personas')}.")
    parameters.update(años=[start, end], municipios_serie=towns, ranking=rank_by, descendente=descending,
                      indicador_mapa=map_metric, año_mapa=map_year)

    return summary, subset, figures, tables, notes, parameters


def cross_section_view(frame, name, tag):
    figures, tables, notes, parameters = {}, {}, [LIMITS[name]], {}
    names = sorted(frame[TOWN].unique())
    towns = st.multiselect("Municipios del análisis (vacío = todos)", names, key=f"{tag}_towns")
    subset = frame[frame[TOWN].isin(towns)] if towns else frame
    metrics = [col for col in frame.select_dtypes("number") if col != YEAR]
    defaults = [AGE_SHARE, RATE if name == DEMO_NAMES[2] else "Renta per cápita (EUR)"]
    x = st.selectbox("Variable X", metrics, index=metrics.index(defaults[0]), key=f"{tag}_x")
    y = st.selectbox("Variable Y", metrics, index=metrics.index(defaults[1]), key=f"{tag}_y")
    choices = ["Pearson", "Spearman", "Lineal simple"]
    methods = st.multiselect("Métodos", choices, default=choices[:2] if name == DEMO_NAMES[2] else choices,
                             key=f"{tag}_methods")
    st.caption("Pearson resume la asociación lineal. Spearman compara rangos. La regresión estima el cambio medio de Y por una unidad de X.")
    if x == y:
        st.info("Elige dos variables distintas.")
        return
    complete = subset.dropna(subset=[x, y])
    scatter = px.scatter(complete, x=x, y=y, hover_name=TOWN, title="Dispersión municipal")
    correlations = []
    summary_parts = []
    for method in methods:
        try:
            result = (regression(subset, method, y, [x]) if method == "Lineal simple"
                      else association(subset, method, x, y))
        except ValueError as exc:
            st.warning(f"{method}. {exc}")
            notes.append(f"{method}. {exc}")
            continue
        summary_parts.append(f"{method}. {result.summary}")
        notes.extend(result.notes)
        if method == "Lineal simple":
            tables["Regresión lineal simple"] = result.table
            intercept, slope = result.table["Coeficiente"]
            endpoints = [complete[x].min(), complete[x].max()]
            scatter.add_scatter(x=endpoints, y=[intercept + slope * value for value in endpoints],
                                mode="lines", name="Ajuste OLS", line={"color": "#f6b65b"})
            figures["Diagnóstico de regresión"] = result.figure
        else:
            correlations.append(result.table)
            if name == DEMO_NAMES[2] and method == "Pearson" and x == AGE_SHARE and y == RATE and not towns:
                coefficient = result.table["Coeficiente"].iat[0]
                notes.append(f"El guion cita 0,60. Con la definición de atención primaria, el padrón de 2024 y "
                             f"todos los municipios, el valor recalculado es {coefficient:.2f} a dos decimales.")
    if correlations:
        tables["Correlaciones"] = pd.concat(correlations, ignore_index=True)
    summary = " ".join(summary_parts) or f"Hay {len(complete)} pares completos en la selección."
    figures = {"Dispersión": scatter, **figures}
    for axis, variable in (("X", x), ("Y", y)):
        figures[f"Mapa {axis}"] = study_map(subset, variable, f"{variable} · 2024")
    extremes = []
    for metric in (x, y):
        observed = subset.dropna(subset=[metric])[[TOWN, metric]]
        for label, data in [("Mínimos", observed.nsmallest(3, metric)), ("Máximos", observed.nlargest(3, metric))]:
            extremes.append(data.rename(columns={metric: "Valor"}).assign(Variable=metric, Extremo=label))
    tables["Extremos municipales"] = pd.concat(extremes, ignore_index=True)
    tables["Municipios seleccionados"] = subset[[TOWN, "INE", x, y]]
    parameters.update(año=2024, municipios=towns or "todos", variables=[x, y], métodos=methods)

    return summary, subset, figures, tables, notes, parameters


def render_study(name, store):
    try:
        frame, clean, history, joins, diagnostics = prepare_study(name)
    except (OSError, ValueError) as exc:
        st.error(f"No se pudo reconstruir el estudio. {exc}")
        return
    tag = f"demo_{DEMO_NAMES.index(name)}"
    analysis_tab, data_tab, export_tab = st.tabs(["Resultados", "Datos y preparación", "Descargas"])
    with data_tab:
        with st.expander("1 · Datos y fuentes"):
            for source in source_records(name):
                st.link_button(source["title"], source["url"])
                if source.get("referencia"):
                    st.caption(f"{source['referencia']} · {source['unidad']} · Consulta {source['consulta']}")
            for key, df in clean.items():
                st.caption(key)
                st.dataframe(df.drop(columns="INE").head(8), hide_index=True)
        with st.expander("2 · Diagnóstico"):
            for key, profile in diagnostics.items():
                st.markdown(f"**{key}** · {profile['filas']} filas · {profile['duplicados']} duplicados exactos")
                st.dataframe(pd.DataFrame(profile["variables"]), hide_index=True)
        with st.expander("3 · Limpieza"):
            st.json(history)
        with st.expander("4 · Unión"):
            if joins:
                st.json(joins)
            else:
                st.write("La serie se analiza desde una tabla con clave municipal y año.")
            st.dataframe(frame.head(15), hide_index=True)

    with analysis_tab:
        st.subheader("5 · Análisis")
        output = (employment_view(frame, tag) if name == DEMO_NAMES[1] else cross_section_view(frame, name, tag))
        if output is None:
            return
        summary, subset, figures, tables, notes, parameters = output

        st.write(summary)
        st.caption(LIMITS[name])
        with st.expander("Supuestos y observaciones del análisis"):
            for note in dict.fromkeys(notes):
                st.write(note)
        st.subheader("6 · Visualización")
        selected = st.radio("Vista", list(figures), horizontal=True, key=f"{tag}_figure")
        st.plotly_chart(figures[selected], key=f"{tag}_plot")
        with st.expander("Tablas de resultados", expanded=True):
            for label, table in tables.items():
                st.markdown(f"**{label}**")
                st.dataframe(table, hide_index=True)
    with export_tab:
        st.subheader("7 · Exportación")
        metadata = {"fuentes": source_records(name), "limpieza e indicadores": history, "uniones": joins,
                    "parámetros": parameters, "cobertura tabla combinada": int(frame["INE"].nunique()),
                    "software": "Madrid Data Explorer",
                    "método": "Pearson (IC de Fisher cuando procede), Spearman por rangos y OLS con errores HC3."
                    if name != DEMO_NAMES[1] else "Serie anual de marzo y cambios entre los dos años seleccionados."}
        head, *rest = tables.items()
        def report():
            return html_report(name, f"{QUESTIONS[name]} {summary}", head[1], metadata, list(figures.values()),
                               list(dict.fromkeys(notes)), sections=[*rest, ("Datos analizados", subset)])
        st.caption("Para guardar una copia en PDF, abre el informe HTML y usa Imprimir → Guardar como PDF.")
        st.download_button("Descargar informe (HTML)", report, f"{tag}-informe.html", "text/html", key=f"{tag}_report", on_click="ignore")
        st.download_button("Descargar extractos originales, limpios y cartografía (ZIP)", data_bundle(clean),
                           f"{tag}-fuentes.zip", "application/zip", key=f"{tag}_bundle")
        st.download_button("Descargar tabla combinada (CSV)", csv_export(frame), f"{tag}-combinada.csv", "text/csv",
                           key=f"{tag}_combined")
        st.download_button("Descargar datos filtrados (CSV)", csv_export(subset), f"{tag}-datos.csv", "text/csv",
                           key=f"{tag}_filtered")
        output = BytesIO()
        with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
            for label, table in tables.items():
                archive.writestr(f"{label}.csv", csv_export(table))
            archive.writestr("metodologia.json", json.dumps(metadata, ensure_ascii=False, indent=2))
        st.download_button("Descargar resultados y metodología (ZIP)", output.getvalue(), f"{tag}-resultados.zip",
                           "application/zip", key=f"{tag}_results")
        st.download_button("Descargar vista actual (HTML)", lambda: figures[selected].to_html(include_plotlyjs=True),
                           f"{tag}-vista.html", "text/html", key=f"{tag}_chart", on_click="ignore")
        if st.button("Añadir tabla combinada a Analizar", key=f"{tag}_store"):
            try:
                dataset = store(name, frame.copy(), [source["url"] for source in metadata["fuentes"]],
                                [*history, *joins], metadata=metadata)
                for index, (label, table) in enumerate(tables.items()):
                    remember_result(st.session_state, dataset, {"análisis": label, **parameters}, table, summary, notes,
                                    list(figures.values()) if index == 0 else [])
                st.success("Tabla disponible en Analizar.")
            except ValueError as exc:
                st.error(str(exc))


def open_demo(name):
    st.session_state.open_demo = name


def show_demos(store):
    name = st.session_state.get("open_demo")
    if name in DEMO_NAMES:
        st.button("Volver a Estudios de ejemplo", on_click=open_demo, args=(None,))
        st.header(name)
        st.write(QUESTIONS[name])
        render_study(name, store)
        return
    st.subheader("Estudios de ejemplo")
    columns = st.columns(3)
    for name, column in zip((DEMO_NAMES[2], DEMO_NAMES[1], DEMO_NAMES[0]), columns):
        with column.container(border=True):
            st.markdown(f"**{name}**")
            st.caption(QUESTIONS[name])
            st.button("Abrir estudio", key=f"open_{DEMO_NAMES.index(name)}", on_click=open_demo, args=(name,))
