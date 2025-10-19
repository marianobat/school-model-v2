
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

def canonicalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Renombra columnas a los nombres esperados por la app.
    Añade aquí cualquier mapeo adicional si cambian nombres en tu modelo.
    """
    colmap = {}
    # Estándares que usa la app:
    if "Alumnos" not in df.columns and "AlumnosTotales" in df.columns:
        colmap["AlumnosTotales"] = "Alumnos"
    if "CostosOperativos" not in df.columns and "CostosOPEX" in df.columns:
        colmap["CostosOPEX"] = "CostosOperativos"
    if "ResultadoNeto" not in df.columns and "Resultado" in df.columns:
        colmap["Resultado"] = "ResultadoNeto"
    if "Facturacion" not in df.columns and "Ingresos" in df.columns:
        colmap["Ingresos"] = "Facturacion"
    if "Caja" not in df.columns and "Cash" in df.columns:
        colmap["Cash"] = "Caja"
    if "NuevosCandidatos" not in df.columns and "Candidatos" in df.columns:
        colmap["Candidatos"] = "NuevosCandidatos"
    if "Rechazados" not in df.columns and "NoAdmitidos" in df.columns:
        colmap["NoAdmitidos"] = "Rechazados"
    if "Admitidos" not in df.columns and "Ingresantes" in df.columns:
        colmap["Ingresantes"] = "Admitidos"
    if "Calidad" not in df.columns and "IndiceCalidad" in df.columns:
        colmap["IndiceCalidad"] = "Calidad"
    if not colmap:
        return df
    return df.rename(columns=colmap)

def fold(df: pd.DataFrame, cols, x="Año"):
    # Garantiza que existan las columnas a graficar
    missing = [c for c in cols if c not in df.columns]
    if missing:
        st.warning(f"Faltan columnas para graficar: {missing}")
        cols = [c for c in cols if c in df.columns]
        if not cols:
            return pd.DataFrame({x: [], "serie": [], "valor": []})
    return df[[x] + cols].melt(id_vars=[x], value_vars=cols, var_name="serie", value_name="valor")

def alt_lines(df_long: pd.DataFrame, y_title: str):
    if df_long.empty:
        return alt.Chart(pd.DataFrame({"Año": [], "valor": [], "serie": []})).mark_line()
    sel = alt.selection_point(fields=["serie"], bind="legend")
    base = alt.Chart(df_long).encode(
        x=alt.X("Año:Q", axis=alt.Axis(grid=True)),
        y=alt.Y("valor:Q", title=y_title),
        color="serie:N",
        tooltip=["Año:Q","serie:N","valor:Q"]
    )
    return base.mark_line(point=True).add_params(sel).transform_filter(sel).properties(height=280)

def kpis(df: pd.DataFrame):
    # Evita KeyError si faltan columnas
    required = ["Alumnos","Calidad","Facturacion","ResultadoNeto","Caja"]
    for r in required:
        if r not in df.columns:
            st.warning(f"KPIs: falta la columna '{r}'. Revísala en el modelo o en 'canonicalize_columns'.")
    # Usa valores existentes con fallback a 0
    def get(row, key, default=0):
        return row[key] if key in row and pd.notna(row[key]) else default

    c1, c2, c3, c4, c5 = st.columns(5)
    first, last = df.iloc[0], df.iloc[-1]
    def delta_fmt(v0, v1):
        try:
            return f"{((v1 - v0) / v0 * 100.0):.1f}%" if v0 else "—"
        except Exception:
            return "—"
    with c1:
        st.metric("Alumnos", int(get(last, "Alumnos")), delta=delta_fmt(get(first, "Alumnos"), get(last, "Alumnos")))
    with c2:
        st.metric("Calidad", f"{get(last, 'Calidad', 0):.2f}", delta=f"{(get(last,'Calidad',0)-get(first,'Calidad',0)):+.2f}")
    with c3:
        st.metric("Facturación anual", f"$ {int(get(last, 'Facturacion'))}", delta=int(get(last,"Facturacion")-get(first,"Facturacion")))
    with c4:
        st.metric("Resultado Neto", f"$ {int(get(last, 'ResultadoNeto'))}", delta=int(get(last,"ResultadoNeto")-get(first,"ResultadoNeto")))
    with c5:
        st.metric("Caja", f"$ {int(get(last, 'Caja'))}", delta=int(get(last,"Caja")-get(first,"Caja")))

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
        # suposición: tu modelo use 'tasa_descenso_demanda' o similar
        if hasattr(p, "tasa_descenso_demanda"):
            p.tasa_descenso_demanda = 0.08
    elif preset.startswith("💸"):
        p = Params()
        if hasattr(p, "cac_base"):
            p.cac_base = p.cac_base * 1.3
        if hasattr(p, "politica_seleccion"):
            p.politica_seleccion = max(0.0, p.politica_seleccion - 0.10)
    elif preset.startswith("🎓"):
        p = Params()
        if hasattr(p, "inversion_calidad_por_alumno"):
            p.inversion_calidad_por_alumno = p.inversion_calidad_por_alumno * 1.2
        if hasattr(p, "cupo_optimo"):
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
    df = canonicalize_columns(df)
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
            st.session_state.snapA = {"df": df.copy(), "params": meta.get("params", {})}
            st.success("Snapshot A guardado.")
    with c4:
        if st.button("📌 Guardar Snapshot B"):
            st.session_state.snapB = {"df": df.copy(), "params": meta.get("params", {})}
            st.success("Snapshot B guardado.")

with tab_comp:
    st.markdown("Compara **A vs B**. Guarda los snapshots en la pestaña *Simulación*.")
    snapA = st.session_state.snapA
    snapB = st.session_state.snapB
    if not snapA or not snapB:
        st.warning("Faltan snapshots A y/o B.")
    else:
        st.success("Comparando snapshots guardados.")
        dfA = canonicalize_columns(snapA["df"]).assign(escenario="A")
        dfB = canonicalize_columns(snapB["df"]).assign(escenario="B")
        dfC = pd.concat([dfA, dfB], ignore_index=True)

        def comp_chart(cols, ytitle):
            long = dfC[["Año","escenario"] + [c for c in cols if c in dfC.columns]].melt(id_vars=["Año","escenario"], var_name="serie", value_name="valor")
            long["serie"] = long["escenario"] + " · " + long["serie"]
            return alt_lines(long, ytitle)

        st.altair_chart(comp_chart(["Alumnos"], "Alumnos"), use_container_width=True)
        st.altair_chart(comp_chart(["Calidad"], "Calidad"), use_container_width=True)
        st.altair_chart(comp_chart(["ResultadoNeto","Caja"], "$/año"), use_container_width=True)

        with st.expander("Ver parámetros de cada snapshot"):
            c1, c2 = st.columns(2)
            with c1:
                st.write("**Snapshot A — parámetros**")
                st.json(snapA.get("params", {}))
            with c2:
                st.write("**Snapshot B — parámetros**")
                st.json(snapB.get("params", {}))

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
    df = canonicalize_columns(df)
    st.download_button("Descargar resultados (.csv)", data=df.to_csv(index=False).encode("utf-8"),
                       file_name="resultados_simulacion.csv", mime="text/csv", use_container_width=True)
    # meta.get('params', {}) permite no romper si tu simulate no devuelve params
    params_json = pd.Series(meta.get("params", {})).to_json()
    st.download_button("Descargar preset (.json)", data=params_json.encode("utf-8"),
                       file_name="preset_params.json", mime="application/json", use_container_width=True)
    with st.expander("Parámetros actuales"):
        st.json(meta.get("params", {}))
