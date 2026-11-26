"""Validated statistics. Inference is opt-in and always reports complete cases."""
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import plotly.express as px

from profiling import CATEGORIES, NUMERIC, TIME

FAMILIES = {
    "Descriptivos": ["Distribución", "Frecuencias", "Descriptivos por grupos"],
    "Correlación y asociación": ["Pearson", "Spearman", "Kendall", "Contingencia y chi-cuadrado", "Fisher exacta", "Matriz de correlación"],
    "Comparar grupos": ["t independiente (Welch)", "t pareada", "ANOVA", "Mann–Whitney", "Wilcoxon", "Kruskal–Wallis"],
    "Regresión": ["Lineal simple", "Lineal múltiple", "Logística binaria", "Poisson"],
    "Series temporales": ["Evolución y cambios", "Autocorrelación temporal", "Descomposición temporal"],
    "Análisis geográfico": ["Comparación municipal", "Moran global"],
    "Exploración multivariante": ["Componentes principales"],
}
PAIRED = {"t pareada", "Wilcoxon"}
GROUPED = {"t independiente (Welch)", "ANOVA", "Mann–Whitney", "Kruskal–Wallis"}
MODELS = set(FAMILIES["Regresión"])


@dataclass
class Result:
    table: pd.DataFrame
    summary: str
    notes: list = field(default_factory=list)
    figure: object = None
    charts: list = field(default_factory=list)


def numeric_values(values):
    return pd.to_numeric(values, errors="coerce").replace([np.inf, -np.inf], np.nan)


def compatible(df, roles):
    nums = [c for c, role in roles.items() if c in df and role in NUMERIC and numeric_values(df[c]).count() >= 2]
    varied = [c for c in nums if numeric_values(df[c]).nunique() >= 2]
    cats = [c for c, role in roles.items() if c in df and role in CATEGORIES and 2 <= df[c].nunique() <= 20]
    time = [c for c, role in roles.items() if c in df and role in TIME]
    geo = [c for c, role in roles.items() if c in df and role == "Código municipal"]
    counts = []
    for column in varied:
        values = numeric_values(df[column]).dropna()
        if (values.ge(0) & values.mod(1).eq(0)).all():
            counts.append(column)
    two_groups = [c for c in cats if df[c].nunique() == 2]
    binary = [c for c in df if roles.get(c) in NUMERIC | CATEGORIES and df[c].nunique() == 2]
    return {"numeric": nums, "varied": varied, "category": cats, "time": time, "geo": geo, "binary": binary, "counts": counts, "two_groups": two_groups}


def descriptive(values):
    clean = numeric_values(values).dropna()
    if clean.empty:
        raise ValueError("La variable carece de observaciones numéricas válidas.")
    modes = clean.mode()
    mode = ", ".join(f"{value:g}" for value in modes.head(5)) if clean.duplicated().any() else "Sin moda repetida"
    summary = {
        "Observaciones": len(clean), "Ausentes (%)": 100 * (len(values) - len(clean)) / len(values),
        "Media": clean.mean(), "Mediana": clean.median(), "Moda": mode, "Desviación estándar": clean.std(),
        "Varianza": clean.var(), "Mínimo": clean.min(), "Máximo": clean.max(),
        "Rango intercuartílico": clean.quantile(.75) - clean.quantile(.25),
    }
    summary.update({f"P{p}": clean.quantile(p / 100) for p in (5, 10, 25, 50, 75, 90, 95)})
    table = pd.DataFrame({"Estadístico": summary.keys(), "Valor": list(summary.values())})
    plot_data = clean.rename("Valor").to_frame()
    return Result(table, f"La mediana es {clean.median():.4g} y la media es {clean.mean():.4g}.",
                  [case_note(len(clean), len(values))], px.histogram(plot_data, x="Valor", title="Distribución"),
                  [px.box(plot_data, y="Valor", title="Diagrama de caja")])


