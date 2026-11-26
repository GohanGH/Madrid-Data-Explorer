"""General chart and map builders that return a figure, its data and method notes."""
import json
from dataclasses import dataclass
from itertools import pairwise
from urllib.parse import quote

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from map_view import ATTRIBUTION, MISSING, PALETTES, map_features, value_text
from maps import municipal_map
from statistical_engine import correlation_matrix, numeric_values
from territories import boundaries, municipal_identifier, official_codes
from transformations import aggregate, filter_rows

CHARTS = ("Barras", "Líneas", "Dispersión", "Burbujas", "Histograma", "Caja", "Violín", "Densidad",
          "Mapa de calor", "Matriz de correlación", "Frecuencias")
MAP_TYPES = ("Coropleta municipal", "Puntos WGS84", "Densidad de puntos", "Polígonos propios")
CATEGORICAL_PALETTES = {
    "Madrid": ["#4bd8b5", "#b7a2f3", "#68a8f3", "#f4b878", "#f28497", "#98cc74", "#c5b8a5"],
    "Contraste": px.colors.qualitative.Safe,
    "Cálida": px.colors.qualitative.Bold,
}
MAP_CLASSIFICATIONS = ("Cuantiles", "Intervalos iguales", "Cortes naturales (Jenks)")
# A stable URL keeps MapLibre from reapplying an equivalent style on widget reruns.
MAP_BASE = "data:application/json," + quote(json.dumps({"version": 8, "sources": {}, "layers": [
    {"id": "fondo", "type": "background", "paint": {"background-color": "#121b23"}},
]}), safe="")
POINT_CAP = 25_000


@dataclass
class Visual:
    figure: object
    table: pd.DataFrame
    notes: list


def style_figure(figure, title, legend):
    figure.update_layout(title=title, template="plotly_dark", paper_bgcolor="#0D1117", plot_bgcolor="#141c26",
                         height=470, margin={"l": 24, "r": 20, "t": 65, "b": 30},
                         showlegend=legend, font={"color": "#edf3f9"})
    return figure


def _kernel_density(frame, labels, palette):
    from scipy.stats import gaussian_kde

    segments = []
    for label, group in (frame.groupby("Color", observed=True) if "Color" in frame else [(None, frame)]):
        values = group["X"].to_numpy(dtype=float)
        if len(values) < 3 or np.ptp(values) == 0:
            raise ValueError("Cada grupo de densidad necesita tres valores con variación.")
        grid = np.linspace(values.min(), values.max(), 160)
        try:
            curve = gaussian_kde(values)(grid)
        except np.linalg.LinAlgError as exc:
            raise ValueError("La densidad no se puede estimar con esta escala o variación.") from exc
        part = pd.DataFrame({"X": grid, "Densidad": curve})
        if label is not None:
            part["Color"] = label
        segments.append(part)
    table = pd.concat(segments, ignore_index=True)
    figure = px.line(table, x="X", y="Densidad", color="Color" if "Color" in table else None,
                     labels=labels, color_discrete_sequence=palette)
    return figure, table


