"""All selection and transformation steps use the general workbench routes."""
import json
from hashlib import sha256
from pathlib import Path

import pytest
from workbench_helpers import (
    add_offline,
    analysis_method,
    associate,
    export_report,
    filtered_version,
    finish_recipe,
    focus,
    go,
    group_sum,
    join,
    map_result,
    prepare,
    press,
    ratio,
    scatter,
    set_widget,
    start,
    submit,
)

from demos import CENSUS, COUNT
from reports import notebook_report
from territories import JOBS, POP, RENT

FIXTURES = Path(__file__).parent / "fixtures"
KEYS = ["Código territorio", "Año"]
AGE = "65 años y más (%)"
CENSUS_METRIC = "Población censada (personas)"
CENTERS = "Centros de atención primaria (número)"
PER_CAPITA = "Centros por 10.000 habitantes calculados"
JOBS_METRIC = "Paro registrado (personas)"


def age_indicator(app, census):
    bands = [f"De {age}-{age + 4} años" for age in range(65, 100, 5)] + ["De 100 y más años"]
    cohorts = filtered_version(app, census, "Edad", bands, "Grupos de 65 o más")
    aggregate = group_sum(app, cohorts, KEYS, CENSUS_METRIC, "Personas mayores")
    total = filtered_version(app, census, "Edad", ["Total"], "Total censado")
    matched = join(app, aggregate, total, KEYS)
    return ratio(app, matched, "Personas mayores", CENSUS_METRIC, AGE)


def test_health_and_income_research_via_workbench():
    app = start()
    keys = add_offline(app, [CENSUS, COUNT, POP, RENT])
    age = age_indicator(app, keys[CENSUS])
    population = filtered_version(app, keys[POP], "Año", [2024], "Padrón de 2024")
    resources = join(app, keys[COUNT], population, KEYS)
    with_rate = ratio(app, resources, CENTERS, "Población (personas)", PER_CAPITA, scale=10_000.)
    health = join(app, age, with_rate, KEYS)
    assert len(app.session_state.tables[health]["df"]) == 179
    assert app.session_state.tables[health]["df"][CENTERS].sum() == 422
    pearson = associate(app, health, "Pearson", AGE, PER_CAPITA)
    spearman = associate(app, health, "Spearman", AGE, PER_CAPITA)
    assert pearson["table"]["Coeficiente"].iat[0] == pytest.approx(.600503, abs=1e-6)
    assert spearman["table"]["Coeficiente"].iat[0] == pytest.approx(.505204, abs=1e-6)
    scatter_plot = scatter(app, health, AGE, PER_CAPITA, "Edad y dotación sanitaria")
    map_entry = map_result(app, health, PER_CAPITA, "Dotación de centros de salud")
    assert len(map_entry["figures"][0].data[0].locations) == 179
    export_report(app, "Envejecimiento y centros", [pearson, spearman, scatter_plot, map_entry])

    income = join(app, age, keys[RENT], KEYS)
    name = "Renta per cápita (EUR)"
    point = associate(app, income, "Pearson", AGE, name)
    assert point["table"]["Coeficiente"].iat[0] == pytest.approx(-.109310, abs=1e-6)
    analysis_method(app, income, "Regresión", "Lineal simple")
    set_widget(app, "selectbox", f"primary_{income}_Lineal simple", name)
    set_widget(app, "multiselect", f"predictors_{income}_Lineal simple", [AGE], rerun=False)
    press(app, f"execute_{income}_Lineal simple")
    model = app.session_state.project_results[-1]
    assert model["table"]["R²"].iat[0] == pytest.approx(.011949, abs=1e-6)
    figure = scatter(app, income, AGE, name, "Edad y renta")
    map_income = map_result(app, income, name, "Renta municipal")
    export_report(app, "Renta y envejecimiento", [point, model, figure, map_income])


