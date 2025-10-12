# app.py — gráficos responsivos (Streamlit + Altair) y nuevos sliders
# requirements.txt: streamlit, numpy, pandas, altair

import streamlit as st
import pandas as pd
import altair as alt
from model.simulate import Params, simulate

st.set_page_config(page_title="School SD Simulator", layout="wide")
st.title("Modelo de Dinámica de Sistemas — Colegio")

# ---------- Helpers ----------
def sidebar_basic(p: Params):
    st.sidebar.header("Básicos")
    p.years = st.sidebar.slider("Años de simulación", 5, 30, p.years)
    p.demanda_potencial = st.sidebar.number_input("Demanda potencial (alumnos)", 100, 200000, p.demanda_potencial, 100)
    p.calidad_base = st.sidebar.slider("Calidad base", 0.0, 1.0, p.calidad_base, 0.01)
    p.beta_hacinamiento = st.sidebar.slider("β hacinamiento → calidad", 0.0, 2.0, p.beta_hacinamiento, 0.05)
    p.tasa_bajas_imprevistas = st.sidebar.slider("Tasa bajas imprevistas (/año)", 0.0, 0.2, p.tasa_bajas_imprevistas, 0.005)
    p.tasa_bajas_max_por_calidad = st.sidebar.slider("Tasa máx. bajas por mala calidad", 0.0, 0.5, p.tasa_bajas_max_por_calidad, 0.01)

    st.sidebar.header("Capacidad")
    p.div_inicial_por_grado = st.sidebar.number_input("Divisiones por grado (inicial)", 1, 10, p.div_inicial_por_grado)
    p.cupo_optimo = st.sidebar.number_input("Cupo ÓPTIMO por aula (calidad)", 10, 60, p.cupo_optimo)
    p.cupo_maximo = st.sidebar.number_input("Cupo MÁXIMO por aula (capacidad dura)", 10, 70, p.cupo_maximo)

    st.sidebar.header("Finanzas")
    p.cuota_mensual = st.sidebar.number_input("Cuota mensual ($/est/mes)", 0.0, 20000.0, p.cuota_mensual, 10.0)
    p.meses = st.sidebar.number_input("Meses facturados", 1, 12, p.meses)
    p.costo_fijo_anual = st.sidebar.number_input("Costo fijo anual ($)", 0.0, 100_000_000.0, p.costo_fijo_anual, 10_000.0)
    p.costo_variable_alumno = st.sidebar.number_input("Costo variable por alumno ($/año)", 0.0, 100_000.0, p.costo_variable_alumno, 10.0)
    p.costo_docente_por_aula = st.sidebar.number_input("Costo docente por aula ($/año)", 0.0, 2_000_000.0, p.costo_docente_por_aula, 1_000.0)
    p.costo_mantenimiento_anual = st.sidebar.number_input("Costo de mantenimiento ($/año)", 0.0, 5_000_000.0, p.costo_mantenimiento_anual, 10_000.0)

    st.sidebar.header("Iniciales")
    p.g_inicial = st.sidebar.number_input("Alumnos por grado (inicial)", 0, 100, p.g_inicial)
    p.candidatos_inicial = st.sidebar.number_input("Candidatos (stock inicial)", 0, 100000, int(p.candidatos_inicial))

def sidebar_marketing(p: Params):
    st.sidebar.header("Marketing & Selección")
    p.prop_mkt = st.sidebar.slider("Proporción de resultado a marketing", 0.0, 0.8, p.prop_mkt, 0.01)
    p.mkt_floor = st.sidebar.number_input("Piso anual de marketing ($)", 0.0, 5_000_000.0, p.mkt_floor, 1_000.0)
    p.cac_base = st.sidebar.number_input("CAC base ($/candidato)", 1.0, 200_000.0, p.cac_base, 10.0)
    p.k_saturacion = st.sidebar.slider("Sensibilidad CAC a saturación", 0.0, 5.0, p.k_saturacion, 0.1)
    p.politica_seleccion = st.sidebar.slider("Política de selección (% aceptados del stock)", 0.0, 1.0, p.politica_seleccion, 0.01)

