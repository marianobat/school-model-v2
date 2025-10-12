# app.py — muestra Admitidos como ingresantes reales y métricas junto a capacidad
# requirements.txt: streamlit, numpy, pandas, altair

import streamlit as st
import pandas as pd
import altair as alt
from model.simulate import Params, simulate

st.set_page_config(page_title="School SD Simulator", layout="wide")
st.title("Modelo de Dinámica de Sistemas — Colegio")

# --------- Helpers ---------
def sidebar_basic(p: Params):
    st.sidebar.header("Básicos")
    p.years = st.sidebar.slider("Años de simulación", 5, 40, p.years)
    p.demanda_potencial = st.sidebar.number_input("Demanda potencial (alumnos)", 100, 500000, p.demanda_potencial, 100)
    p.cupo_optimo = st.sidebar.number_input("Cupo ÓPTIMO por aula (calidad)", 10, 60, p.cupo_optimo)
    p.cupo_maximo = st.sidebar.number_input("Cupo MÁXIMO por aula (referencia)", 10, 80, p.cupo_maximo)

    st.sidebar.header("Calidad y bajas")
    p.calidad_base = st.sidebar.slider("Calidad base", 0.0, 1.0, p.calidad_base, 0.01)
    p.beta_hacinamiento = st.sidebar.slider("β hacinamiento → calidad", 0.0, 2.0, p.beta_hacinamiento, 0.05)
    p.tasa_bajas_imprevistas = st.sidebar.slider("Tasa bajas imprevistas (/año)", 0.0, 0.2, p.tasa_bajas_imprevistas, 0.005)
    p.tasa_bajas_max_por_calidad = st.sidebar.slider("Tasa máx. bajas por mala calidad", 0.0, 0.5, p.tasa_bajas_max_por_calidad, 0.01)

    st.sidebar.header("Iniciales")
    p.div_inicial_por_grado = st.sidebar.number_input("Divisiones por grado (inicial)", 1, 12, p.div_inicial_por_grado)
    p.g_inicial = st.sidebar.number_input("Alumnos por grado (inicial)", 0, 200, p.g_inicial)
    p.candidatos_inicial = st.sidebar.number_input("Candidatos (stock inicial)", 0, 200000, int(p.candidatos_inicial))

def sidebar_marketing_seleccion(p: Params):
    st.sidebar.header("Cuotas y Marketing")
    p.cuota_mensual = st.sidebar.number_input("Cuota mensual ($/est/mes)", 0.0, 100000.0, p.cuota_mensual, 10.0)
    p.prop_mkt = st.sidebar.slider("Proporción resultado → marketing", 0.0, 0.9, p.prop_mkt, 0.01)
    p.mkt_floor = st.sidebar.number_input("Piso anual de marketing ($)", 0.0, 10_000_000.0, p.mkt_floor, 1_000.0)
    p.cac_base = st.sidebar.number_input("CAC base ($/candidato)", 1.0, 500_000.0, p.cac_base, 10.0)
    p.k_saturacion = st.sidebar.slider("Sensibilidad CAC a saturación", 0.0, 5.0, p.k_saturacion, 0.1)

    st.sidebar.header("Selección (admisión)")
    p.politica_seleccion = st.sidebar.slider("Política de selección (% aceptados del stock)", 0.0, 1.0, p.politica_seleccion, 0.01)
    p.alumnos_admitidos_objetivo = st.sidebar.number_input("Alumnos admitidos (objetivo anual)", 0, 10000, p.alumnos_admitidos_objetivo)

