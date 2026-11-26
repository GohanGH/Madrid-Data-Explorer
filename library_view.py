"""Catalogue, original resource imports and the interactive table library."""
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from logging import getLogger
from pathlib import PurePosixPath
from urllib.parse import unquote, urlsplit
from zipfile import BadZipFile

import pandas as pd
import plotly.express as px
import requests
import streamlit as st

from analysis_workspace import dictionary, get_profile, role_map
from catalog import (
    FACETS,
    SORT,
    catalog_page,
    compatible_resources,
    download_resource,
    official_url,
)
from data_tables import csv_export, read_table
from dataset_cards import dataset_metadata, metadata_card
from discovery import coverage, fold, interpret, relevance, retrieve
from interface import metric_cards, navigate, report_chart
from joins import key_role
from loading import loading
from preparation_view import open_column_recipe
from profiling import NUMERIC, ROLES
from statistical_engine import descriptive, numeric_values
from territories import DATA, official_codes, source_metadata
from transformations import filter_rows
from workspace_controls import choose, choose_many, filter_controls
from workspace_state import (
    active_key,
    remove_unused,
    retire_table,
    store_table,
    table_kind,
    version_warnings,
    visible_tables,
)
from workspace_views import focus_table, go_to_data

MODES = ("Palabras clave", "Lenguaje natural")
SECTIONS = ("Biblioteca", "Catálogo", "Importar")
SCOPES = ("Cualquier cobertura", "Municipios", "Distritos", "Barrios", "Comunidad de Madrid")
DATA_ERRORS = (requests.RequestException, ValueError, KeyError, TypeError, OSError, BadZipFile)
CATALOG_BATCH_LIMIT = 12
LOGGER = getLogger(__name__)


@st.cache_data(ttl=600, max_entries=32, show_spinner=False)
def find_sources(query, mode, facets, offset, sort):
    if mode == MODES[1] and query:
        parsed = interpret(query, [name for _, name in official_codes().values()])
        rows, failed = retrieve(parsed, fetch=lambda term, rows: catalog_page(term, rows=rows, filters=facets, sort=sort))
        # CKAN supplies filter options. Natural-language results are a ranked sample.
        info = {}
        try:
            info = catalog_page("", rows=1, filters=facets, sort=sort).get("search_facets", {})
        except DATA_ERRORS:
            failed = True
        return {"count": len(rows), "results": [row[1] for row in rows], "search_facets": info}, failed
    return catalog_page(query, start=offset, filters=facets, sort=sort), False


def matching_scope(dataset, scope, year):
    geo, temporal = coverage(dataset)
    if scope != SCOPES[0] and fold(scope) not in fold(geo or "") and fold(scope) not in fold(dataset.get("title", "")):
        return False
    if year is None:
        return True
    text = fold(temporal or "")
    years = [int(value) for value in re.findall(r"\b(?:19|20)\d{2}\b", text)]
    if len(years) == 2 and re.search(r"[-–—/]|\b(?:a|hasta)\b", text):
        return min(years) <= year <= max(years)
    return year in years


def resource_record(dataset, resource):
    metadata = dataset_metadata(dataset, resource)
    url = resource["url"]
    filename = unquote(PurePosixPath(urlsplit(url).path).name)
    fmt = resource["format"].strip().upper()
    if PurePosixPath(filename).suffix.casefold() != f".{fmt.lower()}":
        filename = f"recurso.{fmt.lower()}"
    metadata["recurso"] = {"url": url, "format": fmt}
    metadata["descargado"] = datetime.now(timezone.utc).isoformat()
    return metadata, filename


def read_resource(dataset, resource):
    with loading("Descargando recurso del catálogo"):
        raw = download_resource(resource)
        frame = read_table(raw, resource["format"])
        if not len(frame):
            raise ValueError("El recurso no contiene observaciones.")
    metadata, filename = resource_record(dataset, resource)
    metadata["sha256"] = sha256(raw).hexdigest()
    return frame, raw, metadata, filename


def existing_original(state, matches):
    candidates = [key for key, item in state.tables.items() if table_kind(item) == "Original" and matches(item)]
    return next((key for key in candidates if not state.tables[key].get("archived")), next(iter(candidates), None))


