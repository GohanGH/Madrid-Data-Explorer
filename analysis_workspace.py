"""Dataset profile, assisted cleaning and statistical study interface."""
from dataclasses import asdict

import pandas as pd
import plotly.express as px
import streamlit as st

from analytics import NEEDS_NUMERIC_X, NEEDS_Y, OPERATIONS, analyze
from assistant import plan_analysis
from data_tables import csv_export
from interface import metric_cards, report_chart, validate_selection
from joins import normalized_name
from loading import loading
from map_view import export_chart, linked_map
from profiling import CATEGORIES, ROLES, corrected, schema
from projects import remember_result
from reports import html_report
from settings import ai_settings
from spatial_stats import moran, municipal_edges
from statistical_engine import (
    FAMILIES,
    GROUPED,
    MODELS,
    PAIRED,
    Result,
    association,
    compatible,
    correlation_matrix,
    descriptive,
    frequencies,
    group_test,
    grouped_descriptives,
    numeric_values,
    principal_components,
    regression,
    temporal,
    time_diagnostics,
)
from territories import normalize_code, official_codes
from transformations import filter_rows
from workspace_controls import choose, choose_many, filter_controls, optional
from workspace_state import active_key, version_warnings, visible_tables
from workspace_views import go_to_data


def get_profile(item):
    if "profile" not in item:
        item["profile"] = schema(item["df"])
    return item["profile"]


def role_map(item):
    overrides = item.get("roles", {})
    return {entry["Variable"]: role if (role := overrides.get(entry["Variable"])) in ROLES else entry["Rol"]
            for entry in get_profile(item)["variables"]}


def dictionary(item):
    roles = role_map(item)
    definitions = item.get("metadata", {}).get("variables", {})
    return pd.DataFrame([{**entry, "Rol": roles[entry["Variable"]],
                          "Descripción": definitions.get(entry["Variable"], "Sin descripción publicada")}
                         for entry in get_profile(item)["variables"]])


def provenance(item, **parameters):
    return {"fuentes": item["sources"], "metadatos": item.get("metadata", {}), "transformaciones": item["history"],
            "roles": role_map(item), "filtros": parameters.pop("filtros", {}), "parámetros": parameters}


def diagnostics(item, key):
    profile = get_profile(item)
    st.subheader("Diagnóstico del dataset")
    st.caption(item.get("metadata", {}).get("descripción") or item["title"])
    percent = 100 * profile["missing"] / item["df"].size if item["df"].size else 0
    metric_cards([("Filas", profile["rows"], None), ("Variables", profile["columns"], None),
                  ("Ausentes", f"{percent:.1f} %", "Proporción de celdas ausentes o vacías."),
                  ("Duplicados", profile["duplicates"], "Filas idénticas posteriores a su primera aparición.")])
    info = dictionary(item)
    st.dataframe(info, hide_index=True)
    valid = compatible(item["df"], role_map(item))
    uses = [family for family, options in FAMILIES.items()
            if any(len(study_spec(option, valid)[0]) > study_spec(option, valid)[1] for option in options)]
    if uses:
        st.caption("Usos posibles según el perfil: " + " · ".join(uses))
    with st.expander("Corregir la clasificación de una variable"):
        column = st.selectbox("Variable", list(role_map(item)), key=f"role_col_{key}")
        if column is not None:
            inferred = role_map(item)[column]
            role = st.selectbox("Rol", ROLES, index=ROLES.index(inferred), key=f"role_value_{key}_{column}")
            if st.button("Guardar clasificación", key=f"role_save_{key}"):
                item.setdefault("roles", {})[column] = role
                st.rerun()
    with st.expander("Vista de datos y procedencia"):
        st.dataframe(item["df"].head(150), hide_index=True)
        st.json(provenance(item))
        st.download_button("Descargar datos (CSV)", csv_export(item["df"]), "madrid-datos.csv", "text/csv",
                           key=f"profile_csv_{key}")


