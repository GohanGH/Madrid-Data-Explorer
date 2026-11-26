import io
import json
from dataclasses import dataclass
from zipfile import ZipFile

import pandas as pd
import pytest
from plotly import graph_objects
from workbench_helpers import (
    add_offline,
    analysis_method,
    associate,
    checked,
    export_report,
    go,
    join,
    map_result,
    press,
    scatter,
    set_widget,
    start,
    submit,
    temporal_change,
)

import project_view
from data_tables import period_change, transform
from discovery import interpret, retrieve
from loading import loading
from projects import load_project, save_project
from spatial_stats import moran, municipal_edges
from territories import JOBS, POP, prepared_series, question_plan

QUESTION = "¿Existe una relación entre el crecimiento poblacional y la evolución del paro registrado en los municipios de la Comunidad de Madrid?"
POP_CHANGE = "Crecimiento de población (%)"
JOB_CHANGE = "Cambio de paro registrado (%)"
DETAILS = {"name": "Estudio Madrid", "question": QUESTION, "description": "Padrón y paro municipal"}


@pytest.mark.parametrize(("question", "topics"), [
    (QUESTION, {"población", "paro"}),
    ("¿Qué municipios tienen mayor envejecimiento y menor renta?", {"envejecimiento", "renta"}),
    ("¿Cómo ha cambiado la población de los municipios rurales?", {"población", "ruralidad"}),
    ("¿Se asocian la contaminación atmosférica y la densidad poblacional?", {"aire", "densidad"}),
    ("¿Cómo se relaciona el transporte público con la población municipal?", {"transporte", "población"}),
    ("¿Qué municipios disponen de menos recursos sanitarios?", {"salud"}),
])
def test_unseen_questions(question, topics):
    query = interpret(question)
    assert set(query.topics) == topics
    if len(topics) > 1:
        assert question_plan(query) is None


def test_relevant_candidates_and_municipal_alias():
    query = interpret(f"{QUESTION} En La Acebeda", ["Acebeda (La)"])
    assert query.geography == "Acebeda (La)"
    rows, failed = retrieve(query, lambda *args, **kwargs: {"results": [
        {"name": "pop", "title": "Población empadronada por sexo. Municipios"},
        {"name": "jobs", "title": "Total paro registrado. Municipios"},
        {"name": "noise", "title": "Bibliotecas. Municipios"},
    ]})
    assert not failed
    assert {entry[1]["name"] for entry in rows} == {"pop", "jobs"}


def test_loading_cleans_up_after_error(monkeypatch):
    events = []

    @dataclass
    class Placeholder:
        def html(self, html):
            assert "rotate(360deg)" in html and "prefers-reduced-motion" in html
            assert "<svg" in html and "&lt;datos&gt;" in html
            events.append("render")

        def empty(self):
            events.append("clear")

    monkeypatch.setattr("loading.st.empty", Placeholder)
    with pytest.raises(RuntimeError, match="fallo"), loading("Leyendo <datos>"):
        raise RuntimeError("fallo")
    assert events == ["render", "clear"]


def test_temporal_changes_filters_and_duplicate_protection():
    frame = pd.DataFrame({"INE": ["0014", "28001", "0029", "0029", "0035"],
                          "Año": [2018, 2025, 2018, 2025, 2018], "Casos": [10, 7, 0, 5, 7]})
    result, missing = period_change(frame, "INE", "Año", "Casos", 2018, 2025, "Cambio (%)")
    assert result.set_index("INE").loc["28001", "Cambio (%)"] == pytest.approx(-30)
    assert missing == 2
    filtered, affected = transform(frame, "Conservar valores", "Año", selected=[2018])
    assert len(filtered) == 3 and affected == 2
    duplicate = pd.concat([frame, frame.iloc[:1].assign(INE="28001")])
    with pytest.raises(ValueError, match="varias filas"):
        period_change(duplicate, "INE", "Año", "Casos", 2018, 2025, "Cambio (%)")


