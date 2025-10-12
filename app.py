import streamlit as st
import pandas as pd
from model.simulate import Params, simulate
from ui.charts import line_plot, dual_plot

st.set_page_config(page_title="School SD Simulator", layout="wide")
st.title("Modelo de Dinámica de Sistemas — Colegio (MVP)")

tabs = st.tabs(["🏠 Inicio","📊 Simulación","📣 Marketing & Captación","📚 Cohortes (1–12)","⚙️ Políticas de expansión","📥 Exportar"])

if "params" not in st.session_state:
    st.session_state.params = Params()

def sidebar_basic():
    p = st.session_state.params
    st.sidebar.header("Básicos")
    p.years = st.sidebar.slider("Años", 5, 30, p.years)
    p.demanda_potencial = st.sidebar.number_input("Demanda potencial", 100, 100000, p.demanda_potencial, 100)
    p.calidad_base = st.sidebar.slider("Calidad base", 0.0, 1.0, p.calidad_base, 0.01)
    p.beta_hacinamiento = st.sidebar.slider("β hacinamiento→calidad", 0.0, 2.0, p.beta_hacinamiento, 0.05)
    p.tasa_egreso_base = st.sidebar.slider("Tasa egreso base", 0.0, 0.3, p.tasa_egreso_base, 0.01)
    p.gamma_hacinamiento = st.sidebar.slider("γ hacinamiento→egreso", 0.0, 0.5, p.gamma_hacinamiento, 0.01)
    p.tasa_bajas_imprevistas = st.sidebar.slider("Tasa bajas imprevistas", 0.0, 0.2, p.tasa_bajas_imprevistas, 0.005)
    p.tasa_bajas_max_por_calidad = st.sidebar.slider("Tasa máx. bajas por mala calidad", 0.0, 0.5, p.tasa_bajas_max_por_calidad, 0.01)
    st.sidebar.header("Capacidad")
    p.div_inicial_por_grado = st.sidebar.number_input("Divisiones por grado", 1, 8, p.div_inicial_por_grado)
    p.cupo_optimo = st.sidebar.number_input("Cupo óptimo por aula", 10, 50, p.cupo_optimo)
    st.sidebar.header("Finanzas")
    p.cuota_mensual = st.sidebar.number_input("Cuota mensual", 0.0, 10000.0, p.cuota_mensual, 10.0)
    p.meses = st.sidebar.number_input("Meses", 1, 12, p.meses)
    p.costo_fijo_anual = st.sidebar.number_input("Costo fijo anual", 0.0, 50000000.0, p.costo_fijo_anual, 10000.0)
    p.costo_variable_alumno = st.sidebar.number_input("Costo variable/alumno", 0.0, 50000.0, p.costo_variable_alumno, 10.0)
    p.costo_docente_por_aula = st.sidebar.number_input("Costo docente/aula", 0.0, 1000000.0, p.costo_docente_por_aula, 1000.0)
    st.sidebar.header("Iniciales")
    p.g_inicial = st.sidebar.number_input("Alumnos por grado (inicial)", 0, 60, p.g_inicial)

def sidebar_marketing():
    p = st.session_state.params
    st.sidebar.header("Marketing")
    p.prop_mkt = st.sidebar.slider("Prop. resultado a marketing", 0.0, 0.5, p.prop_mkt, 0.01)
    p.mkt_floor = st.sidebar.number_input("Piso marketing", 0.0, 2000000.0, p.mkt_floor, 1000.0)
    p.cac_base = st.sidebar.number_input("CAC base", 1.0, 100000.0, p.cac_base, 10.0)
    p.k_saturacion = st.sidebar.slider("Sens. CAC a saturación", 0.0, 5.0, p.k_saturacion, 0.1)

def sidebar_politicas():
    p = st.session_state.params
    st.sidebar.header("Pipeline 12 años")
    p.pipeline_activo = st.sidebar.checkbox("Activar pipeline manual", value=p.pipeline_activo)
    p.pipeline_auto_por_hacinamiento = st.sidebar.checkbox("Auto por hacinamiento en 1°", value=p.pipeline_auto_por_hacinamiento)
    p.umbral_hacinamiento_g1 = st.sidebar.slider("Umbral hacinamiento 1°", 0.0, 0.5, p.umbral_hacinamiento_g1, 0.01)
    p.pipeline_financiacion_externa = st.sidebar.checkbox("Permitir financiación externa", value=p.pipeline_financiacion_externa)
    p.capex_pct_sobre_facturacion = st.sidebar.slider("% CAPEX/Facturación", 0.0, 1.0, p.capex_pct_sobre_facturacion, 0.05)
    p.colchon_financiero = st.sidebar.number_input("Colchón financiero", 0.0, 10000000.0, p.colchon_financiero, 10000.0)
    p.costo_construccion_aula = st.sidebar.number_input("Costo construcción aula", 0.0, 5000000.0, p.costo_construccion_aula, 10000.0)

with tabs[0]:
    st.markdown("**Objetivo**: ver loops y decisiones con un modelo simple pero demostrativo. Ajustá parámetros y mirá las curvas.")

with tabs[1]:
    sidebar_basic()
    df, meta = simulate(st.session_state.params)
    st.pyplot(line_plot(df["Año"], [df["AlumnosTotales"]], ["Alumnos"], "Evolución de Alumnos", "Año", "Alumnos"))
    st.pyplot(dual_plot(df["Año"], df["Facturacion"], df["CostosOPEX"], "Facturación", "Costos", "Finanzas", "Año", "$"))

with tabs[2]:
    sidebar_marketing()
    df, _ = simulate(st.session_state.params)
    st.pyplot(line_plot(df["Año"], [df["BudgetMkt"]], ["Budget"], "Marketing Budget", "Año", "$"))

with tabs[4]:
    sidebar_politicas()
    df, _ = simulate(st.session_state.params)
    st.pyplot(line_plot(df["Año"], [df["AulasTotales"]], ["Aulas"], "Aulas", "Año", "Aulas"))

with tabs[5]:
    df, meta = simulate(st.session_state.params)
    st.download_button("Descargar CSV", data=df.to_csv(index=False).encode("utf-8"), file_name="resultados.csv")