def cleaning(item, key, tables, store):
    st.subheader("Mejoras recomendadas para tus datos")
    suggested = get_profile(item)["advice"]
    dismissed = item.setdefault("dismissed", set())
    options = [i for i in range(len(suggested)) if i not in dismissed]
    if not options:
        st.info("El diagnóstico actual no tiene recomendaciones pendientes.")
        return
    pick = st.selectbox("Recomendación", options, key=f"advice_{key}",
                        format_func=lambda i: f"{suggested[i].operation} · {suggested[i].column or 'Tabla completa'}")
    if pick is None:
        return
    entry = suggested[pick]
    st.write(entry.reason)
    st.caption(f"Registros afectados o por revisar: {entry.count}.")
    df = item["df"]
    derived = None
    if entry.actionable:
        try:
            derived = corrected(df, entry)
            comparison = st.columns(2)
            column = entry.column
            if column:
                changed = df[column].astype("string").fillna("").ne(derived[column].astype("string").fillna(""))
                sample = changed[changed].index[:15]
                if sample.empty:
                    sample = df.index[:15]
                comparison[0].dataframe(df.loc[sample, [column]].astype("string"), hide_index=True)
                comparison[1].dataframe(derived.loc[sample, [column]].astype("string"), hide_index=True)
            else:
                comparison[0].dataframe(df[df.duplicated(keep=False)].head(15), hide_index=True)
                comparison[1].dataframe(derived.head(15), hide_index=True)
            comparison[0].caption("Antes")
            comparison[1].caption("Después")
        except ValueError as exc:
            st.warning(str(exc))
    elif entry.column:
        st.dataframe(df[[entry.column]].head(15), hide_index=True)
    with st.container(horizontal=True):
        if st.button("Aplicar y crear versión", disabled=derived is None, key=f"apply_{key}_{pick}", type="primary"):
            try:
                new = store(f"{item['title']} · limpia", derived, item["sources"],
                            (*item["history"], asdict(entry)), True, metadata=item.get("metadata"))
                tables[new]["original"] = item.get("original", key)
                tables[new]["parent"] = key
                tables[new]["roles"] = dict(item.get("roles", {}))
                st.session_state["studio_focus"] = new
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
        if st.button("Descartar recomendación", key=f"dismiss_{key}_{pick}"):
            dismissed.add(pick)
            st.rerun()


def exploratory(item, key):
    roles = role_map(item)
    df = item["df"]
    valid = compatible(df, roles)
    profile = get_profile(item)
    summary = f"{profile['rows']} filas, {profile['columns']} variables, {profile['duplicates']} duplicados exactos."
    st.subheader("Informe exploratorio")
    st.write(summary)
    selected = valid["numeric"][:3]
    figures, sections = [], []
    for variable in selected:
        result = descriptive(df[variable])
        sections.append((variable, result.table))
        st.write(f"**{variable}.** {result.summary}")
        fig = report_chart(result.figure.update_layout(title=f"Distribución de {variable}"))
        st.plotly_chart(fig)
        figures.append(fig)
    if not selected and valid["category"]:
        result = frequencies(df[valid["category"][0]])
        sections.append((valid["category"][0], result.table))
        st.write(result.summary)
        figures.append(report_chart(result.figure))
        st.plotly_chart(figures[-1])
    info = dictionary(item)
    metadata = provenance(item, exploradas=[label for label, _ in sections])
    st.download_button("Descargar informe exploratorio (HTML)",
                       lambda: html_report(item["title"], summary, info, metadata, figures, sections=sections),
                       "madrid-informe.html", "text/html", key=f"initial_report_{key}", on_click="ignore")


