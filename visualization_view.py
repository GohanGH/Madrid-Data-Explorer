"""Contextual builders for saved visualizations and map layers."""
import json
from hashlib import sha256

import streamlit as st

from analysis_workspace import role_map
from interface import navigate
from map_view import PALETTES, export_chart
from profiling import CATEGORIES, NUMERIC, TIME
from projects import remember_result
from territories import municipal_identifier, official_codes
from visualizations import (
    CATEGORICAL_PALETTES,
    CHARTS,
    MAP_CLASSIFICATIONS,
    MAP_TYPES,
    build_chart,
    build_map_visual,
)
from workspace_controls import choose, choose_many, filter_controls, optional
from workspace_state import active_key, version_warnings, visible_tables
from workspace_views import focus_table, go_to_data

AGG = ("Suma", "Media", "Mediana", "Mínimo", "Máximo", "Recuento de filas")


def plot_style(kind, key, previous, *, chart=True):
    title = st.text_input("Título", value=previous.get("title", kind), key=f"{key}_title", max_chars=200)
    spec = {"title": title, "legend": st.checkbox("Mostrar leyenda", value=previous.get("legend", True), key=f"{key}_legend")}
    with st.expander("Estilo y etiquetas"):
        palette_list = CATEGORICAL_PALETTES if chart else PALETTES
        spec["palette"] = choose("Paleta", palette_list, f"{key}_palette", default=previous.get("palette"))
        if chart and kind != "Matriz de correlación":
            spec["x_title"] = st.text_input("Etiqueta X", value=previous.get("x_title", ""), key=f"{key}_x_title", max_chars=100)
            spec["y_title"] = st.text_input("Etiqueta Y", value=previous.get("y_title", ""), key=f"{key}_y_title", max_chars=100)
            spec["log_x"] = st.checkbox("Eje X logarítmico", value=previous.get("log_x", False), key=f"{key}_log_x")
            spec["log_y"] = st.checkbox("Eje Y logarítmico", value=previous.get("log_y", False), key=f"{key}_log_y")
        elif not chart and kind == "Coropleta municipal":
            spec["unit"] = st.text_input("Unidad para el mapa", value=previous.get("unit", ""), key=f"{key}_unit", max_chars=50)
            spec["legend_title"] = st.text_input("Título de leyenda", value=previous.get("legend_title", ""),
                                                 key=f"{key}_legend_title", max_chars=100)
    return spec


def chart_controls(df, roles, key, previous):
    kind = choose("Tipo de gráfico", CHARTS, f"{key}_kind", default=previous.get("kind"))
    fields = f"{key}_{CHARTS.index(kind)}"
    numbers = [col for col, role in roles.items() if role in NUMERIC]
    dimensions = [col for col, role in roles.items() if role in CATEGORIES | TIME | {"Código municipal", "Identificador"}]
    spec = {"kind": kind, **plot_style(kind, fields, previous), "filters": filter_controls(df, f"{key}_filter", initial=previous.get("filters", []))}
    if kind == "Matriz de correlación":
        spec["columns"] = choose_many("Variables numéricas", numbers, f"{fields}_columns",
                                      default=[col for col in previous.get("columns", []) if col in numbers],
                                      max_selections=15)
        spec["coefficient"] = choose("Coeficiente", ["Pearson", "Spearman", "Kendall"], f"{fields}_coef",
                                     default=previous.get("coefficient"))
        return spec
    if kind in {"Barras", "Líneas"}:
        spec["aggregation"] = optional("Agregación", AGG, f"{fields}_agg", default=previous.get("aggregation"))
    if kind in {"Histograma", "Densidad", "Dispersión", "Burbujas", "Mapa de calor"}:
        spec["x"] = choose("Eje X", numbers, f"{fields}_x", default=previous.get("x"))
    elif kind in {"Caja", "Violín"}:
        spec["x"] = optional("Categoría en eje X", dimensions, f"{fields}_x", default=previous.get("x"))
    else:
        spec["x"] = choose("Eje X", df.columns, f"{fields}_x", default=previous.get("x"))
    if kind not in {"Histograma", "Densidad", "Frecuencias"} and spec.get("aggregation") != "Recuento de filas":
        options = [col for col in numbers if col != spec.get("x")]
        spec["y"] = choose("Eje Y", options, f"{fields}_y", default=previous.get("y"))
    if kind == "Burbujas":
        spec["size"] = choose("Variable de tamaño", numbers, f"{fields}_size", default=previous.get("size"))
    if kind != "Mapa de calor":
        options = list(df.columns) if kind in {"Dispersión", "Burbujas"} else dimensions
        color = optional("Color", options, f"{fields}_color", default=previous.get("color"))
        spec.update(color=color, color_discrete=roles.get(color) not in NUMERIC)
    if kind == "Líneas":
        spec["group"] = optional("Separar líneas por", dimensions, f"{fields}_group", default=previous.get("group"))
    if kind != "Densidad":
        spec["facet"] = optional("Dividir en facetas por", dimensions, f"{fields}_facet", default=previous.get("facet"))
    if kind in {"Barras", "Frecuencias"}:
        spec["stack"] = st.checkbox("Apilar grupos", value=previous.get("stack", False), key=f"{fields}_stack")
        spec["order"] = optional("Orden de categorías", ["Eje X", "Medida ascendente", "Medida descendente"],
                                 f"{fields}_order", default=previous.get("order"))
    if kind in {"Histograma", "Mapa de calor"}:
        spec["bins"] = st.number_input("Divisiones", 5, 100, value=previous.get("bins", 20), key=f"{fields}_bins")
    return spec


