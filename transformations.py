"""Validated table operations used by the preparation workspace and its previews."""
import math
import operator
from dataclasses import dataclass

import numpy as np
import pandas as pd

from data_tables import period_change, ratio_indicator, transform
from statistical_engine import numeric_values
from territories import municipal_identifier

OPERATORS = {"Sumar": operator.add, "Restar": operator.sub, "Multiplicar": operator.mul}
AGGREGATIONS = ("Recuento de filas", "Recuento válido", "Suma", "Media", "Mediana", "Desv. estándar",
                "Mínimo", "Máximo", "Cuantil", "Media ponderada")
COMPARISONS = ("Es igual a", "Es distinto de", "En la selección", "Contiene", "Mayor o igual",
               "Menor o igual", "Entre", "Es ausente", "Tiene valor")
MAX_ROWS = 250_000
MAX_COLUMNS = 3600
MAX_CELLS = 3_000_000


@dataclass
class Change:
    frame: pd.DataFrame
    notes: list


def checked_size(rows, columns):
    if rows > MAX_ROWS or columns > MAX_COLUMNS or rows * columns > MAX_CELLS:
        raise ValueError("El resultado estimado supera los límites de filas, columnas o celdas.")


def require_columns(frame, columns):
    columns = list(columns)
    if not columns or len(set(columns)) != len(columns) or any(column not in frame for column in columns):
        raise ValueError("Selecciona columnas distintas y disponibles.")
    return columns


def new_name(frame, value):
    name = str(value or "").strip()
    if not name or name in frame or len(name) > 200:
        raise ValueError("Escribe un nombre nuevo de entre 1 y 200 caracteres.")
    return name


def typed_value(column, value):
    if pd.api.types.is_bool_dtype(column):
        parsed = str(value).strip().casefold()
        if parsed not in {"true", "false", "sí", "no", "si", "1", "0"}:
            raise ValueError("Escribe sí o no para un valor booleano.")
        return parsed in {"true", "sí", "si", "1"}
    if pd.api.types.is_datetime64_any_dtype(column):
        date = pd.Timestamp(value)
        if pd.isna(date):
            raise ValueError("Escribe una fecha válida en formato ISO.")
        return date
    if pd.api.types.is_numeric_dtype(column):
        text = str(value).strip().replace(",", ".")
        if pd.api.types.is_integer_dtype(column) and text.lstrip("+-").isdigit():
            return int(text)
        try:
            number = float(text)
        except (TypeError, ValueError):
            raise ValueError("Escribe un número válido.") from None
        if not math.isfinite(number):
            raise ValueError("Escribe un número finito.")
        if pd.api.types.is_integer_dtype(column) and number.is_integer():
            return int(number)
        return number
    return str(value)


def condition_mask(frame, clause):
    column = frame[clause["column"]]
    op, value = clause["op"], clause.get("value")
    if op in {"Es ausente", "Tiene valor"}:
        empty = column.isna() | column.astype("string").str.strip().eq("").fillna(False)
        return empty if op == "Es ausente" else ~empty
    if op == "En la selección":
        return column.isin(value)
    if op == "Contiene":
        term = str(value or "").strip()
        if not term:
            raise ValueError("Escribe el texto que quieres buscar.")
        return column.astype("string").str.contains(term, case=False, regex=False, na=False)
    native = typed_value(column, value)
    if op == "Es igual a":
        return column.eq(native).fillna(False)
    if op == "Es distinto de":
        return (column.notna() & column.ne(native)).fillna(False)
    if not (pd.api.types.is_numeric_dtype(column) or pd.api.types.is_datetime64_any_dtype(column)):
        raise ValueError("Convierte la columna a número o fecha antes de aplicar un rango.")
    if op == "Entre":
        end = typed_value(column, clause["end"])
        if native > end:
            raise ValueError("El límite inicial debe ser menor o igual al final.")
        return column.between(native, end).fillna(False)
    if op == "Mayor o igual":
        return column.ge(native).fillna(False)
    if op == "Menor o igual":
        return column.le(native).fillna(False)
    raise ValueError("Criterio de filtro desconocido.")


