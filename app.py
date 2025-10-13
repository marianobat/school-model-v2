import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
from model.simulate import Params, simulate

st.set_page_config(page_title="School SD Simulator", layout="wide")
st.title("Modelo de Dinámica de Sistemas — Colegio")

# --- Migración/compatibilidad de parámetros ---
def ensure_params_defaults(p):
    defaults = Params()
    for k, v in defaults.__dict__.items():
        if not hasattr(p, k):
            setattr(p, k, v)
    return p

if "params" not in st.session_state:
    st.session_state.params = Params()
else:
    st.session_state.params = ensure_params_defaults(st.session_state.params)

# --------- Sidebar (único lugar de edición) ---------
def sidebar_basicos_y_demanda(p: Params):
    st.sidebar.header("Horizonte y Demanda")
    p.years = st.sidebar.slider("Años de simulación", 5, 50, p.years)
    p.demanda_potencial_inicial = st.sidebar.number_input("Demanda potencial inicial (alumnos)", 100, 500000, p.demanda_potencial_inicial, 100)
    p.tasa_descenso_demanda = st.sidebar.slider("Tasa descenso demanda anual", 0.0, 0.30, p.tasa_descenso_demanda, 0.01)

    st.sidebar.header("Capacidad")
    p.div_inicial_por_grado = st.sidebar.number_input("Divisiones por grado (inicial)", 1, 12, p.div_inicial_por_grado)
    p.cupo_optimo = st.sidebar.number_input("Cupo ÓPTIMO por aula (calidad)", 10, 60, p.cupo_optimo)
    p.cupo_maximo = st.sidebar.number_input("Cupo MÁXIMO por aula (capacidad dura)", 10, 80, p.cupo_maximo)

    st.sidebar.header("Calidad y bajas (base)")
    p.calidad_base = st.sidebar.slider("Calidad base", 0.0, 1.0, p.calidad_base, 0.01)
    p.beta_hacinamiento = st.sidebar.slider("β hacinamiento → calidad", 0.0, 2.0, p.beta_hacinamiento, 0.05)
    p.tasa_bajas_imprevistas = st.sidebar.slider("Tasa bajas imprevistas (/año)", 0.0, 0.2, p.tasa_bajas_imprevistas, 0.005)
    p.tasa_bajas_max_por_calidad = st.sidebar.slider("Tasa máx. bajas por mala calidad", 0.0, 0.5, p.tasa_bajas_max_por_calidad, 0.01)

def sidebar_marketing_y_costos(p: Params):
    st.sidebar.header("Cuotas, Marketing e Inversiones")
    p.cuota_mensual = st.sidebar.number_input("Cuota mensual ($/est/mes)", 0.0, 100000.0, p.cuota_mensual, 10.0)
    p.prop_mkt = st.sidebar.slider("Proporción resultado → marketing", 0.0, 0.9, p.prop_mkt, 0.01)
    p.mkt_floor = st.sidebar.number_input("Piso anual de marketing ($)", 0.0, 10_000_000.0, p.mkt_floor, 1_000.0)
    p.cac_base = st.sidebar.number_input("CAC base ($/candidato)", 1.0, 500_000.0, p.cac_base, 10.0)
    p.k_saturacion = st.sidebar.slider("Sensibilidad CAC a saturación", 0.0, 5.0, p.k_saturacion, 0.1)

    st.sidebar.divider()
    p.admitidos_deseados = st.sidebar.number_input("Admitidos deseados (alumnos/año)", 0, 100000, p.admitidos_deseados, 10)

    st.sidebar.header("Costos e inversión")
    p.costo_docente_por_aula = st.sidebar.number_input("Costo docente por AULA ($/año)", 0.0, 2_000_000.0, p.costo_docente_por_aula, 1_000.0)
    p.sueldos_no_docentes = st.sidebar.number_input("Sueldos NO docentes ($/año)", 0.0, 10_000_000.0, p.sueldos_no_docentes, 1_000.0)
    p.inversion_infra_anual = st.sidebar.number_input("Inversión en infraestructura (target $/año)", 0.0, 10_000_000.0, p.inversion_infra_anual, 10_000.0)
    p.inversion_calidad_por_alumno = st.sidebar.number_input("Inversión en calidad por alumno (target $/año)", 0.0, 20_000.0, p.inversion_calidad_por_alumno, 10.0)
    p.mantenimiento_pct_facturacion = st.sidebar.slider("% Mantenimiento sobre facturación", 0.0, 0.5, p.mantenimiento_pct_facturacion, 0.01)

sidebar_basicos_y_demanda(st.session_state.params)
sidebar_marketing_y_costos(st.session_state.params)

# --- Simulación base una vez ---
p = st.session_state.params
df_base, _ = simulate(p)

# --------- Gráficos helpers ---------
def fold(df: pd.DataFrame, cols, x="Año"):
    return df[[x] + cols].melt(id_vars=[x], value_vars=cols, var_name="serie", value_name="valor")