def map_controls(df, roles, key, previous):
    kind = choose("Tipo de mapa", MAP_TYPES, f"{key}_kind", default=previous.get("kind"))
    fields = f"{key}_{MAP_TYPES.index(kind)}"
    numbers = [col for col, role in roles.items() if role in NUMERIC]
    filters = filter_controls(df, f"{key}_filter", label="Filtros temporales y de datos", initial=previous.get("filters", []))
    spec = {"kind": kind, **plot_style(kind, fields, previous, chart=False), "filters": filters}
    raw = None
    if kind in {"Puntos WGS84", "Densidad de puntos"}:
        st.caption("Indica coordenadas WGS84 en grados decimales.")
        spec["latitude"] = choose("Latitud", numbers, f"{fields}_lat", default=previous.get("latitude"))
        spec["longitude"] = choose("Longitud", [col for col in numbers if col != spec["latitude"]],
                                   f"{fields}_lon", default=previous.get("longitude"))
        spec["metric"] = optional("Medida para color o densidad", [col for col in numbers
                                  if col not in {spec["latitude"], spec["longitude"]}],
                                  f"{fields}_metric", default=previous.get("metric"))
        spec["municipal_layer"] = st.checkbox("Superponer límites municipales IGN", value=previous.get("municipal_layer", True),
                                              key=f"{fields}_boundaries")
        if kind == "Densidad de puntos":
            spec["radius"] = st.number_input("Radio visual (píxeles)", 4, 60, value=previous.get("radius", 22),
                                             key=f"{fields}_radius")
    else:
        suggested = next((col for col, role in roles.items() if role == "Código municipal"),
                         next((col for col, role in roles.items() if role == "Municipio"), next(iter(df))))
        spec["code"] = choose("Identificador geográfico", df.columns, f"{fields}_geo", default=previous.get("code", suggested))
        spec["metric"] = choose("Indicador", [col for col in numbers if col != spec["code"]], f"{fields}_metric",
                                default=previous.get("metric"))
        if kind == "Polígonos propios":
            uploaded = st.file_uploader("Colección GeoJSON WGS84", type=["geojson", "json"], key=f"geo_upload_{key}")
            raw = uploaded.getvalue() if uploaded else None
            spec["property"] = st.text_input("Campo de unión del GeoJSON", value=previous.get("property", ""),
                                             key=f"{fields}_property", max_chars=150)
            spec["attribution"] = st.text_input("Fuente cartográfica", value=previous.get("attribution", ""),
                                                key=f"{fields}_attribution", max_chars=200)
        else:
            default = "Nombre municipal" if roles.get(spec["code"]) == "Municipio" else "auto"
            spec["system"] = choose("Formato de identificación", ["auto", "INE", "Almudena", "Nombre municipal"],
                                    f"{fields}_system", default=previous.get("system", default))
            spec["classification"] = choose("Clasificación", MAP_CLASSIFICATIONS, f"{fields}_class",
                                            default=previous.get("classification"))
            spec["aggregation"] = optional("Agregación por municipio", AGG, f"{fields}_agg",
                                           default=previous.get("aggregation"))
            spec["scope"] = choose_many("Limitar a municipios", official_codes(), f"{fields}_scope",
                                        format_func=lambda code: official_codes()[code][1],
                                        default=[code for code in previous.get("scope", []) if code in official_codes()])
    return spec, raw


def map_context(item, key, spec, visual):
    if spec["kind"] != "Coropleta municipal":
        return
    with st.expander("Comparar municipios y abrir registros"):
        st.dataframe(visual.table, hide_index=True, height=230)
        municipalities = official_codes()
        chosen = choose_many("Municipios para comparar", municipalities, f"cfg_compare_map_{key}", max_selections=6,
                             format_func=lambda code: municipalities[code][1])
        if not chosen:
            return
        st.dataframe(visual.table[visual.table["INE"].isin(chosen)], hide_index=True)
        if st.button("Ver sus registros en Datos", key="visual_map_library"):
            raw = item["df"][spec["code"]]
            matches = raw.map(lambda value: municipal_identifier(value, spec["system"])).isin(chosen)
            st.session_state.map_library_filter = (key, spec["code"], raw[matches].drop_duplicates().tolist(), spec["filters"])
            focus_table(key, "Datos")
            st.rerun()


