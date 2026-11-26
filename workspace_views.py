"""Shared project navigation and controls."""
from html import escape
from pathlib import Path

import streamlit as st

from interface import navigate, validate_selection
from projects import project_key
from workspace_state import active_key, table_kind, visible_tables

PAGES = {
    "Home": ":material/home:",
    "Datos": ":material/database:",
    "Preparación": ":material/tune:",
    "Análisis": ":material/analytics:",
    "Visualización": ":material/monitoring:",
    "Resultados": ":material/assignment:",
    "Mis proyectos": ":material/folder_open:",
}
STYLE = Path(__file__).resolve().parent / "workspace.css"


def go_to_data(section, query=None, *, mode=None):
    st.session_state.data_section = section
    if query is not None:
        st.session_state.catalog_keyword = query
        st.session_state.catalog_mode = mode or "Palabras clave"
        st.session_state.catalog_request = (query, mode or "Palabras clave", {}, 0)
        st.session_state.pop("catalog_preview", None)
    navigate("Datos")


def focus_table(key, page=None):
    st.session_state.active_table = key
    if page:
        if page == "Datos":
            st.session_state.data_section = "Biblioteca"
        navigate(page)


def table_choice(label, key, items, default=None):
    available = list(items)
    validate_selection(key, available)
    index = available.index(default) if default in available else 0
    return st.selectbox(label, available, index=index, key=key,
                        format_func=lambda entry: f"{items[entry]['title']} · #{entry}")


def navigation():
    state = st.session_state
    for key in list(state):
        if project_key(key) or key in {"data_section", "catalog_mode", "catalog_keyword", "catalog_scope", "catalog_year"}:
            state[key] = state[key]
    current = state.setdefault("page", "Home")
    if current not in PAGES:
        current = "Home"
        navigate(current)
    if current != "Mis proyectos":
        state.pop("project_export", None)
    st.html(STYLE)
    with st.sidebar:
        st.html('<div class="mde-brand"><span class="mde-monogram">M</span>'
                '<div>Madrid<span>Data Explorer</span></div></div>')
        with st.container(key="mde_navigation"):
            for page, icon in PAGES.items():
                st.button(page, icon=icon, type="primary" if current == page else "tertiary",
                          key=f"nav_{page}", on_click=navigate, args=(page,), width="stretch")
        title = state["project_details"].get("name", "") or "Proyecto sin título"
        st.markdown("**Proyecto activo**")
        st.text(title)
        tables = visible_tables(state)
        if tables:
            active = active_key(state)
            key = "library_active_widget"
            if state.get(key) != active:
                state[key] = active

            def select_table():
                focus_table(state[key])

            st.selectbox("Tabla activa", list(tables), key=key, on_change=select_table,
                         format_func=lambda i: f"{tables[i]['title']} · #{i}")
            st.caption(f"{table_kind(tables[active])} · {len(tables[active]['df']):,} filas")
        else:
            st.caption("Biblioteca vacía")
        st.button("Importar datos", icon=":material/add:", key="sidebar_import", type="tertiary",
                  on_click=go_to_data, args=("Importar",), width="stretch")
    if current != "Home":
        with st.container(horizontal=True, horizontal_alignment="distribute", vertical_alignment="center",
                          key="mde_context"):
            st.text(title)
            st.button("Home", icon=":material/home:", key="return_home", on_click=navigate, args=("Home",), type="tertiary")
    return current


TOPICS = (
    ("Demografía", "groups", "población empadronada"),
    ("Economía", "payments", "renta municipal"),
    ("Medio ambiente", "air", "calidad del aire"),
    ("Salud", "health_and_safety", "centros sanitarios"),
    ("Empleo", "work", "paro registrado"),
    ("Educación", "school", "nivel educativo"),
    ("Transporte", "directions_bus", "transporte público"),
    ("Vivienda", "apartment", "vivienda alquiler"),
    ("Cultura", "local_library", "bibliotecas públicas"),
    ("Seguridad", "shield", "seguridad ciudadana"),
)


def go_to_projects(section):
    st.session_state.project_panel = section
    navigate("Mis proyectos")


def home_screen():
    st.html("""
        <section class="mde-home">
            <h1>Investiga Madrid<br>con sus datos abiertos.</h1>
            <p>Encuentra fuentes, construye tus tablas y responde tus propias preguntas.</p>
        </section>
    """)
    with st.form("home_search", border=False):
        query = st.text_input("Busca en el catálogo oficial", key="home_query",
                              placeholder="Visitas a bibliotecas por municipio", max_chars=350)
        searched = st.form_submit_button("Buscar datos", type="primary", icon=":material/search:")
    if searched:
        go_to_data("Catálogo", query.strip(), mode="Lenguaje natural")
        st.rerun()
    with st.container(horizontal=True, gap="small", key="home_actions"):
        st.button("Nuevo proyecto", icon=":material/create_new_folder:", key="home_new",
                  on_click=go_to_projects, args=("Nuevo",))
        st.button("Abrir proyecto", icon=":material/folder_open:", key="home_open",
                  on_click=go_to_projects, args=("Abrir",))
        st.button("Importar archivo", icon=":material/upload_file:", key="home_import",
                  on_click=go_to_data, args=("Importar",))
        st.button("Ver catálogo", icon=":material/arrow_outward:", key="home_catalog",
                  on_click=go_to_data, args=("Catálogo", ""))
    left, right = st.columns([3, 2], gap="large")
    with left:
        st.subheader("Explorar por tema")
        with st.container(horizontal=True, gap="small", key="home_topics"):
            for label, icon, term in TOPICS:
                st.button(label, icon=f":material/{icon}:", key=f"topic_{label}",
                          on_click=go_to_data, args=("Catálogo", term))
    with right:
        state = st.session_state
        project = state["project_details"]
        tables = visible_tables(state)
        title = escape(project.get("name") or "Proyecto sin título")
        st.html(f'<section class="mde-project"><p>Proyecto activo</p><h2>{title}</h2></section>')
        if project.get("question"):
            st.text(project["question"])
        st.caption(f"{len(tables)} tablas activas · {len(state['project_results'])} resultados guardados")
        if tables:
            st.button("Abrir biblioteca", key="library_home", on_click=go_to_data, args=("Biblioteca",))
