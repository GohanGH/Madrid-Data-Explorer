import io
import json
from pathlib import Path
from zipfile import ZipFile

import numpy as np
import pandas as pd
import pytest

from projects import load_project, remember_result, save_project
from reports import notebook_report
from statistical_engine import (
    association,
    correlation_matrix,
    group_test,
    grouped_descriptives,
    principal_components,
    regression,
    time_diagnostics,
)
from transformations import aggregate, concatenate, execute, filter_rows
from visualizations import CHARTS, build_chart, build_map_visual
from workspace_state import (
    initialize,
    redo_table,
    remove_unused,
    store_table,
    undo_table,
    version_warnings,
    visible_tables,
)

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def arbitrary():
    return pd.DataFrame({"Taller": ["A", "A", "A", "B", "B", "B"],
                         "Año": [2022, 2023, 2024] * 2, "Piezas": [10., 12., 15., 20., 16., 25.],
                         "Horas": [2., 3., 4., 3., 4., 4.], "Lote": ["a-1", "a-2", "a-3", "b-1", "b-2", "b-3"]})


def test_non_destructive_selection_reordering_and_typed_filter(arbitrary):
    source = arbitrary.copy()
    cols = execute(arbitrary, {"op": "select", "columns": ["Horas", "Taller"]}).frame
    assert list(cols) == ["Horas", "Taller"]
    selected = filter_rows(arbitrary, [{"column": "Año", "op": "Entre", "value": "2023", "end": "2024"},
                                       {"column": "Lote", "op": "Contiene", "value": "b-"}])
    assert selected.Piezas.tolist() == [16., 25.]
    fixed = execute(arbitrary, {"op": "replace", "column": "Piezas", "missing": False, "before": "15", "after": "0"}).frame
    assert fixed.Piezas.iloc[2] == 0
    fixed = execute(fixed, {"op": "sort", "columns": ["Piezas"], "ascending": False}).frame
    assert fixed.Piezas.tolist() == [25., 20., 16., 12., 10., 0.]
    pd.testing.assert_frame_equal(arbitrary, source)


@pytest.mark.parametrize(("operation", "expected"), [
    ("Sumar", 12.), ("Restar", 8.), ("Multiplicar", 20.), ("Dividir", 5.),
    ("Porcentaje", 500.), ("Razón por unidad", 50_000.), ("Logaritmo natural", np.log(10)), ("Raíz cuadrada", np.sqrt(10)),
])
def test_visual_math_uses_columns_and_preserves_source(arbitrary, operation, expected):
    spec = {"op": "formula", "formula": operation, "column": "Piezas", "right": "Horas", "name": "Indicador", "scale": 10_000}
    result = execute(arbitrary, spec).frame
    assert result["Indicador"].iat[0] == pytest.approx(expected)
    assert "Indicador" not in arbitrary


def test_expression_guards_division_recode_and_intervals(arbitrary):
    frame = arbitrary.assign(Horas=0.)
    spec = {"op": "formula", "formula": "Dividir", "column": "Piezas", "right": "Horas", "name": "N"}
    assert execute(frame, spec).frame["N"].isna().all()
    classified = execute(frame, {**spec, "formula": "Si se cumple…", "then": "Alto", "otherwise": "Bajo",
                                 "condition": {"column": "Piezas", "op": "Mayor o igual", "value": 15}}).frame
    assert classified["N"].tolist() == ["Bajo", "Bajo", "Alto", "Alto", "Alto", "Alto"]
    sliced = execute(frame, {**spec, "formula": "Intervalos", "bounds": [12, 20]}).frame
    assert sliced["N"].nunique() == 3
    standardized = execute(frame, {**spec, "formula": "Estandarizar (z)"}).frame["N"]
    assert standardized.mean() == pytest.approx(0)
    assert standardized.std() == pytest.approx(1)


def test_grouping_weighted_and_pivot_melt(arbitrary):
    group = aggregate(arbitrary, ["Taller"], "Media ponderada", "Piezas", weight="Horas", name="Media")
    assert group["Media"].iat[0] == pytest.approx((20 + 36 + 60) / 9)
    q1 = aggregate(arbitrary, ["Taller"], "Cuantil", "Piezas", quantile=.25)
    assert q1["Resultado"].iat[0] == pytest.approx(11.)
    spec = {"op": "pivot", "groups": ["Taller"], "category": "Año", "metric": "Piezas"}
    pivoted = execute(arbitrary, spec).frame
    assert list(pivoted) == ["Taller", "2022", "2023", "2024"]
    assert pivoted["2024"].tolist() == [15., 25.]
    long = execute(pivoted, {"op": "melt", "groups": ["Taller"], "columns": ["2022", "2023", "2024"],
                              "category": "Periodo", "name": "Cantidad"}).frame
    assert len(long) == len(arbitrary)
    assert sum(long.Cantidad) == sum(arbitrary.Piezas)
    repeated = concatenate([arbitrary, arbitrary]).frame
    with pytest.raises(ValueError, match="claves no son únicas"):
        execute(repeated, spec)