def sidebar_costos_inversion(p: Params):
    st.sidebar.header("Costos e inversión (impacto en calidad)")
    p.pct_sueldos = st.sidebar.slider("% Sueldos sobre facturación", 0.0, 0.95, p.pct_sueldos, 0.01)
    p.inversion_infra_anual = st.sidebar.number_input("Inversión en infraestructura ($/año)", 0.0, 10_000_000.0, p.inversion_infra_anual, 10_000.0)
    p.inversion_calidad_por_alumno = st.sidebar.number_input("Inversión en calidad por alumno ($/año)", 0.0, 20_000.0, p.inversion_calidad_por_alumno, 10.0)
    p.mantenimiento_pct_facturacion = st.sidebar.slider("% Mantenimiento sobre facturación", 0.0, 0.5, p.mantenimiento_pct_facturacion, 0.01)

    st.sidebar.header("Activos")
    p.activos_inicial = st.sidebar.number_input("Activos iniciales ($)", 0.0, 50_000_000.0, p.activos_inicial, 10_000.0)
    p.tasa_depreciacion_anual = st.sidebar.slider("Tasa de depreciación anual", 0.0, 0.3, p.tasa_depreciacion_anual, 0.01)

def sidebar_expansion(p: Params):
    st.sidebar.header("Expansión (pipeline 12 años)")
    p.pipeline_start_year = st.sidebar.slider("Año de inicio del pipeline (−1 desactiva)", -1, p.years, p.pipeline_start_year)
    p.costo_construccion_aula = st.sidebar.number_input("CAPEX por aula nueva ($)", 0.0, 10_000_000.0, p.costo_construccion_aula, 10_000.0)
    p.costo_docente_por_aula_nueva = st.sidebar.number_input("Costo docente por aula NUEVA ($/año)", 0.0, 2_000_000.0, p.costo_docente_por_aula_nueva, 1_000.0)

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

def choose_series(label: str, options: list[str], default: list[str]) -> list[str]:
    return st.multiselect(label, options=options, default=default, key=label)

# --------- Estado ---------
if "params" not in st.session_state:
    st.session_state.params = Params()

tab_inicio, tab_sim, tab_mkt, tab_costos, tab_coh, tab_exp, tab_export = st.tabs(
    ["🏠 Inicio", "📊 Simulación", "📣 Marketing & Selección", "💰 Finanzas", "📚 Cohortes", "🏗️ Expansión", "📥 Exportar"]
)

# --------- Inicio ---------
with tab_inicio:
    st.markdown("""
**Puntos clave:**
- **Admitidos** = ingresantes reales al sistema (flujo de entrada), no se topean por capacidad; la capacidad **Óptima** y **Máxima** se usan para calidad y referencia.
- **Stock Alumnos**: `Alumnos(t+1) = Alumnos(t) + Admitidos(t) − Bajas(t) − Egresados(t)`.
- **Egresados**: alumnos de **G12 del año anterior**.
- **Pipeline**: año de inicio (−1 desactiva) agrega **1 división/ grado** durante 12 años.
    """)

# --------- Simulación ---------
with tab_sim:
    sidebar_basic(st.session_state.params)
    p = st.session_state.params
    df, _ = simulate(p)

    # Métricas (mostrar Admitidos junto a capacidades)
    c1, c2, c3 = st.columns(3)
    with c1: st.metric("Capacidad Ópt (fin)", f"{int(df['CapacidadOptTotal'].iloc[-1])}")
    with c2: st.metric("Capacidad Máx (fin)", f"{int(df['CapacidadMaxTotal'].iloc[-1])}")
    with c3: st.metric("Admitidos (últ. año)", f"{int(df['Admitidos'].iloc[-1])}")

    c4, c5, c6 = st.columns(3)
    with c4: st.metric("Alumnos (0→fin)", f"{int(df['AlumnosTotales'].iloc[0])} → {int(df['AlumnosTotales'].iloc[-1])}")
    with c5: st.metric("Resultado Neto (fin)", f"${df['ResultadoNeto'].iloc[-1]:,.0f}")
    with c6: st.metric("Calidad (fin)", f"{df['Calidad'].iloc[-1]:.2f}")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Alumnos y Capacidad")
        ac_all = ["AlumnosTotales","Capacidad Máx","Capacidad Ópt"]
        ac_df = df[["Año","AlumnosTotales","CapacidadMaxTotal","CapacidadOptTotal"]].rename(
            columns={"CapacidadMaxTotal":"Capacidad Máx","CapacidadOptTotal":"Capacidad Ópt"})
        ac_sel = choose_series("Series (Alumnos/Capacidad)", ac_all, ac_all)
        if ac_sel:
            st.altair_chart(alt_lines(fold(ac_df, ac_sel), "", "Cantidad"), use_container_width=True)
        else:
            st.info("Seleccioná al menos una serie.")

    with col2:
        st.subheader("Admitidos, Egresados y Bajas")
        flows_all = ["Admitidos","Egresados","BajasTotales"]
        flows_sel = choose_series("Series (Flujos)", flows_all, flows_all)
        if flows_sel:
            st.altair_chart(alt_lines(fold(df, flows_sel), "", "Personas/año"), use_container_width=True)
        else:
            st.info("Seleccioná al menos una serie.")

    st.subheader("Calidad percibida")
    st.line_chart(df, x="Año", y="Calidad", use_container_width=True)

    st.caption("Tabla (primeros años)")
    st.dataframe(df.head(20), use_container_width=True)