def frequencies(values):
    clean = values.astype("string").str.strip().replace("", pd.NA).dropna()
    if clean.empty:
        raise ValueError("La variable carece de categorías observadas.")
    table = clean.astype(str).value_counts().rename_axis("Categoría").reset_index(name="Frecuencia")
    table["Porcentaje válido"] = 100 * table["Frecuencia"] / len(clean)
    return Result(table, f"La categoría más frecuente es {table.iloc[0, 0]}.", [case_note(len(clean), len(values))],
                  px.bar(table.head(20), x="Categoría", y="Frecuencia", title="Frecuencias · hasta 20 categorías"))


def case_note(n, total):
    return f"Se incluyeron {n} observaciones completas y se excluyeron {total - n} filas por datos ausentes o inválidos."


def association(df, test, x, y):
    from scipy import stats

    if x == y:
        raise ValueError("Selecciona dos variables distintas.")
    if test in {"Contingencia y chi-cuadrado", "Fisher exacta"}:
        clean = df[[x, y]].dropna()
        counts = pd.crosstab(clean[x], clean[y])
        if min(counts.shape) < 2 or max(counts.shape) > 20:
            raise ValueError("Se necesitan entre 2 y 20 categorías observadas en cada variable.")
        if test == "Fisher exacta":
            if counts.shape != (2, 2):
                raise ValueError("Fisher exacta requiere una tabla de 2 × 2 con categorías observadas.")
            answer = stats.fisher_exact(counts.to_numpy(), alternative="two-sided")
            table = pd.DataFrame([{"Prueba": test, "Odds ratio (muestra)": answer.statistic,
                                   "p bilateral": answer.pvalue, "Observaciones": len(clean)}])
            return Result(table, f"Fisher exacta bilateral. p = {answer.pvalue:.4g}.",
                          [case_note(len(clean), len(df)), "El contraste supone observaciones independientes."],
                          px.imshow(counts, text_auto=True, title="Tabla de contingencia 2 × 2"))
        stat = stats.chi2_contingency(counts, correction=False)
        v = np.sqrt(stat.statistic / (counts.to_numpy().sum() * (min(counts.shape)-1)))
        small = float((stat.expected_freq < 5).mean())
        notes = ["El contraste supone observaciones independientes."]
        if small > .2 or stat.expected_freq.min() < 1:
            notes.append(f"El {100*small:.1f} % de celdas tiene frecuencia esperada menor de 5. Interpreta el valor p con cautela.")
        header = "Categoría"
        while header in counts:
            header += " (A)"
        table = counts.rename_axis(header).reset_index()
        notes.extend([f"χ² = {stat.statistic:.4g} · gl = {stat.dof} · p = {stat.pvalue:.4g}.",
                      case_note(len(clean), len(df))])
        return Result(table, f"La V de Cramér es {v:.3f} (0 indica ausencia de asociación en la tabla).", notes,
                      px.imshow(counts, text_auto=True, title="Frecuencias observadas"),
                      charts=[])
    clean = df[[x, y]].apply(numeric_values).dropna()
    if len(clean) < 3 or min(clean.nunique()) < 2:
        raise ValueError("Se necesitan al menos tres pares completos y variación en ambas variables.")
    methods = {"Pearson": stats.pearsonr, "Spearman": stats.spearmanr, "Kendall": stats.kendalltau}
    if test not in methods:
        raise ValueError("Método de asociación no disponible.")
    answer = methods[test](clean[x], clean[y])
    direction = "positiva" if answer.statistic > 0 else "negativa" if answer.statistic < 0 else "nula"
    label = "lineal" if test == "Pearson" else "monótona de rangos"
    table = {"Método": [test], "Coeficiente": [answer.statistic], "p": [answer.pvalue],
             "Observaciones": [len(clean)], "Excluidas": [len(df) - len(clean)]}
    if test == "Pearson" and len(clean) >= 4:
        interval = answer.confidence_interval()
        table.update({"IC 95 % inferior": [interval.low], "IC 95 % superior": [interval.high]})
    return Result(pd.DataFrame(table),
                  f"La asociación {label} es {direction}, con coeficiente {answer.statistic:.3f}. No implica causalidad.",
                  [case_note(len(clean), len(df)), "El valor p presupone pares independientes. Revisa atípicos y estructura temporal o espacial."],
                  px.scatter(clean.head(5000), x=x, y=y, title=test))