def filter_rows(frame, filters=()):
    mask = pd.Series(True, index=frame.index)
    for clause in filters:
        if clause["column"] not in frame:
            raise ValueError("La columna del filtro ya no está disponible.")
        mask &= condition_mask(frame, clause)
    return frame.loc[mask]


def expression(frame, spec):
    checked_size(len(frame), len(frame.columns) + 1)
    name = new_name(frame, spec.get("name"))
    op, column = spec["formula"], spec["column"]
    left = numeric_values(frame[column])
    if op in OPERATORS or op in {"Dividir", "Porcentaje", "Razón por unidad"}:
        right = numeric_values(frame[spec["right"]]) if spec.get("right") in frame else float(spec["constant"])
        if op in OPERATORS:
            values = OPERATORS[op](left, right)
        elif op == "Dividir":
            denominator = right.where(right.ne(0)) if isinstance(right, pd.Series) else (right or np.nan)
            values = left / denominator
        else:
            scale = 100 if op == "Porcentaje" else float(spec["scale"])
            if not math.isfinite(scale) or scale <= 0:
                raise ValueError("La escala debe ser positiva y finita.")
            denominator = right.where(right.gt(0)) if isinstance(right, pd.Series) else (right if right > 0 else np.nan)
            values = scale * (left / denominator)
    elif op == "Logaritmo natural":
        values = np.log(left.where(left.gt(0)))
    elif op == "Raíz cuadrada":
        values = np.sqrt(left.where(left.ge(0)))
    elif op == "Estandarizar (z)":
        deviation = left.std(ddof=1)
        if pd.isna(deviation) or deviation <= 0:
            raise ValueError("Se necesitan al menos dos valores válidos con variación.")
        values = (left - left.mean()) / deviation
    elif op == "Si se cumple…":
        mask = condition_mask(frame, spec["condition"])
        values = pd.Series(spec["otherwise"], index=frame.index).where(~mask, spec["then"])
    elif op == "Intervalos":
        bounds = [float(value) for value in spec["bounds"]]
        if not bounds or len(bounds) > 20 or bounds != sorted(set(bounds)) or not all(map(math.isfinite, bounds)):
            raise ValueError("Introduce hasta 20 cortes finitos, distintos y ordenados.")
        values = pd.cut(left, [-np.inf, *bounds, np.inf]).astype("string")
    else:
        raise ValueError("Operación matemática desconocida.")
    if op not in {"Si se cumple…", "Intervalos"}:
        values = numeric_values(values)
    return Change(frame.assign(**{name: values}), [f"{int(values.isna().sum()):,} valores ausentes en la nueva variable."])


def aggregate(frame, groups, method, metric=None, *, quantile=.5, weight=None, name="Resultado"):
    groups = require_columns(frame, groups)
    if not isinstance(name, str) or not name.strip() or name in groups:
        raise ValueError("El nombre de la medida debe ser distinto al de las claves.")
    if method == "Recuento de filas":
        return frame.groupby(groups, dropna=False, observed=True, sort=False).size().rename(name).reset_index()
    if metric not in frame or metric in groups:
        raise ValueError("Selecciona una medida distinta de las claves.")
    work = frame[groups].copy()
    work[name] = frame[metric] if method == "Recuento válido" else numeric_values(frame[metric])
    grouped = work.groupby(groups, dropna=False, observed=True, sort=False)[name]
    if method == "Recuento válido":
        values = grouped.count()
    elif method == "Suma":
        values = grouped.sum(min_count=1)
    elif method == "Cuantil":
        if not 0 <= quantile <= 1:
            raise ValueError("El cuantil debe estar entre cero y uno.")
        values = grouped.quantile(quantile)
    elif method == "Media ponderada":
        if weight not in frame or weight == metric:
            raise ValueError("Selecciona una columna de pesos distinta de la medida.")
        temporary_weight = new_name(work, "__peso_mde")
        weights = numeric_values(frame[weight])
        if weights.lt(0).fillna(False).any():
            raise ValueError("Los pesos deben ser no negativos.")
        weights = weights.where(work[name].notna())
        work[name] = work[name] * weights
        work[temporary_weight] = weights
        totals = work.groupby(groups, dropna=False, observed=True, sort=False)[[name, temporary_weight]].sum(min_count=1)
        values = totals[name] / totals[temporary_weight].where(totals[temporary_weight].gt(0))
    else:
        methods = {"Media": "mean", "Mediana": "median", "Desv. estándar": "std", "Mínimo": "min", "Máximo": "max"}
        if method not in methods:
            raise ValueError("La agregación seleccionada no está disponible.")
        values = grouped.agg(methods[method])
    return values.rename(name).reset_index()


