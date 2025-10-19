import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
from textwrap import dedent

# Import your model exactly as you do today
try:
    from model.simulate import Params, simulate
except Exception:
    # Fallback for running in a flat folder alongside simulate.py
    from simulate import Params, simulate

st.set_page_config(page_title="School SD Simulator — Modo Clase", layout="wide")
st.title("Modelo de Dinámica de Sistemas — Colegio · 🧑‍🏫 Modo Clase")

# ------------------------------
# Helpers
# ------------------------------
def ensure_params_defaults(p):
    defaults = Params()
    for k, v in defaults.__dict__.items():
        if not hasattr(p, k):
            setattr(p, k, v)
    return p

def fold(df: pd.DataFrame, cols, x="Año"):
    return df[[x] + cols].melt(id_vars=[x], value_vars=cols, var_name="serie", value_name="valor")

def alt_lines(df_long: pd.DataFrame, y_title: str):
    sel = alt.selection_point(fields=["serie"], bind="legend")
    base = alt.Chart(df_long).encode(
        x=alt.X("Año:Q", axis=alt.Axis(grid=True)),
        y=alt.Y("valor:Q", title=y_title),
        color="serie:N",
        tooltip=["Año:Q","serie:N","valor:Q"]
    )
    return base.mark_line(point=True).add_params(sel).transform_filter(sel).properties(height=280)

def kpis(df: pd.DataFrame):
    c1, c2, c3, c4, c5 = st.columns(5)
    first, last = df.iloc[0], df.iloc[-1]
    delta_fmt = lambda v0, v1: f"{( (v1 - v0) / v0 * 100.0 ):.1f}%" if v0 else "—"
    with c1:
        st.metric("Alumnos", int(last["Alumnos"]), delta=delta_fmt(first["Alumnos"], last["Alumnos"]))
    with c2:
        st.metric("Calidad", f"{last['Calidad']:.2f}", delta=f"{(last['Calidad']-first['Calidad']):+.2f}")
    with c3:
        st.metric("Facturación anual", f"$ {int(last['Facturacion'])}", delta=int(last["Facturacion"]-first["Facturacion"]))
    with c4:
        st.metric("Resultado Neto", f"$ {int(last['ResultadoNeto'])}", delta=int(last["ResultadoNeto"]-first["ResultadoNeto"]))
    with c5:
        st.metric("Caja", f"$ {int(last['Caja'])}", delta=int(last["Caja"]-first["Caja"]))

def load_params_from_json(txt: str):
    try:
        import json
        d = json.loads(txt)
        p = Params()
        for k, v in d.items():
            if hasattr(p, k):
                setattr(p, k, v)
        return ensure_params_defaults(p)
    except Exception as e:
        st.error(f"No se pudo cargar el preset: {e}")
        return None

# ------------------------------
# Session state bootstrap
# ------------------------------
if "params" not in st.session_state:
    st.session_state.params = ensure_params_defaults(Params())

if "snapA" not in st.session_state:
    st.session_state.snapA = None
if "snapB" not in st.session_state:
    st.session_state.snapB = None

p = st.session_state.params

# ------------------------------
# Sidebar: presets y acciones rápidas
# ------------------------------
st.sidebar.header("🎛️ Presets de clase")
preset = st.sidebar.selectbox(
    "Elegir preset",
    [
        "🟢 Base (status quo)",
        "📉 Crisis natalidad (-8% demanda anual)",
        "💸 Shock económico (+30% CAC, -10% selectividad)",
        "🎓 Apuesta a calidad (+20% inversión en calidad, cupo óptimo -2)"
    ],
    index=0
)

if st.sidebar.button("Aplicar preset", use_container_width=True):
    if preset.startswith("🟢"):
        p = Params()
    elif preset.startswith("📉"):
        p = Params()
        p.tasa_descenso_demanda = 0.08
    elif preset.startswith("💸"):
        p = Params()
        p.cac_base = p.cac_base * 1.3
        p.politica_seleccion = max(0.0, p.politica_seleccion - 0.10)
    elif preset.startswith("🎓"):
        p = Params()
        p.inversion_calidad_por_alumno = p.inversion_calidad_por_alumno * 1.2
        p.cupo_optimo = max(10, p.cupo_optimo - 2)
    st.session_state.params = ensure_params_defaults(p)
    st.success("Preset aplicado.")

st.sidebar.divider()
st.sidebar.subheader("Acciones")
if st.sidebar.button("🔁 Reset a valores por defecto", use_container_width=True):
    st.session_state.params = ensure_params_defaults(Params())
    st.success("Parámetros reseteados.")

uploaded = st.sidebar.file_uploader("📤 Cargar preset (.json)", type=["json"])
if uploaded is not None:
    txt = uploaded.read().decode("utf-8")
    newp = load_params_from_json(txt)
    if newp:
        st.session_state.params = newp
        st.success("Preset cargado.")

st.sidebar.divider()
st.sidebar.caption("Tip: descarga tus parámetros actuales en la pestaña Exportar.")

# ------------------------------
# Panel principal
# ------------------------------
tab_inicio, tab_sim, tab_comp, tab_actividades, tab_export = st.tabs(
    ["🏠 Inicio", "📊 Simulación", "🆚 Comparar escenarios", "🧑‍🏫 Actividades para clase", "📥 Exportar"]
)