def group_test(df, test, x, y, *, design_confirmed=False):
    from scipy import stats

    if not design_confirmed:
        raise ValueError("Confirma el diseño de observación antes de ejecutar la prueba.")
    if x == y:
        raise ValueError("Selecciona dos variables distintas.")
    notes, effects = [], {}
    if test in PAIRED:
        clean = df[[x, y]].apply(numeric_values).dropna()
        if len(clean) < 3:
            raise ValueError("Se requieren al menos tres pares completos.")
        a, b = clean[x], clean[y]
        diffs = a - b
        if diffs.nunique() < 2:
            raise ValueError("Las diferencias no presentan variación suficiente.")
        result = stats.ttest_rel(a, b) if test == "t pareada" else stats.wilcoxon(a, b)
        notes.append("Cada fila debe representar el mismo individuo en ambas mediciones. Revisa la normalidad de las diferencias "
                     "para t pareada, o su simetría para Wilcoxon.")
        if test == "t pareada" and stats.shapiro(diffs.head(5000)).pvalue < .05:
            notes.append("Shapiro–Wilk sugiere desviación de la normalidad de las diferencias.")
        if test == "t pareada":
            interval = result.confidence_interval()
            effects = {"Diferencia de medias": diffs.mean(), "IC 95 % inferior": interval.low,
                       "IC 95 % superior": interval.high, "d pareada": diffs.mean() / diffs.std(ddof=1)}
        else:
            nonzero = diffs[diffs.ne(0)]
            ranks = stats.rankdata(abs(nonzero))
            effects = {"Mediana de diferencias": diffs.median(),
                       "Correlación biserial de rangos": np.dot(ranks, np.sign(nonzero)) / ranks.sum()}
        chart = px.histogram(diffs.rename("Diferencia").to_frame(), x="Diferencia")
    else:
        clean = df[[x, y]].assign(**{x: numeric_values(df[x])}).dropna()
        groups = list(clean.groupby(y, observed=True)[x])
        two = test in {"t independiente (Welch)", "Mann–Whitney"}
        if len(groups) < 2 or len(groups) > 20 or (two and len(groups) != 2):
            raise ValueError("Se requieren exactamente dos grupos." if two else "Se requieren entre dos y veinte grupos.")
        sample = [values.to_numpy(dtype=float) for _, values in groups]
        if min(map(len, sample)) < 3 or clean[x].nunique() < 2:
            raise ValueError("Cada grupo necesita al menos tres observaciones y debe existir variación.")
        if test in {"ANOVA", "t independiente (Welch)"} and all(np.ptp(values) == 0 for values in sample):
            raise ValueError("No hay variación interna en los grupos.")
        functions = {"t independiente (Welch)": lambda *a: stats.ttest_ind(*a, equal_var=False),
                     "ANOVA": stats.f_oneway, "Mann–Whitney": stats.mannwhitneyu, "Kruskal–Wallis": stats.kruskal}
        result = functions[test](*sample)
        notes.append("Las filas de los grupos deben ser independientes. Una agrupación geográfica o longitudinal puede invalidar el valor p.")
        if test in {"ANOVA", "t independiente (Welch)"}:
            if any(np.ptp(v) > 0 and stats.shapiro(v[:5000]).pvalue < .05 for v in sample):
                notes.append("Shapiro–Wilk sugiere desviación de la normalidad en algún grupo.")
            if test == "ANOVA" and stats.levene(*sample).pvalue < .05:
                notes.append("Levene sugiere varianzas distintas. Interpreta ANOVA con cautela.")
        else:
            notes.append("Las pruebas de rangos comparan distribuciones. Para interpretarlas como diferencias de localización revisa su forma.")
        if test == "t independiente (Welch)":
            interval = result.confidence_interval()
            a, b = sample
            delta = a.mean() - b.mean()
            dof = len(a) + len(b) - 2
            pooled = np.sqrt(((len(a) - 1) * a.var(ddof=1) + (len(b) - 1) * b.var(ddof=1)) / dof)
            effects = {"Diferencia de medias A − B": delta, "IC 95 % inferior": interval.low, "IC 95 % superior": interval.high,
                       "g de Hedges (DE agrupada)": (1 - 3 / (4 * dof - 1)) * delta / pooled}
        elif test == "Mann–Whitney":
            effects = {"Correlación biserial de rangos": 2 * result.statistic / (len(sample[0]) * len(sample[1])) - 1}
        elif test == "ANOVA":
            grand = clean[x].mean()
            between = sum(len(values) * (values.mean() - grand) ** 2 for values in sample)
            effects = {"Eta cuadrado": between / ((clean[x] - grand) ** 2).sum()}
        elif test == "Kruskal–Wallis":
            effects = {"Eta cuadrado de rangos": max(0, (result.statistic - len(sample) + 1) / (len(clean) - len(sample)))}
        if two:
            effects = {"Grupo A": str(groups[0][0]), "Grupo B": str(groups[1][0]), **effects}
        chart = px.box(clean, x=y, y=x, title="Distribución por grupo")
    return Result(pd.DataFrame([{"Prueba": test, "Estadístico": result.statistic, "p": result.pvalue,
                                 "Observaciones": len(clean), **effects}]),
                  f"{test} da un estadístico de {result.statistic:.4g} y un valor p de {result.pvalue:.4g}. "
                  "Interprétalo junto con el diseño y los supuestos.",
                  [case_note(len(clean), len(df)), *notes], chart)


