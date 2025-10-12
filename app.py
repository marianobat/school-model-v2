# app.py — versión con gráficos responsivos (Streamlit + Altair)
# Requiere en requirements.txt: streamlit, numpy, pandas, altair

import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
from model.simulate import Params, simulate

st.set_page_config(page_title="School SD Simulator", layout="wide")
st.title("Modelo de Dinámica de Sistemas — Colegio")

# ============ Helpers UI ============
def sidebar_basic(p: Params):
    st.sidebar.header("Básicos")
    p.years = st.sidebar.slider("Años de simulación", 5, 30, p.years)
    p.demanda_potencial = st.sidebar.number_input("Demanda potencial (alumnos)", 100, 100000, p.demanda_potencial, 100)
    p.calidad_base = st.sidebar.slider("Calidad base", 0.0, 1.0, p.calidad_base, 0.01)
    p.beta_hacinamiento = st.sidebar.slider("β hacinamiento → calidad", 0.0, 2.0, p.beta_hacinamiento, 0.05)
    p.tasa_egreso_base = st.sidebar.slider("Tasa egreso base (/año)", 0.0, 0.3, p.tasa_egreso_base, 0.01)
    p.gamma_hacinamiento = st.sidebar.slider("γ hacinamiento → egreso", 0.0, 0.5, p.gamma_hacinamiento, 0.01)
    p.tasa_bajas_imprevistas = st.sidebar.slider("Tasa bajas imprevistas (/año)", 0.0, 0.2, p.tasa_bajas_imprevistas, 0.005)
    p.tasa_bajas_max_por_calidad = st.sidebar.slider("Tasa máx. bajas por mala calidad (/año)", 0.0, 0.5, p.tasa_bajas_max_por_calidad, 0.01)

    st.sidebar.header("Capacidad")
    p.div_inicial_por_grado = st.sidebar.number_input("Divisiones por grado (inicial)", 1, 8, p.div_inicial_por_grado)
    p.cupo_optimo = st.sidebar.number_input("Cupo óptimo por aula", 10, 50, p.cupo_optimo)

    st.sidebar.header("Finanzas")
    p.cuota_mensual = st.sidebar.number_input("Cuota mensual ($/est/mes)", 0.0, 10000.0, p.cuota_mensual, 10.0)
    p.meses = st.sidebar.number_input("Meses facturados", 1, 12, p.meses)
    p.costo_fijo_anual = st.sidebar.number_input("Costo fijo anual ($)", 0.0, 50_000_000.0, p.costo_fijo_anual, 10_000.0)
    p.costo_variable_alumno = st.sidebar.number_input("Costo variable por alumno ($/año)", 0.0, 50_000.0, p.costo_variable_alumno, 10.0)
    p.costo_docente_por_aula = st.sidebar.number_input("Costo docente por aula ($/año)", 0.0, 1_000_000.0, p.costo_docente_por_aula, 1_000.0)

    st.sidebar.header("Iniciales")
    p.g_inicial = st.sidebar.number_input("Alumnos por grado (inicial)", 0, 60, p.g_inicial)

def sidebar_marketing(p: Params):
    st.sidebar.header("Marketing & Captación")
    p.prop_mkt = st.sidebar.slider("Proporción de resultado a marketing", 0.0, 0.5, p.prop_mkt, 0.01)
    p.mkt_floor = st.sidebar.number_input("Piso anual de marketing ($)", 0.0, 2_000_000.0, p.mkt_floor, 1_000.0)
    p.cac_base = st.sidebar.number_input("CAC base ($/candidato)", 1.0, 100_000.0, p.cac_base, 10.0)
    p.k_saturacion = st.sidebar.slider("Sensibilidad CAC a saturación", 0.0, 5.0, p.k_saturacion, 0.1)