def build_chart(frame, spec):
    selected = filter_rows(frame, spec.get("filters", ()))
    kind = spec["kind"]
    title = spec.get("title") or kind
    legend = spec.get("legend", True)
    if selected.empty:
        raise ValueError("Los filtros no dejaron observaciones.")
    if kind == "Matriz de correlación":
        result = correlation_matrix(selected, spec["columns"], spec.get("coefficient", "Pearson"))
        return Visual(style_figure(result.figure, title, legend), result.table, result.notes)
    bindings = {label: spec[key] for label, key in (("X", "x"), ("Y", "y"), ("Color", "color"), ("Tamaño", "size"),
                                                    ("Grupo", "group"), ("Faceta", "facet")) if spec.get(key) is not None}
    if kind not in CHARTS or not bindings or any(column not in selected for column in bindings.values()):
        raise ValueError("Elige un gráfico y las variables disponibles.")
    slots = pd.DataFrame({label: selected[column] for label, column in bindings.items()})
    quantitative = ({"X", "Y"} if kind in {"Dispersión", "Burbujas", "Mapa de calor"} else
                    {"X"} if kind in {"Histograma", "Densidad"} else {"Y"} if kind != "Frecuencias" else set())
    if kind == "Burbujas":
        quantitative.add("Tamaño")
    if kind == "Líneas" and "X" not in slots:
        raise ValueError("Selecciona una variable de orden para el eje X.")
    if kind in {"Barras", "Frecuencias"} and "X" not in slots:
        raise ValueError("Selecciona una categoría o variable del eje X.")
    measure_op = "Recuento de filas" if kind == "Frecuencias" else spec.get("aggregation")
    if measure_op == "Recuento de filas":
        quantitative.discard("Y")
        slots = slots.drop(columns="Y", errors="ignore")
    if not quantitative <= set(slots.columns):
        raise ValueError("Este gráfico requiere medidas numéricas en los campos indicados.")
    for label in quantitative:
        slots[label] = numeric_values(slots[label])
    if "Color" in slots and (kind not in {"Dispersión", "Burbujas"} or spec.get("color_discrete", True)):
        slots["Color"] = slots["Color"].astype("string")
    slots = slots.dropna()
    if not len(slots):
        raise ValueError("No quedan filas con datos válidos para todas las variables.")
    if "Tamaño" in slots and ((slots["Tamaño"] < 0).any() or slots["Tamaño"].max() == 0):
        raise ValueError("El tamaño de las burbujas necesita valores no negativos y al menos un valor positivo.")
    rows = len(slots)
    notes = [(f"{len(frame) - len(selected):,} filas fuera de los filtros. "
             f"{len(selected) - rows:,} filas sin datos válidos para este gráfico.")]
    if measure_op:
        dimensions = [label for label in ["X", "Color", "Grupo", "Faceta"] if label in slots]
        slots = aggregate(slots, dimensions, measure_op, "Y" if "Y" in slots else None, name="Medida")
        slots = slots.rename(columns={"Medida": "Y"})
        notes.append(f"Agregación {measure_op} sobre las {rows:,} filas válidas, por {', '.join(bindings[d] for d in dimensions)}.")
    elif kind in {"Barras", "Líneas"}:
        keys = [label for label in ["X", "Color", "Grupo", "Faceta"] if label in slots]
        if slots.duplicated(keys).any():
            raise ValueError("El eje X se repite dentro de una serie. Elige una agregación, un grupo o un filtro.")
    max_colors = 8 if kind == "Densidad" else 25
    if "Color" in slots and not pd.api.types.is_numeric_dtype(slots["Color"]) and slots["Color"].nunique() > max_colors:
        raise ValueError(f"Filtra a un máximo de {max_colors} series de color para el gráfico.")
    if "Faceta" in slots and slots["Faceta"].nunique() > 10:
        raise ValueError("Filtra la variable de facetas a un máximo de diez niveles.")
    if kind in {"Frecuencias", "Barras", "Caja", "Violín"} and "X" in slots and slots["X"].nunique() > 100:
        raise ValueError("Filtra o agrega el eje X hasta un máximo de 100 valores distintos.")
    if len(slots) > POINT_CAP:
        positions = np.linspace(0, len(slots) - 1, POINT_CAP, dtype=int)
        slots = slots.iloc[positions]
        notes.append(f"El gráfico y sus datos exportables muestran una selección sistemática de {POINT_CAP:,} filas.")
    sort = spec.get("order")
    sort_label = "Y" if sort in {"Medida ascendente", "Medida descendente"} else "X"
    if sort_label in slots and (sort or kind == "Líneas"):
        slots = slots.sort_values(sort_label, ascending=sort != "Medida descendente", kind="stable")
    labels = {**bindings, "X": spec.get("x_title") or bindings.get("X", "Categoría"),
              "Y": spec.get("y_title") or ("Frecuencia" if measure_op == "Recuento de filas" else bindings.get("Y", "Valor"))}
    palette = CATEGORICAL_PALETTES.get(spec.get("palette"), CATEGORICAL_PALETTES["Madrid"])
    color = "Color" if "Color" in slots else None
    facet = "Faceta" if "Faceta" in slots else None
    x, y = ("X" if "X" in slots else None), ("Y" if "Y" in slots else None)
    layout = {"labels": labels, "color_discrete_sequence": palette, "color": color,
              "facet_col": facet, "facet_col_wrap": 2}
    if kind in {"Dispersión", "Burbujas"}:
        figure = px.scatter(slots, x=x, y=y, size="Tamaño" if "Tamaño" in slots else None,
                            color_continuous_scale="Viridis", **layout)
    elif kind in {"Barras", "Frecuencias"}:
        figure = px.bar(slots, x=x, y=y, barmode="stack" if spec.get("stack") else "group", **layout)
    elif kind == "Líneas":
        figure = px.line(slots, x=x, y=y, line_group="Grupo" if "Grupo" in slots else None, markers=True, **layout)
    elif kind == "Histograma":
        figure = px.histogram(slots, x=x, nbins=spec.get("bins", 20), barmode="overlay", opacity=.75, **layout)
    elif kind == "Caja":
        figure = px.box(slots, x=x, y=y, points="outliers", **layout)
    elif kind == "Violín":
        figure = px.violin(slots, x=x, y=y, box=True, points=False, **layout)
    elif kind == "Mapa de calor":
        figure = px.density_heatmap(slots, x=x, y=y, nbinsx=spec.get("bins", 20), nbinsy=spec.get("bins", 20),
                                    labels=labels, color_continuous_scale="Teal", facet_col=facet, facet_col_wrap=2)
    else:
        figure, slots = _kernel_density(slots, labels, palette)
        notes.append("Densidad estimada mediante núcleo gaussiano sobre los datos representados.")
    for axis in ("x", "y"):
        if spec.get(f"log_{axis}"):
            column = slots.get(axis.upper())
            if column is None or not pd.api.types.is_numeric_dtype(column) or column.le(0).any():
                raise ValueError("Una escala logarítmica requiere valores numéricos estrictamente positivos en el eje.")
            if axis == "x":
                figure.update_xaxes(type="log")
            else:
                figure.update_yaxes(type="log")
    table = slots.rename(columns={label: f"{label} · {labels[label]}" for label in slots if label in labels})
    return Visual(style_figure(figure, title, legend), table.reset_index(drop=True), notes)


