import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest
from workbench_helpers import add_offline, checked, go, press, set_widget, start, submit

from discovery import interpret, retrieve
from explore_view import municipality_mentions
from map_view import (
    MISSING,
    PALETTES,
    SELECTION,
    apply_click,
    build_map,
    classify,
    clicked_code,
    map_features,
)
from territories import (
    EXAMPLES,
    POP,
    analysis_window,
    boundaries,
    growth,
    normalize_code,
    official_codes,
    prepared_series,
    question_plan,
)


def test_interpret_geography_synonyms_and_time():
    query = interpret("¿Cómo ha cambiado el desempleo en Getafe entre 2018 y 2025?", ["Getafe"])
    assert (query.topics, query.geography, query.years, query.intent) == (("paro",), "Getafe", (2018, 2025), "evolución")
    assert municipality_mentions("Getafe, Madrid capital y El Álamo") == ["28004", "28065", "28079"]
    assert interpret("Población en los últimos diez años").recent == 10
    assert question_plan(interpret("Tasa de desempleo de Madrid")) is None
    assert question_plan(interpret("Renta de los barrios de Madrid")) is None


def test_candidate_ranking_explains_and_deduplicates():
    high = {"name": "age", "title": "Grado de envejecimiento. Municipios", "notes": ""}
    low = {"name": "other", "title": "Censo electoral", "notes": "envejecimiento"}
    def fetch(term, rows):
        assert rows == 15
        return {"results": [low, high]}
    query = interpret("¿Dónde vive la población más envejecida?")
    results, failed = retrieve(query, fetch)
    assert not failed
    assert [row[1]["name"] for row in results] == ["age", "other"]
    assert "Cobertura municipal indicada" in results[0][2]


def test_cartography_correspondence_and_missing():
    assert len(official_codes()) == 179
    assert {row["id"] for row in boundaries()["features"]} == set(official_codes())
    assert normalize_code("0650", "Almudena") == "28065"
    assert normalize_code("0658", "Almudena") is None
    assert normalize_code("28065") == "28065"
    frame = pd.DataFrame({"INE": ["28065", "28079"], "Valor": [10, float("nan")]})
    features, bins = map_features(frame, "%", "Cuantiles", PALETTES["Azul"])
    props = {f["id"]: f["properties"] for f in features["features"]}
    assert props["28065"]["value"] == "10 %"
    assert props["28079"]["color"] == MISSING and props["28001"]["color"] == MISSING
    document = build_map(features, bins, PALETTES["Azul"], "%").get_root().render()
    assert r"C\u00f3digo INE" in document and "Sin datos" in document
    with pytest.raises(ValueError, match="una fila"):
        map_features(pd.concat([frame, frame]), "%", "Cuantiles", PALETTES["Azul"])


def test_click_and_selected_municipalities():
    code = clicked_code({"last_object_clicked_tooltip": "Municipio Getafe\nCódigo INE28065"})
    assert code == "28065"
    assert apply_click(["28079"], code) == ["28079", "28065"]
    assert apply_click(["28065"], code) == ["28065"]
    assert clicked_code({"last_object_clicked_tooltip": "No municipal 28999"}) is None


def test_population_window_and_growth():
    query = interpret("¿Qué municipios han crecido más en población entre 2015 y 2025?")
    assert question_plan(query) == ("crecimiento", (POP,))
    frame = prepared_series(POP)
    series = analysis_window(frame, query)
    assert (series["Año"].min(), series["Año"].max()) == (2015, 2025)
    growth_table = growth(series, (2015, 2025))
    assert len(growth_table) == 179
    getafe = frame[frame["INE"] == "28065"].set_index("Año")["Valor"]
    value = growth_table.loc[growth_table["INE"] == "28065", "Valor"].iat[0]
    assert value == pytest.approx(100 * (getafe[2025] / getafe[2015] - 1))


@pytest.mark.parametrize("question", EXAMPLES)
def test_old_questions_lead_to_source_discovery_without_running_a_method(question, monkeypatch):
    dataset = {"name": "fuente", "id": "fuente", "title": "Fuentes municipales", "notes": "Variables para el análisis."}
    monkeypatch.setattr("library_view.find_sources", lambda *args, **kwargs: ({"count": 1, "results": [dataset]}, False))
    app = start()
    set_widget(app, "text_input", "home_query", question, rerun=False)
    submit(app, "Buscar datos")
    assert app.session_state.page == "Datos"
    assert app.session_state.catalog_request[:2] == (question, "Lenguaje natural")
    assert any("fuentes candidatas" in node.value for node in app.caption)
    assert not app.session_state.project_results
    assert not app.get("plotly_chart")