def resource_label(resource):
    return f"{resource.get('name') or 'Recurso'} · {resource['format']}"


def import_resource(dataset, resource):
    state = st.session_state
    url = resource["url"]
    duplicate = existing_original(state, lambda item: item.get("metadata", {}).get("recurso", {}).get("url") == url)
    if duplicate is not None:
        return duplicate, False
    cached = state.get("catalog_preview")
    if cached and cached[0] == url:
        frame, raw, metadata, filename = cached[1]
    else:
        frame, raw, metadata, filename = read_resource(dataset, resource)
    title = dataset.get("title") or filename
    if len({item["url"] for item in compatible_resources(dataset)}) > 1:
        title = f"{title} · {resource_label(resource)}"
    key = store_table(state, title, frame, [url], metadata=metadata, raw=raw, filename=filename, focus=False)
    return key, True


@dataclass(frozen=True)
class ImportResult:
    label: str
    added: bool = False
    error: str | None = None
    archived: bool = False


def import_batch(tasks, importer):
    results = []
    for position, (label, args) in enumerate(tasks, 1):
        step = f"{position}/{len(tasks)} · {label}"
        progress = st.status(f"Importando {step}", expanded=False)
        try:
            key, added = importer(*args)
        except Exception as exc:
            if not isinstance(exc, DATA_ERRORS):
                LOGGER.exception("No se pudo importar %s", label)
            detail = str(exc) or type(exc).__name__
            progress.update(label=f"Error · {step}", state="error")
            results.append(ImportResult(label, error=detail))
        else:
            progress.update(label=f"{'Importado' if added else 'Ya en el proyecto'} · {step}", state="complete")
            results.append(ImportResult(label, added, archived=bool(st.session_state.tables[key].get("archived"))))
    return results


def show_import_results(results):
    if not results:
        return
    if count := sum(result.added for result in results):
        st.success(f"Se incorporaron {count} tablas a la biblioteca.")
    with st.expander("Resultado de la última importación", expanded=any(result.error for result in results)):
        for result in results:
            if result.error:
                st.error(f"{result.label}. {result.error}")
            else:
                status = "Importado" if result.added else "Ya en el proyecto"
                if result.archived:
                    status += " como versión retirada"
                st.text(f"{status} · {result.label}")


def update_catalog_selection(widget, dataset, options, *, default=None):
    state = st.session_state
    selected = state[widget]
    if default is not None:
        selected = [default] if selected else []
    basket = {url: entry for url, entry in state.catalog_basket.items() if url not in options or url in selected}
    for url in selected:
        if url in options:
            basket.setdefault(url, (dataset, options[url]))
    if len(basket) > CATALOG_BATCH_LIMIT:
        state.catalog_selection_notice = f"La selección admite hasta {CATALOG_BATCH_LIMIT} recursos por lote."
    else:
        state.catalog_basket = basket