def municipal_values(frame, spec):
    code, metric = spec["code"], spec["metric"]
    if code == metric:
        raise ValueError("Identificador e indicador deben ser variables distintas.")
    roles = frame[code].map(lambda value: municipal_identifier(value, spec.get("system", "auto"))).astype("string")
    work = pd.DataFrame({"INE": roles, "Valor": numeric_values(frame[metric])})
    rejected = int(work["INE"].isna().sum())
    invalid = int(work["Valor"].isna().sum())
    work = work.dropna(subset=["INE"])
    if scope := spec.get("scope"):
        work = work[work["INE"].isin(scope)]
    if work.empty:
        raise ValueError("No hay códigos o nombres municipales reconocidos en la selección.")
    method = spec.get("aggregation")
    if method:
        work = aggregate(work, ["INE"], method, "Valor", name="Medida").rename(columns={"Medida": "Valor"})
    elif work["INE"].duplicated().any():
        raise ValueError("Hay varias observaciones por municipio. Filtra por periodo o selecciona una agregación explícita.")
    table = work.set_index("INE").reindex(list(official_codes())).reset_index()
    table["Municipio"] = table["INE"].map(lambda code: official_codes()[code][1])
    table = table[["INE", "Municipio", "Valor"]].sort_values("Valor", ascending=False, na_position="last", kind="stable")
    notes = [f"{table['Valor'].notna().sum()} de 179 municipios con datos representados.",
             f"{rejected:,} filas sin identificador reconocido y {invalid:,} sin valor numérico previo a la agregación.",
             f"Límites municipales del IGN. {ATTRIBUTION}."]
    if method:
        notes.append(f"Agregación por municipio: {method}. Comprueba que la unidad admite esa operación.")
    return table, notes


def choropleth(table, unit, palette, method, legend_title):
    features, bins = map_features(table, unit, method, palette)
    levels = list(pairwise(bins)) if len(bins) > 1 else ([(bins[0], bins[0])] if bins else [])
    colors = [MISSING, *palette[:len(levels)]]
    maximum = max(1, len(colors) - 1)
    scale = []
    for index, color in enumerate(colors):
        scale.extend([(max(0, (index - .5) / maximum), color), (min(1, (index + .5) / maximum), color)])
    if scale[-1][0] < 1:
        scale.append((1, MISSING))
    props = [feature["properties"] for feature in features["features"]]
    legend = ["Sin datos", *(value_text(a, unit) if a == b else f"{value_text(a, '')} – {value_text(b, unit)}"
                             for a, b in levels)]
    figure = go.Figure(go.Choroplethmap(
        geojson=features, locations=[entry["code"] for entry in props], featureidkey="properties.code",
        z=[colors.index(entry["color"]) for entry in props], zmin=0, zmax=maximum, colorscale=scale,
        marker={"line": {"width": .75, "color": "#506776"}},
        customdata=[[entry["name"], entry["code"], entry["value"]] for entry in props],
        hovertemplate="%{customdata[0]} · %{customdata[1]}<br>%{customdata[2]}<extra></extra>",
        colorbar={"title": {"text": legend_title or unit or "Valor"}, "tickvals": list(range(len(legend))), "ticktext": legend},
    ))
    figure.add_annotation(text=ATTRIBUTION, x=.01, y=.01, xref="paper", yref="paper", showarrow=False,
                          font={"size": 10}, bgcolor="#121b23")
    return figure


