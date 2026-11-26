import pandas as pd
import pytest
from workbench_helpers import (
    analysis_method,
    checked,
    filtered_version,
    focus,
    go,
    join,
    prepare,
    press,
    set_widget,
    start,
    submit,
)

from demos import DEMO_NAMES, demo_table


@pytest.mark.parametrize(("demo", "rows"), list(zip(DEMO_NAMES, [179, 1432, 179])))
def test_official_demo(demo, rows):
    df, _ = demo_table(demo)
    assert len(df) == rows
    assert df["Código territorio"].str.startswith("00").any()
    assert not df.duplicated(["Código territorio", "Año"]).any()


def test_ui_combine_three_and_analyze():
    app = start()
    for idx in range(1, 4):
        app.session_state.tables[idx] = {
            "title": f"Tabla {idx}", "df": pd.DataFrame({"municipio": ["001", "002"], "valor": [idx, idx + 1]}),
            "sources": (f"Fuente {idx}",), "history": (),
        }
    app.session_state.serial = 3
    assert join(app, 1, 2, ["municipio"]) == 4
    assert join(app, 4, 3, ["municipio"]) == 5
    result = app.session_state.tables[5]
    assert len(result["history"]) == 2
    assert len(result["sources"]) == 3
    assert result["df"].columns.tolist() == ["municipio", "valor", "valor_B", "valor_B_2"]
    analysis_method(app, 5, "Descriptivos", "Distribución")
    press(app, "execute_5_Distribución")
    assert app.session_state.project_results[-1]["dataset"] == 5
    assert any(widget.label == "Descargar resultados (CSV)" for widget in app.get("download_button"))
    go(app, "Preparación")
    press(app, "prep_undo")
    assert app.session_state.tables[5]["archived"]
    press(app, "prep_redo")
    assert not app.session_state.tables[5]["archived"]


@pytest.mark.parametrize("demo", DEMO_NAMES)
def test_home_does_not_offer_fixed_analyses(demo):
    app = start()
    assert all(demo not in widget.label for widget in app.button)
    assert app.button(key="home_catalog")
    assert not app.session_state.project_results


def test_ui_catalog_selection(monkeypatch):
    resources = [{"id": str(i), "url": f"https://datos.comunidad.madrid/{i}.csv",
                  "format": "CSV", "name": f"Recurso {i}"} for i in range(2)]
    datasets = [{"id": f"fixture-{i}", "name": f"tabla-{i}", "title": f"Tabla {i}",
                 "resources": [resource]} for i, resource in enumerate(resources)]
    monkeypatch.setattr("library_view.find_sources",
                        lambda *args, **kwargs: ({"count": 2, "results": datasets}, False))
    monkeypatch.setattr("library_view.download_resource", lambda _: b"x\n1\n")
    app = start()
    press(app, "home_catalog")
    press(app, "preview_fixture-0")
    assert not app.session_state.tables
    assert any("x" in node.value and node.value["x"].tolist() == [1] for node in app.dataframe)
    for i in range(2):
        set_widget(app, "checkbox", f"catalog_check_fixture-{i}", True)
    press(app, "import_basket")
    assert app.session_state.page == "Datos"
    assert len(app.session_state.tables) == 2
    assert all(item["raw"] == b"x\n1\n" for item in app.session_state.tables.values())
    go(app, "Resultados")
    press(app, "notebook_table")
    go(app, "Datos")
    set_widget(app, "radio", "data_section", "Biblioteca")
    monkeypatch.setattr("library_view.download_resource", lambda _: b"x\n2\n3\n")
    press(app, "refresh_1")
    assert len(app.session_state.tables) == 2
    press(app, "refresh_confirm_1")
    assert app.session_state.tables[3]["supersedes"] == 1
    assert app.session_state.tables[1]["raw"] == b"x\n1\n"
    go(app, "Resultados")
    assert any("Resultado histórico" in node.value for node in app.warning)
    assert app.session_state.project_results[0]["table"]["x"].tolist() == [1]