# --------- Marketing & Selección ---------
with tab_mkt:
    sidebar_marketing_seleccion(st.session_state.params)
    p = st.session_state.params
    df, _ = simulate(p)

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Candidatos (stock)")
        st.line_chart(df, x="Año", y="CandidatosStock", use_container_width=True)

        st.subheader("Flujos: nuevos candidatos y admitidos")
        fl_all = ["NuevosCandidatos","Admitidos"]
        fl_sel = choose_series("Series (Funnel)", fl_all, fl_all)
        if fl_sel:
            st.altair_chart(alt_lines(fold(df, fl_sel), "", "Personas/año"), use_container_width=True)
        else:
            st.info("Seleccioná al menos una serie.")

    with c2:
        st.subheader("Budget y CAC")
        bc_all = ["Marketing","CAC"]
        bc_sel = choose_series("Series (Budget/CAC)", bc_all, bc_all)
        if bc_sel:
            st.altair_chart(alt_lines(fold(df, bc_sel), "", "Valor"), use_container_width=True)
        else:
            st.info("Seleccioná al menos una serie.")
        st.subheader("Calidad (para conversión)")
        st.line_chart(df, x="Año", y="Calidad", use_container_width=True)

# --------- Finanzas ---------
with tab_costos:
    sidebar_costos_inversion(st.session_state.params)
    p = st.session_state.params
    df, _ = simulate(p)

    st.subheader("Facturación")
    st.line_chart(df, x="Año", y="Facturacion", use_container_width=True)

    st.subheader("Composición OPEX (stacked)")
    opex_all = ["Sueldos","InversionInfra","InversionCalidadAlumno","Mantenimiento","Marketing","DocentesNuevas"]
    opex_sel = choose_series("Partidas OPEX", opex_all, opex_all)
    if opex_sel:
        opex_long = fold(df, opex_sel)
        stack = alt.Chart(opex_long).mark_area().encode(
            x="Año:Q",
            y=alt.Y("valor:Q", stack="zero", title="$ por año"),
            color=alt.Color("serie:N", legend=alt.Legend(orient="bottom", columns=3)),
            tooltip=["Año","serie","valor"]
        ).interactive()
        st.altair_chart(stack, use_container_width=True)
    else:
        st.info("Seleccioná al menos una partida de OPEX.")

    st.subheader("Resultados")
    res_all = ["ResultadoOperativo","ResultadoNeto"]
    res_sel = choose_series("Series (Resultados)", res_all, res_all)
    if res_sel:
        st.altair_chart(alt_lines(fold(df, res_sel), "", "$ por año"), use_container_width=True)
    else:
        st.info("Seleccioná al menos una serie.")

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
    sidebar_expansion(st.session_state.params)
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
