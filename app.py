from __future__ import annotations

import io
import os
import pandas as pd
import plotly.express as px
import streamlit as st

from catalog import search_catalog, compatible_resources, download_table, describe_table
from assistant import ask_ai, numeric_summary
from joins import join_preview

st.set_page_config(page_title="Madrid Data Explorer", page_icon="📊", layout="wide")
st.title("Madrid Data Explorer")
st.caption("Explora y analiza datos abiertos de la Comunidad de Madrid · Prototipo DATAMAD 2026")

with st.sidebar:
    st.header("Configuración")
    st.info("Fuente: API oficial de datos.comunidad.madrid. Los datos no están almacenados en esta app.")
    model = st.text_input("Modelo OpenAI", value="gpt-4.1-mini", help="Debe estar disponible para tu cuenta API.")
    api_key = os.getenv("OPENAI_API_KEY", "")
    try:
        api_key = st.secrets.get("OPENAI_API_KEY", api_key)
    except (FileNotFoundError, KeyError):
        pass
    st.caption("IA " + ("activada ✓" if api_key else "no configurada; el análisis manual sigue disponible"))
    st.warning("Los conjuntos de datos tienen coberturas y frecuencias diferentes. Un cruce no implica causalidad.")

st.session_state.setdefault("tables", {})
tab_search, tab_join, tab_analysis, tab_chat = st.tabs(
    ["🔎 Buscar datos", "🔗 Combinar datasets", "📈 Analizar", "💬 Consultar con IA"])

with tab_search:
    with st.form("busqueda"):
        query = st.text_input("Tema o palabra clave", value="salud",
                              placeholder="hospitales, población, calidad del aire...")
        submitted = st.form_submit_button("Buscar en el catálogo", type="primary")
    if submitted:
        with st.spinner("Consultando el catálogo oficial..."):
            try:
                count, datasets = search_catalog(query)
                st.session_state.datasets = datasets
                st.session_state.query = query
                st.session_state.count = count
            except Exception as exc:
                st.error(f"No se pudo acceder al catálogo: {exc}")
    datasets = st.session_state.get("datasets", [])
    if datasets:
        st.success(f"{st.session_state.get('count', len(datasets))} resultados en el catálogo. Se muestran hasta {len(datasets)}.")
        options = list(range(len(datasets)))
        index = st.selectbox("Selecciona un conjunto de datos", options,
                             format_func=lambda i: datasets[i].get("title", "Sin título"))
        ds = datasets[index]
        st.write(ds.get("notes") or "Sin descripción disponible.")
        st.caption(f"Identificador: {ds.get('name', 'desconocido')}")
        resources = compatible_resources(ds)
        if resources:
            ri = st.selectbox("Recurso para analizar", range(len(resources)),
                              format_func=lambda i: f"{resources[i].get('name') or 'Recurso'} · {resources[i].get('format')}")
            resource = resources[ri]
            st.link_button("Ver recurso original", resource["url"])
            if st.button("Cargar tabla", type="primary"):
                with st.spinner("Descargando y leyendo el recurso..."):
                    try:
                        df = download_table(resource)
                        if df.empty:
                            st.warning("El recurso está vacío.")
                        else:
                            name = ds.get("title", "Dataset")
                            key = f"{ds.get('name', 'dataset')} · {resource.get('name') or resource.get('id', 'recurso')}"
                            if key not in st.session_state.tables and len(st.session_state.tables) >= 8:
                                raise ValueError("Máximo 8 tablas cargadas. Elimina una desde Combinar datasets.")
                            st.session_state.tables[key] = {
                                "df": df, "title": name, "source": resource["url"]}
                            st.session_state.active_table = key
                            st.session_state.messages = []
                            st.success(f"Cargadas {len(df):,} filas y {len(df.columns)} columnas. "
                                       "Puedes cargar otro dataset o abrir Combinar datasets.")
                    except Exception as exc:
                        st.error(f"No se pudo cargar: {exc}")
        else:
            st.warning("Este dataset no ofrece un recurso CSV, JSON o Excel compatible por HTTPS.")
    elif submitted:
        st.info("No se encontraron resultados.")

