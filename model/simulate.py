import numpy as np
import pandas as pd
from dataclasses import dataclass, asdict
from typing import Dict, Any, Tuple

@dataclass
class Params:
    # Horizonte
    years: int = 20

    # Demanda/mercado (ajuste: demanda inicial 6000)
    demanda_potencial: int = 6000

    # Calidad y dinámicas
    calidad_base: float = 0.75
    beta_hacinamiento: float = 0.8
    # NOTA: mantenemos "bajas por calidad" y "bajas imprevistas" (ajuste: bajas imprevistas 0.01)
    tasa_bajas_imprevistas: float = 0.01
    tasa_bajas_max_por_calidad: float = 0.12
    gamma_hacinamiento: float = 0.20  # si quieres reactivar egreso sensible a hacinamiento

    # Capacidad / aulas por grado (12 grados)
    div_inicial_por_grado: int = 2    # ajuste: 2
    cupo_optimo: int = 30             # usado para hacinamiento (calidad)
    cupo_maximo: int = 35             # NUEVO: capacidad dura (límite físico)

    # Marketing & Captación (con STOCK de candidatos)
    prop_mkt: float = 0.10
    mkt_floor: float = 30_000.0
    cac_base: float = 800.0
    k_saturacion: float = 2.0
    politica_seleccion: float = 0.50  # NUEVO: 0..1 % candidatos aceptados/año

    # Finanzas
    cuota_mensual: float = 80.0
    meses: int = 12
    costo_fijo_anual: float = 2_000_000.0
    costo_variable_alumno: float = 300.0
    costo_docente_por_aula: float = 60_000.0
    costo_mantenimiento_anual: float = 120_000.0  # NUEVO: para composición OPEX

    # Pipeline de expansión (12 años, 1 división por grado)
    pipeline_activo: bool = False
    pipeline_auto_por_hacinamiento: bool = False
    umbral_hacinamiento_g1: float = 0.05
    pipeline_financiacion_externa: bool = False
    capex_pct_sobre_facturacion: float = 0.20
    colchon_financiero: float = 200_000.0
    costo_construccion_aula: float = 100_000.0

    # Iniciales
    g_inicial: int = 25               # alumnos por grado
    candidatos_inicial: float = 100.0 # NUEVO: stock inicial de candidatos