def model_design(clean, predictors, categorical, interaction):
    design = pd.DataFrame(index=clean.index)
    terms, references = {}, []
    for predictor in predictors:
        if predictor not in categorical:
            design[predictor] = clean[predictor].astype(float)
            terms[predictor] = [predictor]
    for predictor in categorical:
        observed = sorted(clean[predictor].astype("string").unique().tolist())
        if not 2 <= len(observed) <= 12:
            raise ValueError("Cada predictor categórico debe tener entre 2 y 12 niveles en los casos completos.")
        references.append(f"{predictor}. Nivel de referencia: {observed[0]}.")
        terms[predictor] = []
        for level in observed[1:]:
            label = f"{predictor} = {level}"
            while label in design:
                label += " (categoría)"
            design[label] = clean[predictor].astype("string").eq(level).astype(float)
            terms[predictor].append(label)
    if interaction:
        if len(interaction) != 2 or len(set(interaction)) != 2 or any(term not in terms for term in interaction):
            raise ValueError("Selecciona dos predictores distintos para la interacción.")
        for a in terms[interaction[0]]:
            for b in terms[interaction[1]]:
                label = f"{a} × {b}"
                while label in design:
                    label += " (interacción)"
                design[label] = design[a] * design[b]
    if len(design.columns) > 40:
        raise ValueError("La codificación o interacción genera demasiados coeficientes (límite de 40).")
    return design, references