def sidebar_politicas(p: Params):
    st.sidebar.header("Expansión (pipeline 12 años)")
    p.pipeline_activo = st.sidebar.checkbox("Activar pipeline manual", value=p.pipeline_activo)
    p.pipeline_auto_por_hacinamiento = st.sidebar.checkbox("Auto por hacinamiento en 1º", value=p.pipeline_auto_por_hacininamiento) if hasattr(p, "pipeline_auto_por_hacininamiento") else st.sidebar.checkbox("Auto por hacinamiento en 1º", value=p.pipeline_auto_por_hacinamiento)
    p.umbral_hacinamiento_g1 = st.sidebar.slider("Umbral de hacinamiento en 1º", 0.0, 0.5, p.umbral_hacinamiento_g1, 0.01)
    p.pipeline_financiacion_externa = st.sidebar.checkbox("Permitir financiación externa", value=p.pipeline_financiacion_externa)
    p.capex_pct_sobre_facturacion = st.sidebar.slider("% CAPEX sobre facturación (límite)", 0.0, 1.0, p.capex_pct_sobre_facturacion, 0.05)
    p.colchon_financiero = st.sidebar.number_input("Colchón financiero ($)", 0.0, 20_000_000.0, p.colchon_financiero, 10_000.0)
    p.costo_construccion_aula = st.sidebar.number_input("Costo construcción por aula ($)", 0.0, 10_000_000.0, p.costo_construccion_aula, 10_000.0)

def fold(df: pd.DataFrame, cols: list[str], x="Año") -> pd.DataFrame:
    return df[[x] + cols].melt(id_vars=[x], value_vars=cols, var_name="serie", value_name="valor")

def alt_lines(df_long: pd.DataFrame, title: str, y_title: str):
    base = alt.Chart(df_long).encode(
        x=alt.X("Año:Q"),
        y=alt.Y("valor:Q", title=y_title),
        color=alt.Color("serie:N", legend=alt.Legend(orient="bottom", columns=2)),
        tooltip=["Año","serie","valor"]
    )
    lines = base.mark_line()
    points = base.mark_circle(size=30)
    return (lines + points).properties(title=title).interactive()

# ---------- Estado ----------
if "params" not in st.session_state:
    st.session_state.params = Params()

# ---------- Tabs ----------
tab_inicio, tab_sim, tab_mkt, tab_coh, tab_polit, tab_export = st.tabs(
    ["🏠 Inicio", "📊 Simulación", "📣 Marketing & Selección", "📚 Cohortes (1–12)", "⚙️ Expansión", "📥 Exportar"]
)

# ---------- Inicio ----------
with tab_inicio:
    st.markdown("""
**Propósito:** visualizar cómo decisiones (calidad, marketing, selección, inversión en aulas) generan loops y afectan matrícula, capacidad y finanzas.

- **Capacidad dura**: `Aulas * cupo MÁXIMO`.  
- **Hacinamiento (calidad)**: se evalúa con `cupo ÓPTIMO`.  
- **Candidatos (STOCK)**: Marketing → **Nuevos candidatos**; Selección → **Aceptados** (limitados por capacidad y demanda).  
- **Egresos base**: `AlumnosTotales / 12`.  
- **Alumnos** nunca supera la **capacidad dura**.
    """)

# ---------- Simulación ----------
with tab_sim:
    sidebar_basic(st.session_state.params)
    p = st.session_state.params
    df, meta = simulate(p)

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Alumnos (0→fin)", f"{int(df['AlumnosTotales'].iloc[0])} → {int(df['AlumnosTotales'].iloc[-1])}")
    with c2:
        st.metric("Capacidad máx (fin)", f"{int(df['CapacidadMaxTotal'].iloc[-1])}")
    with c3:
        st.metric("Resultado Neto (fin)", f"${df['ResultadoNeto'].iloc[-1]:,.0f}")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Alumnos")
        st.line_chart(df, x="Año", y="AlumnosTotales", use_container_width=True)

        st.subheader("Calidad percibida")
        st.line_chart(df, x="Año", y="Calidad", use_container_width=True)

    with col2:
        st.subheader("Alumnos vs Capacidad")
        df_ac = df[["Año","AlumnosTotales","CapacidadMaxTotal","CapacidadOptTotal"]].rename(
            columns={"CapacidadMaxTotal":"Capacidad Máx", "CapacidadOptTotal":"Capacidad Ópt"}
        )
        ac_long = fold(df_ac, ["AlumnosTotales","Capacidad Máx","Capacidad Ópt"])
        st.altair_chart(alt_lines(ac_long, "Alumnos vs Capacidad", "Cantidad"), use_container_width=True)

        st.subheader("Bajas y Egresos base")
        be_long = fold(df[["Año","BajasTotales","EgresosBase"]], ["BajasTotales","EgresosBase"])
        st.altair_chart(alt_lines(be_long, "Bajas vs Egresos base", "Personas/año"), use_container_width=True)

    st.divider()
    st.caption("Primeros años")
    st.dataframe(df.head(20), use_container_width=True)