with tab_inicio:
    st.markdown(dedent("""
    ### Novedades para docencia
    - **Tarjetas KPI** al inicio para leer el escenario de un vistazo.
    - **Snapshots A/B** para comparar dos escenarios (antes/después).
    - **Presets didácticos** (crisis natalidad, shock económico, apuesta a calidad).
    - **Cargar/Descargar presets** en JSON para tus clases.
    - **Guía de actividades** con consignas listadas para facilitación.
    """))
    st.info("Ajusta parámetros en la barra lateral (izquierda) y mira abajo.")

with tab_sim:
    # Ejecutar simulación
    df, meta = simulate(st.session_state.params)
    kpis(df)
    st.subheader("Alumnos, Calidad y Resultado Neto")
    cols = ["Alumnos", "Calidad", "ResultadoNeto"]
    st.altair_chart(alt_lines(fold(df, cols), "Valor"), use_container_width=True)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Dinámica de Admisiones**")
        st.altair_chart(alt_lines(fold(df, ["NuevosCandidatos","Admitidos","Rechazados"]), "Personas/año"), use_container_width=True)
    with c2:
        st.markdown("**Sostenibilidad Económica**")
        st.altair_chart(alt_lines(fold(df, ["Facturacion","CostosOperativos","ResultadoNeto"]), "$/año"), use_container_width=True)

    st.divider()
    c3, c4 = st.columns(2)
    with c3:
        if st.button("📌 Guardar Snapshot A"):
            st.session_state.snapA = {"df": df.copy(), "params": meta["params"]}
            st.success("Snapshot A guardado.")
    with c4:
        if st.button("📌 Guardar Snapshot B"):
            st.session_state.snapB = {"df": df.copy(), "params": meta["params"]}
            st.success("Snapshot B guardado.")

with tab_comp:
    st.markdown("Compara **A vs B**. Guarda los snapshots en la pestaña *Simulación*.")
    snapA = st.session_state.snapA
    snapB = st.session_state.snapB
    if not snapA or not snapB:
        st.warning("Faltan snapshots A y/o B.")
    else:
        st.success("Comparando snapshots guardados.")
        dfA = snapA["df"].assign(escenario="A")
        dfB = snapB["df"].assign(escenario="B")
        dfC = pd.concat([dfA, dfB], ignore_index=True)

        def comp_chart(cols, ytitle):
            long = dfC[["Año","escenario"] + cols].melt(id_vars=["Año","escenario"], var_name="serie", value_name="valor")
            long["serie"] = long["escenario"] + " · " + long["serie"]
            return alt_lines(long, ytitle)

        st.altair_chart(comp_chart(["Alumnos"], "Alumnos"), use_container_width=True)
        st.altair_chart(comp_chart(["Calidad"], "Calidad"), use_container_width=True)
        st.altair_chart(comp_chart(["ResultadoNeto","Caja"], "$/año"), use_container_width=True)

        with st.expander("Ver parámetros de cada snapshot"):
            c1, c2 = st.columns(2)
            with c1:
                st.write("**Snapshot A — parámetros**")
                st.json(snapA["params"])
            with c2:
                st.write("**Snapshot B — parámetros**")
                st.json(snapB["params"])

with tab_actividades:
    st.markdown(dedent("""
    ### Guía rápida para clase
    1) **Explora un preset** (sidebar) y discute hipótesis: ¿qué esperarían que pase con *alumnos*, *calidad* y *caja*?
    2) **Ajusta 1–2 palancas** (p. ej., *política de admisiones*, *cupo óptimo*, *inversión en calidad*).
    3) **Guarda Snapshot A**, cambia una palanca e **iteraa**. Guarda **Snapshot B**.
    4) **Compara A vs B** y redacta 3 decisiones operativas para el próximo año.
    5) **Pregunta de reflexión**: si crece la demanda orgánica por calidad, ¿qué pasa con el CAC y la selectividad a 3–5 años?
    6) **Extensión**: simula *crisis de natalidad* y define un plan de resiliencia de admisiones y costos.

    ### Sugerencias de evaluación formativa
    - Explicar con palabras propias la relación *hacinamiento → calidad → bajas → demanda*.
    - Identificar una métrica adelantada (*leading*) y una rezagada (*lagging*).
    - Entregar un breve memo (5–8 líneas) con *trade‑offs* de corto vs. largo plazo.
    """))
    st.info("Usa las pestañas **Simulación** y **Comparar** para completar las consignas.")

with tab_export:
    st.subheader("Descargar resultados y preset")
    df, meta = simulate(st.session_state.params)
    st.download_button("Descargar resultados (.csv)", data=df.to_csv(index=False).encode("utf-8"),
                       file_name="resultados_simulacion.csv", mime="text/csv", use_container_width=True)
    st.download_button("Descargar preset (.json)", data=pd.Series(meta["params"]).to_json().encode("utf-8"),
                       file_name="preset_params.json", mime="application/json", use_container_width=True)
    with st.expander("Parámetros actuales"):
        st.json(meta["params"])