def candidate_card(dataset, query):
    state = st.session_state
    identifier = str(dataset.get("id") or dataset.get("name"))
    title = str(dataset.get("title", "Recurso sin título"))
    options = {resource["url"]: resource for resource in compatible_resources(dataset)}
    selected = [url for url in state.catalog_basket if url in options]
    check_key = f"catalog_check_{identifier}"
    state[check_key] = bool(selected)
    with st.container(horizontal=True, gap="small", vertical_alignment="center"):
        st.checkbox(f"Seleccionar {title}", key=check_key, label_visibility="collapsed", disabled=not options,
                    on_change=update_catalog_selection, args=(check_key, dataset, options),
                    kwargs={"default": next(iter(options), None)})
        details = st.expander(title)
    with details:
        metadata_card(dataset_metadata(dataset))
        if query:
            _, reasons = relevance(query, dataset)
            if reasons:
                st.caption(" · ".join(reasons))
        if not options:
            st.caption("La ficha no ofrece un recurso tabular compatible en los dominios admitidos.")
            return
        if len(options) > 1:
            picks_key = f"catalog_picks_{identifier}"
            state[picks_key] = selected
            st.multiselect("Recursos para importar", list(options), key=picks_key,
                           format_func=lambda url: resource_label(options[url]),
                           on_change=update_catalog_selection, args=(picks_key, dataset, options))
        url = choose("Recurso", options, f"catalog_resource_{identifier}", format_func=lambda url: resource_label(options[url]))
        resource = options[url]
        with st.container(horizontal=True, gap="small"):
            if st.button("Previsualizar", key=f"preview_{identifier}"):
                try:
                    st.session_state.catalog_preview = (resource["url"], read_resource(dataset, resource))
                except DATA_ERRORS as exc:
                    st.error(f"No se pudo previsualizar el recurso. {exc}")
            if st.button("Importar y abrir", key=f"catalog_open_{identifier}"):
                try:
                    key, _ = import_resource(dataset, resource)
                    if state.tables[key].get("archived"):
                        st.info("El recurso ya está en el proyecto. Puedes recuperarlo desde las versiones retiradas de la biblioteca.")
                    else:
                        state.catalog_basket.pop(url, None)
                        state.catalog_opened = key
                        st.rerun()
                except DATA_ERRORS as exc:
                    st.error(f"No se pudo importar. {exc}")
            st.link_button("Archivo oficial", resource["url"])
        cached = st.session_state.get("catalog_preview")
        if cached and cached[0] == resource["url"]:
            frame = cached[1][0]
            st.caption(f"{len(frame):,} filas · {len(frame.columns)} variables · vista de hasta 25 filas")
            st.dataframe(frame.head(25), hide_index=True)


def local_catalog():
    sources = dict(source_metadata())
    health = sources["centros_sanitarios_por_tipo"]
    sources["centros_atencion_primaria_recuento"] = {**health, "title": "Centros de atención primaria (recuento municipal)",
                                                    "unidad": "centros"}
    with st.expander("Extractos oficiales disponibles sin conexión"):
        st.caption("Cortes del catálogo con fecha, fuente y unidad. Puedes importarlos a cualquier proyecto.")
        keys = list(sources)
        chosen = choose_many("Extractos", keys, "local_catalog_picks", format_func=lambda k: sources[k]["title"])
        if chosen:
            for key in chosen:
                source = sources[key]
                st.link_button(source["title"], source["url"])
                st.caption(f"{source['referencia']} · {source['unidad']} · {source['cobertura']}")
            if st.button("Importar extractos", key="import_offline", type="primary"):
                successes = []
                for key in chosen:
                    source = sources[key]
                    name = f"{key}.csv"
                    if any(item.get("metadata", {}).get("extracto") == key for item in visible_tables(st.session_state).values()):
                        continue
                    try:
                        raw = (DATA / name).read_bytes()
                        frame = read_table(raw, "CSV")
                        metadata = {**source, "extracto": key, "formato": "CSV", "fuente": source["url"],
                                    "cobertura temporal": source["referencia"], "cobertura geográfica": source["cobertura"]}
                        successes.append(store_table(st.session_state, source["title"], frame, [source["url"]],
                                                     metadata=metadata, raw=raw, filename=name, focus=False))
                    except DATA_ERRORS as exc:
                        st.error(f"{source['title']}. {exc}")
                if successes:
                    st.success(f"Se incorporaron {len(successes)} tablas a la biblioteca.")