def simulate(par: Params) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    T = par.years
    G = 12
    t = np.arange(T+1)

    # Estados
    Gk = np.zeros((T+1, G), dtype=float)  # alumnos por grado
    Div = np.zeros((T+1, G), dtype=float) # divisiones por grado
    Cand = np.zeros(T+1, dtype=float)     # NUEVO: stock de candidatos

    # Iniciales
    Gk[0, :] = par.g_inicial
    Div[0, :] = par.div_inicial_por_grado
    Cand[0] = par.candidatos_inicial

    # Series agregadas
    alumnos = np.zeros(T+1)
    calidad = np.zeros(T+1)
    facturacion = np.zeros(T+1)
    costo_docentes = np.zeros(T+1)
    costo_variable = np.zeros(T+1)
    costo_marketing = np.zeros(T+1)
    costo_mantenimiento = np.zeros(T+1)
    costo_fijo = np.zeros(T+1)
    costos_opex = np.zeros(T+1)
    resultado_operativo = np.zeros(T+1)
    capex = np.zeros(T+1)
    resultado_neto = np.zeros(T+1)

    # Marketing
    budget_mkt = np.zeros(T+1)
    cac = np.zeros(T+1)
    nuevos_candidatos = np.zeros(T+1)
    seleccionados = np.zeros(T+1)     # aceptados desde candidatos → G1 (ingresantes)

    # Bajas / egresos
    bajas_totales = np.zeros(T+1)
    egresos_base = np.zeros(T+1)      # ajuste: alumnos/12 (base)

    # Pipeline
    pipeline_construcciones = np.zeros(T+1)
    pipeline_start = None

    # Helpers
    def capacidad_optima_por_grado(Div_row):
        return Div_row * par.cupo_optimo

    def capacidad_max_por_grado(Div_row):
        return Div_row * par.cupo_maximo

    for k in range(T+1):
        # Totales y capacidades
        alumnos[k] = Gk[k, :].sum()
        Cap_opt_k = capacidad_optima_por_grado(Div[k, :])
        Cap_max_k = capacidad_max_por_grado(Div[k, :])

        Cap_total_max = Cap_max_k.sum()

        # Hacinamiento (para calidad) usando cupo ÓPTIMO
        with np.errstate(divide='ignore', invalid='ignore'):
            hac_k = np.maximum(0.0, (Gk[k, :] - Cap_opt_k) / np.maximum(Cap_opt_k, 1.0))
        hac_prom = 0.0 if alumnos[k] <= 0 else float(np.dot(Gk[k, :], hac_k) / alumnos[k])

        # Calidad
        calidad[k] = np.clip(par.calidad_base - par.beta_hacinamiento * hac_prom, 0.0, 1.0)

        # Finanzas OPEX (componentes)
        facturacion[k] = alumnos[k] * par.cuota_mensual * par.meses
        total_aulas = Div[k, :].sum()
        costo_docentes[k] = par.costo_docente_por_aula * total_aulas
        costo_variable[k] = par.costo_variable_alumno * alumnos[k]
        # Marketing budget (se contabiliza como OPEX)
        saturacion = 0.0 if par.demanda_potencial <= 0 else min(1.0, alumnos[k] / par.demanda_potencial)
        budget_mkt[k] = max(par.mkt_floor, par.mkt_floor + par.prop_mkt * max(facturacion[k] - (par.costo_fijo_anual + costo_variable[k] + costo_docentes[k] + par.costo_mantenimiento_anual), 0.0))
        costo_marketing[k] = budget_mkt[k]
        costo_mantenimiento[k] = par.costo_mantenimiento_anual
        costo_fijo[k] = par.costo_fijo_anual

        costos_opex[k] = costo_docentes[k] + costo_variable[k] + costo_marketing[k] + costo_mantenimiento[k] + costo_fijo[k]
        resultado_operativo[k] = facturacion[k] - costos_opex[k]

        # CAC y candidatos (STOCK)
        cac[k] = par.cac_base * (1.0 + par.k_saturacion * saturacion)
        nuevos_candidatos[k] = 0.0 if cac[k] <= 0 else budget_mkt[k] / cac[k]

        # Selección desde stock de candidatos a alumnos (G1)
        # Límite por política de selección y por capacidad dura (cupo MÁXIMO)
        capacidad_disponible = max(Cap_total_max - alumnos[k], 0.0)  # total
        gap_demanda = max(par.demanda_potencial - alumnos[k], 0.0)
        seleccion_teorica = par.politica_seleccion * Cand[k]
        seleccionados[k] = min(seleccion_teorica, capacidad_disponible, gap_demanda)

        # Bajas por calidad + imprevistas (aplican a todos los grados con misma tasa)
        tasa_bajas_total = min(1.0, par.tasa_bajas_imprevistas + (1.0 - calidad[k]) * par.tasa_bajas_max_por_calidad)
        baj_k = tasa_bajas_total * Gk[k, :]
        bajas_totales[k] = baj_k.sum()

        # Egresos (AJUSTE): base = alumnos/12 (aprox. cohorte que egresa)
        egresos_base[k] = alumnos[k] / 12.0
        # Asignamos egreso base al grado 12, limitado por G12 (si hay desbalance no fuerza negativos)
        eg12_base = min(Gk[k, 11], egresos_base[k])
        eg_k = np.zeros(G, dtype=float)
        eg_k[11] = eg12_base

        # Pipeline: decidir y construir (para k < T)
        build_this_year = False
        if k < T:
            if (pipeline_start is None) and par.pipeline_auto_por_hacinamiento:
                cap_g1_opt = Cap_opt_k[0]
                hac_1 = 0.0 if cap_g1_opt <= 0 else max(0.0, (Gk[k, 0] - cap_g1_opt) / cap_g1_opt)
                ok_fin = True
                if not par.pipeline_financiacion_externa:
                    capex_lim = par.capex_pct_sobre_facturacion * facturacion[k]
                    disponible = max(resultado_operativo[k] - par.colchon_financiero, 0.0)
                    ok_fin = max(0.0, min(capex_lim, disponible)) >= par.costo_construccion_aula
                if (hac_1 > par.umbral_hacinamiento_g1) and ok_fin:
                    pipeline_start = k

            if par.pipeline_activo or (pipeline_start is not None):
                start = 0 if pipeline_start is None else pipeline_start
                if 0 <= (k - start) < 12:
                    build_this_year = True

            capex[k] = par.costo_construccion_aula if build_this_year else 0.0
            resultado_neto[k] = resultado_operativo[k] - capex[k]

            # Evolución de stocks:
            # 1) Candidatos
            next_Cand = Cand[k] + nuevos_candidatos[k] - seleccionados[k]
            next_Cand = max(next_Cand, 0.0)

            # 2) Alumnos por grado
            next_G = np.zeros(G, dtype=float)
            # Grado 1: entran "seleccionados", salen bajas y (si se aplicara) egreso local (0)
            next_G[0] = Gk[k, 0] + seleccionados[k] - baj_k[0]

            # Promoción simple: lo que queda en k pasa a k+1 (menos bajas y egreso local si lo hubiera)
            for gi in range(1, G):
                promo = Gk[k, gi-1] - baj_k[gi-1]  # sin egreso local en k-1
                next_G[gi] = Gk[k, gi] + promo - baj_k[gi]

            # Egreso base en 12º (ya restado en next_G? Aún no; lo aplicamos ahora)
            next_G[11] = max(next_G[11] - eg12_base, 0.0)

            # 3) Divisiones (capacidad): si se construye, agregar una división al tramo correspondiente del pipeline
            next_Div = Div[k, :].copy()
            if build_this_year:
                tramo = (k if pipeline_start is None else k - pipeline_start) % 12
                next_Div[tramo] += 1.0
                pipeline_construcciones[k] = 1.0

            # ENFORCE: Alumnos nunca mayor que capacidad MÁXIMA (corte blando vía selección ya lo limita; aquí reforzamos)
            total_next = next_G.sum()
            cap_total_max_next = (next_Div * par.cupo_maximo).sum()
            if total_next > cap_total_max_next:
                # Escalar proporcionalmente (mantiene distribución entre grados)
                factor = cap_total_max_next / max(total_next, 1e-9)
                next_G = next_G * factor

            # Avanzar 1 paso
            Gk[k+1, :] = np.maximum(0.0, next_G)
            Div[k+1, :] = next_Div
            Cand[k+1] = next_Cand
        else:
            capex[k] = 0.0
            resultado_neto[k] = resultado_operativo[k]
            # no hay k+1

    # Totales de aulas
    aulas = Div.sum(axis=1)

    # Redondeo de variables vinculadas a alumnos y candidatos para VISUALIZACIÓN
    def rint(arr):  # round to int but keep np.array dtype
        return np.rint(arr).astype(int)

    data = {
        "Año": t,
        "AlumnosTotales": rint(alumnos),
        "Calidad": calidad,
        "AulasTotales": rint(aulas),
        "Facturacion": facturacion,
        "CostosOPEX": costos_opex,
        "CostoDocentes": costo_docentes,
        "CostoVariableAlumno": costo_variable,
        "CostoMarketing": costo_marketing,
        "CostoMantenimiento": costo_mantenimiento,
        "CostoFijo": costo_fijo,
        "ResultadoOperativo": resultado_operativo,
        "CAPEX": capex,
        "ResultadoNeto": resultado_neto,
        "BudgetMkt": costo_marketing,        # alias
        "CAC": cac,
        "CandidatosStock": rint(Cand),
        "NuevosCandidatos": rint(nuevos_candidatos),
        "Seleccionados": rint(seleccionados),
        "BajasTotales": rint(bajas_totales),
        "EgresosBase": rint(egresos_base),
        "PipelineConstrucciones": pipeline_construcciones,
        "CapacidadMaxTotal": rint((Div * par.cupo_maximo).sum(axis=1)),
        "CapacidadOptTotal": rint((Div * par.cupo_optimo).sum(axis=1)),
    }

    # Series por grado (enteros para alumnos)
    for gi in range(G):
        data[f"G{gi+1}"] = rint(Gk[:, gi])
        data[f"DivG{gi+1}"] = Div[:, gi]
        Cap_opt_series = Div[:, gi] * par.cupo_optimo
        with np.errstate(divide='ignore', invalid='ignore'):
            hac_series = np.maximum(0.0, (Gk[:, gi] - Cap_opt_series) / np.maximum(Cap_opt_series, 1.0))
        data[f"HacG{gi+1}"] = hac_series

    df = pd.DataFrame(data)
    meta = {"params": asdict(par)}
    return df, meta