def test_registered_unemployment_series_groups_and_map():
    app = start()
    ids = add_offline(app, [JOBS, POP])
    root = ids[JOBS]
    assert len(app.session_state.tables[root]["df"]) == 1432
    totals = group_sum(app, root, ["Año"], JOBS_METRIC, "Total municipal")
    aggregate = app.session_state.tables[totals]["df"].set_index("Año")["Total municipal"]
    assert (aggregate.loc[2018], aggregate.loc[2025]) == (380051, 293817)
    assert 100 * (aggregate.loc[2025] / aggregate.loc[2018] - 1) == pytest.approx(-22.69, abs=.005)
    municipalities = filtered_version(app, root, "Territorio", ["Madrid", "Getafe", "Alcalá de Henares"])
    title = "Evolución y cambios"
    analysis_method(app, municipalities, "Series temporales", title)
    set_widget(app, "selectbox", f"time_group_{municipalities}", "Territorio", rerun=False)
    press(app, f"execute_{municipalities}_{title}")
    result = app.session_state.project_results[-1]
    assert len(result["table"]) == 24
    assert result["table"]["Territorio"].nunique() == 3
    frame2025 = filtered_version(app, root, "Año", [2025])
    population = filtered_version(app, ids[POP], "Año", [2025], "Padrón de referencia de 2025")
    reference = join(app, frame2025, population, KEYS)
    assert len(app.session_state.tables[reference]["df"]) == 179
    indicator = "Recuentos por 1.000 habitantes"
    with_ratio = ratio(app, reference, JOBS_METRIC, "Población (personas)", indicator, scale=1_000.)
    layer = map_result(app, with_ratio, indicator, "Paro registrado por 1.000 residentes en 2025")
    export_report(app, "Paro por municipios", [result, layer])


def test_new_cultural_domain_uses_official_sources_not_example_routes(monkeypatch):
    import streamlit as st

    records = json.loads((FIXTURES / "bibliotecas_fuentes.json").read_text(encoding="utf-8"))
    datasets = [{"id": row["name"], "name": row["name"], "title": row["title"],
                 "resources": [{"name": row["title"], "url": row["url"], "format": "CSV"}]} for row in records]
    by_url = {row["url"]: (FIXTURES / row["extracto"]).read_bytes() for row in records}
    assert all(sha256(by_url[row["url"]]).hexdigest() == row["sha256_extracto"] for row in records)
    monkeypatch.setattr("library_view.find_sources", lambda *args: ({"count": len(datasets), "results": datasets}, False))
    monkeypatch.setattr("library_view.download_resource", lambda resource: by_url[resource["url"]])
    download_button = st.download_button
    deferred = []

    def capture_report(label, data, *args, **kwargs):
        if label == "Descargar informe HTML":
            deferred.append(data)
        return download_button(label, data, *args, **kwargs)

    monkeypatch.setattr(st, "download_button", capture_report)
    app = start()
    go(app, "Datos")
    set_widget(app, "text_input", "catalog_keyword", "bibliotecas públicas visitas población atendida", rerun=False)
    submit(app, "Buscar")
    for dataset in datasets:
        set_widget(app, "checkbox", f"catalog_check_{dataset['id']}", True)
    press(app, "import_basket")
    visit_name, population_name = "Visitas", "Población atendida"
    for key, measurement in ((1, population_name), (2, visit_name)):
        focus(app, key)
        prepare(app, key, "Organizar", "Renombrar columna")
        set_widget(app, "selectbox", f"cfg_recipe_{key}_rename_column", "Valor", rerun=False)
        set_widget(app, "text_input", f"cfg_recipe_{key}_rename_name", measurement, rerun=False)
        finish_recipe(app)
    table = join(app, 3, 4, KEYS)
    point = associate(app, table, "Pearson", population_name, visit_name)
    ranked = associate(app, table, "Spearman", population_name, visit_name)
    assert point["table"]["Observaciones"].iat[0] == 179
    assert ranked["table"]["Observaciones"].iat[0] == 179
    assert point["table"]["Coeficiente"].iat[0] == pytest.approx(.989836, abs=1e-6)
    assert ranked["table"]["Coeficiente"].iat[0] == pytest.approx(.967979, abs=1e-6)
    graph = scatter(app, table, population_name, visit_name, "Población atendida y visitas")
    layer = map_result(app, table, visit_name, "Visitas a bibliotecas públicas")
    draft = export_report(app, "Bibliotecas públicas", [point, ranked, graph, layer])
    html = notebook_report(draft, app.session_state.project_details, app.session_state.project_results, app.session_state.tables)
    assert all(row["url"] in html for row in records)
    assert "Interpretación de la investigación" in html and "Visitas a bibliotecas públicas" in html
    downloaded = deferred[-1]()
    assert all(row["url"] in downloaded for row in records)
    assert "Interpretación de la investigación" in downloaded and "Visitas a bibliotecas públicas" in downloaded
