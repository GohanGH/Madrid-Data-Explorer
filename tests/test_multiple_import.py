from dataclasses import dataclass

import pandas as pd
import pytest
import requests
import streamlit as st
from workbench_helpers import (
    associate,
    go,
    join,
    map_result,
    press,
    scatter,
    set_widget,
    start,
    submit,
)

from projects import load_project

CODES = ["0014", "0029", "0035", "0040", "0053"]
KEY = "Código territorio"


def catalog_dataset(number, *, geography="Municipios"):
    url = f"https://datos.comunidad.madrid/datos-{number}.csv"
    return {"id": f"ds-{number}", "name": f"ds-{number}", "title": f"Medición {number}. {geography}",
            "resources": [{"url": url, "name": f"Recurso {number}", "format": "CSV"}]}


def catalog_check(app, dataset, value=True):
    return set_widget(app, "checkbox", f"catalog_check_{dataset['id']}", value)


def test_import_five_catalog_datasets_and_use_them_in_one_project(monkeypatch):
    a, b, c, d, e = [catalog_dataset(i, geography="Distritos" if i == 4 else "Municipios") for i in range(1, 6)]
    # All five fixtures share municipal identifiers so the analytical join is meaningful.
    csv_data = {}
    for i, dataset in enumerate([a, b, c, d, e], 1):
        lines = [f"{KEY},Medida {i}", *(f"{code},{10 * i + val * i}" for code, val in zip(CODES, [1, 5, 3, 8, 9]))]
        csv_data[dataset["resources"][0]["url"]] = "\n".join(lines).encode()

    def search(query, mode, facets, offset, sort):
        rows = [d, e] if query else [c] if offset == 20 else [a, b]
        return {"count": 2 if query else 21, "results": rows}, False

    monkeypatch.setattr("library_view.find_sources", search)
    monkeypatch.setattr("library_view.download_resource", lambda resource: csv_data[resource["url"]])
    app = start()
    old = pd.DataFrame({"Variable anterior": [23]})
    app.session_state.tables[1] = {"title": "Tabla anterior", "df": old, "history": (), "sources": ()}
    app.session_state.serial = 1

    press(app, "home_catalog")
    catalog_check(app, a)
    catalog_check(app, b)
    press(app, "catalog_next")
    catalog_check(app, c)
    press(app, "catalog_prev")
    assert all(app.checkbox(key=f"catalog_check_{row['id']}").value for row in [a, b])
    set_widget(app, "text_input", "catalog_keyword", "medición", rerun=False)
    submit(app, "Buscar")
    catalog_check(app, d)
    set_widget(app, "selectbox", "catalog_scope", "Municipios", rerun=False)
    submit(app, "Buscar")
    assert all(widget.key != "catalog_check_ds-4" for widget in app.checkbox)
    catalog_check(app, e)
    assert len(app.session_state.catalog_basket) == 5
    assert not any(item in app.session_state.tables for item in range(2, 7))

    submit(app, "Importar seleccionados")
    assert not app.session_state.catalog_basket
    assert len(app.selectbox(key="library_active_widget").options) == 6
    assert app.session_state.active_table == 1
    pd.testing.assert_frame_equal(app.session_state.tables[1]["df"], old)
    for i, (url, raw) in enumerate(csv_data.items(), 2):
        assert app.session_state.tables[i]["sources"] == (url,)
        assert app.session_state.tables[i]["raw"] == raw

    combined = 2
    for right in range(3, 7):
        combined = join(app, combined, right, [KEY])
    assert set(app.session_state.tables[combined]["sources"]) == set(csv_data)
    assert len(app.session_state.tables[combined]["history"]) == 4
    result = associate(app, combined, "Pearson", "Medida 1", "Medida 5")
    assert result["table"]["Coeficiente"].iat[0] == pytest.approx(1.)
    assert result["table"]["Observaciones"].iat[0] == 5
    assert scatter(app, combined, "Medida 1", "Medida 5", "Medidas combinadas")["dataset"] == combined
    assert map_result(app, combined, "Medida 5", "Mapa de la combinación")["dataset"] == combined

    go(app, "Mis proyectos")
    press(app, "prepare_zip")
    tables, _, _, results, _ = load_project(app.session_state.project_export)
    assert {tables[i]["raw"] for i in range(2, 7)} == set(csv_data.values())
    assert len(results) == 3


