"""Visual recipes and sequential joins with a confirmation preview."""
import json

import pandas as pd
import streamlit as st

from analysis_workspace import cleaning, diagnostics, role_map
from interface import metric_cards
from joins import join_preview, key_evidence
from loading import loading
from profiling import NUMERIC
from transformations import AGGREGATIONS, concatenate, execute
from workspace_controls import (
    choose,
    choose_many,
    clause_controls,
    filter_controls,
    optional,
)
from workspace_state import (
    active_key,
    parent_keys,
    redo_table,
    store_table,
    table_kind,
    undo_table,
    version_warnings,
    visible_tables,
)
from workspace_views import focus_table, go_to_data, table_choice

LABELS = {
    "Organizar": {"Elegir, quitar o reordenar columnas": "select", "Renombrar columna": "rename",
                  "Filtrar filas": "filter", "Ordenar filas": "sort", "Quitar duplicados": "deduplicate"},
    "Limpiar": {"Convertir tipo": "cast", "Sustituir o recodificar": "replace", "Normalizar texto": "normalize",
                "Crear código INE": "geo", "Marcar extremos (IQR)": "outlier"},
    "Crear variables": {"Constructor de expresiones": "formula", "Construir razón o tasa": "ratio",
                       "Agrupar y resumir": "aggregate"},
    "Cambiar estructura": {"Largo a ancho · Pivotar": "pivot", "Ancho a largo": "melt",
                           "Dividir texto": "split", "Combinar columnas": "combine", "Concatenar tablas": "concat"},
    "Tiempo": {"Transformar serie temporal": "time"},
}
TIME_METHODS = ("Comparar dos periodos", "Cambio absoluto", "Variación porcentual", "Crecimiento acumulado",
                "Rezago", "Media móvil", "Agregar por periodo")
FORMULAS = ("Sumar", "Restar", "Multiplicar", "Dividir", "Porcentaje", "Razón por unidad",
            "Logaritmo natural", "Raíz cuadrada", "Estandarizar (z)", "Si se cumple…", "Intervalos")


def simple_controls(df, key, op):
    if op in {"select", "sort", "deduplicate"}:
        defaults = list(df) if op == "select" else []
        cols = choose_many("Columnas en orden", df.columns, f"{key}_columns", default=defaults)
        spec = {"columns": cols}
        if op == "sort":
            spec["ascending"] = st.checkbox("Ascendente", value=True, key=f"{key}_asc")
        if op == "select":
            st.caption("El resultado usa el orden en que seleccionas las columnas.")
        if op == "deduplicate":
            st.caption("Si la selección está vacía se comparan todas las columnas.")
        return spec
    if op == "filter":
        return {"filters": filter_controls(df, key, label="Condiciones de filtrado")}
    column = choose("Columna", df.columns, f"{key}_column")
    spec = {"column": column}
    if op == "rename":
        spec["name"] = st.text_input("Nombre nuevo", key=f"{key}_name")
    elif op == "cast":
        target = choose("Convertir a", ["Número", "Fecha", "Texto"], f"{key}_target")
        spec["target"] = target
        if target == "Número":
            spec["decimal_comma"] = st.checkbox("Coma decimal y punto de miles", key=f"{key}_decimal")
        elif target == "Fecha":
            spec["date_format"] = st.text_input("Formato de origen", "%Y-%m-%d", key=f"{key}_format",
                                                help="Por ejemplo, %d/%m/%Y corresponde a 31/12/2025.")
    elif op == "replace":
        spec["missing"] = st.checkbox("Sustituir valores ausentes", key=f"{key}_missing")
        if not spec["missing"]:
            spec["before"] = st.text_input("Valor de origen", key=f"{key}_before")
        spec["to_missing"] = st.checkbox("Convertir coincidencias en ausentes", key=f"{key}_to_missing")
        if not spec["to_missing"]:
            spec["after"] = st.text_input("Valor nuevo", key=f"{key}_after")
    elif op == "normalize":
        spec["casefold"] = st.checkbox("Unificar mayúsculas y minúsculas", key=f"{key}_casefold")
    elif op == "geo":
        spec["system"] = choose("Sistema de entrada", ["auto", "INE", "Almudena", "Nombre municipal"], f"{key}_system")
        spec["name"] = st.text_input("Nombre de salida", "Código INE normalizado", key=f"{key}_name")
    elif op == "outlier":
        spec["name"] = st.text_input("Nombre de la marca", "Valor extremo", key=f"{key}_name")
    return spec


