import io
import json
from zipfile import ZipFile

import pandas as pd
import pytest
import streamlit as st
from shapely.geometry import shape
from streamlit.testing.v1 import AppTest

import demos
from data_tables import ratio_indicator, read_table
from demos import (
    ABS,
    AGE_SHARE,
    CENSUS,
    DEMO_NAMES,
    PCT,
    RATE,
    data_bundle,
    employment,
    prepare_study,
    study_map,
)
from statistical_engine import association, regression, temporal
from territories import boundaries, normalize_code, official_codes


@pytest.mark.parametrize("name", DEMO_NAMES)
def test_offline_study_sources_cleaning_and_exports(name):
    combined, cleaned, history, joins, diagnostics = prepare_study(name)
    assert len(official_codes()) == 179
    assert set(combined["INE"]) == set(official_codes())
    assert not combined.duplicated(["INE", "Año"]).any()
    assert history and diagnostics
    assert all(j["cardinalidad"] == "uno a uno" and j["filas_A_perdidas"] == 0 for j in joins)
    with ZipFile(io.BytesIO(data_bundle(cleaned))) as bundle:
        for key, data in cleaned.items():
            raw = bundle.read(f"extractos_originales/{key}.csv")
            assert raw == demos.raw_source(key)
            assert read_table(raw, "csv")["Código territorio"].iloc[0] == "0014"
            derivative = read_table(bundle.read(f"tablas_limpias/{key}.csv"), "csv")
            assert derivative["INE"].equals(data["INE"])
        assert len(json.loads(bundle.read("cartografia/municipios.geojson"))["features"]) == 179


def test_indicators_and_geographic_alignment():
    assert normalize_code("0014", "auto") == normalize_code(14, "auto") == "28001"
    assert normalize_code("0015", "Almudena") is None
    frame, clean, _, joins, _ = prepare_study(DEMO_NAMES[2])
    assert len(joins) == 4
    assert len(clean[CENSUS]) == 179 * 22
    acebeda = frame.set_index("INE").loc["28001"]
    assert acebeda[AGE_SHARE] == 50
    assert acebeda[RATE] == pytest.approx(10_000 / 68)
    assert frame[RATE].sub(frame["Centros por 10.000 habitantes"]).abs().max() <= .0051
    assert frame[AGE_SHARE].sub(frame["Población de 65 años y más (%)"]).abs().max() <= .0051
    features = boundaries()["features"]
    assert {feature["id"] for feature in features} == set(official_codes())
    assert all(shape(feature["geometry"]).is_valid for feature in features)
    result = study_map(frame.iloc[:1], RATE, "Salud")
    assert len(result.data[0].locations) == 179
    assert list(result.data[1].locations) == [frame["INE"].iloc[0]]
    assert result.layout.map.style == "white-bg"


def test_ratio_keeps_zero_counts_and_missing_denominators():
    frame = pd.DataFrame({"casos": [0, 3, 2], "personas": [4, 0, None]})
    result, missing = ratio_indicator(frame, "%", "casos", "personas", 100)
    assert result["%"].iloc[0] == 0
    assert missing == 2
    assert "%" not in frame


def test_official_analysis_reproduces_all_three_studies():
    rent, *_ = prepare_study(DEMO_NAMES[0])
    health, *_ = prepare_study(DEMO_NAMES[2])
    jobs, *_ = prepare_study(DEMO_NAMES[1])
    signal = association(health, "Pearson", AGE_SHARE, RATE).table.iloc[0]
    assert signal["Coeficiente"] == pytest.approx(.601, abs=.001)
    assert signal["IC 95 % inferior"] < signal["Coeficiente"] < signal["IC 95 % superior"]
    assert signal["Observaciones"] == 179
    y = "Renta per cápita (EUR)"
    assert association(rent, "Spearman", AGE_SHARE, y).table["Observaciones"].iat[0] == 179
    fit = regression(rent, "Lineal simple", y, [AGE_SHARE]).table.set_index("Variable")
    pearson = association(rent, "Pearson", AGE_SHARE, y).table["Coeficiente"].iat[0]
    assert fit.loc[AGE_SHARE, "R²"] == pytest.approx(pearson ** 2)
    ranking = employment(jobs, (2018, 2025)).set_index("INE")
    assert ranking.at["28092", ABS] == -4323
    assert ranking.at["28092", PCT] == pytest.approx(100 * ranking.at["28092", ABS] / ranking.at["28092", "2018"])
    result = temporal(jobs[jobs["INE"].eq("28092")], "Año", jobs.columns[3], "Año", "Territorio")
    assert result.table["Año"].tolist() == list(range(2018, 2026))


def test_study_report_follows_changes_in_filters_and_keeps_charts_offline(monkeypatch):
    reports = []
    original = demos.html_report

    def capture(*args, **kwargs):
        report = original(*args, **kwargs)
        reports.append((args, report))
        return report

    download = st.download_button

    def request_report(label, data, *args, **kwargs):
        if label == "Descargar informe (HTML)":
            data = data()
        return download(label, data, *args, **kwargs)

    monkeypatch.setattr(demos, "html_report", capture)
    monkeypatch.setattr(st, "download_button", request_report)
    app = AppTest.from_file("app.py", default_timeout=45).run()
    app.button(key="open_1").click().run()
    assert not app.exception
    app.select_slider(key="demo_1_years").set_value((2020, 2024)).run()
    assert not app.exception
    args, report = reports[-1]
    assert args[3]["parámetros"]["años"] == [2020, 2024]
    assert list(args[2].columns[2:4]) == ["2020", "2024"]
    assert 'plotly.js' in report and '"white-bg"' in report
    assert "Datos analizados" in report
