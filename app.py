# app.py — Streamlit con: Rechazados, Demanda decreciente, Caja/Deuda, CAPEX financiado,
# migración de Params y keys únicos para widgets en pestañas repetidas.
# requirements.txt: streamlit, numpy, pandas, altair

import streamlit as st
import pandas as pd
import altair as alt
from model.simulate import Params, simulate

st.set_page_config(page_title="School SD Simulator", layout="wide")
st.title("Modelo de Dinámica de Sistemas — Colegio")

# --- Migración/compatibilidad de parámetros ---
def ensure_params_defaults(p):
    """Completa atributos faltantes con defaults de la clase Params actual."""
    defaults = Params()
    for k, v in defaults.__dict__.items():
        if not hasattr(p, k):
            setattr(p, k, v)
    return p

# --------- Estado ---------
if "params" not in st.session_state:
    st.session_state.params = Params()
else:
    st.session_state.params = ensure_params_defaults(st.session_state.params)

# --------- Helpers ---------
def sidebar_basicos_y_demanda(p: Params):
    st.sidebar.header("Horizonte y Demanda")
    p.years = st.sidebar.slider("Años de simulación", 5, 50, p.years)
    p.demanda_potencial_inicial = st.sidebar.number_input("Demanda potencial inicial (alumnos)", 100, 500000, p.demanda_potencial_inicial, 100)
    p.tasa_descenso_demanda = st.sidebar.slider("Tasa descenso demanda anual", 0.0, 0.30, p.tasa_descenso_demanda, 0.01)

    st.sidebar.header("Capacidad")
    p.div_inicial_por_grado = st.sidebar.number_input("Divisiones por grado (inicial)", 1, 12, p.div_inicial_por_grado)
    p.cupo_optimo = st.sidebar.number_input("Cupo ÓPTIMO por aula (calidad)", 10, 60, p.cupo_optimo)
    p.cupo_maximo = st.sidebar.number_input("Cupo MÁXIMO por aula (capacidad dura)", 10, 80, p.cupo_maximo)

    st.sidebar.header("Calidad y bajas")
    p.calidad_base = st.sidebar.slider("Calidad base", 0.0, 1.0, p.calidad_base, 0.01)
    p.beta_hacinamiento = st.sidebar.slider("β hacinamiento → calidad", 0.0, 2.0, p.beta_hacinamiento, 0.05)
    p.tasa_bajas_imprevistas = st.sidebar.slider("Tasa bajas imprevistas (/año)", 0.0, 0.2, p.tasa_bajas_imprevistas, 0.005)
    p.tasa_bajas_max_por_calidad = st.sidebar.slider("Tasa máx. bajas por mala calidad", 0.0, 0.5, p.tasa_bajas_max_por_calidad, 0.01)

    st.sidebar.header("Iniciales académicos")
    p.g_inicial = st.sidebar.number_input("Alumnos por grado (inicial)", 0, 200, p.g_inicial)
    p.candidatos_inicial = st.sidebar.number_input("Candidatos (stock inicial)", 0, 200000, int(p.candidatos_inicial))

def sidebar_marketing_y_admision(p: Params):
    st.sidebar.header("Cuotas y Marketing")
    p.cuota_mensual = st.sidebar.number_input("Cuota mensual ($/est/mes)", 0.0, 100000.0, p.cuota_mensual, 10.0)
    p.prop_mkt = st.sidebar.slider("Proporción resultado → marketing", 0.0, 0.9, p.prop_mkt, 0.01)
    p.mkt_floor = st.sidebar.number_input("Piso anual de marketing ($)", 0.0, 10_000_000.0, p.mkt_floor, 1_000.0)
    p.cac_base = st.sidebar.number_input("CAC base ($/candidato)", 1.0, 500_000.0, p.cac_base, 10.0)
    p.k_saturacion = st.sidebar.slider("Sensibilidad CAC a saturación", 0.0, 5.0, p.k_saturacion, 0.1)

    st.sidebar.header("Selección (admisión)")
    p.politica_seleccion = st.sidebar.slider("Política de selección (% aceptados del stock)", 0.0, 1.0, p.politica_seleccion, 0.01)
    p.alumnos_admitidos_objetivo = st.sidebar.number_input("Alumnos admitidos (objetivo anual)", 0, 10000, p.alumnos_admitidos_objetivo)