def catalogue():
    state = st.session_state
    previous = state.get("catalog_request")
    with st.form("catalog_search", border=False):
        query = st.text_input("Buscar datos abiertos", key="catalog_keyword", max_chars=350,
                              placeholder="Por ejemplo, visitas a bibliotecas por municipio")
        mode = st.radio("Tipo de búsqueda", MODES, horizontal=True, key="catalog_mode")
        with st.expander("Filtros y orden"):
            scope = st.selectbox("Cobertura geográfica", SCOPES, key="catalog_scope")
            year_text = st.text_input("Año cubierto según la ficha", key="catalog_year", max_chars=4)
            facets = {}
            for label, field in FACETS.items():
                values = {i["name"]: i.get("display_name") or i["name"]
                          for i in state.get("catalog_facets", {}).get(field, {}).get("items", [])}
                facets[label] = choose(label, [None, *values], f"catalog_facet_{field}",
                                       format_func=lambda value, labels=values: labels.get(value, "Cualquiera"))
            sort = st.selectbox("Orden en CKAN", list(SORT), key="catalog_sort")
        submitted = st.form_submit_button("Buscar", type="primary", icon=":material/search:")
    if submitted:
        if year_text and not re.fullmatch(r"[12][0-9]{3}", year_text):
            st.error("Indica un año de cuatro dígitos o deja el campo vacío.")
        else:
            state.catalog_request = (query.strip(), mode, {"facets": facets, "scope": scope,
                                    "year": int(year_text) if year_text else None, "sort": sort}, 0)
            previous = state.catalog_request
            state.pop("catalog_preview", None)
    if notice := state.pop("catalog_selection_notice", None):
        st.warning(notice)
    basket = state.setdefault("catalog_basket", {})
    if basket:
        with st.expander(f"Selección para importar · {len(basket)} recursos", expanded=True):
            tasks = [(f"{dataset.get('title') or 'Dataset'} · {resource_label(resource)}", (dataset, resource))
                     for dataset, resource in basket.values()]
            for label, _ in tasks:
                st.text(label)
            left, right = st.columns(2)
            if left.button("Importar seleccionados", key="import_basket", type="primary"):
                results = import_batch(tasks, import_resource)
                state.catalog_import_results = results
                for url, result in zip(tuple(basket), results, strict=True):
                    if result.error is None:
                        del basket[url]
                st.rerun()
            if right.button("Vaciar selección", key="clear_basket"):
                basket.clear()
                st.rerun()
    show_import_results(state.get("catalog_import_results"))
    if previous is not None:
        text, search_mode, config, offset = previous
        try:
            with loading("Consultando el catálogo oficial"):
                result, failed = find_sources(text, search_mode, config.get("facets", {}), offset, config.get("sort", "Relevancia"))
        except DATA_ERRORS as exc:
            st.warning(f"El catálogo no respondió. Puedes volver a buscar o usar los extractos locales. {exc}")
        else:
            state.catalog_facets = result.get("search_facets", {})
            if failed:
                st.info("Algunas consultas al catálogo quedaron sin respuesta.")
            scope = config.get("scope", SCOPES[0])
            year = config.get("year")
            matches = [dataset for dataset in result["results"] if matching_scope(dataset, scope, year)]
            if search_mode == MODES[0] or not text:
                st.caption(f"{result['count']:,} fichas en CKAN · página {offset // 20 + 1} · {len(matches)} visibles")
                prev, nxt = st.columns(2)
                if prev.button("Anterior", disabled=offset == 0, key="catalog_prev"):
                    state.catalog_request = (text, search_mode, config, max(0, offset - 20))
                    st.rerun()
                if nxt.button("Siguiente", disabled=offset + 20 >= result["count"], key="catalog_next"):
                    state.catalog_request = (text, search_mode, config, offset + 20)
                    st.rerun()
            else:
                st.caption(f"{len(matches)} fuentes candidatas · ordenadas por relevancia")
            if scope != SCOPES[0] or year:
                st.caption("Cobertura aplicada a las fichas recuperadas. Las fichas sin esa cobertura explícita quedan fuera.")
            if not matches:
                st.info("No hay fichas visibles con estos filtros. Amplía la búsqueda o cambia de página.")
            parsed = interpret(text, [name for _, name in official_codes().values()]) if search_mode == MODES[1] and text else None
            for dataset in matches:
                candidate_card(dataset, parsed)
    local_catalog()


def import_local_file(file):
    state = st.session_state
    raw = file.getvalue()
    fmt = file.name.rsplit(".", 1)[-1].upper()
    digest = sha256(raw).hexdigest()
    duplicate = existing_original(state, lambda item: item.get("metadata", {}).get("sha256") == digest
                                  and item.get("metadata", {}).get("formato") == fmt)
    if duplicate is not None:
        return duplicate, False
    with loading(f"Leyendo {file.name}"):
        frame = read_table(raw, fmt)
    key = store_table(state, file.name, frame, [f"Archivo de sesión: {file.name}"],
                      metadata={"formato": fmt, "sha256": digest, "descripción": "Archivo importado por el usuario."},
                      raw=raw, filename=file.name, focus=False)
    return key, True