def pivot_table(frame, spec):
    indexes, category, metric = spec["groups"], spec["category"], spec.get("metric")
    method = spec.get("aggregation")
    keys = require_columns(frame, [*indexes, category])
    work = frame.dropna(subset=keys)
    if work.empty:
        raise ValueError("Las claves de la tabla dinámica están vacías.")
    labels = work[category].astype("string")
    if labels.nunique() != work[category].nunique():
        raise ValueError("Dos categorías tienen la misma representación de texto.")
    work = work.assign(**{category: labels})
    checked_size(len(work[indexes].drop_duplicates()), len(indexes) + labels.nunique())
    if method:
        temporary = "__medida_mde"
        while temporary in work:
            temporary += "_"
        work = aggregate(work, keys, method, metric, name=temporary)
        metric = temporary
    elif metric not in frame or metric in keys:
        raise ValueError("Selecciona una medida distinta de las claves.")
    elif work.duplicated(keys).any():
        raise ValueError("Las claves no son únicas. Define una agregación o filtra antes de pivotar.")
    result = work.pivot(index=indexes, columns=category, values=metric)
    overlap = set(result.columns) & set(indexes)
    if overlap:
        raise ValueError("El nombre de una categoría coincide con una clave. Renombra la clave antes de pivotar.")
    return result.reset_index().rename_axis(columns=None)


def restructure(frame, spec):
    op = spec["op"]
    if op == "pivot":
        return pivot_table(frame, spec)
    if op == "melt":
        fixed, variables = spec["groups"], spec["columns"]
        require_columns(frame, [*fixed, *variables])
        if not variables:
            raise ValueError("Elige las variables que convertirás en filas.")
        checked_size(len(frame) * len(variables), len(fixed) + 2)
        category, name = new_name(frame, spec["category"]), new_name(frame, spec["name"])
        if category == name:
            raise ValueError("Los nombres de salida deben ser distintos.")
        return frame.melt(id_vars=fixed, value_vars=variables, var_name=category, value_name=name)
    if op == "combine":
        cols = require_columns(frame, spec["columns"])
        values = frame[cols[0]].astype("string")
        for column in cols[1:]:
            values = values.str.cat(frame[column].astype("string"), sep=spec["separator"])
        return frame.assign(**{new_name(frame, spec["name"]): values})
    prefix = str(spec.get("name") or "").strip()
    separator, count = spec["separator"], int(spec["count"])
    if not prefix or not separator or not 2 <= count <= 12:
        raise ValueError("Indica un prefijo, un separador literal y entre 2 y 12 columnas.")
    checked_size(len(frame), len(frame.columns) + count)
    pieces = frame[spec["column"]].astype("string").str.split(separator, n=count - 1, regex=False, expand=True)
    names = [new_name(frame, f"{prefix} {i+1}") for i in range(count)]
    return frame.assign(**{name: pieces.get(i, pd.NA) for i, name in enumerate(names)})