def sidebar_costos_inversion_y_calidad(p: Params):
    st.sidebar.header("Costos e inversión (impacto en calidad)")
    p.pct_sueldos = st.sidebar.slider("% Sueldos sobre facturación", 0.0, 0.95, p.pct_sueldos, 0.01)
    p.inversion_infra_anual = st.sidebar.number_input("Inversión en infraestructura ($/año)", 0.0, 10_000_000.0, p.inversion_infra_anual, 10_000.0)
    p.inversion_calidad_por_alumno = st.sidebar.number_input("Inversión en calidad por alumno ($/año)", 0.0, 20_000.0, p.inversion_calidad_por_alumno, 10.0)
    p.mantenimiento_pct_facturacion = st.sidebar.slider("% Mantenimiento sobre facturación", 0.0, 0.5, p.mantenimiento_pct_facturacion, 0.01)

    st.sidebar.header("Activos")
    p.activos_inicial = st.sidebar.number_input("Activos iniciales ($)", 0.0, 50_000_000.0, p.activos_inicial, 10_000.0)
    p.tasa_depreciacion_anual = st.sidebar.slider("Tasa de depreciación anual", 0.0, 0.3, p.tasa_depreciacion_anual, 0.01)

def sidebar_financiamiento_y_pipeline(p: Params, key_prefix: str = "fin"):
    st.sidebar.header("Expansión (pipeline 12 años)")
    p.pipeline_start_year = st.sidebar.slider(
        "Año de inicio del pipeline (−1 desactiva)",
        min_value=-1, max_value=p.years, value=p.pipeline_start_year, key=f"{key_prefix}_pipeline_start_year"
    )
    p.costo_construccion_aula = st.sidebar.number_input(
        "CAPEX por aula nueva ($)",
        min_value=0.0, max_value=10_000_000.0, value=p.costo_construccion_aula, step=10_000.0,
        key=f"{key_prefix}_costo_construccion_aula"
    )
    p.costo_docente_por_aula_nueva = st.sidebar.number_input(
        "Costo docente por aula NUEVA ($/año)",
        min_value=0.0, max_value=2_000_000.0, value=p.costo_docente_por_aula_nueva, step=1_000.0,
        key=f"{key_prefix}_costo_docente_por_aula_nueva"
    )

    st.sidebar.header("Financiamiento")
    p.caja_inicial = st.sidebar.number_input(
        "Caja inicial ($)",
        min_value=0.0, max_value=50_000_000.0, value=p.caja_inicial, step=10_000.0,
        key=f"{key_prefix}_caja_inicial"
    )
    p.pct_capex_financiado = st.sidebar.slider(
        "% CAPEX financiado", min_value=0.0, max_value=1.0, value=p.pct_capex_financiado, step=0.05,
        key=f"{key_prefix}_pct_capex_financiado"
    )
    p.tasa_interes_deuda = st.sidebar.slider(
        "Tasa de interés deuda (anual)", min_value=0.0, max_value=0.5, value=p.tasa_interes_deuda, step=0.01,
        key=f"{key_prefix}_tasa_interes_deuda"
    )
    p.anos_amortizacion_deuda = st.sidebar.number_input(
        "Años de amortización de deuda", min_value=1, max_value=40, value=p.anos_amortizacion_deuda, step=1,
        key=f"{key_prefix}_anos_amortizacion_deuda"
    )
    p.deuda_inicial = st.sidebar.number_input(
        "Deuda inicial ($)",
        min_value=0.0, max_value=50_000_000.0, value=p.deuda_inicial, step=10_000.0,
        key=f"{key_prefix}_deuda_inicial"
    )

def fold(df: pd.DataFrame, cols: list[str], x="Año") -> pd.DataFrame:
    return df[[x] + cols].melt(id_vars=[x], value_vars=cols, var_name="serie", value_name="valor")

def alt_lines(df_long: pd.DataFrame, title: str, y_title: str):
    sel = alt.selection_point(fields=["serie"], bind="legend")  # toggle por leyenda
    base = alt.Chart(df_long).encode(
        x=alt.X("Año:Q"),
        y=alt.Y("valor:Q", title=y_title),
        color=alt.Color("serie:N", legend=alt.Legend(orient="bottom", columns=3)),
        tooltip=["Año","serie","valor"]
    ).add_params(sel).transform_filter(sel)
    return (base.mark_line() + base.mark_circle(size=28)).properties(title=title).interactive()