def import_files():
    state = st.session_state
    st.subheader("Archivos propios")
    files = st.file_uploader("Selecciona uno o varios archivos", type=["csv", "tsv", "xlsx", "xls", "json"],
                             accept_multiple_files=True, key="local_upload")
    if files and st.button("Importar archivos", key="import_local_files", type="primary"):
        state.local_import_results = import_batch([(file.name, (file,)) for file in files], import_local_file)
        st.rerun()
    results = state.get("local_import_results", [])
    show_import_results(results)
    if any(result.error is None and not result.archived for result in results) and visible_tables(state):
        st.button("Abrir biblioteca", on_click=go_to_data, args=("Biblioteca",), key="after_import")


def dataset_overview(item, key):
    info = get_profile(item)
    roles = role_map(item)
    meta = item.get("metadata", {})
    with st.container(key="library_summary"):
        st.subheader(item["title"])
        st.caption(f"{table_kind(item)} · #{key} · {meta.get('formato') or 'Tabla del proyecto'}")
        metric_cards([("Filas", info["rows"], None), ("Columnas", info["columns"], None),
                      ("Celdas ausentes", info["missing"], None), ("Filas duplicadas", info["duplicates"], None)], width=154)
    if meta.get("descripción"):
        st.text(meta["descripción"])
    periods = [entry for entry, role in roles.items() if role in {"Año", "Fecha"}]
    codes = [entry for entry, role in roles.items() if role == "Código municipal"]
    grain = "(sin determinar)"
    for possible in [codes[:1] + periods[:1], codes[:1], periods[:1]]:
        if possible and item["df"][possible].notna().all().all() and not item["df"].duplicated(possible).any():
            grain = " × ".join(possible)
            break
    fields = {"Cobertura": meta.get("cobertura geográfica") or meta.get("cobertura") or "Sin indicar",
              "Periodo en la ficha": meta.get("cobertura temporal") or "Sin indicar", "Actualización": meta.get("actualización") or "Sin indicar",
              "Clave candidata de observación": grain}
    with st.expander("Ficha y procedencia"):
        st.dataframe(pd.DataFrame(fields.items(), columns=["Campo", "Valor"]), hide_index=True)
        for source in item["sources"]:
            if official_url(source):
                st.link_button("Abrir fuente original", source)
            else:
                st.text(source)
        if official_url(meta.get("ficha") or ""):
            st.link_button("Ficha del catálogo", meta["ficha"])
        st.dataframe(dictionary(item), hide_index=True)
    for warning in version_warnings(st.session_state.tables, key):
        st.warning(warning)


def column_panel(item, key, frame):
    df = item["df"]
    column = choose("Variable", df.columns, f"cfg_column_{key}")
    total = df[column]
    view = frame[column]
    inferred = role_map(item)[column]
    st.caption(f"{inferred} · {total.dtype}")
    st.caption(f"{len(total):,} observaciones · {int(total.isna().sum()):,} ausentes · {total.nunique():,} únicos")
    notes = [advice.reason for advice in get_profile(item)["advice"] if advice.column == column]
    for note in notes[:4]:
        st.caption(note)
    if inferred in NUMERIC and numeric_values(view).notna().any():
        result = descriptive(view)
        st.write(result.summary)
        st.dataframe(result.table.astype({"Valor": "string"}).head(10), hide_index=True, height=208)
        st.plotly_chart(report_chart(result.figure).update_layout(height=270))
    elif inferred not in {"Identificador", "Código municipal", "Fecha", "Año"}:
        counts = view.astype("string").fillna("(Ausente)").value_counts().head(12).rename_axis("Valor").reset_index(name="Frecuencia")
        st.dataframe(counts, hide_index=True, height=180)
        if not counts.empty:
            st.plotly_chart(report_chart(px.bar(counts, x="Valor", y="Frecuencia")).update_layout(height=260))
    else:
        st.dataframe(view.drop_duplicates().head(20).to_frame("Valores distintos"), hide_index=True, height=180)
    with st.expander("Cambiar clasificación"):
        role = choose("Rol", ROLES, f"cfg_column_role_{key}_{column}", default=inferred)
        if st.button("Guardar rol", key=f"save_library_role_{key}_{column}"):
            item.setdefault("roles", {})[column] = role
            st.rerun()
    with st.container(horizontal=True, gap="small"):
        st.button("Cambiar tipo", key=f"shortcut_cast_{key}", on_click=open_column_recipe, args=(key, column, "cast"))
        st.button("Renombrar variable", key=f"shortcut_rename_{key}", on_click=open_column_recipe, args=(key, column, "rename"))