def test_linked_map_click_retains_municipal_selection(monkeypatch):
    event = {"last_object_clicked_tooltip": "Municipio Getafe / Código INE 28065",
             "last_object_clicked": {"lat": 40.3, "lng": -3.7}}
    monkeypatch.setattr("map_view.st_folium", lambda *args, **kwargs: event)
    app = checked(AppTest.from_string("from explore_view import full_map\nfull_map()", default_timeout=50).run())
    assert app.session_state[SELECTION] == ["28065"]
    assert any("Getafe" in frame.value.get("Municipio", pd.Series(dtype=str)).tolist()
               for frame in app.dataframe)
    checked(app.run())
    assert app.session_state[SELECTION] == ["28065"]


def test_natural_language_query_lists_ranked_sources(monkeypatch):
    dataset = {"id": "educacion", "name": "educacion", "title": "Nivel educativo municipal", "notes": "Estudios por municipio."}
    monkeypatch.setattr("library_view.find_sources", lambda *args, **kwargs: ({"count": 1, "results": [dataset]}, False))
    app = start()
    set_widget(app, "text_input", "home_query", "Quiero comparar desempleo y nivel educativo", rerun=False)
    submit(app, "Buscar datos")
    assert any(node.label == "Nivel educativo municipal" for node in app.expander)
    assert any("fuentes candidatas" in node.value for node in app.caption)


def test_map_indicator_and_filter_survive_navigation():
    app = start()
    ids = add_offline(app, [POP])
    key = ids[POP]
    go(app, "Visualización")
    set_widget(app, "radio", "visual_section", "Mapas")
    prefix = f"cfg_visual_new_{key}_map"
    set_widget(app, "number_input", f"{prefix}_filter_count", 1)
    set_widget(app, "selectbox", f"{prefix}_filter_0_column", "Año")
    set_widget(app, "text_input", f"{prefix}_filter_0_value", "2019")
    set_widget(app, "selectbox", f"{prefix}_0_palette", "Verde")
    go(app, "Home")
    go(app, "Visualización")
    assert app.selectbox(key=f"{prefix}_0_metric").value == "Población (personas)"
    assert app.text_input(key=f"{prefix}_filter_0_value").value == "2019"
    assert app.selectbox(key=f"{prefix}_0_palette").value == "Verde"
    assert app.get("plotly_chart")


def test_comparison_search_surfaces_both_indicators():
    jobs = {"name": "paro", "title": "Paro registrado. Municipios"}
    school = {"name": "estudios", "title": "Población por nivel educativo. Municipios"}
    unrelated = {"name": "certificados", "title": "Nivel educativo y titulaciones"}
    query = interpret("Comparar desempleo y nivel educativo")
    results, _ = retrieve(query, lambda term, rows: {"results": [school, unrelated, jobs]})
    assert [r[1]["name"] for r in results[:2]] == ["paro", "estudios"]


def test_real_map_component_mounts():
    app = checked(AppTest.from_string("from explore_view import full_map\nfull_map()", default_timeout=45).run())
    assert app.get("component_instance")
    assert any("179 de 179" in message.value for message in app.caption)


def test_jenks_separates_natural_clusters_and_keeps_ties():
    values = pd.Series([1, 1, 2, 80, 80, 81, 1000, 1001])
    assert classify(values, "Cortes naturales (Jenks)", count=3) == [1, 2, 81, 1001]


def test_topic_card_opens_catalogue_and_selection_survives_home(monkeypatch):
    monkeypatch.setattr("library_view.find_sources", lambda *args, **kwargs: ({"count": 0, "results": []}, False))
    app = start()
    press(app, "topic_Vivienda")
    assert "alquiler" in app.text_input(key="catalog_keyword").value
    assert app.button(key="nav_Datos").proto.type == "primary"
    go(app, "Home")
    go(app, "Datos")
    assert "alquiler" in app.text_input(key="catalog_keyword").value


def test_relationship_interpretation_and_metric_cards_in_regression():
    # This legacy renderer is tested directly and is not a route of the workbench.
    app = checked(AppTest.from_string(
        "from explore_view import relationship_report\nrelationship_report('regression')", default_timeout=45,
    ).run())
    assert any("negativa muy débil" in node.value for node in app.markdown)
    metrics = {node.label: node.value for node in app.metric}
    assert metrics == {"Correlación de Pearson": "-0,109", "Municipios comparados": "179", "Año de referencia": "2024"}
    assert app.button(key="relationship_regression_Dispersión").proto.type == "primary"
    press(app, "relationship_regression_Tabla")
    assert app.button(key="relationship_regression_Tabla").proto.type == "primary"
    assert len(app.dataframe[0].value) == 179