def time_operation(frame, spec):
    method, period, metric = spec["method"], spec["period"], spec["metric"]
    entity = spec.get("entity")
    cols = require_columns(frame, [*([entity] if entity else []), period, metric])
    if method == "Comparar dos periodos":
        if not entity:
            raise ValueError("Selecciona una entidad por la que comparar.")
        if spec["start"] >= spec["end"]:
            raise ValueError("El periodo final debe ser posterior al inicial.")
        result, missing = period_change(frame, entity, period, metric, spec["start"], spec["end"], spec["name"])
        return Change(result, [f"{missing} entidades sin porcentaje. Se requiere una base positiva."])
    name = new_name(frame, spec.get("name"))
    work = frame[cols].copy()
    raw_period = work[period]
    if pd.api.types.is_numeric_dtype(raw_period):
        years = numeric_values(raw_period)
        valid_years = years.between(1, 9999) & years.mod(1).eq(0)
        work[period] = years.where(valid_years)
        time_unit = "anual"
    else:
        work[period] = pd.to_datetime(raw_period, format="ISO8601", errors="coerce")
        time_unit = "fecha"
    missing = int(work[period].isna().sum())
    work = work.dropna(subset=[period, *([entity] if entity else [])]).sort_values(period, kind="stable")
    if work.empty:
        raise ValueError("Convierte primero la columna a años enteros o fechas ISO válidas.")
    if method == "Agregar por periodo":
        frequency = spec["frequency"]
        if time_unit == "anual" and frequency != "Año":
            raise ValueError("Un año sin fecha no se puede desagregar en meses o trimestres.")
        if time_unit == "fecha":
            code = {"Mes": "M", "Trimestre": "Q", "Año": "Y"}[frequency]
            work[period] = work[period].dt.to_period(code).dt.start_time
        result = aggregate(work, [*([entity] if entity else []), period], spec["aggregation"], metric, name=name)
    else:
        keys = [*([entity] if entity else []), period]
        if work.duplicated(keys).any():
            raise ValueError("Hay varias filas por entidad y periodo. Agrega o filtra antes de calcular.")
        values = numeric_values(work[metric])
        if entity:
            groups = values.groupby(work[entity], sort=False, observed=True)
        else:
            groups = values.groupby(np.zeros(len(work), dtype=int))
        window = int(spec.get("window", 2))
        if not 1 <= window <= 120:
            raise ValueError("El rezago o ventana debe estar entre 1 y 120 observaciones.")
        if method == "Rezago":
            result_values = groups.shift(window)
        elif method == "Media móvil":
            result_values = groups.transform(lambda items: items.rolling(window, min_periods=window).mean())
        elif method == "Crecimiento acumulado":
            base = groups.transform(lambda series: series.iloc[0])
            result_values = 100 * (values - base) / base.where(base.gt(0))
        elif method in {"Variación porcentual", "Cambio absoluto"}:
            previous = groups.shift(1)
            result_values = values - previous
            if method == "Variación porcentual":
                result_values = 100 * result_values / previous.where(previous.gt(0))
        else:
            raise ValueError("Operación temporal desconocida.")
        result = work.assign(**{name: numeric_values(result_values)})
    notes = [f"{missing} filas sin periodo válido. Los intervalos sin observaciones se conservan sin interpolar."]
    if method in {"Rezago", "Media móvil", "Cambio absoluto", "Variación porcentual"}:
        notes.append("La operación usa observaciones consecutivas disponibles, aunque haya intervalos entre ellas.")
    return Change(result, notes)


def concatenate(frames):
    if len(frames) < 2:
        raise ValueError("Selecciona dos o más tablas.")
    columns = set().union(*(frame.columns for frame in frames))
    checked_size(sum(len(frame) for frame in frames), len(columns))
    result = pd.concat(frames, ignore_index=True, sort=False)
    different = len({tuple(frame.columns) for frame in frames}) > 1
    notes = ["Las columnas se alinean por nombre y se conservan las ausencias."] if different else []
    return Change(result, notes)