def test_global_moran_invariant_to_row_order_and_rejects_bad_grain():
    frame = prepared_series(POP).query("Año == 2025")
    a = moran(frame["Valor"], frame["INE"], permutations=99, seed=17)
    shuffled = frame.sample(frac=1, random_state=9)
    b = moran(shuffled["Valor"], shuffled["INE"], permutations=99, seed=17)
    pd.testing.assert_frame_equal(a.table, b.table)
    assert len(municipal_edges()) == 468
    assert a.table["Municipios"].iat[0] == 179
    assert .01 <= a.table["p bilateral"].iat[0] <= 1
    assert len(a.figure.data) == 2
    with pytest.raises(ValueError, match="una fila"):
        moran(pd.concat([frame["Valor"], frame["Valor"]]), pd.concat([frame["INE"], frame["INE"]]))


def test_moran_weights_and_islands_on_controlled_graph(monkeypatch):
    monkeypatch.setattr("spatial_stats.municipal_edges", lambda: (
        ("28001", "28002"), ("28002", "28003"), ("28003", "28004")
    ))
    codes = pd.Series(["28001", "28002", "28003", "28004", "28005"])
    result = moran(pd.Series([1, 2, 3, 4, 99]), codes, permutations=99, seed=3).table.iloc[0]
    assert result["I de Moran"] == pytest.approx(0.4)
    assert result["I esperado"] == pytest.approx(-1 / 3)
    assert result["Sin vecinos"] == 1


def test_portable_archive_types_and_validation():
    frame = pd.DataFrame({"Código": pd.Series(["0014", None], dtype="string"),
                          "Fecha": pd.to_datetime(["2018-01-01", None]), "Medida": pd.array([3, None], dtype="Int64")})
    items = {1: {"df": frame, "title": "Original", "history": (), "sources": ("https://example.test/source",)},
             2: {"df": frame, "title": "Limpia", "history": ({"operación": "filtro"},), "sources": (),
                 "parent": 1, "original": 1, "roles": {"Código": "Código municipal"}}}
    result = {"dataset": 2, "params": {"análisis": "Distribución"}, "summary": "Descripción", "notes": [],
              "table": pd.DataFrame({"Valor": [3, "Sin moda"]}), "figures": [graph_objects.Figure(graph_objects.Scatter(y=[1, 2]))]}
    config = {"studio_filter_2": "Fecha", "studio_values_2_Fecha": [pd.Timestamp("2018-01-01")],
              "saved_palette_territory": "Verde", "irrelevant": "sin exportar"}
    raw = save_project(items, [2], config, [result], DETAILS)
    restored, undo, settings, results, details = load_project(raw)
    pd.testing.assert_frame_equal(restored[1]["df"], frame)
    assert restored[2]["original"] == 1 and undo == [2]
    assert settings == {k: v for k, v in config.items() if k != "irrelevant"}
    pd.testing.assert_frame_equal(results[0]["table"], result["table"])
    assert list(results[0]["figures"][0].data[0].y) == [1, 2]
    assert details["created"] and details["modified"]
    corrupt = io.BytesIO()
    with ZipFile(corrupt, "w") as archive:
        archive.writestr("manifest.json", json.dumps({"version": 999}))
    with pytest.raises(ValueError, match="incompatible"):
        load_project(corrupt.getvalue())
    with ZipFile(corrupt, "a") as archive:
        archive.writestr("../escape", "archivo inesperado")
    with pytest.raises(ValueError, match="Estructura"):
        load_project(corrupt.getvalue())