def choose_series(label: str, options: list[str], default: list[str], key: str) -> list[str]:
    return st.multiselect(label, options=options, default=default, key=key)

# --------- Tabs ---------
tab_inicio, tab_sim, tab_mkt, tab_costos, tab_fin, tab_coh, tab_exp, tab_export = st.tabs(
    ["🏠 Inicio", "📊 Simulación", "📣 Marketing & Admisión", "💰 OPEX & Resultados", "🏦 Caja & Deuda", "📚 Cohortes", "🏗️ Expansión", "📥 Exportar"]
)

# --------- Inicio ---------
with tab_inicio:
    st.markdown("""
**Novedades del modelo:**
- **Candidatos**: entradas = *NuevosCandidatos*; salidas = **Admitidos** (a G1) y **Rechazados** (salen del sistema).
- **Demanda**: decrece **5% anual** (editable) y limita el crecimiento.
- **Caja** y **Deuda** como **stocks**. **CAPEX** se divide en **Propio** y **Financiado** con **Intereses** y **Amortización**.
- **Promoción**: flujo interno G(i−1) → G(i) (pipeline educativo).
    """)

# --------- Simulación (vista principal) ---------
with tab_sim:
    sidebar_basicos_y_demanda(st.session_state.params)
    p = st.session_state.params
    df, _ = simulate(p)

    c1, c2, c3 = st.columns(3)
    with c1: st.metric("Alumnos (0→fin)", f"{int(df['AlumnosTotales'].iloc[0])} → {int(df['AlumnosTotales'].iloc[-1])}")
    with c2: st.metric("Demanda (0→fin)", f"{int(df['DemandaPotencial'].iloc[0])} → {int(df['DemandaPotencial'].iloc[-1])}")
    with c3: st.metric("Calidad (fin)", f"{df['Calidad'].iloc[-1]:.2f}")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Alumnos, Capacidad y Demanda")
        ac_all = ["AlumnosTotales","Capacidad Máx","Capacidad Ópt","Demanda"]
        ac_df = df[["Año","AlumnosTotales","CapacidadMaxTotal","CapacidadOptTotal","DemandaPotencial"]].rename(
            columns={"CapacidadMaxTotal":"Capacidad Máx","CapacidadOptTotal":"Capacidad Ópt","DemandaPotencial":"Demanda"})
        ac_sel = choose_series("Series (Alumnos/Capacidad/Demanda)", ac_all, ["AlumnosTotales","Capacidad Máx","Demanda"], key="sim_ac")
        if ac_sel:
            st.altair_chart(alt_lines(fold(ac_df, ac_sel), "", "Cantidad"), use_container_width=True)

    with col2:
        st.subheader("Admitidos, Rechazados, Egresados y Bajas")
        flows_all = ["Admitidos","Rechazados","Egresados","BajasTotales"]
        flows_sel = choose_series("Series (Flujos)", flows_all, ["Admitidos","Egresados","BajasTotales"], key="sim_flows")
        if flows_sel:
            st.altair_chart(alt_lines(fold(df, flows_sel), "", "Personas/año"), use_container_width=True)

    st.subheader("Calidad percibida")
    st.line_chart(df, x="Año", y="Calidad", use_container_width=True)

    st.caption("Tabla (primeros años)")
    st.dataframe(df.head(20), use_container_width=True)

# --------- Marketing & Admisión ---------
with tab_mkt:
    sidebar_marketing_y_admision(st.session_state.params)
    p = st.session_state.params
    df, _ = simulate(p)

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Candidatos (stock)")
        st.line_chart(df, x="Año", y="CandidatosStock", use_container_width=True)

        st.subheader("Funnel: Nuevos, Admitidos, Rechazados")
        fl_all = ["NuevosCandidatos","Admitidos","Rechazados"]
        fl_sel = choose_series("Series (Funnel)", fl_all, fl_all, key="mkt_funnel")
        if fl_sel:
            st.altair_chart(alt_lines(fold(df, fl_sel), "", "Personas/año"), use_container_width=True)

    with c2:
        st.subheader("Marketing y CAC")
        bc_all = ["Marketing","CAC"]
        bc_sel = choose_series("Series (Budget/CAC)", bc_all, bc_all, key="mkt_bc")
        if bc_sel:
            st.altair_chart(alt_lines(fold(df, bc_sel), "", "Valor"), use_container_width=True)
        st.subheader("Demanda potencial")
        st.line_chart(df, x="Año", y="DemandaPotencial", use_container_width=True)