def expression_controls(df, key, op, numeric):
    name = st.text_input("Nombre de salida", key=f"{key}_name")
    if op == "ratio":
        if len(numeric) < 2:
            st.info("Se requieren dos medidas numéricas.")
            return None
        left = choose("Numerador", numeric, f"{key}_column")
        right = choose("Denominador positivo", [c for c in numeric if c != left], f"{key}_right")
        scale = st.number_input("Escala", min_value=0.000001, value=100.0, key=f"{key}_scale")
        return {"name": name, "column": left, "right": right, "scale": scale}
    formula = choose("Operación matemática", FORMULAS, f"{key}_formula")
    if formula == "Si se cumple…":
        condition = clause_controls(df, f"{key}_if")
        then = st.text_input("Etiqueta si se cumple", key=f"{key}_then")
        otherwise = st.text_input("Etiqueta en otro caso", key=f"{key}_otherwise")
        return {"name": name, "formula": formula, "column": condition["column"], "condition": condition,
                "then": then, "otherwise": otherwise}
    if not numeric:
        st.info("Selecciona una medida numérica o convierte su tipo.")
        return None
    left = choose("Columna de entrada", numeric, f"{key}_column")
    spec = {"name": name, "formula": formula, "column": left}
    if formula in FORMULAS[:6]:
        spec["right"] = choose("Segundo operando", [None, *numeric], f"{key}_right",
                               format_func=lambda c: "Constante" if c is None else c)
        if spec["right"] is None:
            spec["constant"] = st.number_input("Constante", value=1.0, key=f"{key}_constant")
        if formula == "Razón por unidad":
            spec["scale"] = st.number_input("Escala (por ejemplo, 10.000)", min_value=.000001, value=100.0, key=f"{key}_scale")
    if formula == "Intervalos":
        entered = st.text_input("Cortes separados por comas", placeholder="10, 20, 50", key=f"{key}_bounds")
        spec["bounds"] = [value.strip() for value in entered.split(",") if value.strip()]
    return spec


def aggregate_controls(df, key, op, numeric):
    groups = choose_many("Claves de agrupación", df.columns, f"{key}_groups")
    remainder = [c for c in df if c not in groups]
    category = choose("Variable de las columnas resultantes", remainder, f"{key}_category") if op == "pivot" else None
    rest = [c for c in remainder if c != category]
    available = [entry for entry in AGGREGATIONS if op != "pivot" or entry not in {"Cuantil", "Media ponderada"}]
    method = choose("Agregación", [None, *available] if op == "pivot" else available, f"{key}_aggregation",
                    format_func=lambda entry: entry or "Sin agregación (claves únicas)")
    choices = rest if method in {None, "Recuento válido"} else [col for col in rest if col in numeric]
    metric = choose("Medida", choices, f"{key}_metric") if method != "Recuento de filas" else None
    spec = {"groups": groups, "category": category, "aggregation": method, "metric": metric}
    if op == "aggregate":
        spec["name"] = st.text_input("Nombre de salida", "Resultado", key=f"{key}_name")
    if method == "Cuantil":
        spec["quantile"] = st.number_input("Cuantil", min_value=0.0, max_value=1.0, value=.5, key=f"{key}_quantile")
    if method == "Media ponderada":
        spec["weight"] = choose("Peso", [col for col in numeric if col != metric], f"{key}_weight")
    return spec