def sidebar_politicas(p: Params):
    st.sidebar.header("Políticas de expansión (pipeline 12 años)")
    p.pipeline_activo = st.sidebar.checkbox("Activar pipeline manual", value=p.pipeline_activo)
    p.pipeline_auto_por_hacinamiento = st.sidebar.checkbox("Auto por hacinamiento en 1º", value=p.pipeline_auto_por_hacinamiento)
    p.umbral_hacinamiento_g1 = st.sidebar.slider("Umbral de hacinamiento en 1º", 0.0, 0.5, p.umbral_hacinamiento_g1, 0.01)
    p.pipeline_financiacion_externa = st.sidebar.checkbox("Permitir financiación externa", value=p.pipeline_financiacion_externa)
    p.capex_pct_sobre_facturacion = st.sidebar.slider("% CAPEX sobre facturación (límite)", 0.0, 1.0, p.capex_pct_sobre_facturacion, 0.05)
    p.colchon_financiero = st.sidebar.number_input("Colchón financiero ($)", 0.0, 10_000_000.0, p.colchon_financiero, 10_000.0)
    p.costo_construccion_aula = st.sidebar.number_input("Costo construcción por aula ($)", 0.0, 5_000_000.0, p.costo_construccion_aula, 10_000.0)

def fold_df(df: pd.DataFrame, cols: list[str], xcol: str = "Año") -> pd.DataFrame:
    """Convierte varias columnas en formato long para Altair."""
    out = df[[xcol] + cols].melt(id_vars=[xcol], value_vars=cols, var_name="serie", value_name="valor")
    return out

# ============ Estado inicial ============
if "params" not in st.session_state:
    st.session_state.params = Params()

# ============ Tabs ============
tab_inicio, tab_sim, tab_mkt, tab_coh, tab_polit, tab_export = st.tabs(
    ["🏠 Inicio", "📊 Simulación", "📣 Marketing & Captación", "📚 Cohortes (1–12)", "⚙️ Políticas de expansión", "📥 Exportar"]
)

# ============ Inicio ============
with tab_inicio:
    st.markdown("""
**Propósito pedagógico:** visualizar cómo decisiones (calidad, marketing, inversión en aulas) generan **loops** de refuerzo y balanceo, y su impacto en matrícula, capacidad y finanzas.

**Loops clave:**  
- **R1** Reputación/atracción (Calidad ↑ → Ingresantes ↑ → Alumnos ↑)  
- **R2** Marketing endógeno (Resultado ↑ → BudgetMkt ↑ → Candidatos ↑)  
- **R3** Expansión/pipeline (Aulas ↑ → Capacidad ↑ → Hacinamiento ↓ → Calidad ↑)  
- **B1** Saturación de mercado (Gap ↓)  
- **B2** Hacinamiento (Calidad ↓, Bajas ↑)  
- **B3** CAC creciente (Saturación ↑ → CAC ↑)  
    """)

# ============ Simulación ============
with tab_sim:
    sidebar_basic(st.session_state.params)
    p = st.session_state.params
    df, meta = simulate(p)

    # Métricas
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Alumnos (0 → fin)", f"{int(df['AlumnosTotales'].iloc[0])} → {int(df['AlumnosTotales'].iloc[-1])}")
    with c2:
        st.metric("Capacidad (fin)", f"{int(df['AulasTotales'].iloc[-1] * p.cupo_optimo)}")
    with c3:
        st.metric("Resultado Neto (fin)", f"${df['ResultadoNeto'].iloc[-1]:,.0f}")

    # Gráficos
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Alumnos")
        st.line_chart(df, x="Año", y="AlumnosTotales", use_container_width=True)

        st.subheader("Calidad percibida")
        st.line_chart(df, x="Año", y="Calidad", use_container_width=True)

    with col2:
        st.subheader("Alumnos vs Capacidad")
        df_cap = df.copy()
        df_cap["Capacidad"] = df_cap["AulasTotales"] * p.cupo_optimo
        folded_ac = fold_df(df_cap, ["AlumnosTotales", "Capacidad"])
        chart_ac = alt.Chart(folded_ac, title="Alumnos vs Capacidad").mark_line().encode(
            x=alt.X("Año:Q"),
            y=alt.Y("valor:Q", title="Cantidad"),
            color=alt.Color("serie:N", title=""),
            tooltip=["Año","serie","valor"]
        ).interactive()
        st.altair_chart(chart_ac, use_container_width=True)

        st.subheader("Finanzas OPEX")
        folded_fin = fold_df(df, ["Facturacion", "CostosOPEX"])
        chart_fin = alt.Chart(folded_fin, title="Facturación vs Costos").mark_line().encode(
            x="Año:Q", y=alt.Y("valor:Q", title="$ por año"),
            color=alt.Color("serie:N", title=""),
            tooltip=["Año","serie","valor"]
        ).interactive()
        st.altair_chart(chart_fin, use_container_width=True)

    st.divider()
    st.caption("Primeros años")
    st.dataframe(df.head(20), use_container_width=True)

