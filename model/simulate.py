
import numpy as np
import pandas as pd
from dataclasses import dataclass, asdict
from typing import Dict, Any, Tuple

@dataclass
class Params:
    years: int = 20
    demanda_potencial: int = 1000
    calidad_base: float = 0.75
    beta_hacinamiento: float = 0.8
    tasa_egreso_base: float = 0.10
    gamma_hacinamiento: float = 0.20
    tasa_bajas_imprevistas: float = 0.03
    tasa_bajas_max_por_calidad: float = 0.12
    div_inicial_por_grado: int = 2
    cupo_optimo: int = 30
    prop_mkt: float = 0.10
    mkt_floor: float = 30_000.0
    cac_base: float = 800.0
    k_saturacion: float = 2.0
    cuota_mensual: float = 80.0
    meses: int = 12
    costo_fijo_anual: float = 2_000_000.0
    costo_variable_alumno: float = 300.0
    costo_docente_por_aula: float = 60_000.0
    pipeline_activo: bool = False
    pipeline_auto_por_hacinamiento: bool = False
    umbral_hacinamiento_g1: float = 0.05
    pipeline_financiacion_externa: bool = False
    capex_pct_sobre_facturacion: float = 0.20
    colchon_financiero: float = 200_000.0
    costo_construccion_aula: float = 100_000.0
    g_inicial: int = 25