def structure_controls(df, key, op):
    if op == "melt":
        groups = choose_many("Columnas que se conservan", df.columns, f"{key}_groups")
        columns = choose_many("Columnas que pasan a filas", [column for column in df if column not in groups], f"{key}_columns")
        category = st.text_input("Nombre de la categoría", "Variable de origen", key=f"{key}_category")
        name = st.text_input("Nombre del valor", "Medida", key=f"{key}_name")
        return {"groups": groups, "columns": columns, "category": category, "name": name}
    separator = st.text_input("Separador literal", " | " if op == "combine" else "-", key=f"{key}_separator")
    if op == "combine":
        return {"columns": choose_many("Columnas en orden", df.columns, f"{key}_columns"), "separator": separator,
                "name": st.text_input("Nombre de salida", "Texto combinado", key=f"{key}_name")}
    return {"column": choose("Columna de origen", df.columns, f"{key}_column"), "separator": separator,
            "count": st.number_input("Cantidad máxima de fragmentos", 2, 12, 2, key=f"{key}_parts"),
            "name": st.text_input("Prefijo de salida", "Parte", key=f"{key}_name")}


def temporal_controls(df, key, numeric, roles):
    if len(df.columns) < 2 or not numeric:
        st.info("La serie necesita un periodo y una medida.")
        return None
    method = choose("Operación temporal", TIME_METHODS, f"{key}_method")
    preferred = next((column for column, role in roles.items() if role in {"Año", "Fecha"}), None)
    period = choose("Columna de periodo", df.columns, f"{key}_period", default=preferred)
    metric = choose("Medida", [c for c in numeric if c != period], f"{key}_metric")
    if metric is None:
        st.info("Elige una medida distinta del periodo.")
        return None
    entities = [c for c in df if c not in {period, metric}]
    hint = next((c for c in entities if roles.get(c) == "Código municipal"), None)
    entity = (choose("Entidad", entities, f"{key}_entity", default=hint) if method == "Comparar dos periodos"
              else optional("Entidad o grupo", entities, f"{key}_optional_entity", default=hint))
    name = st.text_input("Nombre de salida", f"{method} · {metric}", key=f"{key}_name_{method}")
    spec = {"method": method, "period": period, "metric": metric, "entity": entity, "name": name}
    if method == "Comparar dos periodos":
        periods = df[period].dropna().drop_duplicates().tolist()
        try:
            periods.sort()
        except TypeError:
            st.info("Convierte la columna de periodo a un tipo uniforme.")
            return None
        if len(periods) < 2:
            st.info("Se necesitan al menos dos periodos.")
            return None
        spec["start"] = choose("Periodo inicial", periods, f"{key}_start")
        spec["end"] = choose("Periodo final", periods, f"{key}_end", default=periods[-1])
    elif method in {"Rezago", "Media móvil"}:
        spec["window"] = st.number_input("Observaciones por ventana", 1 if method == "Rezago" else 2, 120, 3, key=f"{key}_window")
    elif method == "Agregar por periodo":
        spec["frequency"] = choose("Frecuencia de salida", ["Mes", "Trimestre", "Año"], f"{key}_frequency")
        spec["aggregation"] = choose("Agregación", [method for method in AGGREGATIONS if method not in {"Cuantil", "Media ponderada"}],
                                     f"{key}_aggregation", default="Suma")
        st.caption("Comprueba que la unidad y la frecuencia original admiten la agregación.")
    return spec


def open_column_recipe(key, column, op):
    state = st.session_state
    category, label = next((family, label) for family, operations in LABELS.items()
                           for label, operation in operations.items() if operation == op)
    state.prep_section = "Transformar"
    state.cfg_prep_category = category
    state[f"cfg_prep_op_{category}"] = label
    state[f"cfg_recipe_{key}_{op}_column"] = column
    focus_table(key, "Preparación")


def revision_choice(state, parents, operation, key):
    revisions = {i: table for i, table in visible_tables(state).items()
                 if parent_keys(table) == parents and table["history"] and operation in table["history"][-1]}
    if not revisions:
        return None
    return choose("Guardar como", [None, *revisions], key,
                  format_func=lambda i: "Rama independiente" if i is None else f"Revisión de #{i} · {revisions[i]['title']}",
                  help="Una revisión avisa en los resultados que dependen de la versión anterior.")