def test_select_multiple_resources_and_retry_only_failed_import(monkeypatch):
    first, later = catalog_dataset(1), catalog_dataset(2)
    main = first["resources"][0]
    extra = {**main, "name": "Desglose", "url": "https://datos.comunidad.madrid/desglose.csv"}
    first["resources"] = [main, extra, dict(main)]
    rows = [first, later]
    monkeypatch.setattr("library_view.find_sources", lambda *args: ({"count": len(rows), "results": rows}, False))
    attempts = []
    errors = {extra["url"]}

    def download(resource):
        url = resource["url"]
        attempts.append(url)
        if url in errors:
            raise requests.HTTPError("No se pudo descargar el desglose.")
        return b"Medida\n2\n3\n"

    native_status = st.status
    progress = []

    def status(label, *args, **kwargs):
        progress.append(label)
        return native_status(label, *args, **kwargs)

    monkeypatch.setattr(st, "status", status)
    monkeypatch.setattr("library_view.download_resource", download)
    app = start()
    press(app, "home_catalog")
    catalog_check(app, first)
    picks = f"catalog_picks_{first['id']}"
    assert app.multiselect(key=picks).value == [main["url"]]
    assert len(app.multiselect(key=picks).options) == 2
    set_widget(app, "multiselect", picks, [main["url"], extra["url"]])
    catalog_check(app, later)
    catalog_check(app, later, False)
    assert set(app.session_state.catalog_basket) == {main["url"], extra["url"]}
    catalog_check(app, later)
    press(app, "import_basket")

    assert len(app.session_state.tables) == 2
    assert list(app.session_state.catalog_basket) == [extra["url"]]
    assert app.multiselect(key=picks).value == [extra["url"]]
    assert [label.split()[1] for label in progress] == ["1/3", "2/3", "3/3"]
    assert any("Desglose" in node.value and "No se pudo descargar" in node.value for node in app.error)
    assert attempts == [main["url"], extra["url"], later["resources"][0]["url"]]

    errors.clear()
    set_widget(app, "multiselect", picks, [extra["url"], main["url"]])
    press(app, "import_basket")
    assert not app.session_state.catalog_basket
    assert len(app.session_state.tables) == 3
    assert attempts.count(main["url"]) == 1 and attempts.count(extra["url"]) == 2
    assert any("Ya en el proyecto" in node.value for node in app.text)
    assert "Desglose" in app.session_state.tables[3]["title"]


@dataclass(frozen=True)
class UploadedFile:
    name: str
    raw: bytes

    def getvalue(self):
        return self.raw


def test_import_multiple_local_files_even_if_one_is_invalid(monkeypatch):
    first = UploadedFile("mediciones.csv", b"A,B\n1,2\n")
    files = [first, UploadedFile("erroneo.csv", b"A,B\n1,2,3\n"),
             UploadedFile("copia.csv", first.raw), UploadedFile(first.name, b"A,B\n4,5\n")]
    native_uploader = st.file_uploader

    def upload(*args, **kwargs):
        if kwargs.get("key") == "local_upload":
            assert kwargs["accept_multiple_files"] is True
            return files
        return native_uploader(*args, **kwargs)

    monkeypatch.setattr(st, "file_uploader", upload)
    app = start()
    press(app, "home_import")
    press(app, "import_local_files")
    assert [row["raw"] for row in app.session_state.tables.values()] == [files[0].raw, files[3].raw]
    assert any("erroneo.csv" in node.value and "número de campos" in node.value for node in app.error)
    assert any("Ya en el proyecto · copia.csv" in node.value for node in app.text)
    assert len(app.selectbox(key="library_active_widget").options) == 2
    press(app, "import_local_files")
    assert len(app.session_state.tables) == 2
    submit(app, "Abrir biblioteca")
    assert app.session_state.data_section == "Biblioteca"