def test_column_shortcut_and_revision_keep_history():
    app = start()
    app.session_state.tables[1] = {"title": "Datos", "df": pd.DataFrame({"Grupo": ["A", "B"], "Medida": [12, 15]}),
                                  "sources": (), "history": ()}
    app.session_state.serial = 1
    go(app, "Datos")
    set_widget(app, "selectbox", "cfg_column_1", "Medida")
    press(app, "shortcut_rename_1")
    assert app.session_state.page == "Preparación"
    assert app.selectbox(key="cfg_recipe_1_rename_column").value == "Medida"

    original_filter = filtered_version(app, 1, "Grupo", ["A"])
    go(app, "Resultados")
    press(app, "notebook_table")
    prepare(app, 1, "Organizar", "Filtrar filas")
    set_widget(app, "multiselect", "cfg_recipe_1_filter_0_values_Grupo", ["B"], rerun=False)
    press(app, "preview_recipe")
    set_widget(app, "selectbox", "cfg_recipe_revision_1_filter", original_filter, rerun=False)
    press(app, "confirm_recipe")
    replacement = app.session_state.tables[app.session_state.active_table]
    assert replacement["supersedes"] == original_filter
    assert replacement["df"]["Grupo"].tolist() == ["B"]
    go(app, "Resultados")
    assert any("Resultado histórico" in node.value for node in app.warning)
    assert app.session_state.project_results[0]["table"]["Grupo"].tolist() == ["A"]


def test_ui_ai_plan_runs_local_analysis(monkeypatch):
    from types import SimpleNamespace

    import openai

    monkeypatch.setenv("OPENAI_API_KEY", "test")
    reply = SimpleNamespace(output_text='{"operation":"ranking","x":"v1","y":"v2"}')
    monkeypatch.setattr(openai, "OpenAI", lambda **_: SimpleNamespace(
        responses=SimpleNamespace(create=lambda **_: reply)))
    app = start()
    app.session_state.tables[1] = {
        "title": "Indicador", "df": pd.DataFrame({"municipio": ["A", "B"], "renta": [1, 3]}),
        "sources": ("Fuente de prueba",), "history": (),
    }
    go(app, "Análisis")
    set_widget(app, "radio", "cfg_analysis_view", "Operaciones rápidas y asistente")
    set_widget(app, "radio", "analysis_mode", "Pregunta en lenguaje natural")
    set_widget(app, "text_input", "cfg_ai_question_1", "¿Qué municipio tiene mayor renta?")
    press(app, "ask_assistant")
    assert not app.session_state.project_results
    press(app, "execute_quick")
    result = app.session_state.project_results[-1]["table"]
    assert result["Grupo"].tolist() == ["B", "A"]
    assert result["Media"].tolist() == [3, 1]


def test_advanced_filters_survive_navigation():
    app = start()
    app.session_state.tables[1] = {
        "title": "Datos", "df": pd.DataFrame({"grupo": ["A", "B"], "valor": [1, 3]}),
        "sources": ("Fuente",), "history": (),
    }
    go(app, "Análisis")
    focus(app, 1)
    set_widget(app, "number_input", "cfg_analysis_filter_1_count", 1)
    set_widget(app, "selectbox", "cfg_analysis_filter_1_0_op", "En la selección")
    set_widget(app, "multiselect", "cfg_analysis_filter_1_0_values_grupo", ["B"])
    go(app, "Home")
    go(app, "Análisis")
    assert app.selectbox(key="cfg_analysis_filter_1_0_column").value == "grupo"
    assert app.multiselect(key="cfg_analysis_filter_1_0_values_grupo").value == ["B"]


def test_new_project_from_home_is_non_destructive_until_confirmed():
    app = start()
    app.session_state.tables[1] = {"title": "Editable", "df": pd.DataFrame({"Medida": [2]}), "sources": (), "history": ()}
    press(app, "home_new")
    assert app.button(key="new_project").disabled and app.session_state.tables
    set_widget(app, "text_input", "new_project_name", "Otro proyecto")
    set_widget(app, "checkbox", "new_confirm", True, rerun=False)
    press(app, "new_project")
    assert app.session_state.page == "Home"
    assert app.session_state.project_details["name"] == "Otro proyecto"
    assert not app.session_state.tables


def test_library_imports_and_normalizes_project_metadata(monkeypatch):
    import streamlit as st

    class File:
        name = "datos.csv"

        def getvalue(self):
            return b"codigo_territorio,medida\n0014,5\n0029,7\n"

    native = st.file_uploader
    monkeypatch.setattr(st, "file_uploader", lambda *args, **kwargs: [File()] if kwargs.get("key") == "local_upload"
                        else native(*args, **kwargs))
    app = start()
    press(app, "home_import")
    press(app, "import_local_files")
    submit(app, "Abrir biblioteca")
    assert app.session_state.tables[1]["df"]["codigo_territorio"].iat[0] == "0014"
    assert app.session_state.tables[1]["raw"] == File().getvalue()
    checked(app)