def execute(frame, spec):
    """Evaluate a declarative recipe and return a previewable table."""
    op, notes = spec["op"], []
    if op == "select":
        result = frame[require_columns(frame, spec["columns"])]
    elif op == "rename":
        name = new_name(frame, spec["name"])
        result = frame.rename(columns={spec["column"]: name})
    elif op == "filter":
        result = filter_rows(frame, spec["filters"])
    elif op == "sort":
        result = frame.sort_values(require_columns(frame, spec["columns"]), ascending=spec["ascending"], kind="stable")
    elif op == "deduplicate":
        result = frame.drop_duplicates(subset=spec.get("columns") or None)
    elif op == "cast":
        column, target = spec["column"], spec["target"]
        if target == "Texto":
            result = frame.assign(**{column: frame[column].astype("string")})
            affected = 0
        else:
            result, affected = transform(frame, f"Convertir a {target.lower()}", column,
                                         decimal_comma=spec.get("decimal_comma", False),
                                         date_format=spec.get("date_format", "%Y-%m-%d"))
        notes.append(f"{affected} valores pasaron a ausentes durante la conversión.")
    elif op in {"replace", "normalize", "geo", "outlier"}:
        column = spec["column"]
        current = frame[column]
        if op == "replace":
            mask = current.isna() if spec["missing"] else current.eq(typed_value(current, spec["before"])).fillna(False)
            replacement = pd.NA if spec.get("to_missing") else typed_value(current, spec["after"])
            if pd.api.types.is_integer_dtype(current) and isinstance(replacement, float):
                current = current.astype("Float64")
            changed = current.mask(mask, replacement)
            notes.append(f"{int(mask.sum())} coincidencias para sustituir.")
        elif op == "normalize":
            changed = current.astype("string").str.normalize("NFC").str.strip().str.replace(r"\s+", " ", regex=True)
            if spec.get("casefold"):
                changed = changed.str.casefold()
        elif op == "geo":
            changed = current.map(lambda value: municipal_identifier(value, spec["system"])).astype("string")
            notes.append(f"{int((current.notna() & changed.isna()).sum())} códigos sin correspondencia en Madrid.")
        else:
            values = numeric_values(current)
            q1, q3 = values.quantile([.25, .75]).tolist()
            if values.count() < 4 or not q3 > q1:
                raise ValueError("El indicador necesita al menos cuatro valores y un rango intercuartílico positivo.")
            iqr = q3 - q1
            changed = (values.lt(q1 - 1.5 * iqr) | values.gt(q3 + 1.5 * iqr)).astype("boolean").where(values.notna())
            notes.append(f"{int(changed.sum())} valores fuera de los límites de Tukey. Revisa el contexto antes de excluirlos.")
        target = new_name(frame, spec["name"]) if op in {"geo", "outlier"} else column
        result = frame.assign(**{target: changed})
    elif op == "ratio":
        result, missing = ratio_indicator(frame, spec["name"], spec["column"], spec["right"], float(spec["scale"]))
        notes.append(f"{missing} valores ausentes. El denominador debe ser positivo.")
    elif op == "formula":
        return expression(frame, spec)
    elif op == "aggregate":
        result = aggregate(frame, spec["groups"], spec["aggregation"], spec.get("metric"),
                           weight=spec.get("weight"), quantile=spec.get("quantile", .5), name=spec["name"])
        notes.append("Las ausencias en las claves se conservan como grupo. Las medidas excluyen valores inválidos.")
    elif op in {"pivot", "melt", "split", "combine"}:
        result = restructure(frame, spec)
    elif op == "time":
        return time_operation(frame, spec)
    else:
        raise ValueError("Transformación desconocida.")
    checked_size(*result.shape)
    return Change(result.reset_index(drop=True), notes)
