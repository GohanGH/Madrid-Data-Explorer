"""Uniones con estimación previa y claves de salida reutilizables."""
import re
import unicodedata

import pandas as pd


def normalized_name(value):
    ascii_value = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", ascii_value.lower()).strip("_")


def key_role(column):
    name = normalized_name(column)
    if name in {"cod_ine", "codigo_ine", "ine", "codigo_municipio", "cod_municipio", "cmun", "municipio_codigo", "codigo_territorio"}:
        return "Código municipal"
    if name in {"municipio", "nombre_municipio", "municipio_nombre", "nom_mun", "territorio"}:
        return "Nombre municipal"
    if name in {"anio", "ano", "year", "ejercicio"}:
        return "Año"
    if name in {"fecha", "date"}:
        return "Fecha"
    return None


def suggest_keys(left, right):
    return [(a, b, key_role(a)) for a in left for b in right
            if key_role(a) and key_role(a) == key_role(b)]


def _key_part(values):
    if pd.api.types.is_float_dtype(values) or values.dtype == object:
        values = values.map(lambda v: str(int(v)) if isinstance(v, float) and v.is_integer() else v)
    return values.astype("string").str.normalize("NFC").str.strip().str.casefold()


def _year_part(values):
    years = pd.to_numeric(values, errors="coerce")
    return years.where(years.between(1, 9999) & years.mod(1).eq(0)).astype("Int64").astype("string")


def _keys(frame, columns, side, roles):
    parts = []
    for column, role in zip(columns, roles):
        part = _key_part(frame[column])
        if role == "Código municipal":
            from territories import normalize_code

            part = part.map(lambda value: normalize_code(value, "auto")).astype("string").fillna(part)
        elif role == "Año":
            part = _year_part(frame[column])
        parts.append(part)
    keys = zip(*(part.fillna("") for part in parts))
    return pd.Series([(side, i) if "" in key else ("valid", *key)
                      for i, key in enumerate(keys)], dtype=object)


def key_evidence(left, right, limit=20):
    """Rank named or semantically compatible pairs using a bounded sample of actual values."""
    pairs = {(a, b) for a, b, _ in suggest_keys(left, right)}
    right_names = {}
    for col in right:
        right_names.setdefault(normalized_name(col), []).append(col)
    for col in left:
        pairs.update((col, right_col) for right_col in right_names.get(normalized_name(col), []))
    if not pairs:
        cols_a, cols_b = list(left)[:14], list(right)[:14]
        pairs = {(a, b) for a in cols_a for b in cols_b
                 if left[a].dtype == right[b].dtype}
    evidence = []
    for a, b in sorted(pairs)[:200]:
        role_a, role_b = key_role(a), key_role(b)
        role = role_a if role_a == role_b else None
        a_keys = set(_keys(left[[a]].head(500), [a], "A", [role]))
        b_keys = set(_keys(right[[b]].head(500), [b], "B", [role]))
        overlap = len(a_keys & b_keys)
        if overlap or role or normalized_name(a) == normalized_name(b):
            evidence.append({"Izquierda": a, "Derecha": b, "Rol común": role or "Sin identificar",
                             "Tipo A": str(left[a].dtype), "Tipo B": str(right[b].dtype),
                             "Valores comunes en la muestra": overlap})
    return sorted(evidence, key=lambda row: (-row["Valores comunes en la muestra"], row["Izquierda"], row["Derecha"]))[:limit]