def study_spec(name, valid):
    nums, varied, cats = valid["numeric"], valid["varied"], valid["category"]
    if name == "Frecuencias":
        return cats, 0, "Se requieren variables categóricas de entre 2 y 20 valores."
    if name in {"Contingencia y chi-cuadrado", "Fisher exacta", "Pearson", "Spearman", "Kendall"}:
        options = valid["two_groups"] if name == "Fisher exacta" else cats if name.startswith("Contingencia") else varied
        return options, 1, "Se requieren dos variables compatibles con variación."
    if name in PAIRED:
        return nums, 1, "Se requieren dos mediciones numéricas y pares verificables."
    if name in GROUPED | {"Descriptivos por grupos"}:
        groups = valid["two_groups"] if name in {"t independiente (Welch)", "Mann–Whitney"} else cats
        return nums if groups else [], 0, "Se requiere una medida numérica y una variable con los grupos necesarios."
    if name in {"Matriz de correlación", "Componentes principales"}:
        return varied, 1, "Se requieren al menos dos medidas numéricas con variación."
    if name in {"Evolución y cambios", "Autocorrelación temporal", "Descomposición temporal"}:
        return nums if valid["time"] else [], 0, "Se requieren un periodo y un indicador numérico."
    if name in {"Comparación municipal", "Moran global"}:
        return nums if valid["geo"] else [], 0, "Se requieren un código municipal y un indicador numérico."
    if name in MODELS:
        predictors = 2 if name == "Lineal múltiple" else 1
        responses = valid["binary"] if name == "Logística binaria" else valid["counts"] if name == "Poisson" else nums
        choices = varied if name == "Lineal simple" else [*varied, *cats]
        responses = [column for column in responses if len(set(choices) - {column}) >= predictors]
        return responses, 0, "Se requieren una respuesta válida y predictores numéricos con variación."
    return nums, 0, "Se requiere una variable numérica válida."


def geo_study(df, valid, names, key):
    column = st.selectbox("Código municipal", valid["geo"], key=f"geo_code_{key}")
    period = st.selectbox("Variable temporal", [None, *valid["time"]], format_func=lambda x: x or "Sin periodo", key=f"geo_period_{key}")
    years = sorted(df[period].dropna().unique(), reverse=True) if period else []
    validate_selection(f"geo_first_{key}", years)
    validate_selection(f"geo_second_{key}", [None, *years])
    validate_selection(f"geo_metrics_{key}", names, multiple=True)
    a = st.selectbox("Periodo principal", years, key=f"geo_first_{key}") if years else None
    b = st.selectbox("Periodo de comparación", [None, *years], key=f"geo_second_{key}",
                     format_func=lambda x: "Mismo periodo" if x is None else str(x)) if years else None
    metrics = st.multiselect("Indicadores", names, max_selections=2, key=f"geo_metrics_{key}")
    if not metrics:
        return
    system = st.selectbox("Formato de código", ["INE", "Almudena"], index=int(normalized_name(column) == "codigo_territorio"),
                          key=f"geo_system_{key}")
    codes = df[column].map(lambda value: normalize_code(value, system) or normalize_code(value))
    frames = []
    for index, metric in enumerate(metrics if len(metrics) == 2 or b is None else metrics * 2):
        period_value = (b or a) if index else a
        subset = df[period].eq(period_value) if period and period_value is not None else pd.Series(True, index=df.index)
        frame = pd.DataFrame({"INE": codes[subset], "Valor": numeric_values(df.loc[subset, metric])}).dropna(subset=["INE"])
        label = f"{metric} · {period_value}" if period_value is not None else metric
        frames.append((label, frame))
    st.caption("Las vistas comparten selección municipal, zoom y centro. Los rankings y diferencias se calculan por código INE.")
    areas = st.columns(len(frames))
    for index, (label, frame) in enumerate(frames):
        with areas[index]:
            st.write(f"**{label}**")
            linked_map(frame, title=label, unit="", key=f"studio_{key}_{index}",
                       sync=f"studio_viewport_{key}" if len(frames) == 2 else None)
    if any(frame["INE"].duplicated().any() for _, frame in frames):
        st.warning("Filtra la tabla hasta obtener una fila por municipio y periodo.")
        return
    ranking = frames[0][1].dropna().sort_values("Valor", ascending=False)
    ranking = ranking.rename(columns={"Valor": frames[0][0]})
    if len(frames) == 2 and frames[0][0] != frames[1][0]:
        first, second = (entry[0] for entry in frames)
        ranking = ranking.merge(frames[1][1].rename(columns={"Valor": second}), on="INE", how="outer")
        if len(metrics) == 1:
            ranking["Cambio absoluto (principal − comparación)"] = ranking[first] - ranking[second]
    ranking["Municipio"] = ranking["INE"].map(lambda code: official_codes()[code][1])
    ranking = ranking.sort_values(frames[0][0], ascending=False)
    st.dataframe(ranking.head(179), hide_index=True)
    with st.expander("Distribución territorial"):
        chart = report_chart(px.histogram(ranking, x=frames[0][0], title="Distribución entre municipios"))
        st.plotly_chart(chart)
        export_chart(chart, f"geo_distribution_{key}")
    if st.button("Guardar comparación en Resultados", key=f"keep_geo_{key}"):
        params = {"análisis": "Comparación municipal", "código": column, "periodo": period, "principal": a,
                  "comparación": b, "variables": metrics, "formato": system}
        save_result(key, params, Result(ranking, "Comparación territorial por código municipal.", figure=chart))
    st.download_button("Descargar comparación territorial", csv_export(ranking), "madrid-territorio.csv", "text/csv",
                       key=f"geo_csv_{key}")


