"""Small contextual controls shared by filters, transformations and visualizations."""
import streamlit as st

from interface import validate_selection
from transformations import COMPARISONS


def choose(label, options, key, *, default=None, **kwargs):
    options = list(options)
    validate_selection(key, options)
    index = options.index(default) if default in options else 0
    return st.selectbox(label, options, index=index, key=key, **kwargs)


def choose_many(label, options, key, *, default=(), **kwargs):
    options = list(options)
    validate_selection(key, options, multiple=True)
    return st.multiselect(label, options, default=list(default), key=key, **kwargs)


def optional(label, options, key, *, default=None):
    return choose(label, [None, *options], key, default=default, format_func=lambda value: value or "Sin seleccionar")


def clause_controls(frame, key, initial=None):
    initial = initial or {}
    column = choose("Columna", frame.columns, f"{key}_column", default=initial.get("column"))
    op = choose("Criterio", COMPARISONS, f"{key}_op", default=initial.get("op"))
    clause = {"column": column, "op": op}
    if op == "En la selección":
        values = frame[column].dropna().drop_duplicates().head(500).tolist()
        clause["value"] = choose_many("Valores", values, f"{key}_values_{column}",
                                       default=[entry for entry in initial.get("value", []) if entry in values]
                                       if isinstance(initial.get("value"), list) else [])
    elif op not in {"Es ausente", "Tiene valor"}:
        clause["value"] = st.text_input("Valor inicial" if op == "Entre" else "Valor", value=str(initial.get("value", "")) if not isinstance(initial.get("value"), list) else "", key=f"{key}_value")
        if op == "Entre":
            clause["end"] = st.text_input("Valor final", value=str(initial.get("end", "")), key=f"{key}_end")
    return clause


def filter_controls(frame, key, *, label="Filtros", initial=()):
    if not len(frame.columns):
        return []
    with st.expander(label):
        count = st.number_input("Cantidad de condiciones (se cumplen todas)", min_value=0, max_value=4, value=min(len(initial), 4),
                                key=f"{key}_count")
        return [clause_controls(frame, f"{key}_{i}", initial[i] if i < len(initial) else None) for i in range(count)]