def alt_lines(df_long: pd.DataFrame, y_title: str):
    sel = alt.selection_point(fields=["serie"], bind="legend")
    base = alt.Chart(df_long).encode(
        x=alt.X("Año:Q"),
        y=alt.Y("valor:Q", title=y_title),
        color=alt.Color("serie:N", legend=alt.Legend(orient="bottom", columns=3)),
        tooltip=["Año","serie","valor"]
    ).add_params(sel).transform_filter(sel)
    return (base.mark_line() + base.mark_circle(size=28)).interactive()

def choose_series(label: str, options, default, key: str):
    return st.multiselect(label, options=options, default=default, key=key)

# --------- Tabs ---------
tab_inicio, tab_sim, tab_mkt, tab_costos, tab_fin, tab_coh, tab_exp, tab_export = st.tabs(
    ["🏠 Inicio", "📊 Simulación", "📣 Marketing & Admisión", "💰 OPEX & Resultados", "🏦 Caja & Deuda", "📚 Cohortes", "🏗️ Expansión", "📥 Exportar"]
)

with tab_inicio:
    st.markdown("""
- **Candidatos orgánicos**: si la **calidad** supera un umbral y aún hay **pool** de demanda, llegan candidatos extra (boca a boca) sin costo de CAC.
- **Selectividad** = Admitidos/NuevosCandidatos. Si es alta, baja la **calidad** futura.
- **Admitidos(t)** afectan **G1(t+1)** → impactan **AlumnosTotales** desde el año siguiente.
    """)

with tab_sim:
    df = df_base
    c1, c2, c3 = st.columns(3)
    with c1: st.metric("Alumnos (0→fin)", f"{int(df['AlumnosTotales'].iloc[0])} → {int(df['AlumnosTotales'].iloc[-1])}")
    with c2: st.metric("Demanda (0→fin)", f"{int(df['DemandaPotencial'].iloc[0])} → {int(df['DemandaPotencial'].iloc[-1])}")
    with c3: st.metric("Calidad (fin)", f"{df['Calidad'].iloc[-1]:.2f}")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Alumnos, Capacidad y Demanda")
        ac_df = df[["Año","AlumnosTotales","CapacidadMaxTotal","CapacidadOptTotal","DemandaPotencial"]].rename(
            columns={"CapacidadMaxTotal":"Capacidad Máx","CapacidadOptTotal":"Capacidad Ópt","DemandaPotencial":"Demanda"})
        ac_all = ["AlumnosTotales","Capacidad Máx","Capacidad Ópt","Demanda"]
        ac_sel = choose_series("Series (Alumnos/Capacidad/Demanda)", ac_all, ["AlumnosTotales","Capacidad Máx","Demanda"], key="sim_ac")
        if ac_sel:
            st.altair_chart(alt_lines(fold(ac_df, ac_sel), "Cantidad"), use_container_width=True)

    with col2:
        st.subheader("Admitidos, Rechazados, Egresados y Bajas")
        flows_all = ["Admitidos","Rechazados","Egresados","BajasTotales"]
        flows_sel = choose_series("Series (Flujos)", flows_all, ["Admitidos","Egresados","BajasTotales"], key="sim_flows")
        if flows_sel:
            st.altair_chart(alt_lines(fold(df, flows_sel), "Personas/año"), use_container_width=True)

    st.subheader("Calidad percibida")
    st.line_chart(df, x="Año", y="Calidad", use_container_width=True)

with tab_mkt:
    df = df_base
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Candidatos: Pagados vs Orgánicos")
        cand_all = ["NuevosCandidatos","NuevosCandidatosMkt","NuevosCandidatosQ"]
        cand_sel = choose_series("Series (Candidatos)", cand_all, ["NuevosCandidatos","NuevosCandidatosMkt","NuevosCandidatosQ"], key="mkt_cands")
        if cand_sel:
            st.altair_chart(alt_lines(fold(df, cand_sel), "Personas/año"), use_container_width=True)

        st.subheader("Funnel: Nuevos, Admitidos, Rechazados")
        fl_all = ["NuevosCandidatos","Admitidos","Rechazados"]
        fl_sel = choose_series("Series (Funnel)", fl_all, fl_all, key="mkt_funnel")
        if fl_sel:
            st.altair_chart(alt_lines(fold(df, fl_sel), "Personas/año"), use_container_width=True)

    with c2:
        st.subheader("Selectividad y CAC")
        left = alt.layer(
            alt.Chart(df).mark_line(point=True).encode(x="Año:Q", y=alt.Y("Selectividad:Q", title="Selectividad (0..1)")),
            alt.Chart(df).mark_line(point=True).encode(x="Año:Q", y=alt.Y("CAC:Q", title="CAC ($/cand)"))
        ).resolve_scale(y='independent')
        st.altair_chart(left, use_container_width=True)

        st.subheader("Demanda potencial")
        st.line_chart(df, x="Año", y="DemandaPotencial", use_container_width=True)

