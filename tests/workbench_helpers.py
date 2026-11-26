"""UI drivers for the research acceptance cases."""
from streamlit.testing.v1 import AppTest


def start():
    return checked(AppTest.from_file("app.py", default_timeout=65).run())


def checked(app):
    assert not app.exception, [error.message for error in app.exception]
    return app


def press(app, key):
    return checked(app.button(key=key).click().run())


def submit(app, label):
    return checked(next(widget for widget in app.button if widget.label == label).click().run())


def set_widget(app, kind, key, value, *, rerun=True):
    getattr(app, kind)(key=key).set_value(value)
    return checked(app.run()) if rerun else app


def go(app, page):
    if "page" in app.session_state and app.session_state["page"] == page:
        return app
    return press(app, f"nav_{page}")


def focus(app, key):
    return app if app.session_state["active_table"] == key else set_widget(app, "selectbox", "library_active_widget", key)


def add_offline(app, keys):
    go(app, "Datos")
    set_widget(app, "radio", "data_section", "Catálogo")
    set_widget(app, "multiselect", "local_catalog_picks", keys)
    press(app, "import_offline")
    return {item["metadata"]["extracto"]: key for key, item in app.session_state.tables.items()}


def prepare(app, key, category, op):
    go(app, "Preparación")
    focus(app, key)
    set_widget(app, "radio", "prep_section", "Transformar")
    set_widget(app, "selectbox", "cfg_prep_category", category)
    set_widget(app, "selectbox", f"cfg_prep_op_{category}", op)


def finish_recipe(app, name=None):
    press(app, "preview_recipe")
    if name:
        field = next(widget for widget in app.text_input if widget.label == "Nombre de la tabla de salida")
        field.set_value(name)
    press(app, "confirm_recipe")
    return app.session_state["active_table"]


def join(app, left, right, keys):
    go(app, "Preparación")
    set_widget(app, "radio", "prep_section", "Combinar")
    set_widget(app, "selectbox", "join_left", left)
    set_widget(app, "selectbox", f"join_right_{left}", right)
    set_widget(app, "multiselect", f"keys_a_{left}", keys, rerun=False)
    set_widget(app, "multiselect", f"keys_b_{right}", keys, rerun=False)
    press(app, "join_preview")
    assert app.button(key="join_save").disabled
    set_widget(app, "checkbox", "join_confirmed", True, rerun=False)
    press(app, "join_save")
    return app.session_state["active_table"]


def analysis_method(app, dataset, family, method):
    go(app, "Análisis")
    focus(app, dataset)
    set_widget(app, "radio", "cfg_analysis_view", "Métodos estadísticos")
    press(app, f"family_{dataset}_{family}")
    set_widget(app, "selectbox", f"method_{dataset}_{family}", method)


def filtered_version(app, dataset, column, values, name=None):
    prepare(app, dataset, "Organizar", "Filtrar filas")
    prefix = f"cfg_recipe_{dataset}_filter"
    set_widget(app, "number_input", f"{prefix}_count", 1)
    set_widget(app, "selectbox", f"{prefix}_0_column", column)
    set_widget(app, "selectbox", f"{prefix}_0_op", "En la selección")
    set_widget(app, "multiselect", f"{prefix}_0_values_{column}", values, rerun=False)
    return finish_recipe(app, name)


def group_sum(app, dataset, columns, metric, output):
    prepare(app, dataset, "Crear variables", "Agrupar y resumir")
    prefix = f"cfg_recipe_{dataset}_aggregate"
    set_widget(app, "multiselect", f"{prefix}_groups", columns)
    set_widget(app, "selectbox", f"{prefix}_aggregation", "Suma")
    set_widget(app, "selectbox", f"{prefix}_metric", metric, rerun=False)
    set_widget(app, "text_input", f"{prefix}_name", output, rerun=False)
    return finish_recipe(app)


def ratio(app, dataset, numerator, denominator, name, scale=100.0):
    prepare(app, dataset, "Crear variables", "Construir razón o tasa")
    prefix = f"cfg_recipe_{dataset}_ratio"
    set_widget(app, "selectbox", f"{prefix}_column", numerator)
    set_widget(app, "selectbox", f"{prefix}_right", denominator, rerun=False)
    set_widget(app, "text_input", f"{prefix}_name", name, rerun=False)
    set_widget(app, "number_input", f"{prefix}_scale", scale, rerun=False)
    return finish_recipe(app)


def temporal_change(app, dataset, name, start=2018, end=2025):
    prepare(app, dataset, "Tiempo", "Transformar serie temporal")
    prefix = f"cfg_recipe_{dataset}_time"
    set_widget(app, "selectbox", f"{prefix}_start", start, rerun=False)
    set_widget(app, "selectbox", f"{prefix}_end", end, rerun=False)
    set_widget(app, "text_input", f"{prefix}_name_Comparar dos periodos", name, rerun=False)
    return finish_recipe(app)


def associate(app, dataset, method, x, y):
    analysis_method(app, dataset, "Correlación y asociación", method)
    set_widget(app, "selectbox", f"primary_{dataset}_{method}", x)
    set_widget(app, "selectbox", f"second_{dataset}_{method}", y, rerun=False)
    press(app, f"execute_{dataset}_{method}")
    return app.session_state.project_results[-1]


def scatter(app, dataset, x, y, name):
    go(app, "Visualización")
    focus(app, dataset)
    set_widget(app, "radio", "visual_section", "Gráficos")
    prefix = f"cfg_visual_new_{dataset}_chart"
    set_widget(app, "selectbox", f"{prefix}_kind", "Dispersión")
    set_widget(app, "selectbox", f"{prefix}_2_x", x)
    set_widget(app, "selectbox", f"{prefix}_2_y", y, rerun=False)
    set_widget(app, "text_input", f"{prefix}_2_title", name, rerun=False)
    press(app, "render_visual")
    assert app.get("plotly_chart")
    press(app, "keep_visual")
    return app.session_state.project_results[-1]


def map_result(app, dataset, value, title):
    go(app, "Visualización")
    focus(app, dataset)
    set_widget(app, "radio", "visual_section", "Mapas")
    prefix = f"cfg_visual_new_{dataset}_map_0"
    set_widget(app, "selectbox", f"{prefix}_metric", value, rerun=False)
    set_widget(app, "text_input", f"{prefix}_title", title, rerun=False)
    press(app, "render_visual")
    assert app.get("plotly_chart")
    press(app, "keep_visual")
    return app.session_state.project_results[-1]


def export_report(app, title, selected):
    go(app, "Resultados")
    set_widget(app, "radio", "cfg_results_section", "Informes")
    if app.selectbox(key="cfg_report_picker").value:
        set_widget(app, "selectbox", "cfg_report_picker", None)
    set_widget(app, "text_input", "report_title_new", title, rerun=False)
    set_widget(app, "multiselect", "report_entries_new", [entry["id"] for entry in selected], rerun=False)
    set_widget(app, "text_area", "report_new_conclusions", "Interpretación de la investigación.", rerun=False)
    submit(app, "Guardar borrador")
    draft = app.session_state.project_details["reports"][-1]
    assert draft["title"] == title
    assert any(action.label == "Descargar informe HTML" for action in app.get("download_button"))
    return draft