def regression(df, model, response, predictors, exposure=None, *, positive=None, spatial_code=None,
               permutations=999, seed=42, categorical=(), interaction=()):
    import statsmodels.api as sm
    from statsmodels.tools.sm_exceptions import PerfectSeparationError

    if model not in MODELS:
        raise ValueError("Modelo no disponible.")
    if spatial_code is not None:
        df = df.reset_index(drop=True)
    columns = [response, *predictors, *([exposure] if exposure else [])]
    categorical = list(categorical)
    if (len(set(columns)) != len(columns) or len(predictors) > 10 or not predictors
            or len(set(categorical)) != len(categorical) or not set(categorical) <= set(predictors)):
        raise ValueError("Elige variables distintas y entre uno y diez predictores.")
    if (model == "Lineal simple" and (len(predictors) != 1 or categorical or interaction)
            or model == "Lineal múltiple" and len(predictors) < 2):
        raise ValueError("La regresión simple requiere un predictor numérico y la múltiple al menos dos predictores.")
    clean = df[columns].copy()
    for col in columns:
        if col not in categorical and (model != "Logística binaria" or col != response):
            clean[col] = numeric_values(clean[col])
    clean = clean.dropna()
    if len(clean) < 6:
        raise ValueError("Hay pocos casos completos para estimar el modelo.")
    X, references = model_design(clean, predictors, categorical, interaction)
    if len(clean) < len(X.columns) + 3:
        raise ValueError("Hay pocos casos completos para el número de coeficientes.")
    constant = "Intercepto"
    while constant in X:
        constant += " (modelo)"
    X.insert(0, constant, 1.0)
    if np.linalg.matrix_rank(X) < X.shape[1]:
        raise ValueError("El modelo no es identificable: hay predictores constantes o colineales.")
    y = clean[response]
    if y.nunique() < 2:
        raise ValueError("La respuesta debe tener variación.")
    notes = [case_note(len(clean), len(df)),
             "Los coeficientes son asociaciones condicionadas. Revisa independencia, especificación y observaciones influyentes.",
             *references]
    if np.linalg.cond(X) > 1e6:
        notes.append("La matriz de diseño está mal condicionada. Revisa escalas y multicolinealidad.")
    extra = None
    try:
        if model == "Logística binaria":
            if y.nunique() != 2 or positive not in y.unique():
                raise ValueError("La respuesta requiere dos clases y una clase positiva elegida.")
            y = y.eq(positive).astype(float)
            if y.value_counts().min() < 3:
                raise ValueError("Se requieren al menos tres casos completos por clase.")
            fitted = sm.Logit(y, X).fit(disp=False, maxiter=100)
            if not fitted.mle_retvals["converged"] or np.abs(fitted.params).max() > 40:
                raise ValueError("La logística no converge de forma fiable o presenta separación.")
            extra = "Odds ratio"
            summary = f"Pseudo-R² de McFadden = {fitted.prsquared:.3f}. La clase positiva es {positive}."
            if y.value_counts().min() < 10 * len(predictors):
                notes.append("Hay pocos casos por clase y predictor. Los intervalos pueden ser inestables.")
        elif model == "Poisson":
            y = y.astype(float)
            if ((y < 0) | (y % 1 != 0)).any():
                raise ValueError("Poisson requiere recuentos enteros no negativos.")
            if exposure and (clean[exposure] <= 0).any():
                raise ValueError("La exposición debe ser estrictamente positiva.")
            offset = np.log(clean[exposure].astype(float)) if exposure else None
            fitted = sm.GLM(y, X, family=sm.families.Poisson(), offset=offset).fit()
            if not fitted.converged:
                raise ValueError("El modelo Poisson no convergió.")
            dispersion = fitted.pearson_chi2 / fitted.df_resid
            summary = f"La dispersión de Pearson es {dispersion:.3f} (cerca de 1 según el modelo Poisson)."
            if dispersion > 1.5:
                notes.append("Posible sobredispersión. Los errores estándar e intervalos Poisson pueden ser demasiado estrechos.")
            if exposure:
                notes.append(f"Se usó el logaritmo de {exposure} como offset de exposición.")
            extra = "Razón de tasas"
        else:
            fitted = sm.OLS(y.astype(float), X).fit(cov_type="HC3")
            summary = f"El modelo explica aproximadamente el {100*fitted.rsquared:.1f} % de la variabilidad observada."
            notes.append(f"R² ajustado = {fitted.rsquared_adj:.3f}. Errores estándar HC3 y gráfico de residuos.")
    except (np.linalg.LinAlgError, PerfectSeparationError) as exc:
        raise ValueError("El modelo no es estimable con los datos y predictores seleccionados.") from exc
    if not np.isfinite(fitted.params).all():
        raise ValueError("El modelo produjo coeficientes no finitos. Revisa la escala y el diseño.")
    interval = fitted.conf_int().to_numpy()
    table = pd.DataFrame({"Variable": X.columns, "Coeficiente": fitted.params.to_numpy(), "Error estándar": fitted.bse.to_numpy(),
                          "IC 95 % inferior": interval[:, 0], "IC 95 % superior": interval[:, 1], "p": fitted.pvalues.to_numpy()})
    if model in {"Lineal simple", "Lineal múltiple"}:
        table["R²"] = fitted.rsquared
        table["Observaciones"] = len(clean)
    if extra:
        with np.errstate(over="ignore"):
            table[extra] = np.exp(table["Coeficiente"])
            table[f"{extra} · IC inferior"] = np.exp(interval[:, 0])
            table[f"{extra} · IC superior"] = np.exp(interval[:, 1])
    predicted = fitted.fittedvalues if model != "Logística binaria" else fitted.predict(X)
    diag = pd.DataFrame({"Predicción": predicted, "Residuo": y.astype(float) - predicted})
    charts = []
    if model == "Lineal simple":
        predictor = predictors[0]
        fit = px.scatter(clean.head(5000), x=predictor, y=response, title="Ajuste lineal simple")
        endpoints = [float(clean[predictor].min()), float(clean[predictor].max())]
        fit.add_scatter(x=endpoints, y=[float(fitted.params[constant] + fitted.params[predictor] * point)
                                      for point in endpoints], mode="lines", name="Ajuste OLS")
        charts.append(fit)
    if spatial_code is not None:
        from spatial_stats import moran

        try:
            spatial = moran(diag["Residuo"], df.loc[clean.index, spatial_code], permutations=permutations, seed=seed)
        except ValueError as exc:
            notes.append(f"Diagnóstico espacial de residuos sin calcular. {exc}")
        else:
            stat = spatial.table.iloc[0]
            for column in spatial.table:
                table[f"Residuos · {column}"] = stat[column]
            notes.extend([f"Residuos de la regresión. {spatial.summary}",
                          ("La permutación de residuos ajustados es un diagnóstico exploratorio. "
                          "Su intercambiabilidad puede verse afectada por el propio modelo."),
                          *spatial.notes])
            charts.append(spatial.figure)
    return Result(table, summary, notes,
                  px.scatter(diag.head(5000), x="Predicción", y="Residuo", title="Diagnóstico · residuos frente a predicción"),
                  charts)


