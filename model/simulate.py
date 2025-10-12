import numpy as np
import pandas as pd
from dataclasses import dataclass, asdict
from typing import Dict, Any, Tuple

@dataclass
class Params:
    # Horizonte
    years: int = 20

    # Mercado / demanda
    demanda_potencial: int = 6000

    # Calidad y dinámica (hacinamiento afecta calidad)
    calidad_base: float = 0.75
    beta_hacinamiento: float = 0.8

    # Bajas
    tasa_bajas_imprevistas: float = 0.01
    tasa_bajas_max_por_calidad: float = 0.12

    # Capacidad (12 grados)
    div_inicial_por_grado: int = 2
    cupo_optimo: int = 25    # óptimo para calidad
    cupo_maximo: int = 30    # límite físico (para referencia/visual; no topea admitidos)

    # Marketing & selección con STOCK de candidatos
    prop_mkt: float = 0.10
    mkt_floor: float = 30_000.0
    cac_base: float = 800.0
    k_saturacion: float = 2.0
    politica_seleccion: float = 0.50   # % de candidatos del stock que pasan el filtro
    alumnos_admitidos_objetivo: int = 300  # objetivo anual de admisión

    # Finanzas
    cuota_mensual: float = 500.0
    meses: int = 12
    pct_sueldos: float = 0.60
    inversion_infra_anual: float = 200_000.0
    inversion_calidad_por_alumno: float = 200.0
    mantenimiento_pct_facturacion: float = 0.08
    costo_docente_por_aula_nueva: float = 60_000.0
    # Activos / depreciación
    activos_inicial: float = 2_000_000.0
    tasa_depreciacion_anual: float = 0.05

    # Pipeline (1 división/ grado por 12 años) activado por año elegido
    pipeline_start_year: int = -1  # -1 desactivado; >=0 año de inicio
    costo_construccion_aula: float = 100_000.0

    # Iniciales de stocks
    g_inicial: int = 50                   # alumnos por grado inicial
    candidatos_inicial: float = 100.0     # stock de candidatos inicial

    # Sensibilidades de calidad a inversión (normalizadores)
    k_q_inv_alumno: float = 0.20
    k_q_infra_inversion: float = 0.15
    k_q_mantenimiento_netodep: float = 0.20
    ref_inv_alumno: float = 200.0
    ref_infra: float = 200_000.0
    ref_mant: float = 100_000.0