with tab_join:
    tables = st.session_state.tables
    st.subheader("Tablas disponibles")
    if tables:
        st.dataframe(pd.DataFrame([
            {"Tabla": k, "Filas": len(v["df"]), "Columnas": len(v["df"].columns), "Fuente": v["source"]}
            for k, v in tables.items()]), use_container_width=True)
        remove = st.selectbox("Eliminar tabla de la sesión", list(tables), key="remove_table")
        if st.button("Eliminar tabla seleccionada"):
            del tables[remove]
            if st.session_state.get("active_table") == remove:
                st.session_state.active_table = next(iter(tables), None)
            st.rerun()
    else:
        st.info("Carga al menos dos recursos desde Buscar datos.")

    if len(tables) >= 2:
        names = list(tables)
        left_name = st.selectbox("Tabla A", names, key="join_left")
        right_name = st.selectbox("Tabla B", [n for n in names if n != left_name], key="join_right")
        left = tables[left_name]["df"]
        right = tables[right_name]["df"]
        ca, cb = st.columns(2)
        with ca:
            left_key = st.multiselect("Clave(s) de A en orden", list(left.columns),
                                      default=[left.columns[0]], key="join_left_key")
        with cb:
            right_key = st.multiselect("Clave(s) de B en el mismo orden", list(right.columns),
                                       default=[right.columns[0]], key="join_right_key")
        how = st.selectbox("Tipo de unión", ["inner", "left", "outer", "right"],
                           format_func=lambda x: {"inner": "Inner: coincidencias", "left": "Left: conservar A",
                                                  "outer": "Full: conservar ambas", "right": "Right: conservar B"}[x])
        st.warning("Comprueba que ambas claves representan la misma entidad y periodo. "
                   "Para datos longitudinales, selecciona claves compuestas, por ejemplo municipio Y año. "
                   "El orden de las columnas seleccionadas debe coincidir entre A y B.")
        if st.button("Ejecutar unión", type="primary"):
            try:
                merged, info = join_preview(left, right, left_key, right_key, how)
                new_name = f"UNIÓN {left_name[:24]} + {right_name[:24]} ({how})"
                if new_name not in tables and len(tables) >= 8:
                    raise ValueError("Límite de 8 tablas; elimina una antes de guardar la unión.")
                tables[new_name] = {"df": merged, "title": new_name,
                                    "source": tables[left_name]["source"] + " | " + tables[right_name]["source"]}
                st.session_state.active_table = new_name
                st.session_state.join_info = info
                st.session_state.messages = []
                st.success("Unión creada. Puedes usarla para otro cruce o analizarla.")
            except Exception as exc:
                st.error(f"No se pudo unir: {exc}")
        if "join_info" in st.session_state:
            st.write("Diagnóstico de la última unión:")
            st.json(st.session_state.join_info)

with tab_analysis:
    tables = st.session_state.tables
    if not tables:
        st.info("Busca y carga primero un recurso en la pestaña Buscar datos.")
    else:
        active = st.selectbox("Tabla para analizar", list(tables),
                              index=list(tables).index(st.session_state.active_table)
                              if st.session_state.get("active_table") in tables else 0,
                              key="analysis_active")
        st.session_state.active_table = active
        df = tables[active]["df"]
        st.subheader(tables[active]["title"])
        st.caption("Fuentes: " + tables[active]["source"])
        overview = describe_table(df)
        a, b, c = st.columns(3)
        a.metric("Filas", f"{overview['filas']:,}")
        b.metric("Columnas", overview["columnas"])
        c.metric("Celdas vacías", f"{int(df.isna().sum().sum()):,}")
        st.dataframe(df.head(500), use_container_width=True)
        with st.expander("Tipos de variables y valores faltantes"):
            st.dataframe(pd.DataFrame(overview["variables"]), use_container_width=True)
        st.subheader("Estadísticas descriptivas")
        st.code(numeric_summary(df), language="text")
        numeric_cols = df.select_dtypes(include="number").columns.tolist()
        if numeric_cols:
            metric = st.selectbox("Variable numérica", numeric_cols)
            kind = st.radio("Tipo de gráfico", ["Histograma", "Media por grupo"], horizontal=True)
            if kind == "Histograma":
                fig = px.histogram(df, x=metric, nbins=35, title=f"Distribución de {metric}")
                st.plotly_chart(fig, use_container_width=True)
            else:
                group = st.selectbox("Agrupar por", [str(c) for c in df.columns if str(c) != metric])
                subset = df[[group, metric]].dropna()
                if subset[group].nunique() > 100:
                    st.warning("Más de 100 grupos: se muestran los 30 primeros por media.")
                summary = (subset.groupby(group, dropna=False)[metric].agg(["mean", "count"])
                           .sort_values("mean", ascending=False).head(30).reset_index())
                st.dataframe(summary, use_container_width=True)
                st.plotly_chart(px.bar(summary, x=group, y="mean", title=f"Media de {metric} por {group}"),
                                use_container_width=True)
        csv = df.to_csv(index=False).encode("utf-8-sig")
        st.download_button("Descargar tabla en CSV", data=csv, file_name="madrid_datos.csv", mime="text/csv")

with tab_chat:
    tables = st.session_state.tables
    active = st.session_state.get("active_table")
    if active not in tables:
        st.info("Para consultar con IA, primero carga una tabla desde Buscar datos.")
    else:
        df = tables[active]["df"]
        st.caption("La IA recibe nombres de columnas, cinco filas de ejemplo y estadísticas agregadas. No ejecuta código.")
        if not api_key:
            st.warning("Configura OPENAI_API_KEY en los secretos del servidor para activar el chat.")
        for message in st.session_state.get("messages", []):
            with st.chat_message(message["role"]):
                st.write(message["content"])
        question = st.chat_input("¿Qué podemos concluir sobre los datos cargados?", disabled=not bool(api_key))
        if question:
            st.session_state.setdefault("messages", []).append({"role": "user", "content": question})
            with st.chat_message("user"):
                st.write(question)
            with st.chat_message("assistant"):
                with st.spinner("Interpretando los datos..."):
                    try:
                        from openai import OpenAI
                        answer = ask_ai(OpenAI(api_key=api_key), model, question,
                                        tables[active]["title"], df, numeric_summary(df))
                    except Exception as exc:
                        answer = f"No se pudo completar la consulta a la IA: {exc}"
                    st.write(answer)
                    st.caption("Fuentes: " + tables[active]["source"])
                    st.session_state.messages.append({"role": "assistant", "content": answer})