def temporal(df, period, target, role, by=None, window=3):
    if period == target or by in {period, target} or window < 2:
        raise ValueError("Selecciona variables distintas y al menos dos observaciones para la media móvil.")
    cols = [period, target, *([by] if by else [])]
    clean = df[cols].copy()
    clean[target] = numeric_values(clean[target])
    if role == "Año":
        years = numeric_values(clean[period])
        clean[period] = years.where(years.between(1, 9999) & years.mod(1).eq(0)).astype("Int64")
    else:
        clean[period] = pd.to_datetime(clean[period], errors="coerce", format="ISO8601")
    clean = clean.dropna().sort_values(period)
    if len(clean) < 2 or clean.duplicated([period, *([by] if by else [])]).any():
        raise ValueError("Se necesitan al menos dos filas y una fila por periodo y grupo. Filtra los totales o agrega de forma explícita.")
    occupied = set(cols)

    def output_name(base):
        while base in occupied:
            base += " (resultado)"
        occupied.add(base)
        return base

    if not by:
        by = output_name("Serie")
        clean[by] = target
    if clean[by].nunique() > 30:
        raise ValueError("Filtra a un máximo de 30 series antes de comparar.")
    groups = clean.groupby(by, sort=False, observed=True)
    previous = groups[target].shift()
    change, percentage, average = map(output_name, ["Cambio absoluto", "Cambio (%)", "Media móvil"])
    clean[change] = clean[target] - previous
    clean[percentage] = 100 * clean[change] / previous.where(previous.ne(0))
    clean[average] = groups[target].transform(lambda v: v.rolling(window, min_periods=window).mean())
    if role == "Año":
        frequency = "anual"
    else:
        dates = pd.DatetimeIndex(clean[period].drop_duplicates().sort_values())
        frequency = (pd.infer_freq(dates) if len(dates) >= 3 else None) or "irregular o indeterminada"
    spans = groups[target].agg(["first", "last"])
    notes = [case_note(len(clean), len(df)),
             f"Frecuencia {frequency}. Los cambios comparan observaciones consecutivas disponibles y no se interpolan huecos.",
             f"Media móvil de {window} observaciones consecutivas. Cambio porcentual omitido cuando la base es cero."]
    for name, first, last in spans.head(6).itertuples():
        notes.append(f"{name}: cambio entre primera y última observación = {last-first:.4g}.")
    figure = px.line(clean, x=period, y=target, color=by, markers=True, title="Evolución")
    return Result(clean, f"Se comparan {len(spans)} series ordenadas por {period}.", notes, figure,
                  [px.line(clean, x=period, y=average, color=by, title="Tendencia suavizada")])