def join_preview(left, right, left_key, right_key, how, max_rows=250_000):
    if (not left.columns.is_unique or not right.columns.is_unique
            or not left_key or len(left_key) != len(right_key)
            or len(set(left_key)) != len(left_key) or len(set(right_key)) != len(right_key)
            or any(c not in left for c in left_key) or any(c not in right for c in right_key)):
        raise ValueError("Selecciona claves existentes, distintas y en el mismo orden.")
    if how not in {"inner", "left", "right", "outer"}:
        raise ValueError("Tipo de unión no permitido.")
    paired_roles = [(key_role(x), key_role(y)) for x, y in zip(left_key, right_key)]
    roles = [x if x == y else None for x, y in paired_roles]
    a, b = _keys(left, left_key, "A", roles), _keys(right, right_key, "B", roles)
    ac, bc = a.value_counts(), b.value_counts()
    shared = ac.index.intersection(bc.index)
    if ((ac.reindex(shared) > 1) & (bc.reindex(shared) > 1)).any():
        raise ValueError("Unión muchos a muchos: la misma clave se repite en ambas tablas. "
                         "Añade periodo o categoría a la clave, o resuelve los duplicados.")
    matched = sum(int(ac[k]) * int(bc[k]) for k in shared)
    unmatched_a, unmatched_b = ~a.isin(shared), ~b.isin(shared)
    only_a, only_b = int(unmatched_a.sum()), int(unmatched_b.sum())
    estimate = matched + (only_a if how in {"left", "outer"} else 0) + (
        only_b if how in {"right", "outer"} else 0)
    if estimate > max_rows or estimate * (len(left.columns) + len(right.columns)) > 3_000_000:
        raise ValueError(f"La unión produciría {estimate:,} filas y supera el límite de filas o celdas.")

    dup_a, dup_b = int(a.duplicated().sum()), int(b.duplicated().sum())
    warnings = []
    if not matched:
        warnings.append("Las claves seleccionadas carecen de coincidencias.")
    if dup_a or dup_b:
        warnings.append("Hay claves repetidas. Revisa el nivel de detalle antes de interpretar el resultado.")
    years = None
    for (left_column, right_column), role in zip(zip(left_key, right_key), roles):
        if role == "Año":
            left_years = set(_year_part(left[left_column]).dropna())
            right_years = set(_year_part(right[right_column]).dropna())
            years = {"comunes": sorted(left_years & right_years), "solo_A": sorted(left_years - right_years),
                     "solo_B": sorted(right_years - left_years)}
            break
    if years and not years["comunes"]:
        warnings.append("Los conjuntos tienen años distintos. Comprueba la comparabilidad temporal.")
    if any(x != y and x and y for x, y in paired_roles):
        warnings.append("Algunas claves tienen funciones geográficas o temporales distintas.")
    if (any(key_role(c) in {"Año", "Fecha"} for c in [*left, *right])
            and not any(x == y and x in {"Año", "Fecha"} for x, y in paired_roles)):
        warnings.append("Hay columnas temporales fuera de la unión. Comprueba que los periodos sean comparables.")

    occupied = set(left) | set(right)
    def unique(base):
        name, index = base, 2
        while name in occupied:
            name = f"{base}_{index}"
            index += 1
        occupied.add(name)
        return name

    rename = {c: unique(f"{c}_B") for c in right if c in left}
    internal = unique("__join_key")
    merged = left.reset_index(drop=True).assign(**{internal: a}).merge(
        right.rename(columns=rename).reset_index(drop=True).assign(**{internal: b}), on=internal, how=how
    ).drop(columns=internal)
    for column, right_column in zip(left_key, right_key):
        # A synthetic match key treats blank values as missing, but retains original data.
        second_name = rename.get(right_column, right_column)
        first, second = merged[column], merged[second_name]
        if first.dtype != second.dtype:
            first, second = first.astype(object), second.astype(object)
        merged[column] = first.combine_first(second)
        if column == right_column:
            merged = merged.drop(columns=second_name)
    examples_a = left[left_key].iloc[unmatched_a.to_numpy()].head(10).astype("string").fillna("(Ausente)")
    examples_b = right[right_key].iloc[unmatched_b.to_numpy()].head(10).astype("string").fillna("(Ausente)")
    return merged, {
        "claves": list(zip(left_key, right_key)), "filas_A": len(left), "filas_B": len(right),
        "filas": len(merged), "filas_coincidentes": matched, "solo_izquierda": only_a,
        "solo_derecha": only_b, "coincidencia_A_pct": round(100 * (len(left)-only_a) / max(len(left), 1), 2),
        "coincidencia_B_pct": round(100 * (len(right)-only_b) / max(len(right), 1), 2),
        "duplicados_clave_A": dup_a, "duplicados_clave_B": dup_b,
        "claves_nulas_A": sum(key[0] == "A" for key in a),
        "claves_nulas_B": sum(key[0] == "B" for key in b),
        "cardinalidad": f"{'muchos' if dup_a else 'uno'} a {'muchos' if dup_b else 'uno'}",
        "años": years,
        "filas_A_perdidas": only_a if how in {"inner", "right"} else 0,
        "filas_B_perdidas": only_b if how in {"inner", "left"} else 0,
        "ejemplos_sin_coincidencia_A": examples_a.to_dict("records"),
        "ejemplos_sin_coincidencia_B": examples_b.to_dict("records"),
        "advertencias": warnings,
    }