def refresh_panel(item, key):
    state = st.session_state
    resource = item.get("metadata", {}).get("recurso", {})
    if not (table_kind(item) == "Original" and official_url(resource.get("url", ""))):
        return
    if st.button("Comprobar actualización de la fuente", key=f"refresh_{key}"):
        try:
            frame, raw, metadata, filename = read_resource({"title": item["title"]}, resource)
            if metadata["sha256"] == item.get("metadata", {}).get("sha256"):
                state.pop("library_refresh", None)
                st.info("El archivo coincide con la versión activa.")
            else:
                state.library_refresh = (key, frame, raw, metadata, filename)
        except DATA_ERRORS as exc:
            st.error(f"No se pudo recuperar la fuente. {exc}")
    proposal = state.get("library_refresh")
    if proposal is None or proposal[0] != key:
        return
    _, frame, raw, fetched, filename = proposal
    st.caption(f"Revisión descargada · {len(frame):,} filas · {len(frame.columns)} columnas")
    before = set(item["df"])
    if before != set(frame):
        st.warning("Cambió el esquema de columnas. Revisa la vista previa antes de guardar.")
    st.dataframe(frame.head(10), hide_index=True)
    if st.button("Guardar como revisión nueva", key=f"refresh_confirm_{key}", type="primary"):
        try:
            stamp = {field: fetched[field] for field in ("descargado", "sha256")}
            store_table(state, f"{item['title']} · revisión", frame, item["sources"],
                        [*item["history"], {"operación": "actualizar fuente", "versión anterior": key, **stamp}],
                        True, metadata={**item.get("metadata", {}), **stamp}, raw=raw, filename=filename, supersedes=key)
            state.pop("library_refresh", None)
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))


def manage_table(item, key):
    state = st.session_state
    with st.expander("Administrar tabla"):
        title = st.text_input("Nombre de la tabla", value=item["title"], max_chars=200, key=f"table_title_{key}")
        with st.container(horizontal=True, gap="small"):
            if st.button("Renombrar", key=f"rename_table_{key}", disabled=not title.strip()):
                item["title"] = title.strip()
                st.rerun()
            if st.button("Duplicar tabla", key=f"duplicate_table_{key}"):
                try:
                    step = {"operación": "duplicar", "origen": key}
                    store_table(state, f"{item['title']} · copia", item["df"], item["sources"], (*item["history"], step),
                                True, metadata=item.get("metadata"), kind="Derivada", parents=(key,), roles=item.get("roles"))
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
            st.download_button("Exportar tabla (CSV)", lambda: csv_export(item["df"]), "tabla.csv", "text/csv",
                               key=f"library_export_{key}", on_click="ignore")
            if "raw" in item:
                st.download_button("Descargar original", item["raw"], item.get("filename") or "original",
                                   key=f"library_raw_{key}", on_click="ignore")
        refresh_panel(item, key)
        confirmed = st.checkbox("Confirmo retirar esta tabla de la biblioteca activa", key=f"retire_confirm_{key}")
        if st.button("Retirar tabla", key=f"retire_table_{key}", disabled=not confirmed):
            retire_table(state, key)
            st.rerun()