def simulate(par: Params):
    T = par.years; G = 12
    t = np.arange(T+1)
    Gk = np.zeros((T+1, G)); Gk[0,:] = par.g_inicial
    Div = np.zeros((T+1, G)); Div[0,:] = par.div_inicial_por_grado

    alumnos = np.zeros(T+1); calidad = np.zeros(T+1)
    fact = np.zeros(T+1); opex = np.zeros(T+1)
    rop = np.zeros(T+1); capex = np.zeros(T+1); rnet = np.zeros(T+1)
    budget = np.zeros(T+1); cac = np.zeros(T+1); cands = np.zeros(T+1)
    ing1 = np.zeros(T+1); eg12 = np.zeros(T+1); pipe = np.zeros(T+1)
    start = None

    for k in range(T+1):
        alumnos[k] = Gk[k,:].sum()
        Cap_k = Div[k,:] * par.cupo_optimo
        hac_k = np.maximum(0, (Gk[k,:] - Cap_k)/np.maximum(Cap_k,1))
        hac_prom = 0 if alumnos[k]==0 else float((Gk[k,:]*hac_k).sum()/alumnos[k])
        calidad[k] = np.clip(par.calidad_base - par.beta_hacinamiento*hac_prom, 0, 1)

        fact[k] = alumnos[k]*par.cuota_mensual*par.meses
        opex[k] = par.costo_fijo_anual + par.costo_variable_alumno*alumnos[k] + par.costo_docente_por_aula*Div[k,:].sum()
        rop[k] = fact[k] - opex[k]

        sat = 0 if par.demanda_potencial<=0 else min(1, alumnos[k]/par.demanda_potencial)
        budget[k] = max(par.mkt_floor, par.mkt_floor + par.prop_mkt*max(rop[k],0))
        cac[k] = par.cac_base*(1 + par.k_saturacion*sat)
        cands[k] = 0 if cac[k]<=0 else budget[k]/cac[k]
        gap = max(par.demanda_potencial - alumnos[k], 0)
        ing1[k] = min(gap, cands[k]*calidad[k])

        tb = min(1, par.tasa_bajas_imprevistas + (1 - calidad[k]) * par.tasa_bajas_max_por_calidad)
        eg_k = (par.tasa_egreso_base + par.gamma_hacinamiento*hac_k)*Gk[k,:]
        baj_k = tb*Gk[k,:]
        eg12[k] = eg_k[-1] + baj_k[-1]

        if k < T:
            if (start is None) and par.pipeline_auto_por_hacinamiento:
                cap_g1 = Cap_k[0]
                hac1 = 0 if cap_g1<=0 else max(0, (Gk[k,0]-cap_g1)/cap_g1)
                ok_fin = True
                if not par.pipeline_financiacion_externa:
                    lim = par.capex_pct_sobre_facturacion*fact[k]
                    disp = max(rop[k]-par.colchon_financiero, 0)
                    ok_fin = max(0, min(lim, disp)) >= par.costo_construccion_aula
                if (hac1 > par.umbral_hacinamiento_g1) and ok_fin:
                    start = k

            build = False
            if par.pipeline_activo or (start is not None):
                s = 0 if start is None else start
                build = (0 <= (k - s) < 12)

            capex[k] = par.costo_construccion_aula if build else 0
            rnet[k] = rop[k] - capex[k]

            nextG = np.zeros(G)
            nextG[0] = Gk[k,0] + ing1[k] - eg_k[0] - baj_k[0]
            for gi in range(1,G):
                promo = Gk[k,gi-1] - eg_k[gi-1] - baj_k[gi-1]
                nextG[gi] = Gk[k,gi] + promo - eg_k[gi] - baj_k[gi]

            nextD = Div[k,:].copy()
            if build:
                tramo = (k if start is None else k - start) % 12
                nextD[tramo] += 1.0
                pipe[k] = 1.0

            Gk[k+1,:] = np.maximum(0,nextG)
            Div[k+1,:] = nextD
        else:
            capex[k] = 0
            rnet[k] = rop[k] - capex[k]

    aulas = Div.sum(axis=1)
    df = pd.DataFrame({
        "Año": t,
        "AlumnosTotales": alumnos,
        "Calidad": calidad,
        "AulasTotales": aulas,
        "Facturacion": fact,
        "CostosOPEX": opex,
        "ResultadoOperativo": rop,
        "CAPEX": capex,
        "ResultadoNeto": rnet,
        "BudgetMkt": budget,
        "CAC": cac,
        "Candidatos": cands,
        "Ingresantes_G1": ing1,
        "Egresados_12": eg12,
        "PipelineConstrucciones": pipe,
    })
    for gi in range(G):
        df[f"G{gi+1}"] = Gk[:,gi]
        df[f"DivG{gi+1}"] = Div[:,gi]
        cap_series = Div[:,gi]*par.cupo_optimo
        hac_series = np.maximum(0,(Gk[:,gi]-cap_series)/np.maximum(cap_series,1))
        df[f"HacG{gi+1}"] = hac_series

    return df, {"params": {
        "years": par.years, "demanda_potencial": par.demanda_potencial,
        "calidad_base": par.calidad_base, "beta_hacinamiento": par.beta_hacinamiento,
        "tasa_egreso_base": par.tasa_egreso_base, "gamma_hacinamiento": par.gamma_hacinamiento,
        "tasa_bajas_imprevistas": par.tasa_bajas_imprevistas, "tasa_bajas_max_por_calidad": par.tasa_bajas_max_por_calidad,
        "div_inicial_por_grado": par.div_inicial_por_grado, "cupo_optimo": par.cupo_optimo,
        "prop_mkt": par.prop_mkt, "mkt_floor": par.mkt_floor, "cac_base": par.cac_base, "k_saturacion": par.k_saturacion,
        "cuota_mensual": par.cuota_mensual, "meses": par.meses, "costo_fijo_anual": par.costo_fijo_anual,
        "costo_variable_alumno": par.costo_variable_alumno, "costo_docente_por_aula": par.costo_docente_por_aula,
        "pipeline_activo": par.pipeline_activo, "pipeline_auto_por_hacinamiento": par.pipeline_auto_por_hacinamiento,
        "umbral_hacinamiento_g1": par.umbral_hacinamiento_g1, "pipeline_financiacion_externa": par.pipeline_financiacion_externa,
        "capex_pct_sobre_facturacion": par.capex_pct_sobre_facturacion, "colchon_financiero": par.colchon_financiero,
        "costo_construccion_aula": par.costo_construccion_aula, "g_inicial": par.g_inicial
    }}