SUGGESTIONS = {
    "Pearson": "Mide asociación lineal entre medidas. Revisa dispersión, atípicos e independencia.",
    "Spearman": "Mide asociación monótona usando rangos. Puede ser útil con asimetría y valores extremos.",
    "Kendall": "Mide concordancia de rangos. Revisa empates y posible dependencia entre observaciones.",
    "Fisher exacta": "Contrasta asociación en una tabla 2 × 2, también con frecuencias pequeñas.",
    "Descriptivos por grupos": "Resume una medida cuantitativa por categorías. No efectúa un contraste.",
    "Poisson": "Modela recuentos enteros. Para comparar exposición desigual, indica una medida de exposición válida.",
    "t independiente (Welch)": "Compara medias de dos grupos independientes sin suponer varianzas iguales.",
    "t pareada": "Compara diferencias entre dos mediciones de las mismas unidades.",
    "Evolución y cambios": "Conserva el periodo observado y permite ver tendencias o cambios entre periodos.",
    "Moran global": "Evalúa dependencia espacial con una observación por municipio y un grafo de vecindad.",
    "Lineal simple": "Estima la asociación con un predictor cuantitativo y ofrece diagnósticos de residuos.",
    "Componentes principales": "Resume varias medidas estandarizadas. Los componentes son descriptivos.",
}


def save_result(key, params, answer):
    figures = [figure for figure in [answer.figure, *answer.charts] if figure is not None]
    try:
        remember_result(st.session_state, key, params, answer.table, answer.summary, answer.notes, figures)
    except ValueError as exc:
        st.warning(str(exc))
    else:
        st.success("Resultado añadido al cuaderno.")


def show_answer(item, key, params, answer):
    method = params["análisis"]
    st.subheader("Resultado")
    st.write(answer.summary)
    show = answer.table
    if method == "Distribución":
        show = show.astype({"Valor": "string"})
    st.dataframe(show.head(3000), hide_index=True)
    if len(show) > 3000:
        st.caption(f"Vista de 3.000 filas. La descarga contiene las {len(show):,} filas.")
    figures = [report_chart(figure) for figure in [answer.figure, *answer.charts] if figure is not None]
    for figure in figures:
        st.plotly_chart(figure)
    for note in answer.notes:
        st.caption(note)
    meta = provenance(item, **params)
    with st.expander("Descargas y metodología"):
        st.json(meta)
        st.download_button("Descargar resultados (CSV)", lambda: csv_export(answer.table), "madrid-resultados.csv",
                           "text/csv", key=f"study_csv_{key}", on_click="ignore")
        for index, figure in enumerate(figures):
            export_chart(figure, f"studio_{key}_{index}", label=f"Descargar gráfico {index + 1} (HTML)")
        st.download_button("Descargar informe estadístico (HTML)",
                           lambda: html_report(method, answer.summary, answer.table, meta, figures, answer.notes),
                           "madrid-estudio.html", "text/html", on_click="ignore", key=f"study_html_{key}")
        if method == "Moran global":
            neighbors = pd.DataFrame(municipal_edges(), columns=["INE A", "INE B"])
            st.caption("La descarga enumera la red del IGN. Se analiza la subred con datos válidos.")
            st.download_button("Descargar vecinos del IGN (CSV)", csv_export(neighbors), "madrid-vecindad.csv", "text/csv",
                               key=f"neighbors_csv_{key}", on_click="ignore")