def test_full_new_research_and_project_roundtrip(monkeypatch):
    actual_uploader = project_view.st.file_uploader
    actual_download = project_view.st.download_button
    published = {}

    def upload(*args, **kwargs):
        if kwargs.get("key") == "project_import" and "restore" in published:
            return io.BytesIO(published["restore"])
        return actual_uploader(*args, **kwargs)

    def request_download(label, data, *args, **kwargs):
        if label == "Descargar informe estadístico (HTML)":
            published["report"] = data()
            data = published["report"]
        return actual_download(label, data, *args, **kwargs)

    monkeypatch.setattr("library_view.find_sources", lambda *args, **kwargs: ({"count": 0, "results": []}, False))
    monkeypatch.setattr(project_view.st, "download_button", request_download)
    monkeypatch.setattr(project_view.st, "file_uploader", upload)
    app = start()
    set_widget(app, "text_input", "home_query", QUESTION, rerun=False)
    submit(app, "Buscar datos")
    assert app.session_state.page == "Datos"
    assert not app.session_state.project_results
    ids = add_offline(app, [POP, JOBS])
    pop = temporal_change(app, ids[POP], POP_CHANGE)
    jobs = temporal_change(app, ids[JOBS], JOB_CHANGE)
    table = join(app, pop, jobs, ["Código territorio"])
    frame = app.session_state.tables[table]["df"].copy()
    assert len(frame) == 179 and frame["Código territorio"].str.startswith("28").all()
    for method, expected in [("Pearson", .461633), ("Spearman", .439129)]:
        entry = associate(app, table, method, POP_CHANGE, JOB_CHANGE)
        assert entry["table"]["Coeficiente"].iat[0] == pytest.approx(expected, abs=1e-6)
    analysis_method(app, table, "Regresión", "Lineal simple")
    set_widget(app, "selectbox", f"primary_{table}_Lineal simple", JOB_CHANGE)
    set_widget(app, "multiselect", f"predictors_{table}_Lineal simple", [POP_CHANGE], rerun=False)
    set_widget(app, "selectbox", f"spatial_code_{table}_Lineal simple", "Código territorio", rerun=False)
    press(app, f"execute_{table}_Lineal simple")
    fit = app.session_state.project_results[-1]
    model = fit["table"]
    assert model["R²"].iat[0] == pytest.approx(.213105, abs=1e-6)
    assert model["Residuos · I de Moran"].iat[0] == pytest.approx(.120402, abs=1e-6)
    assert "2.342589" in published["report"] and "datos.comunidad.madrid" in published["report"]

    analysis_method(app, table, "Análisis geográfico", "Moran global")
    set_widget(app, "selectbox", f"primary_{table}_Moran global", POP_CHANGE, rerun=False)
    press(app, f"execute_{table}_Moran global")
    assert app.session_state.project_results[-1]["table"]["Municipios"].iat[0] == 179
    graph = scatter(app, table, POP_CHANGE, JOB_CHANGE, "Población y cambio del paro")
    layer = map_result(app, table, POP_CHANGE, "Crecimiento por municipio")
    export_report(app, "Población y empleo", [fit, graph, layer])

    go(app, "Home")
    pd.testing.assert_frame_equal(app.session_state.tables[table]["df"], frame)
    assert app.session_state.tables[table]["history"][-1]["operación"] == "unión"
    go(app, "Mis proyectos")
    set_widget(app, "text_input", "project_question", QUESTION, rerun=False)
    submit(app, "Guardar datos del proyecto")
    press(app, "prepare_zip")
    assert not app.error
    published["restore"] = app.session_state.project_export
    set_widget(app, "radio", "project_panel", "Nuevo")
    set_widget(app, "checkbox", "new_confirm", True, rerun=False)
    press(app, "new_project")
    assert not app.session_state.tables
    press(app, "home_open")
    press(app, "restore_project")
    assert not app.error
    pd.testing.assert_frame_equal(app.session_state.tables[table]["df"], frame)
    assert app.session_state.project_details["question"] == QUESTION
    assert app.session_state["active_table"] == table
    assert app.session_state["method_5_Análisis geográfico"] == "Moran global"
    restored_model = next(e["table"] for e in app.session_state.project_results if e["params"]["análisis"] == "Lineal simple")
    pd.testing.assert_frame_equal(restored_model, model)
    assert app.session_state.project_details["reports"][0]["title"] == "Población y empleo"
    checked(app)