# ---------- Marketing & Selección ----------
with tab_mkt:
    sidebar_marketing(st.session_state.params)
    p = st.session_state.params
    df, _ = simulate(p)

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Stock de candidatos")
        st.line_chart(df, x="Año", y="CandidatosStock", use_container_width=True)

        st.subheader("Flujos: nuevos candidatos y seleccionados")
        fl_long = fold(df[["Año","NuevosCandidatos","Seleccionados"]], ["NuevosCandidatos","Seleccionados"])
        st.altair_chart(alt_lines(fl_long, "Funnel anual", "Personas/año"), use_container_width=True)

    with col2:
        st.subheader("Budget y CAC")
        bc_long = fold(df[["Año","BudgetMkt","CAC"]], ["BudgetMkt","CAC"])
        st.altair_chart(alt_lines(bc_long, "Marketing ($) y CAC ($/candidato)", "valor"), use_container_width=True)

        st.subheader("Calidad (para conversión)")
        st.line_chart(df, x="Año", y="Calidad", use_container_width=True)

# ---------- Cohortes ----------
with tab_coh:
    p = st.session_state.params
    df, _ = simulate(p)

    st.subheader("Alumnos por grado (G1..G12)")
    g_cols = [f"G{i}" for i in range(1,13)]
    gdf = df[["Año"] + g_cols].copy()
    heat = (
        alt.Chart(gdf.melt(id_vars=["Año"], var_name="Grado", value_name="Alumnos"))
        .mark_rect()
        .encode(
            x=alt.X("Año:O", sort="ascending"),
            y=alt.Y("Grado:O", sort=g_cols),
            color=alt.Color("Alumnos:Q", scale=alt.Scale(scheme="blues")),
            tooltip=["Año","Grado","Alumnos"],
        )
        .properties(height=520, title="Heatmap de alumnos por grado y año")  # ↑ altura para visibilidad
    )
    st.altair_chart(heat, use_container_width=True)

    st.caption("Tabla (primeros años)")
    st.dataframe(gdf.head(20), use_container_width=True)

# ---------- Expansión / Pipeline ----------
with tab_polit:
    sidebar_politicas(st.session_state.params)
    p = st.session_state.params
    df, _ = simulate(p)

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Aulas (stock) y pipeline")
        st.line_chart(df, x="Año", y="AulasTotales", use_container_width=True)
        bar = alt.Chart(df).mark_bar().encode(
            x="Año:Q", y=alt.Y("PipelineConstrucciones:Q", title="Aulas/año"),
            tooltip=["Año","PipelineConstrucciones"]
        ).properties(title="Construcciones por año")
        st.altair_chart(bar, use_container_width=True)

    with col2:
        st.subheader("Resultados")
        res_long = fold(df[["Año","ResultadoOperativo","ResultadoNeto"]], ["ResultadoOperativo","ResultadoNeto"])
        st.altair_chart(alt_lines(res_long, "Resultado operativo vs neto", "$ por año"), use_container_width=True)

        st.subheader("Alumnos vs Capacidad")
        df_ac = df[["Año","AlumnosTotales","CapacidadMaxTotal","CapacidadOptTotal"]].rename(
            columns={"CapacidadMaxTotal":"Capacidad Máx", "CapacidadOptTotal":"Capacidad Ópt"}
        )
        ac_long = fold(df_ac, ["AlumnosTotales","Capacidad Máx","Capacidad Ópt"])
        st.altair_chart(alt_lines(ac_long, "", "Cantidad"), use_container_width=True)

# ---------- Exportar ----------
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