def preview_and_save(key, label, spec, parents, calculation, *, kind, roles=None):
    state = st.session_state
    signature = json.dumps([parents, spec], default=str, ensure_ascii=False, sort_keys=True)
    if st.button("Generar vista previa", key="preview_recipe", type="primary"):
        state.pop("pending_recipe", None)
        try:
            with loading("Preparando vista previa"):
                state.pending_recipe = (signature, calculation())
        except (ValueError, TypeError, KeyError, ArithmeticError) as exc:
            st.error(f"No se pudo calcular. {exc}")
    pending = state.get("pending_recipe")
    if pending is None or pending[0] != signature:
        return
    change = pending[1]
    for note in change.notes:
        st.caption(note)
    st.caption(f"Vista previa · {len(change.frame):,} filas × {len(change.frame.columns)} columnas")
    st.dataframe(change.frame.head(30), hide_index=True, key="recipe_table_preview")
    title = st.text_input("Nombre de la tabla de salida", value=f"{state.tables[key]['title']} · {label}"[:200],
                          key=f"cfg_recipe_name_{key}_{spec['op']}", max_chars=200)
    supersedes = revision_choice(state, parents, "receta", f"cfg_recipe_revision_{key}_{spec['op']}")
    if st.button("Confirmar y guardar versión", key="confirm_recipe", type="primary"):
        try:
            bases = [state.tables[parent] for parent in parents]
            sources = [source for item in bases for source in item["sources"]]
            history = [step for item in bases for step in item["history"]]
            history.append({"operación": label, "receta": spec, "orígenes": list(parents), "observaciones": change.notes})
            if supersedes is not None:
                history[-1]["revisión de"] = supersedes
            metadata = (bases[0].get("metadata", {}) if len(bases) == 1
                        else {"fuentes": [item.get("metadata", {}) for item in bases]})
            new = store_table(state, title, change.frame, sources, history, True, metadata=metadata,
                              kind=kind, parents=parents, roles=roles, supersedes=supersedes)
            state.pop("pending_recipe", None)
            state.prep_notice = f"Versión #{new} guardada."
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))


def transforms(item, key, items):
    df = item["df"]
    category = choose("Herramienta", [*LABELS, "Reutilizar receta"], "cfg_prep_category")
    roles = role_map(item)
    numeric = [col for col, role in roles.items() if role in NUMERIC]
    parents = (key,)
    if category == "Reutilizar receta":
        recipes = {i: table["history"][-1] for i, table in st.session_state.tables.items()
                   if table["history"] and "receta" in table["history"][-1]
                   and table["history"][-1]["receta"]["op"] != "concat"}
        if not recipes:
            st.info("Guarda una transformación para volver a usar su receta.")
            return
        selected = choose("Receta disponible", recipes, "cfg_reuse_recipe",
                          format_func=lambda i: f"#{i} · {recipes[i]['operación']}")
        spec = recipes[selected]["receta"]
        label = recipes[selected]["operación"]
        st.json(spec, expanded=False)
    else:
        label = choose("Transformación", LABELS[category], f"cfg_prep_op_{category}")
        op = LABELS[category][label]
        fields = f"cfg_recipe_{key}_{op}"
        if op in {"ratio", "formula"}:
            params = expression_controls(df, fields, op, numeric)
        elif op in {"aggregate", "pivot"}:
            params = aggregate_controls(df, fields, op, numeric)
        elif op in {"melt", "split", "combine"}:
            params = structure_controls(df, fields, op)
        elif op == "time":
            params = temporal_controls(df, fields, numeric, roles)
        elif op == "concat":
            more = choose_many("Tablas que se añaden por filas", [i for i in items if i != key], f"{fields}_tables",
                               format_func=lambda i: items[i]["title"])
            parents = (key, *more)
            params = {"tables": list(parents)}
        else:
            params = simple_controls(df, fields, op)
        if params is None:
            return
        spec = {"op": op, **params}
    kind = ("Combinada" if spec["op"] == "concat" else "Derivada"
            if spec["op"] in {"formula", "ratio", "time", "aggregate", "outlier"} else "Transformada")
    roles_after = dict(item.get("roles", {}))
    if spec["op"] == "rename" and spec["column"] in roles_after:
        roles_after[spec["name"]] = roles_after.pop(spec["column"])
    if spec["op"] == "cast":
        roles_after.pop(spec["column"], None)
    if spec["op"] == "geo":
        roles_after[spec["name"]] = "Código municipal"
    if spec["op"] in {"pivot", "melt", "concat"}:
        roles_after = None

    def calculate():
        return concatenate([items[i]["df"] for i in parents]) if spec["op"] == "concat" else execute(df, spec)

    preview_and_save(key, label, spec, parents, calculate, kind=kind, roles=roles_after)