# --------- OPEX & Resultados ---------
with tab_costos:
    sidebar_costos_inversion_y_calidad(st.session_state.params)
    p = st.session_state.params
    df, _ = simulate(p)

    st.subheader("Facturación")
    st.line_chart(df, x="Año", y="Facturacion", use_container_width=True)

    st.subheader("Composición OPEX (stacked)")
    opex_all = ["Sueldos","InversionInfra","InversionCalidadAlumno","Mantenimiento","Marketing","DocentesNuevas"]
    opex_sel = choose_series("Partidas OPEX", opex_all, opex_all, key="opex_parts")
    if opex_sel:
        opex_long = fold(df, opex_sel)
        stack = alt.Chart(opex_long).mark_area().encode(
            x="Año:Q",
            y=alt.Y("valor:Q", stack="zero", title="$ por año"),
            color=alt.Color("serie:N", legend=alt.Legend(orient="bottom", columns=3)),
            tooltip=["Año","serie","valor"]
        ).interactive()
        st.altair_chart(stack, use_container_width=True)

    st.subheader("Resultados y CAPEX")
    res_all = ["ResultadoOperativo","ResultadoNeto","CAPEX_Total","CAPEX_Propio","CAPEX_Financiado"]
    res_sel = choose_series("Series (Resultados/CAPEX)", res_all, ["ResultadoOperativo","ResultadoNeto","CAPEX_Total"], key="res_capex")
    if res_sel:
        st.altair_chart(alt_lines(fold(df, res_sel), "", "$ por año"), use_container_width=True)

# --------- Caja & Deuda ---------
with tab_fin:
    sidebar_financiamiento_y_pipeline(st.session_state.params, key_prefix="fin")
    p = st.session_state.params
    df, _ = simulate(p)

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Caja y Deuda (stocks)")
        st.altair_chart(alt_lines(fold(df, ["Caja","Deuda"]), "", "$"), use_container_width=True)
    with c2:
        st.subheader("Intereses y Amortización (flujos)")
        st.altair_chart(alt_lines(fold(df, ["InteresDeuda","AmortizacionDeuda"]), "", "$/año"), use_container_width=True)

# --------- Cohortes ---------
with tab_coh:
    p = st.session_state.params
    df, _ = simulate(p)
    st.subheader("Alumnos por grado (G1..G12)")
    g_cols = [f"G{i}" for i in range(1,13)]
    gdf = df[["Año"] + g_cols].copy()
    heat = alt.Chart(gdf.melt(id_vars=["Año"], var_name="Grado", value_name="Alumnos")).mark_rect().encode(
        x=alt.X("Año:O", sort="ascending"),
        y=alt.Y("Grado:O", sort=g_cols),
        color=alt.Color("Alumnos:Q", scale=alt.Scale(scheme="blues")),
        tooltip=["Año","Grado","Alumnos"]
    ).properties(height=560)
    st.altair_chart(heat, use_container_width=True)
    st.caption("Tabla (primeros años)")
    st.dataframe(gdf.head(20), use_container_width=True)

# --------- Expansión / Pipeline ---------
with tab_exp:
    sidebar_financiamiento_y_pipeline(st.session_state.params, key_prefix="exp")
    p = st.session_state.params
    df, _ = simulate(p)

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Aulas (stock)")
        st.line_chart(df, x="Año", y="AulasTotales", use_container_width=True)
    with c2:
        st.subheader("Construcciones por año (pipeline)")
        bar = alt.Chart(df).mark_bar().encode(
            x="Año:Q",
            y=alt.Y("PipelineConstrucciones:Q", title="Aulas/año"),
            tooltip=["Año","PipelineConstrucciones"]
        )
        st.altair_chart(bar, use_container_width=True)

# --------- Exportar ---------
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