def grouped_descriptives(df, measure, group):
    if measure == group:
        raise ValueError("Selecciona un grupo y una medida distintos.")
    clean = df[[measure, group]].assign(**{measure: numeric_values(df[measure])}).dropna()
    if not 2 <= clean[group].nunique() <= 20:
        raise ValueError("Los casos completos deben contener entre 2 y 20 grupos.")
    summary = clean.groupby(group, observed=True)[measure].agg(
        Observaciones="size", Media="mean", Mediana="median", Desviación="std", Mínimo="min", Máximo="max",
    ).reset_index()
    return Result(summary, f"Resumen descriptivo en {len(summary)} grupos.",
                  [case_note(len(clean), len(df)), "Cada grupo se resume por separado y sin ponderación."],
                  px.box(clean.head(10_000), x=group, y=measure))


def correlation_matrix(df, columns, method):
    if not 2 <= len(columns) <= 15 or len(set(columns)) != len(columns):
        raise ValueError("Selecciona entre dos y quince medidas distintas.")
    methods = {"Pearson": "pearson", "Spearman": "spearman", "Kendall": "kendall"}
    if method not in methods:
        raise ValueError("Elige un coeficiente válido.")
    values = df[columns].apply(numeric_values)
    matrix = values.corr(method=methods[method], min_periods=3)
    valid = values.notna().astype(int)
    counts = valid.T @ valid
    records = [{"Variable A": a, "Variable B": b, "Coeficiente": matrix.loc[a, b],
                "Pares completos": int(counts.loc[a, b]), "Pares excluidos": len(df) - int(counts.loc[a, b])}
               for index, a in enumerate(columns) for b in columns[index + 1:]]
    chart = px.imshow(matrix, zmin=-1, zmax=1, color_continuous_scale="RdBu_r", text_auto=".2f",
                      title=f"Matriz de correlación · {method}")
    return Result(pd.DataFrame(records), f"{len(records)} pares de variables con coeficiente {method}.",
                  ["Cada celda utiliza sus propios pares completos. Las celdas vacías carecen de variación o de casos suficientes.",
                   "La matriz es descriptiva y puede mezclar muestras distintas."], chart)


def regular_series(df, period, metric, role):
    if period == metric:
        raise ValueError("El periodo y la medida deben ser distintos.")
    clean = df[[period, metric]].copy()
    clean[metric] = numeric_values(clean[metric])
    clean[period] = (numeric_values(clean[period]) if role == "Año"
                     else pd.to_datetime(clean[period], errors="coerce", format="ISO8601"))
    clean = clean.dropna().sort_values(period)
    if not 8 <= len(clean) <= 10_000 or clean[period].duplicated().any():
        raise ValueError("Se requieren entre 8 y 10.000 periodos únicos para una sola serie.")
    periods = clean[period]
    frequency = ("anual" if periods.mod(1).eq(0).all() and periods.diff().iloc[1:].eq(1).all() else None
                 ) if role == "Año" else pd.infer_freq(pd.DatetimeIndex(periods))
    if not frequency:
        raise ValueError("La serie tiene huecos o intervalos irregulares. Revisa o agrega los periodos en Preparación.")
    if clean[metric].nunique() < 2:
        raise ValueError("La serie necesita variación.")
    return clean, frequency