# ============ Marketing & Captación ============
with tab_mkt:
    sidebar_marketing(st.session_state.params)
    p = st.session_state.params
    df, _ = simulate(p)

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Presupuesto de Marketing")
        st.line_chart(df, x="Año", y="BudgetMkt", use_container_width=True)

        st.subheader("Costo de Adquisición (CAC)")
        st.line_chart(df, x="Año", y="CAC", use_container_width=True)

    with col2:
        st.subheader("Candidatos vs Ingresantes (G1)")
        folded_ci = fold_df(df, ["Candidatos", "Ingresantes_G1"])
        chart_ci = alt.Chart(folded_ci, title="Funnel de captación").mark_line().encode(
            x="Año:Q", y=alt.Y("valor:Q", title="Personas"),
            color=alt.Color("serie:N", title=""),
            tooltip=["Año","serie","valor"]
        ).interactive()
        st.altair_chart(chart_ci, use_container_width=True)

        st.subheader("Calidad (para conversión)")
        st.line_chart(df, x="Año", y="Calidad", use_container_width=True)

# ============ Cohortes (1–12) ============
with tab_coh:
    p = st.session_state.params
    df, _ = simulate(p)

    st.subheader("Alumnos por grado (G1..G12)")
    g_cols = [f"G{i}" for i in range(1, 13)]
    df_g = df[["Año"] + g_cols].copy()
    # Heatmap (Altair)
    heat_data = df_g.melt(id_vars=["Año"], var_name="Grado", value_name="Alumnos")
    heat = alt.Chart(heat_data, title="Heatmap de alumnos por grado y año").mark_rect().encode(
        x=alt.X("Año:O", sort="ascending"),
        y=alt.Y("Grado:O", sort=g_cols),
        color=alt.Color("Alumnos:Q", scale=alt.Scale(scheme="blues")),
        tooltip=["Año","Grado","Alumnos"]
    ).properties(height=320)
    st.altair_chart(heat, use_container_width=True)

    st.caption("Tabla (primeros años)")
    st.dataframe(df_g.head(20), use_container_width=True)

# ============ Políticas de expansión ============
with tab_polit:
    sidebar_politicas(st.session_state.params)
    p = st.session_state.params
    df, _ = simulate(p)

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Aulas (stock) y pipeline")
        st.line_chart(df, x="Año", y="AulasTotales", use_container_width=True)
        # Construcciones por año (barras)
        bar = alt.Chart(df, title="Construcciones por año (pipeline)").mark_bar().encode(
            x="Año:Q", y=alt.Y("PipelineConstrucciones:Q", title="Aulas"),
            tooltip=["Año","PipelineConstrucciones"]
        )
        st.altair_chart(bar, use_container_width=True)

    with col2:
        st.subheader("Resultados")
        folded_res = fold_df(df, ["ResultadoOperativo", "ResultadoNeto"])
        chart_res = alt.Chart(folded_res, title="Resultado operativo vs neto").mark_line().encode(
            x="Año:Q", y=alt.Y("valor:Q", title="$ por año"),
            color=alt.Color("serie:N", title=""),
            tooltip=["Año","serie","valor"]
        ).interactive()
        st.altair_chart(chart_res, use_container_width=True)

        st.subheader("Alumnos vs Capacidad")
        df2 = df.copy()
        df2["Capacidad"] = df2["AulasTotales"] * p.cupo_optimo
        folded2 = fold_df(df2, ["AlumnosTotales", "Capacidad"])
        chart2 = alt.Chart(folded2).mark_line().encode(
            x="Año:Q", y=alt.Y("valor:Q", title="Cantidad"),
            color=alt.Color("serie:N", title=""),
            tooltip=["Año","serie","valor"]
        ).interactive()
        st.altair_chart(chart2, use_container_width=True)

# ============ Exportar ============
with tab_export:
    p = st.session_state.params
    df, meta = simulate(p)
    st.download_button(
        "Descargar CSV de resultados",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name="resultados_simulacion.csv",
        mime="text/csv",
        use_container_width=True
    )
    st.download_button(
        "Descargar preset (.json) de parámetros",
        data=pd.Series(meta["params"]).to_json().encode("utf-8"),
        file_name="preset_params.json",
        mime="application/json",
        use_container_width=True
    )
    with st.expander("Parámetros actuales"):
        st.json(meta["params"])