with tab_costos:
    df = df_base
    last = df.iloc[-1]
    k1, k2, k3, k4, k5, k6 = st.columns(6)
    with k1: st.metric("Facturación (fin)", f"${last['Facturacion']:,.0f}")
    with k2: st.metric("Costos Totales (cash)", f"${last['CostosTotalesCash']:,.0f}")
    with k3: st.metric("OPEX (fin)", f"${last['CostosOPEX']:,.0f}")
    with k4: st.metric("Resultado Neto (fin)", f"${last['ResultadoNeto']:,.0f}")
    with k5: st.metric("Caja (fin)", f"${last['Caja']:,.0f}")
    with k6: st.metric("Deuda (fin)", f"${last['Deuda']:,.0f}")

    st.subheader("Facturación vs Costos Totales vs Rentabilidad ($/año)")
    series_fcr = ["Facturacion","CostosTotalesCash","ResultadoNeto"]
    st.altair_chart(alt_lines(fold(df, series_fcr), "$/año"), use_container_width=True)

    st.subheader("Composición OPEX — Absoluto ($/año)")
    opex_parts = ["Sueldos","InversionInfra","InversionCalidadAlumno","Mantenimiento","Marketing"]
    opex_long = fold(df, opex_parts)
    stack_abs = alt.Chart(opex_long).mark_area().encode(
        x="Año:Q",
        y=alt.Y("valor:Q", stack="zero", title="$ por año"),
        color=alt.Color("serie:N", legend=alt.Legend(orient="bottom", columns=3)),
        tooltip=["Año","serie","valor"]
    ).interactive()
    st.altair_chart(stack_abs, use_container_width=True)

    st.subheader("Composición OPEX — % de Facturación")
    df_pct = df.copy()
    for c in opex_parts:
        df_pct[c] = (df_pct[c] / df_pct["Facturacion"]).fillna(0.0).replace([np.inf, -np.inf], 0.0)
    opex_pct_long = fold(df_pct, opex_parts)
    stack_pct = alt.Chart(opex_pct_long).mark_area().encode(
        x="Año:Q",
        y=alt.Y("valor:Q", stack="normalize", title="% de facturación"),
        color=alt.Color("serie:N", legend=alt.Legend(orient="bottom", columns=3)),
        tooltip=["Año","serie",alt.Tooltip("valor:Q", format=".1%")]
    ).interactive()
    st.altair_chart(stack_pct, use_container_width=True)

with tab_fin:
    df = df_base
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Caja y Deuda (stocks)")
        sel = ["Caja","Deuda"]
        st.altair_chart(alt_lines(fold(df, sel), "$"), use_container_width=True)
    with c2:
        st.subheader("Intereses y Amortización (flujos)")
        st.altair_chart(alt_lines(fold(df, ["InteresDeuda","AmortizacionDeuda"]), "$/año"), use_container_width=True)

with tab_coh:
    df = df_base
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

# Expansión (controles en esta pestaña y simulación local)
def exp_controls_in_body(p: Params, key_prefix: str = "exp"):
    st.subheader("Parámetros de Expansión y Financiamiento")
    c1, c2, c3 = st.columns(3)
    with c1:
        p.pipeline_start_year = st.number_input(
            "Año de inicio del pipeline (−1 desactiva)", min_value=-1, max_value=p.years, value=p.pipeline_start_year, step=1,
            key=f"{key_prefix}_pipeline_start_year"
        )
        p.costo_construccion_aula = st.number_input(
            "CAPEX por aula nueva ($)", min_value=0.0, max_value=10_000_000.0, value=p.costo_construccion_aula, step=10_000.0,
            key=f"{key_prefix}_capex_aula"
        )
    with c2:
        p.pct_capex_financiado = st.slider(
            "% CAPEX financiado", min_value=0.0, max_value=1.0, value=p.pct_capex_financiado, step=0.05,
            key=f"{key_prefix}_pct_fin"
        )
        p.tasa_interes_deuda = st.slider(
            "Tasa de interés deuda (anual)", min_value=0.0, max_value=0.5, value=p.tasa_interes_deuda, step=0.01,
            key=f"{key_prefix}_tasa_int"
        )
    with c3:
        p.anos_amortizacion_deuda = st.number_input(
            "Años de amortización de deuda", min_value=1, max_value=40, value=p.anos_amortizacion_deuda, step=1,
            key=f"{key_prefix}_anos_amort"
        )
        p.caja_inicial = st.number_input(
            "Caja inicial ($)", min_value=0.0, max_value=50_000_000.0, value=p.caja_inicial, step=10_000.0,
            key=f"{key_prefix}_caja_ini"
        )
        p.deuda_inicial = st.number_input(
            "Deuda inicial ($)", min_value=0.0, max_value=50_000_000.0, value=p.deuda_inicial, step=10_000.0,
            key=f"{key_prefix}_deuda_ini"
        )

with tab_exp:
    exp_controls_in_body(st.session_state.params, key_prefix="exp")
    p = st.session_state.params
    df = simulate(p)[0]

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

with tab_export:
    df, meta = df_base, {"params": st.session_state.params.__dict__}
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
