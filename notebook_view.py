"""Research notebook and printable reports built from saved workspace outputs."""
from functools import partial
from uuid import uuid4

import streamlit as st

from data_tables import csv_export
from interface import navigate
from map_view import export_chart
from projects import MAX_RESULTS, remember_result
from reports import notebook_report
from workspace_controls import choose, choose_many
from workspace_state import active_key, version_warnings, visible_tables

REPORT_SECTIONS = (
    ("Introducción", "introduction"), ("Objetivos", "objectives"), ("Metodología", "methodology"),
    ("Discusión", "discussion"), ("Limitaciones", "limitations"), ("Conclusiones", "conclusions"),
    ("Fuentes adicionales", "sources"),
)


def change_position(entries, index, shift):
    target = index + shift
    if 0 <= target < len(entries):
        entries[index], entries[target] = entries[target], entries[index]


def notebook():
    state = st.session_state
    entries = state.project_results
    items = visible_tables(state)
    with st.container(horizontal=True, gap="small"):
        if items and st.button("Guardar tabla activa", key="notebook_table"):
            key = active_key(state)
            item = items[key]
            try:
                entry = remember_result(state, key, {"análisis": "Tabla de datos"}, item["df"],
                                        f"Versión #{key} · {len(item['df']):,} filas", [], [],
                                        kind="Tabla", title=item["title"])
                state.notebook_focus = entry["id"]
                st.rerun()
            except ValueError as exc:
                st.warning(str(exc))
        st.button("Ir a Análisis", on_click=navigate, args=("Análisis",), key="results_analysis")
        st.button("Ir a Visualización", on_click=navigate, args=("Visualización",), key="results_visual")
    if not entries:
        st.info("Los análisis ejecutados y las visualizaciones que guardes aparecerán aquí.")
        return
    records = {entry["id"]: entry for entry in entries}
    if pending := state.pop("notebook_focus", None):
        state.cfg_notebook_entry = pending
    picked = choose("Resultados guardados en orden de presentación", records, "cfg_notebook_entry",
                    format_func=lambda key: f"{list(records).index(key) + 1}. {records[key]['title']} · {records[key]['kind']}")
    entry = records[picked]
    index = entries.index(entry)
    item = state.tables.get(entry["dataset"], {})
    warnings = version_warnings(state.tables, entry["dataset"])
    if entry.get("snapshot") and entry["snapshot"] != item.get("snapshot"):
        warnings.append("El identificador de la tabla actual difiere del registrado en este resultado.")
    if warnings:
        st.warning("Resultado histórico. " + " ".join(warnings))
    st.subheader(entry["title"])
    st.caption(f"{entry['kind']} · versión #{entry['dataset']} · {entry.get('created') or 'fecha de ejecución sin registrar'}")
    st.write(entry["summary"])
    if entry["annotation"]:
        st.text(entry["annotation"])
    if entry["interpretation"]:
        st.text(entry["interpretation"])
    for number, figure in enumerate(entry["figures"]):
        st.plotly_chart(figure, key=f"notebook_figure_{picked}_{number}", config={"displaylogo": False})
    table = entry["table"]
    if len(table.columns):
        show = table.head(500)
        if "Valor" in show and show["Valor"].dtype == object:
            show = show.assign(Valor=show["Valor"].astype("string"))
        st.dataframe(show, hide_index=True)
        if len(table) > 500:
            st.caption("Vista de 500 filas. La descarga incluye la tabla completa.")
    with st.expander("Metodología y exportación"):
        st.json({"versión": entry["dataset"], "fecha": entry["created"], "parámetros": entry["params"],
                 "fuentes": item.get("sources", []), "transformaciones": item.get("history", []),
                 "metadatos": item.get("metadata", {})}, expanded=False)
        for note in entry["notes"]:
            st.caption(note)
        if len(table.columns):
            st.download_button("Descargar datos (CSV)", lambda: csv_export(table), "resultado.csv", "text/csv",
                               key=f"notebook_csv_{picked}", on_click="ignore")
        for number, figure in enumerate(entry["figures"]):
            export_chart(figure, f"notebook_{picked}_{number}", label=f"Descargar figura {number + 1} (HTML)")
    with st.expander("Anotar y organizar"):
        with st.form(f"annotation_{picked}", border=False):
            name = st.text_input("Nombre del resultado", value=entry["title"], max_chars=200)
            annotation = st.text_area("Anotación", value=entry["annotation"], max_chars=3000)
            interpretation = st.text_area("Interpretación", value=entry["interpretation"], max_chars=5000)
            if st.form_submit_button("Guardar anotaciones", type="primary"):
                entry.update(title=name.strip() or entry["title"], annotation=annotation, interpretation=interpretation)
                st.rerun()
        with st.container(horizontal=True, gap="small"):
            st.button("Subir", icon=":material/arrow_upward:", key="notebook_up", disabled=index == 0,
                      on_click=change_position, args=(entries, index, -1))
            st.button("Bajar", icon=":material/arrow_downward:", key="notebook_down", disabled=index == len(entries) - 1,
                      on_click=change_position, args=(entries, index, 1))
            if st.button("Duplicar resultado", key="duplicate_result", disabled=len(entries) >= MAX_RESULTS):
                copy = {**entry, "id": uuid4().hex, "title": f"{entry['title']} · copia"}
                entries.insert(index + 1, copy)
                state.notebook_focus = copy["id"]
                st.rerun()
        confirmed = st.checkbox("Confirmo eliminar el resultado guardado", key=f"confirm_result_{picked}")
        if st.button("Eliminar resultado", key="delete_result", disabled=not confirmed):
            entries.pop(index)
            st.rerun()