def regression_parameters(df, available, method, response, key):
    quantitative = [col for col in available["varied"] if col != response]
    categories = [col for col in available["category"] if col != response and df[col].nunique() <= 12]
    options = quantitative if method == "Lineal simple" else [*quantitative, *categories]
    predictors = choose_many("Predictores", options, f"predictors_{key}_{method}",
                             max_selections=1 if method == "Lineal simple" else 10)
    categorical = [col for col in predictors if col in categories]
    interaction = []
    if method != "Lineal simple" and len(predictors) >= 2:
        interaction = choose_many("Interacción de dos predictores (opcional)", predictors,
                                  f"cfg_interaction_{key}_{method}", max_selections=2)
        if len(interaction) == 1:
            st.caption("Añade un segundo predictor para calcular la interacción.")
    exposure = None
    if method == "Poisson":
        exposure = optional("Exposición para el offset logarítmico", [c for c in quantitative if c not in predictors],
                            f"exposure_{key}_{method}")
    positive = None
    if method == "Logística binaria":
        positive = choose("Clase positiva", df[response].dropna().unique().tolist(), f"positive_{key}_{method}")
    return {"predictores": predictors, "categóricos": categorical, "interacción": interaction,
            "exposición": exposure, "clase_positiva": positive}


def run_study(item, key):
    full = item["df"]
    filters = filter_controls(full, f"cfg_analysis_filter_{key}", label="Filtrar observaciones")
    try:
        df = filter_rows(full, filters)
    except ValueError as exc:
        st.warning(str(exc))
        return
    if df.empty:
        st.info("Los filtros no dejaron observaciones.")
        return
    roles = role_map(item)
    valid = compatible(df, roles)
    family_key = f"family_{key}"
    family = st.session_state.get(family_key, "Descriptivos")
    with st.container(horizontal=True, gap="small", key="analysis_families"):
        for name, methods in FAMILIES.items():
            enabled = any(len(study_spec(method, valid)[0]) > study_spec(method, valid)[1] for method in methods)
            st.button(name, type="primary" if name == family else "tertiary", disabled=not enabled,
                      key=f"family_{key}_{name}", help=None if enabled else study_spec(methods[0], valid)[2],
                      on_click=st.session_state.update, args=({family_key: name},))
    if family not in FAMILIES:
        family = "Descriptivos"
    method = choose("Método", FAMILIES[family], f"method_{key}_{family}")
    options, minimum, why = study_spec(method, valid)
    if len(options) <= minimum:
        st.info(why)
        return
    if method == "Comparación municipal":
        geo_study(df, valid, options, key)
        return
    if advice := SUGGESTIONS.get(method):
        st.caption(advice)
    multi = method in {"Matriz de correlación", "Componentes principales"}
    grouped = method in GROUPED | {"Descriptivos por grupos"}
    x = y = None
    params = {"análisis": method, "filtros": filters}
    if multi:
        variables = choose_many("Medidas", options, f"cfg_multi_{key}_{method}",
                                max_selections=15 if method.startswith("Matriz") else 12)
        params["variables"] = variables
        if method == "Matriz de correlación":
            params["coeficiente"] = choose("Coeficiente", ["Pearson", "Spearman", "Kendall"], f"cfg_corr_{key}")
    else:
        x = choose("Variable principal", options, f"primary_{key}_{method}")
        params["variable"] = x
        if minimum:
            y = choose("Segunda variable", [c for c in options if c != x], f"second_{key}_{method}")
        elif grouped:
            categories = valid["two_groups"] if method in {"t independiente (Welch)", "Mann–Whitney"} else valid["category"]
            y = choose("Variable de grupo", [c for c in categories if c != x], f"group_{key}_{method}")
            if y is None:
                st.info("Elige un grupo distinto del indicador.")
                return
        if y:
            params["segunda variable"] = y
    inferential = method in PAIRED | GROUPED
    confirmed = not inferential or st.checkbox(
        "Cada fila contiene dos mediciones de la misma unidad" if method in PAIRED
        else "Las filas de los grupos son observaciones independientes", key=f"design_{key}_{method}")
    if method in MODELS:
        params.update(regression_parameters(df, valid, method, x, key))
    spatial_code = None
    if method == "Moran global" or (method in {"Lineal simple", "Lineal múltiple"} and valid["geo"]):
        spatial_options = valid["geo"] if method == "Moran global" else [None, *valid["geo"]]
        spatial_code = choose("Código para el diagnóstico espacial", spatial_options, f"spatial_code_{key}_{method}",
                              format_func=lambda c: c or "Sin diagnóstico espacial")
        if spatial_code:
            permutations = choose("Permutaciones", [99, 999, 4999], f"spatial_perm_{key}_{method}", default=999)
            seed = st.number_input("Semilla", min_value=0, max_value=2**32 - 1, value=42, key=f"spatial_seed_{key}_{method}")
            params.update(código_espacial=spatial_code, permutaciones=permutations, semilla=seed)
    if family == "Series temporales":
        period = choose("Periodo", valid["time"], f"time_period_{key}")
        params["periodo"] = period
        if method == "Evolución y cambios":
            by = optional("Separar series por", [c for c in roles if roles[c] in CATEGORIES | {"Código municipal"}],
                          f"time_group_{key}")
            window = st.number_input("Ventana de media móvil", min_value=2, max_value=30, value=3, key=f"time_window_{key}")
            params.update(grupo=by, ventana=window)
        else:
            label = "Rezagos" if method == "Autocorrelación temporal" else "Observaciones por ciclo"
            params["longitud"] = st.number_input(label, min_value=1 if method == "Autocorrelación temporal" else 2,
                                                  max_value=100, value=4, key=f"cfg_length_{key}_{method}")
    selected = [col for col in (x, y) if col] if not multi else params["variables"]
    selected += [col for col in [*params.get("predictores", []), params.get("periodo"), spatial_code] if col and col not in selected]
    if selected:
        with st.expander("Datos y supuestos del método"):
            st.caption(f"{len(df):,} filas tras filtros. Los recuentos del resultado aplican los casos válidos específicos del método.")
            st.dataframe(pd.DataFrame([{"Variable": col, "Rol": roles[col], "Ausentes": int(df[col].isna().sum()),
                                        "Distintos": df[col].nunique()} for col in selected]), hide_index=True)
            if df.duplicated().any():
                st.warning("Hay filas idénticas. Comprueba si son observaciones repetidas antes de interpretar inferencias.")
            if valid["time"] or valid["geo"]:
                st.caption("Si hay medidas repetidas, periodos o territorios vecinos, revisa la independencia. "
                           "Una asociación o valor p pequeño no demuestra causalidad ni importancia práctica.")
    insufficient = multi and len(params["variables"]) < 2
    if st.button("Ejecutar análisis", type="primary", disabled=not confirmed or insufficient, key=f"execute_{key}_{method}"):
        try:
            with loading("Calculando resultado"):
                answer = calculate_study(df, method, params, roles, confirmed)
            save_result(key, params, answer)
            st.session_state.study_preview = (key, params, answer)
        except (ValueError, TypeError, KeyError, ArithmeticError) as exc:
            st.warning(str(exc))
            st.session_state.pop("study_preview", None)
    preview = st.session_state.get("study_preview")
    if preview and preview[:2] == (key, params):
        show_answer(item, key, params, preview[2])
    else:
        previous = next((entry for entry in reversed(st.session_state.project_results)
                         if entry["dataset"] == key and entry["params"] == params), None)
        if previous:
            answer = Result(previous["table"], previous["summary"], previous["notes"], charts=previous["figures"])
            show_answer(item, key, params, answer)