def test_text_and_temporal_transformations(arbitrary):
    separated = execute(arbitrary, {"op": "split", "column": "Lote", "name": "Grupo", "separator": "-", "count": 2}).frame
    combined = execute(separated, {"op": "combine", "columns": ["Grupo 1", "Grupo 2"], "name": "Lote nuevo", "separator": "-"}).frame
    assert combined["Lote nuevo"].tolist() == arbitrary.Lote.tolist()
    template = {"op": "time", "period": "Año", "metric": "Piezas", "entity": "Taller", "name": "Resultado", "window": 2}
    for method, expected in [("Rezago", 10.), ("Media móvil", 13.5), ("Crecimiento acumulado", 50.),
                             ("Variación porcentual", 25.), ("Cambio absoluto", 3.)]:
        result = execute(arbitrary, {**template, "method": method}).frame
        assert result[result.Taller == "A"]["Resultado"].iloc[-1] == pytest.approx(expected)
    with pytest.raises(ValueError, match="desagregar"):
        execute(arbitrary, {**template, "method": "Agregar por periodo", "frequency": "Mes", "aggregation": "Suma"})


def test_spatial_id_and_refresh_invalidate_dependents_only(arbitrary):
    state = {}
    initialize(state)
    root = store_table(state, "Primera fuente", arbitrary)
    child = store_table(state, "Derivada", arbitrary, parents=(root,), reversible=True)
    unrelated = store_table(state, "Otra fuente", arbitrary)
    assert not version_warnings(state["tables"], child)
    revision = store_table(state, "Primera fuente actualizada", arbitrary.assign(Piezas=3), supersedes=root, reversible=True)
    assert version_warnings(state["tables"], child)
    assert not version_warnings(state["tables"], unrelated)
    with pytest.raises(ValueError, match="referencia"):
        remove_unused(state, root)
    assert undo_table(state) == revision
    assert revision not in visible_tables(state) and not version_warnings(state["tables"], child)
    assert redo_table(state) == revision and revision in visible_tables(state)
    frame = pd.DataFrame({"Lugar": ["La Acebeda", "Madrid", "Getafe", "No reconocible"]})
    linked = execute(frame, {"op": "geo", "column": "Lugar", "system": "Nombre municipal", "name": "INE"}).frame
    assert linked["INE"].tolist()[:3] == ["28001", "28079", "28065"]
    assert pd.isna(linked["INE"].iat[-1])


def test_general_statistics_and_identified_effects(arbitrary):
    rank = association(arbitrary, "Kendall", "Piezas", "Horas")
    assert rank.table["Observaciones"].iat[0] == 6
    matrix = correlation_matrix(arbitrary, ["Piezas", "Horas"], "Spearman")
    assert matrix.table["Pares completos"].iat[0] == 6
    stats = grouped_descriptives(arbitrary, "Piezas", "Taller")
    assert stats.table["Observaciones"].tolist() == [3, 3]
    compare = group_test(arbitrary, "t independiente (Welch)", "Piezas", "Taller", design_confirmed=True).table
    assert compare["Grupo A"].iat[0] == "A" and compare["Diferencia de medias A − B"].iat[0] < 0
    assert compare["IC 95 % inferior"].iat[0] < compare["IC 95 % superior"].iat[0]
    fisher = association(arbitrary.assign(Tipo=["X", "X", "Y", "X", "Y", "Y"]), "Fisher exacta", "Taller", "Tipo")
    assert fisher.table["p bilateral"].iat[0] == pytest.approx(1.)


def test_categorical_regression_and_interactions():
    x = np.tile(np.arange(1, 9), 2)
    group = np.repeat(["A", "B"], 8)
    delta = (group == "B").astype(int)
    noise = np.tile([.1, -.1, .05, -.05], 4)
    df = pd.DataFrame({"X": x, "Grupo": group, "Y": 5 + 3*x + 4*delta + 2*x*delta + noise})
    result = regression(df, "Lineal múltiple", "Y", ["X", "Grupo"], categorical=["Grupo"], interaction=["X", "Grupo"])
    coeffs = result.table.set_index("Variable")["Coeficiente"]
    assert coeffs.loc["X × Grupo = B"] == pytest.approx(2., abs=.001)
    assert any("Nivel de referencia: A" in note for note in result.notes)