def report_editor():
    state = st.session_state
    project = state.project_details
    drafts = project.setdefault("reports", [])
    entries = {entry["id"]: entry for entry in state.project_results}
    lookup = {draft["id"]: draft for draft in drafts}
    if pending := state.pop("report_focus", None):
        state.cfg_report_picker = pending
    chosen = choose("Informe", [None, *lookup], "cfg_report_picker",
                    format_func=lambda key: lookup[key]["title"] if key else "Nuevo informe")
    previous = lookup.get(chosen, {})
    key = chosen or "new"
    with st.form(f"report_{key}", border=False):
        title = st.text_input("Título del informe", value=previous.get("title") or project.get("name", "Informe de investigación"),
                              max_chars=200, key=f"report_title_{key}")
        if project.get("question"):
            st.text(project["question"])
        else:
            st.caption("La pregunta que llevará el encabezado se define en Mis proyectos.")
        selected = choose_many("Resultados en orden de presentación", entries, f"report_entries_{key}",
                               default=[i for i in previous.get("entries", []) if i in entries],
                               format_func=lambda i: entries[i]["title"])
        content = {}
        with st.expander("Secciones del informe", expanded=True):
            for label, field in REPORT_SECTIONS:
                content[field] = st.text_area(label, value=previous.get(field, ""), max_chars=6000,
                                              key=f"report_{key}_{field}")
        save = st.form_submit_button("Guardar borrador", type="primary")
    if save:
        if not chosen and len(drafts) >= 12:
            st.warning("Se pueden guardar hasta doce borradores en un proyecto.")
        else:
            record = {"id": chosen or uuid4().hex, "title": title.strip() or "Informe de investigación", "entries": selected,
                      **content}
            if chosen:
                previous.update(record)
            else:
                drafts.append(record)
                state.report_focus = record["id"]
            st.rerun()
    if chosen:
        if any(ref not in entries for ref in previous["entries"]):
            st.warning("El borrador referencia resultados retirados. Revisa su selección antes de descargar.")
        st.caption("Puedes guardar una copia PDF desde Imprimir en el navegador.")
        # Deferred downloads run on a worker without Streamlit's session context.
        tables = {i: dict(item) for i, item in state.tables.items()}
        render = partial(notebook_report, dict(previous), dict(project), [dict(entry) for entry in entries.values()], tables)
        st.download_button("Descargar informe HTML", render, "madrid-informe.html", "text/html",
            key=f"export_report_{key}", on_click="ignore")
        with st.expander("Administrar borrador"):
            confirmed = st.checkbox("Confirmo eliminar este borrador", key=f"discard_report_{key}")
            if st.button("Eliminar borrador", disabled=not confirmed, key=f"delete_report_{key}"):
                drafts.remove(previous)
                st.rerun()


def results_screen():
    st.title("Resultados")
    selected = st.radio("Espacio de resultados", ["Cuaderno", "Informes"], horizontal=True, key="cfg_results_section",
                        label_visibility="collapsed")
    if selected == "Cuaderno":
        notebook()
    else:
        report_editor()