def simulate(par: Params) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    T = par.years
    G = 12
    t = np.arange(T+1)

    # Stocks
    Gk = np.zeros((T+1, G), dtype=float)   # alumnos por grado
    Div = np.zeros((T+1, G), dtype=float)  # divisiones por grado
    Cand = np.zeros(T+1, dtype=float)      # candidatos
    Act = np.zeros(T+1, dtype=float)       # activos (para depreciación)

    # Iniciales
    Gk[0, :] = par.g_inicial
    Div[0, :] = par.div_inicial_por_grado
    Cand[0] = par.candidatos_inicial
    Act[0] = par.activos_inicial

    # Series agregadas
    alumnos = np.zeros(T+1)
    calidad = np.zeros(T+1)
    facturacion = np.zeros(T+1)
    sueldos = np.zeros(T+1)
    inv_infra = np.zeros(T+1)
    inv_calidad_alumno = np.zeros(T+1)
    mantenimiento = np.zeros(T+1)
    docentes_nuevas = np.zeros(T+1)
    marketing = np.zeros(T+1)
    costos_opex = np.zeros(T+1)
    resultado_operativo = np.zeros(T+1)
    capex = np.zeros(T+1)
    resultado_neto = np.zeros(T+1)

    # Marketing y candidatos
    cac = np.zeros(T+1)
    nuevos_candidatos = np.zeros(T+1)
    admitidos = np.zeros(T+1)  # (antes "seleccionados"): ingresantes reales

    # Flujos de salida
    bajas_totales = np.zeros(T+1)
    egresados = np.zeros(T+1)  # = G12 del año anterior

    # Pipeline
    pipeline_construcciones = np.zeros(T+1)

    def cap_opt(row_div):
        return row_div * par.cupo_optimo

    def cap_max(row_div):
        return row_div * par.cupo_maximo

    def construir_en_anio(k: int) -> bool:
        if par.pipeline_start_year < 0:
            return False
        return (0 <= (k - par.pipeline_start_year) < 12)

    for k in range(T+1):
        # Totales y capacidades
        alumnos[k] = Gk[k, :].sum()
        Cap_opt_k = cap_opt(Div[k, :])
        Cap_max_k = cap_max(Div[k, :])
        Cap_total_max = Cap_max_k.sum()

        # Hacinamiento (para calidad) vs óptimo
        with np.errstate(divide='ignore', invalid='ignore'):
            hac_k = np.maximum(0.0, (Gk[k, :] - Cap_opt_k) / np.maximum(Cap_opt_k, 1.0))
        hac_prom = 0.0 if alumnos[k] <= 0 else float(np.dot(Gk[k, :], hac_k) / alumnos[k])

        # Facturación y costos base
        facturacion[k] = alumnos[k] * par.cuota_mensual * par.meses
        sueldos[k] = par.pct_sueldos * facturacion[k]
        inv_infra[k] = par.inversion_infra_anual
        inv_calidad_alumno[k] = par.inversion_calidad_por_alumno * alumnos[k]
        mantenimiento[k] = par.mantenimiento_pct_facturacion * facturacion[k]

        # Marketing (budget) y CAC
        saturacion = 0.0 if par.demanda_potencial <= 0 else min(1.0, alumnos[k] / par.demanda_potencial)
        margen_prov = facturacion[k] - (sueldos[k] + inv_calidad_alumno[k] + inv_infra[k] + mantenimiento[k])
        marketing[k] = max(par.mkt_floor, par.mkt_floor + par.prop_mkt * max(margen_prov, 0.0))
        cac[k] = par.cac_base * (1.0 + par.k_saturacion * saturacion)
        nuevos_candidatos[k] = 0.0 if cac[k] <= 0 else marketing[k] / cac[k]

        # Admitidos (ingresantes reales): gobernados por objetivo y política vs stock y demanda (NO por capacidad)
        gap_demanda = max(par.demanda_potencial - alumnos[k], 0.0)
        cuota = par.alumnos_admitidos_objetivo
        adm_teor = min(cuota, par.politica_seleccion * Cand[k])
        admitidos[k] = min(adm_teor, gap_demanda)

        # Bajas (usa calidad del período anterior para evitar simultaneidad)
        calidad_prev = calidad[k-1] if k > 0 else par.calidad_base
        tasa_bajas_total = min(1.0, par.tasa_bajas_imprevistas + (1.0 - calidad_prev) * par.tasa_bajas_max_por_calidad)
        baj_k = tasa_bajas_total * Gk[k, :]
        bajas_totales[k] = baj_k.sum()

        # Egresados = alumnos de G12 del año anterior
        eg_prev = Gk[k-1, 11] if k > 0 else 0.0
        egresados[k] = eg_prev

        # Calidad con efectos de inversión y mantenimiento vs depreciación
        dep = par.tasa_depreciacion_anual * Act[k]
        inv_alum_norm = (par.inversion_calidad_por_alumno / max(par.ref_inv_alumno, 1e-9))
        infra_norm = (inv_infra[k] / max(par.ref_infra, 1e-9))
        mant_norm = ((mantenimiento[k] - dep) / max(par.ref_mant, 1e-9))
        calidad_raw = (par.calidad_base
                       - par.beta_hacinamiento * hac_prom
                       + par.k_q_inv_alumno * inv_alum_norm
                       + par.k_q_infra_inversion * infra_norm
                       + par.k_q_mantenimiento_netodep * mant_norm)
        calidad[k] = float(np.clip(calidad_raw, 0.0, 1.0))

        # OPEX (docentes_nuevas se completa tras pipeline)
        costos_opex[k] = sueldos[k] + inv_infra[k] + inv_calidad_alumno[k] + mantenimiento[k] + marketing[k]
        resultado_operativo[k] = facturacion[k] - costos_opex[k]

        if k < T:
            # Pipeline
            build = construir_en_anio(k)
            capex[k] = par.costo_construccion_aula if build else 0.0
            docentes_nuevas[k] = par.costo_docente_por_aula_nueva if build else 0.0

            # OPEX final (sumando docentes de aulas nuevas)
            costos_opex[k] += docentes_nuevas[k]
            resultado_operativo[k] = facturacion[k] - costos_opex[k]
            resultado_neto[k] = resultado_operativo[k] - capex[k]

            # Stocks:
            # 1) Candidatos
            next_C = max(Cand[k] + nuevos_candidatos[k] - admitidos[k], 0.0)

            # 2) Alumnos por grado
            next_G = np.zeros(G, dtype=float)
            # Entradas a G1: admitidos; salidas: bajas
            next_G[0] = Gk[k, 0] + admitidos[k] - baj_k[0]
            # Promoción k→k+1 (sin egresos intermedios), restando bajas locales
            for gi in range(1, G):
                promo = Gk[k, gi-1] - baj_k[gi-1]
                next_G[gi] = Gk[k, gi] + promo - baj_k[gi]
            # Egreso en 12º: restar egresados (del año anterior)
            next_G[11] = max(next_G[11] - eg_prev, 0.0)

            # 3) Divisiones
            next_D = Div[k, :].copy()
            if build:
                tramo = (k - par.pipeline_start_year) % 12 if par.pipeline_start_year >= 0 else 0
                next_D[tramo] += 1.0
                pipeline_construcciones[k] = 1.0

            # 4) Activos (capex suma; inversión_infra es OPEX)
            next_Act = Act[k] + capex[k] - dep

            # Avances
            Gk[k+1, :] = np.maximum(0.0, next_G)
            Div[k+1, :] = next_D
            Cand[k+1] = next_C
            Act[k+1] = max(next_Act, 0.0)
        else:
            capex[k] = 0.0
            docentes_nuevas[k] = 0.0
            resultado_neto[k] = resultado_operativo[k]

    aulas = Div.sum(axis=1)

    # Redondeo de presentación
    def rint(a): return np.rint(a).astype(int)

    df = pd.DataFrame({
        "Año": t,
        "AlumnosTotales": rint(Gk.sum(axis=1)),
        "Calidad": calidad,
        "AulasTotales": rint(aulas),
        "CapacidadMaxTotal": rint((Div * par.cupo_maximo).sum(axis=1)),
        "CapacidadOptTotal": rint((Div * par.cupo_optimo).sum(axis=1)),
        "Facturacion": facturacion,
        "Sueldos": sueldos,
        "InversionInfra": inv_infra,
        "InversionCalidadAlumno": inv_calidad_alumno,
        "Mantenimiento": mantenimiento,
        "DocentesNuevas": docentes_nuevas,
        "Marketing": marketing,
        "CostosOPEX": sueldos + inv_infra + inv_calidad_alumno + mantenimiento + marketing + docentes_nuevas,
        "ResultadoOperativo": resultado_operativo,
        "CAPEX": capex,
        "ResultadoNeto": resultado_neto,
        "CAC": cac,
        "CandidatosStock": rint(Cand),
        "NuevosCandidatos": rint(nuevos_candidatos),
        "Admitidos": rint(admitidos),
        "BajasTotales": rint(bajas_totales),
        "Egresados": rint(egresados),
        "PipelineConstrucciones": pipeline_construcciones,
        "Activos": Act
    })

    # Series por grado
    for gi in range(G):
        df[f"G{gi+1}"] = rint(Gk[:, gi])
        df[f"DivG{gi+1}"] = Div[:, gi]
        Cap_opt_series = Div[:, gi] * par.cupo_optimo
        with np.errstate(divide='ignore', invalid='ignore'):
            hac_series = np.maximum(0.0, (Gk[:, gi] - Cap_opt_series) / np.maximum(Cap_opt_series, 1.0))
        df[f"HacG{gi+1}"] = hac_series

    meta = {"params": asdict(par)}
    return df, meta