def test_time_diagnostics_require_regular_periods_and_pca():
    rng = np.random.default_rng(8)
    years = np.arange(1990, 2022)
    values = 13 + np.arange(32)*.4 + np.tile([1., 2., -1., -2.], 8)
    df = pd.DataFrame({"Año": years, "Medida": values, "Otra": values + rng.normal(0, .2, 32)})
    check = time_diagnostics(df, "Año", "Medida", "Año", "Autocorrelación temporal", 5)
    assert len(check.table) == 5
    decomposition = time_diagnostics(df, "Año", "Medida", "Año", "Descomposición temporal", 4)
    assert decomposition.table["Estacional"].iloc[2] == pytest.approx(-1.)
    with pytest.raises(ValueError, match="huecos"):
        time_diagnostics(df.drop(index=9), "Año", "Medida", "Año", "Autocorrelación temporal", 5)
    components = principal_components(df, ["Medida", "Otra"])
    assert components.table["Variable"].tolist() == ["Medida", "Otra"]
    assert len(components.figure.data[0].x) == 32


@pytest.mark.parametrize("kind", CHARTS)
def test_chart_builders_use_selected_data(arbitrary, kind):
    spec = {"kind": kind, "title": "Talleres", "x": "Año", "y": "Piezas", "color": "Taller",
            "size": "Horas", "columns": ["Piezas", "Horas"]}
    if kind in {"Histograma", "Densidad"}:
        spec = {"kind": kind, "title": "Talleres", "x": "Piezas", "color": "Taller"}
    elif kind == "Mapa de calor":
        spec.update(x="Horas", color=None)
    elif kind != "Burbujas":
        spec.pop("size")
    visual = build_chart(arbitrary, spec)
    assert visual.figure.data and visual.figure.layout.title.text == "Talleres"
    assert not visual.table.empty
    assert visual.notes


def test_universal_maps_show_all_ign_absences_and_gps():
    frame = pd.DataFrame({"Municipio": ["Madrid", "Getafe", "Getafe"], "Bibliotecas": [8, 3, 2]})
    spec = {"kind": "Coropleta municipal", "code": "Municipio", "system": "Nombre municipal", "metric": "Bibliotecas"}
    with pytest.raises(ValueError, match="varias observaciones"):
        build_map_visual(frame, spec)
    visual = build_map_visual(frame, {**spec, "aggregation": "Suma"})
    assert len(visual.figure.data[0].locations) == 179
    assert visual.table.set_index("INE").loc["28065", "Valor"] == 5
    assert len(visual.table.dropna()) == 2
    assert "Sin datos" in visual.figure.data[0].colorbar.ticktext
    frame = pd.DataFrame({"y": [40.4, 40., 999], "x": [-3.5, -3.2, -3.1], "Visitas": [2, 5, 6]})
    for kind in ["Puntos WGS84", "Densidad de puntos"]:
        visual = build_map_visual(frame, {"kind": kind, "latitude": "y", "longitude": "x",
                                          "metric": "Visitas", "municipal_layer": True})
        assert len(visual.figure.data) == 2 and len(visual.table) == 2


def test_project_version_one_and_two_preserve_multiple_results_and_notes(arbitrary):
    tables, undo, config, entries, project = load_project((FIXTURES / "proyecto_31.zip").read_bytes())
    assert tables[1]["df"]["Código territorio"].iat[0] == "0014"
    assert entries[0]["id"] and entries[0]["title"] == "Distribución"
    assert config["saved_palette_territory"] == "Verde"
    state = {"tables": tables, "undo": undo, "project_results": entries}
    initialize(state)
    state["serial"] = max(tables)
    raw = b"Taller;Piezas\nA;10\n"
    key = store_table(state, "Archivo", arbitrary, ("Fuente declarada",), raw=raw, filename="original.csv")
    project["reports"] = []
    for operation in ["Dispersión", "Caja"]:
        visual = build_chart(arbitrary, {"kind": operation, "x": "Horas", "y": "Piezas"})
        entry = remember_result(state, key, {"análisis": operation}, visual.table, "Figura", [], [visual.figure], kind="Gráfico")
        entry.update(annotation="<script>prueba</script>", interpretation="Interpretación propia")
    draft = {field: "" for field in ("introduction", "objectives", "methodology", "discussion", "limitations", "conclusions", "sources")}
    draft.update(title="Informe exportado", id="informe-test", entries=[entry["id"] for entry in entries])
    project["reports"].append(draft)
    raw_project = save_project(tables, undo, {"active_table": key}, entries, project)
    restored, _, settings, outputs, details = load_project(raw_project)
    assert len(outputs) == 3 and restored[key]["raw"] == raw
    assert settings["active_table"] == key and details["reports"][0]["entries"] == draft["entries"]
    assert outputs[-1]["interpretation"] == "Interpretación propia"
    html = notebook_report(draft, details, outputs, restored)
    assert "&lt;script&gt;prueba&lt;/script&gt;" in html and "Interpretación propia" in html
    assert "Fuente declarada" in html and html.index("Dispersión") < html.index("Caja")
    with ZipFile(io.BytesIO(raw_project)) as archive:
        assert json.loads(archive.read("manifest.json"))["version"] == 2