def calculate_study(df, method, params, roles, confirmed=False):
    x, y = params.get("variable"), params.get("segunda variable")
    if method == "Distribución":
        return descriptive(df[x])
    if method == "Frecuencias":
        return frequencies(df[x])
    if method == "Descriptivos por grupos":
        return grouped_descriptives(df, x, y)
    if method == "Matriz de correlación":
        return correlation_matrix(df, params["variables"], params["coeficiente"])
    if method == "Componentes principales":
        return principal_components(df, params["variables"])
    if method in PAIRED | GROUPED:
        return group_test(df, method, x, y, design_confirmed=confirmed)
    if method in MODELS:
        return regression(df, method, x, params["predictores"], params["exposición"],
                          positive=params["clase_positiva"], categorical=params["categóricos"],
                          interaction=params["interacción"], spatial_code=params.get("código_espacial"),
                          permutations=params.get("permutaciones", 999), seed=params.get("semilla", 42))
    if method == "Moran global":
        return moran(df[x], df[params["código_espacial"]], permutations=params["permutaciones"], seed=params["semilla"])
    if method in FAMILIES["Series temporales"]:
        period = params["periodo"]
        if method == "Evolución y cambios":
            return temporal(df, period, x, roles[period], params["grupo"], params["ventana"])
        return time_diagnostics(df, period, x, roles[period], method, params["longitud"])
    return association(df, method, x, y)