def library():
    state = st.session_state
    items = visible_tables(state)
    archived = {key: item for key, item in state.tables.items() if item.get("archived")}
    if archived:
        with st.expander(f"Versiones retiradas · {len(archived)}"):
            target = choose("Versión", archived, "archived_choice", format_func=lambda k: archived[k]["title"])
            if st.button("Recuperar tabla", key="restore_table"):
                archived[target]["archived"] = False
                focus_table(target)
                st.rerun()
            confirmed = st.checkbox("Confirmo eliminar definitivamente la versión seleccionada", key="discard_confirmation")
            if st.button("Eliminar si no tiene dependencias", key="discard_table", disabled=not confirmed):
                try:
                    remove_unused(state, target)
                    st.rerun()
                except ValueError as exc:
                    st.warning(str(exc))
    if not items:
        st.info("Incorpora datos del catálogo o importa archivos para iniciar la biblioteca.")
        st.button("Ir al catálogo", on_click=go_to_data, args=("Catálogo",))
        return
    key = active_key(state)
    item = items[key]
    df = item["df"]
    dataset_overview(item, key)
    with st.container(horizontal=True):
        st.button("Preparar tabla", on_click=navigate, args=("Preparación",), key="open_prep")
        st.button("Analizar tabla", on_click=navigate, args=("Análisis",), key="open_analysis")
        st.button("Crear visualización", on_click=navigate, args=("Visualización",), key="open_visuals")
    if len(items) > 1:
        with st.expander("Relaciones con otras tablas"):
            pairs = [{"Tabla": f"#{other_key} {other['title']}", "Izquierda": column,
                      "Derecha": related, "Tipo": key_role(column)}
                     for other_key, other in items.items() if other_key != key
                     for column in df.columns if key_role(column)
                     for related in other["df"] if key_role(related) == key_role(column)]
            if pairs:
                st.dataframe(pd.DataFrame(pairs[:60]), hide_index=True)
            else:
                st.caption("Sin sugerencias por rol. Puedes elegir cualquier clave al combinar.")
    chosen = choose_many("Columnas visibles", df.columns, f"cfg_library_columns_{key}", default=list(df))
    filters = filter_controls(df, f"cfg_library_filter_{key}", label="Filtrar filas")
    if state.get("map_library_filter", (None,))[0] == key:
        _, geo_column, geo_values, source_filters = state.map_library_filter
        geo_filters = [{"column": geo_column, "op": "En la selección", "value": geo_values}]
        if st.button("Quitar selección del mapa", key="remove_map_filter"):
            state.pop("map_library_filter", None)
            st.rerun()
        filters.extend([*source_filters, *geo_filters])
    try:
        view = filter_rows(df, filters)
    except DATA_ERRORS as exc:
        st.info(str(exc))
        return
    left, right = st.columns([3, 2], gap="large")
    with left:
        st.caption(f"{len(view):,} filas tras aplicar los filtros")
        if chosen:
            selection = view[chosen]
            st.dataframe(selection.head(5000), hide_index=True, height=390)
            if len(view) > 5000:
                st.caption("Vista de las primeras 5.000 filas. El CSV incluye toda la selección.")
            st.download_button("Descargar selección (CSV)", lambda: csv_export(selection), "seleccion.csv", "text/csv",
                               key=f"library_selection_{key}", on_click="ignore")
            if st.button("Guardar subconjunto", key=f"save_subset_{key}"):
                try:
                    step = {"operación": "subconjunto", "columnas": chosen, "filtros": filters}
                    store_table(state, f"{item['title']} · subconjunto", selection, item["sources"],
                                (*item["history"], step), True, kind="Transformada", parents=(key,),
                                metadata=item.get("metadata"), roles=item.get("roles"))
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
        else:
            st.info("Selecciona al menos una columna visible.")
    with right:
        column_panel(item, key, view)
    manage_table(item, key)


def data_screen():
    st.title("Datos")
    state = st.session_state
    opened = state.pop("catalog_opened", None)
    if opened is not None:
        focus_table(opened, "Datos")
    state.setdefault("data_section", "Biblioteca" if visible_tables(state) else "Catálogo")
    view = st.radio("Fuente de datos", SECTIONS, horizontal=True, key="data_section", label_visibility="collapsed")
    if view == "Biblioteca":
        library()
    elif view == "Catálogo":
        catalogue()
    else:
        import_files()