def joins(items, key):
    if len(items) < 2:
        st.info("Importa al menos dos tablas para combinar.")
        return
    state = st.session_state
    st.subheader("Combinar tablas")
    left_key = table_choice("Tabla izquierda", "join_left", items, key)
    right_options = {i: item for i, item in items.items() if i != left_key}
    right_key = table_choice("Tabla derecha", f"join_right_{left_key}", right_options)
    left, right = items[left_key], items[right_key]
    a, b = left["df"], right["df"]
    first, second = st.columns(2)
    with first:
        st.caption(f"Izquierda · {len(a):,} filas · {table_kind(left)}")
        keys_a = choose_many("Claves izquierdas en orden", a.columns, f"keys_a_{left_key}")
    with second:
        st.caption(f"Derecha · {len(b):,} filas · {table_kind(right)}")
        keys_b = choose_many("Claves derechas en el mismo orden", b.columns, f"keys_b_{right_key}")
    with st.expander("Sugerencias de claves por nombre, tipo y valores"):
        cache = state.get("join_key_evidence")
        if cache is None or cache[0] != (left_key, right_key):
            cache = ((left_key, right_key), key_evidence(a, b))
            state.join_key_evidence = cache
        if cache[1]:
            st.dataframe(pd.DataFrame(cache[1]), hide_index=True)
            st.caption("Coincidencias estimadas sobre las primeras 500 filas. Comprueba el grano, las unidades y el período.")
        else:
            st.info("Puedes elegir manualmente las claves. Incorpora el periodo a la clave cuando corresponda.")
    methods = {"inner": "Solo coincidencias", "left": "Conservar izquierda", "right": "Conservar derecha", "outer": "Conservar ambas"}
    method = choose("Tipo de unión", methods, "join_method", format_func=methods.get)
    signature = (left_key, right_key, tuple(keys_a), tuple(keys_b), method)
    if st.button("Previsualizar unión", type="primary", key="join_preview"):
        state.pop("pending_join", None)
        state.join_confirmed = False
        try:
            with loading("Comprobando coincidencias y granularidad"):
                frame, detail = join_preview(a, b, keys_a, keys_b, method)
            state.pending_join = (signature, frame, detail)
        except (ValueError, TypeError) as exc:
            st.error(str(exc))
    pending = state.get("pending_join")
    if pending is None or pending[0] != signature:
        return
    _, frame, info = pending
    metric_cards([("Salida", info["filas"], None), ("Cardinalidad", info["cardinalidad"], None),
                  ("Sin pareja a la izquierda", info["solo_izquierda"], None),
                  ("Sin pareja a la derecha", info["solo_derecha"], None)])
    for warning in info["advertencias"]:
        st.warning(warning)
    with st.expander("Examinar claves sin coincidencia y detalles"):
        for side in ("A", "B"):
            records = info[f"ejemplos_sin_coincidencia_{side}"]
            if records:
                st.caption(f"Ejemplos de la tabla {side}")
                st.dataframe(pd.DataFrame(records), hide_index=True)
        st.json(info, expanded=False)
    st.dataframe(frame.head(30), hide_index=True)
    confirmed = st.checkbox("Confirmo que las claves representan entidades y granos compatibles", key="join_confirmed")
    st.text_input("Nombre de la tabla combinada", f"Unión #{left_key} + #{right_key}",
                          key=f"cfg_join_name_{left_key}_{right_key}", max_chars=200)
    supersedes = revision_choice(state, (left_key, right_key), "cardinalidad", f"cfg_join_revision_{left_key}_{right_key}")

    def confirm():
        try:
            step = {"operación": "unión", "tipo": method, "A": left_key, "B": right_key, **info}
            if supersedes is not None:
                step["revisión de"] = supersedes
            # Shared columns describe the left value. Renamed right collisions are profiled separately.
            roles = {column: role for column, role in right.get("roles", {}).items() if column not in a}
            roles.update(left.get("roles", {}))
            new = store_table(state, state[f"cfg_join_name_{left_key}_{right_key}"], frame, (*left["sources"], *right["sources"]),
                              (*left["history"], *right["history"], step), True, kind="Combinada",
                              parents=(left_key, right_key), roles=roles, supersedes=supersedes,
                              metadata={"fuentes A y B": [left.get("metadata", {}), right.get("metadata", {})]})
        except ValueError as exc:
            state.pending_join_error = str(exc)
        else:
            state.pop("pending_join", None)
            state.pending_join_notice = f"Unión #{new} guardada. Puedes seleccionarla en la siguiente unión."

    st.button("Guardar unión", key="join_save", disabled=not confirmed, type="primary", on_click=confirm)