def coordinate_map(frame, spec):
    lat, lon = spec["latitude"], spec["longitude"]
    if lat == lon:
        raise ValueError("Selecciona latitud y longitud en columnas distintas.")
    cols = [lat, lon]
    metric = spec.get("metric")
    if metric and metric not in cols:
        cols.append(metric)
    work = frame[cols].apply(numeric_values)
    mask = work[lat].between(-90, 90) & work[lon].between(-180, 180)
    work = work.loc[mask].copy()
    notes = [f"{len(frame) - len(work):,} coordenadas ausentes o fuera del rango WGS84."]
    if work.empty:
        raise ValueError("No hay coordenadas GPS válidas.")
    if len(work) > POINT_CAP:
        raise ValueError(f"Filtra a un máximo de {POINT_CAP:,} registros para dibujar los puntos.")
    if spec.get("municipal_layer"):
        outlines = go.Choroplethmap(geojson=boundaries(), locations=list(official_codes()), z=[0] * 179,
                                    colorscale=[[0, "#26343e"], [1, "#26343e"]], showscale=False,
                                    marker={"line": {"color": "#516772", "width": .65}}, hoverinfo="skip")
        figure = go.Figure(outlines)
        notes.append(ATTRIBUTION)
    else:
        figure = go.Figure()
    extra = {}
    if spec["kind"] == "Densidad de puntos":
        if metric:
            if work[metric].lt(0).fillna(False).any():
                raise ValueError("Para ponderar la densidad, elige una medida no negativa.")
            extra["z"] = work[metric]
        figure.add_trace(go.Densitymap(lat=work[lat], lon=work[lon], radius=spec.get("radius", 22),
                                       colorscale="Viridis", **extra))
        notes.append("La intensidad es exploratoria, en función del radio visual. No se agrega por municipio.")
    else:
        marker = {"size": 8, "color": "#4bd8b5", "opacity": .8}
        if metric:
            marker.update(color=work[metric], colorscale="Viridis", showscale=True)
        figure.add_trace(go.Scattermap(lat=work[lat], lon=work[lon], mode="markers", marker=marker))
    center = {"lat": float(work[lat].median()), "lon": float(work[lon].median())}
    span = max(float(work[lat].max() - work[lat].min()), float(work[lon].max() - work[lon].min()))
    zoom = max(0, min(13, float(np.log2(240 / max(span, .001)))))
    figure.update_layout(map={"style": MAP_BASE, "center": center, "zoom": zoom})
    return figure, work, notes


def build_map_visual(frame, spec, uploaded_geo=None):
    selected = filter_rows(frame, spec.get("filters", ()))
    if selected.empty:
        raise ValueError("Los filtros no dejaron observaciones.")
    kind, title = spec["kind"], spec.get("title") or spec["kind"]
    if kind == "Coropleta municipal":
        table, notes = municipal_values(selected, spec)
        figure = choropleth(table, spec.get("unit", ""), PALETTES.get(spec.get("palette"), PALETTES["Azul"]),
                            spec.get("classification", MAP_CLASSIFICATIONS[0]), spec.get("legend_title"))
        figure.update_layout(map={"style": MAP_BASE, "center": {"lat": 40.53, "lon": -3.77}, "zoom": 7.0})
    elif kind in {"Puntos WGS84", "Densidad de puntos"}:
        figure, table, notes = coordinate_map(selected, spec)
    elif kind == "Polígonos propios":
        if not uploaded_geo:
            raise ValueError("Carga una colección GeoJSON WGS84 para generar esta vista.")
        if not spec.get("property") or not spec.get("attribution"):
            raise ValueError("Indica el campo de unión del GeoJSON y la atribución cartográfica.")
        figure, joined, total = municipal_map(selected, spec["code"], spec["metric"], uploaded_geo, spec["property"])
        table = selected[[spec["code"], spec["metric"]]].dropna().copy()
        ids = set(figure.data[0].locations)
        table = table[table[spec["code"]].astype("string").str.strip().isin(ids)]
        notes = [f"{joined} de {total} observaciones con geometría.", spec["attribution"]]
    else:
        raise ValueError("Tipo de mapa no disponible.")
    figure.update_coloraxes(showscale=spec.get("legend", True))
    if kind == "Coropleta municipal":
        figure.update_traces(showscale=spec.get("legend", True), selector={"type": "choroplethmap"})
    elif kind == "Densidad de puntos":
        figure.update_traces(showscale=spec.get("legend", True), selector={"type": "densitymap"})
    return Visual(style_figure(figure, title, spec.get("legend", True)), table.reset_index(drop=True), notes)