def time_diagnostics(df, period, metric, role, method, length):
    clean, frequency = regular_series(df, period, metric, role)
    values = clean[metric].astype(float).to_numpy()
    notes = [case_note(len(clean), len(df)), f"Frecuencia observada: {frequency}. Se usa una única serie regular."]
    if method == "Autocorrelación temporal":
        from statsmodels.tsa.stattools import acf

        if not 1 <= length < len(values):
            raise ValueError("El número de rezagos debe ser menor que el número de observaciones.")
        acf_values = acf(values, nlags=length, fft=True)
        table = pd.DataFrame({"Rezago": np.arange(1, length + 1), "Autocorrelación": acf_values[1:]})
        figure = px.bar(table, x="Rezago", y="Autocorrelación")
        bound = 1.96 / np.sqrt(len(values))
        for cutoff in [-bound, bound]:
            figure.add_hline(y=cutoff, line_dash="dot")
        notes.append("Bandas orientativas de ruido blanco. Una tendencia o estacionalidad puede producir autocorrelación.")
    elif method == "Descomposición temporal":
        from statsmodels.tsa.seasonal import seasonal_decompose

        if length < 2 or len(values) < 2 * length:
            raise ValueError("La descomposición requiere al menos dos ciclos completos del periodo seleccionado.")
        result = seasonal_decompose(values, model="additive", period=length)
        labels = [name if name not in {period, metric} else f"{name} (componente)"
                  for name in ("Tendencia", "Estacional", "Residuo")]
        table = clean.assign(**dict(zip(labels, (result.trend, result.seasonal, result.resid))))
        figure = px.line(table, x=period, y=[metric, *labels])
        notes.append(f"Modelo aditivo con {length} observaciones por ciclo. La tendencia y el residuo quedan incompletos en los bordes.")
    else:
        raise ValueError("Diagnóstico temporal no disponible.")
    return Result(table, f"{method} sobre {len(clean)} periodos.", notes, figure)


def principal_components(df, columns):
    if not 2 <= len(columns) <= 12 or len(set(columns)) != len(columns):
        raise ValueError("Selecciona de 2 a 12 variables cuantitativas distintas.")
    complete = df[columns].apply(numeric_values).dropna().head(20_001)
    if not max(5, len(columns) + 1) <= len(complete) <= 20_000:
        raise ValueError("Se necesitan más casos completos que variables, con un máximo de 20.000 filas.")
    centered = complete.to_numpy(dtype=float)
    deviation = centered.std(axis=0, ddof=1)
    if (deviation <= 0).any() or not np.isfinite(deviation).all():
        raise ValueError("Las variables deben presentar variación en la muestra completa.")
    standardized = (centered - centered.mean(axis=0)) / deviation
    _, singular, rotation = np.linalg.svd(standardized, full_matrices=False)
    signs = np.sign(rotation[np.arange(len(columns)), abs(rotation).argmax(axis=1)])
    rotation *= signs[:, np.newaxis]
    proportions = 100 * singular**2 / (singular**2).sum()
    labels = [f"CP {i+1}" for i in range(len(columns))]
    table = pd.DataFrame(rotation.T, columns=labels).assign(Variable=columns)
    scores = pd.DataFrame(standardized @ rotation[:2].T, columns=labels[:2]).head(5000)
    figure = px.scatter(scores, x=labels[0], y=labels[1], title="Puntuaciones de los dos primeros componentes")
    chart = px.bar(pd.DataFrame({"Componente": labels, "Varianza (%)": proportions}), x="Componente", y="Varianza (%)")
    return Result(table, f"Los dos primeros componentes explican {proportions[:2].sum():.1f} % de la varianza.",
                  [case_note(len(complete), len(df)), "Se estandarizan las variables con desviación muestral. Análisis descriptivo.",
                   "Se representan hasta 5.000 puntuaciones. La tabla contiene los coeficientes de cada componente."], figure, [chart])