def visual_screen():
    st.title("Visualización")
    state = st.session_state
    items = visible_tables(state)
    if not items:
        st.info("Importa una tabla para construir un gráfico o un mapa.")
        st.button("Ir a Datos", on_click=go_to_data, args=("Catálogo",), key="visual_empty")
        return
    key = active_key(state)
    item = items[key]
    mode = st.radio("Constructor", ["Gráficos", "Mapas"], horizontal=True, key="visual_section", label_visibility="collapsed")
    geographic = mode == "Mapas"
    kind = "Mapa" if geographic else "Gráfico"
    entries = {entry["id"]: entry for entry in state.project_results if entry.get("kind") == kind and "visual" in entry["params"]}
    editor = choose("Editar una vista guardada", [None, *entries], f"cfg_visual_entry_{kind}",
                    format_func=lambda value: entries[value]["title"] if value else f"Nuevo {kind.lower()}")
    entry = entries.get(editor)
    if entry and entry["dataset"] != key:
        saved_source = entry["dataset"]
        st.caption("La vista guardada se generó con otra tabla. Puedes abrir la tabla original o aplicar su configuración a la activa.")
        if saved_source in items and st.button("Usar la tabla de esta vista", key="use_saved_visual_table"):
            focus_table(saved_source)
            st.rerun()
    view_key = f"cfg_visual_{editor or 'new'}_{key}_{'map' if geographic else 'chart'}"
    previous = entry["params"]["visual"] if entry else {}
    if entry:
        previous = {**previous, "title": entry["title"]}
    frame = item["df"]
    st.caption(f"#{key} · {item['title']} · {len(frame):,} filas")
    for warning in version_warnings(state.tables, key):
        st.warning(warning)
    display, controls = st.columns([2.3, 1], gap="large")
    with controls:
        roles = role_map(item)
        if geographic:
            spec, uploaded = map_controls(frame, roles, view_key, previous)
        else:
            spec, uploaded = chart_controls(frame, roles, view_key, previous), None
        expensive = len(frame) > 10_000 or spec["kind"] in {"Densidad", "Densidad de puntos", "Matriz de correlación", "Polígonos propios"}
        if expensive:
            st.caption("Actualiza la vista cuando hayas terminado de cambiar los controles.")
        refresh = st.button("Actualizar vista", type="primary", key="render_visual")
    marker = sha256(uploaded).hexdigest() if uploaded else None
    signature = json.dumps([key, spec, marker], default=str, ensure_ascii=False, sort_keys=True)
    preview = state.get("visual_preview")
    with display:
        if refresh or (not expensive and (not preview or preview[0] != signature)):
            try:
                visual = build_map_visual(frame, spec, uploaded) if geographic else build_chart(frame, spec)
                state.visual_preview = (signature, visual)
            except (ValueError, TypeError, KeyError, ArithmeticError) as exc:
                state.visual_preview = (signature, str(exc))
            preview = state.visual_preview
        if (not preview or preview[0] != signature) and entry:
            st.plotly_chart(entry["figures"][0], key="original_visual")
            st.caption("Vista guardada. Actualiza para ver los cambios de los controles.")
        elif not preview or preview[0] != signature:
            st.info("Configura las variables y pulsa Actualizar vista.")
        elif isinstance(preview[1], str):
            st.info(preview[1])
        else:
            saved_visual(preview[1], item, key, kind, spec, entry)


def saved_visual(visual, item, key, kind, spec, entry):
    st.plotly_chart(visual.figure, config={"displaylogo": False}, key="workbench_visual")
    if kind == "Mapa":
        map_context(item, key, spec, visual)
    for note in visual.notes:
        st.caption(note)
    with st.expander("Datos y descargas"):
        st.dataframe(visual.table.head(30), hide_index=True)
        export_chart(visual.figure, f"workbench_{kind}", label=f"Descargar {kind.lower()} (HTML)")
    with st.container(horizontal=True, gap="small"):
        save = st.button("Guardar como nueva vista" if entry else "Guardar en Resultados", type="primary", key="keep_visual")
        overwrite = bool(entry and st.button("Actualizar vista guardada", key="overwrite_visual", disabled=entry["dataset"] != key))
        st.button("Ir a Resultados", on_click=navigate, args=("Resultados",), key="visual_go_outputs")
    if save or overwrite:
        try:
            remember_result(st.session_state, key, {"análisis": spec["kind"], "visual": spec}, visual.table,
                            f"{kind} construido a partir de la versión #{key}.", visual.notes, [visual.figure], kind=kind,
                            title=spec["title"], entry_id=entry["id"] if overwrite else None)
            st.success("Vista guardada en el cuaderno.")
        except ValueError as exc:
            st.warning(str(exc))
