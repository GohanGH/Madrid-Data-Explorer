"""Project identity and portable workspace archives."""
from datetime import datetime, timezone

import streamlit as st

from interface import navigate, validate_selection
from loading import loading
from projects import load_project, project_key, save_project
from workspace_state import active_key


def restore_workspace(tables, undo, config, results, details):
    state = st.session_state
    protected = {"tables", "undo", "serial", "project_details", "project_results"}
    for key in list(state):
        if key not in protected:
            del state[key]
    state.update(config)
    state.update(tables=tables, undo=undo, serial=max(tables, default=0), project_results=results, project_details=details)
    state.setdefault("redo_stack", [])
    active_key(state)
    state.project_panel = "Proyecto activo"
    navigate("Mis proyectos")


def archive_controls(tables):
    state = st.session_state
    previous = state.project_details
    if "created" not in previous:
        previous["created"] = datetime.now(timezone.utc).isoformat()
    with st.form("project_identity", border=False):
        name = st.text_input("Nombre", value=previous.get("name", "Proyecto sin título"), max_chars=200, key="project_name")
        question = st.text_input("Pregunta de investigación", value=previous.get("question", ""), max_chars=500, key="project_question")
        description = st.text_area("Descripción", value=previous.get("description", ""), max_chars=3000, key="project_description")
        if st.form_submit_button("Guardar datos del proyecto"):
            previous.update(name=name.strip() or "Proyecto sin título", question=question, description=description)
            state.pop("project_export", None)
            st.success("Identidad del proyecto guardada.")
    st.caption(f"{len(tables)} tablas y versiones · {len(state.project_results)} resultados · {len(previous.get('reports', []))} informes")
    if st.button("Preparar archivo ZIP", key="prepare_zip", type="primary"):
        state.pop("project_export", None)
        try:
            config = {key: value for key, value in state.items() if project_key(key)}
            details = {"name": "Proyecto sin título", "question": "", "description": "", **previous}
            with loading("Preparando copia del proyecto"):
                state.project_export = save_project(tables, state.undo, config, state.project_results, details)
        except (ValueError, TypeError, OverflowError) as exc:
            st.error(str(exc))
    if "project_export" in state:
        st.download_button("Descargar proyecto (ZIP)", state.project_export, "madrid-proyecto.zip",
                           "application/zip", on_click="ignore", key="download_project")


def new_project(tables):
    name = st.text_input("Nombre del proyecto nuevo", value="Proyecto sin título", max_chars=200, key="new_project_name")
    question = st.text_input("Pregunta de investigación (opcional)", max_chars=500, key="new_project_question")
    active = bool(tables or st.session_state.project_results or st.session_state.project_details.get("reports"))
    confirmed = not active or st.checkbox("He guardado mi trabajo y confirmo iniciar un proyecto vacío", key="new_confirm")

    def create():
        details = {"name": name.strip(), "question": question, "description": "",
                   "created": datetime.now(timezone.utc).isoformat()}
        restore_workspace({}, [], {}, [], details)
        navigate("Home")

    st.button("Crear proyecto vacío", key="new_project", type="primary", disabled=not confirmed or not name.strip(), on_click=create)


def open_project(tables):
    state = st.session_state
    uploaded = st.file_uploader("Archivo de proyecto (.zip)", type=["zip"], key="project_import")
    active = bool(tables or state.project_results or state.project_details.get("reports"))
    confirmed = not active or st.checkbox("Confirmo sustituir el proyecto activo", key="project_replace")
    error = state.pop("project_import_error", None)
    if error:
        st.error(error)

    def restore():
        try:
            restored = load_project(uploaded.getvalue())
        except ValueError as exc:
            state.project_import_error = f"No se pudo abrir el proyecto. {exc}"
        else:
            restore_workspace(*restored)

    st.button("Restaurar proyecto", disabled=uploaded is None or not confirmed, type="primary", on_click=restore,
              key="restore_project")


def projects_panel(tables):
    st.title("Mis proyectos")
    panels = ["Proyecto activo", "Nuevo", "Abrir"]
    validate_selection("project_panel", panels)
    panel = st.radio("Gestionar proyecto", panels, horizontal=True, key="project_panel", label_visibility="collapsed")
    if panel == "Proyecto activo":
        archive_controls(tables)
    elif panel == "Nuevo":
        new_project(tables)
    else:
        open_project(tables)