def history(item, key, items):
    st.subheader("Historial de la tabla")
    st.caption(f"Versión #{key} · {table_kind(item)}")
    steps = item["history"]
    if not steps:
        st.info("La tabla original queda disponible para iniciar una rama nueva.")
    for number, step in enumerate(steps, 1):
        title = str(step.get("operación") or step.get("operation") or "Operación")
        with st.expander(f"{number}. {title}"):
            st.json(step)
    candidates = {i: table for i, table in st.session_state.tables.items() if i != key}
    if candidates:
        compare = table_choice("Comparar con otra versión", f"cfg_compare_{key}", candidates,
                               next(iter(parent_keys(item)), None))
        a, b = st.columns(2)
        for slot, (i, table) in zip((a, b), ((key, item), (compare, candidates[compare]))):
            slot.caption(f"#{i} · {table['title']} · {len(table['df']):,} filas")
            slot.dataframe(table["df"].head(12), hide_index=True)
        if compare in items and st.button("Continuar desde la versión comparada", key="branch_from_version"):
            st.session_state.active_table = compare
            st.rerun()


def preparation_screen():
    st.title("Preparación")
    state = st.session_state
    items = visible_tables(state)
    with st.container(horizontal=True, horizontal_alignment="right"):
        st.button("Deshacer", key="prep_undo", disabled=not state.undo, on_click=undo_table, args=(state,))
        st.button("Rehacer", key="prep_redo", disabled=not state.redo_stack, on_click=redo_table, args=(state,))
    if not items:
        st.info("Incorpora una tabla al proyecto para preparar los datos.")
        st.button("Ir a Datos", on_click=go_to_data, args=("Catálogo",), key="prep_empty")
        return
    key = active_key(state)
    item = items[key]
    st.caption(f"#{key} · {item['title']} · {len(item['df']):,} filas")
    if failure := state.pop("pending_join_error", None):
        st.error(failure)
    for pane in ("prep_notice", "pending_join_notice"):
        if message := state.pop(pane, None):
            st.success(message)
    for warning in version_warnings(state.tables, key):
        st.warning(warning)
    section = st.radio("Herramienta de preparación", ["Transformar", "Combinar", "Historial", "Diagnóstico y limpieza"],
                       horizontal=True, key="prep_section", label_visibility="collapsed")
    if section == "Transformar":
        transforms(item, key, items)
    elif section == "Combinar":
        joins(items, key)
    elif section == "Historial":
        history(item, key, items)
    else:
        diagnostics(item, key)
        if hasattr(state, "active_table"):
            def save_correction(title, df, sources, steps, reversible, *, metadata):
                return store_table(state, title, df, sources, steps, reversible, kind="Transformada",
                                   parents=(key,), metadata=metadata, roles=item.get("roles"))

            cleaning(item, key, state.tables, save_correction)
