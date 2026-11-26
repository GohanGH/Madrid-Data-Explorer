"""Punto de entrada del espacio de investigación de Madrid Data Explorer."""
import streamlit as st

from analysis_workspace import analysis_screen
from library_view import data_screen
from notebook_view import results_screen
from preparation_view import preparation_screen
from project_view import projects_panel
from visualization_view import visual_screen
from workspace_state import initialize
from workspace_views import home_screen, navigation

st.set_page_config(page_title="Madrid Data Explorer", page_icon=":material/analytics:",
                   layout="wide", initial_sidebar_state="auto")

initialize(st.session_state)
page = navigation()
if page != "Mis proyectos":
    st.session_state.pop("project_export", None)

views = {
    "Home": home_screen,
    "Datos": data_screen,
    "Preparación": preparation_screen,
    "Análisis": analysis_screen,
    "Visualización": visual_screen,
    "Resultados": results_screen,
    "Mis proyectos": lambda: projects_panel(st.session_state.tables),
}
views[page]()