def quick_analysis(item, key):
    source = item["df"]
    filters = filter_controls(source, f"cfg_quick_filter_{key}")
    try:
        df = filter_rows(source, filters)
    except ValueError as exc:
        st.warning(str(exc))
        return
    mode = st.radio("Modo", ["Manual", "Pregunta en lenguaje natural"], horizontal=True, key="analysis_mode")
    if mode == "Manual":
        operation = choose("Operación", OPERATIONS, "analysis_operation", format_func=OPERATIONS.get)
        numeric = df.select_dtypes(include="number").columns.tolist()
        x = choose("Primera variable", numeric if operation in NEEDS_NUMERIC_X else df.columns, f"x_{key}_{operation}")
        y = choose("Segunda variable", [col for col in numeric if col != x], f"y_{key}_{operation}") if operation in NEEDS_Y else None
        plan = {"operation": operation, "x": x, "y": y}
    else:
        api_key, model, base_url = ai_settings(st.secrets)
        if not api_key:
            st.info("El asistente opcional requiere una clave. Los métodos y las operaciones manuales están disponibles.")
            return
        st.caption("El proveedor recibe la pregunta y hasta 100 nombres de variables. El cálculo se ejecuta aquí.")
        question = st.text_input("Pregunta", max_chars=1500, key=f"cfg_ai_question_{key}")
        if st.button("Interpretar pregunta", disabled=not question.strip(), key="ask_assistant"):
            from openai import OpenAI, OpenAIError

            st.session_state.pop("ai_plan", None)
            try:
                with loading("Proponiendo un análisis"):
                    client = OpenAI(api_key=api_key, base_url=base_url or None, timeout=20, max_retries=1)
                    st.session_state.ai_plan = (key, question, plan_analysis(client, model, question, df))
            except (ValueError, OpenAIError) as exc:
                st.error(f"No se obtuvo un plan válido. {exc}")
        saved = st.session_state.get("ai_plan")
        if not saved or tuple(saved[:2]) != (key, question):
            return
        plan = saved[2]
        st.json(plan, expanded=False)
    params = {"análisis": OPERATIONS[plan["operation"]], "plan": plan, "filtros": filters}
    if st.button("Ejecutar operación", type="primary", key="execute_quick"):
        try:
            table, figure, notes = analyze(df, plan)
        except ValueError as exc:
            st.warning(str(exc))
            return
        answer = Result(table, params["análisis"], notes, figure)
        st.session_state.quick_preview = (key, params, answer)
        save_result(key, params, answer)
    preview = st.session_state.get("quick_preview")
    if preview and preview[:2] == (key, params):
        show_answer(item, key, params, preview[2])


def analysis_screen():
    st.title("Análisis")
    state = st.session_state
    tables = visible_tables(state)
    if not tables:
        st.info("Importa una tabla para elegir variables y métodos.")
        st.button("Ir al catálogo", on_click=go_to_data, args=("Catálogo",), key="analysis_empty")
        return
    key = active_key(state)
    item = tables[key]
    st.caption(f"#{key} · {item['title']} · {len(item['df']):,} filas")
    for warning in version_warnings(state.tables, key):
        st.warning(warning)
    options = ["Métodos estadísticos", "Operaciones rápidas y asistente"]
    view = st.radio("Espacio de análisis", options, horizontal=True, key="cfg_analysis_view", label_visibility="collapsed")
    if view == options[0]:
        run_study(item, key)
    else:
        quick_analysis(item, key)
