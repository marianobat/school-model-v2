import numpy as np
import pandas as pd
from dataclasses import dataclass, asdict
from typing import Dict, Any, Tuple

@dataclass
class Params:
    # Horizonte
    years: int = 20

    # Mercado / Demanda
    demanda_potencial_inicial: int = 6000
    tasa_descenso_demanda: float = 0.05  # 5% anual

    # Calidad y dinámica (hacinamiento afecta calidad)
    calidad_base: float = 0.75
    beta_hacinamiento: float = 0.8

    # Bajas
    tasa_bajas_imprevistas: float = 0.01
    tasa_bajas_max_por_calidad: float = 0.12

    # Capacidad (12 grados)
    div_inicial_por_grado: int = 2
    cupo_optimo: int = 25    # óptimo para calidad
    cupo_maximo: int = 30    # límite físico (capacidad dura)

    # Marketing & selección con STOCK de candidatos
    prop_mkt: float = 0.10
    mkt_floor: float = 30_000.0
    cac_base: float = 800.0
    k_saturacion: float = 2.0
    politica_seleccion: float = 0.50   # % de candidatos del stock que pasan el filtro
    alumnos_admitidos_objetivo: int = 300  # objetivo anual de admisión

    # Finanzas (ingresos y costos operativos)
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

    # Financiamiento / caja / deuda
    caja_inicial: float = 500_000.0
    pct_capex_financiado: float = 0.60     # % del CAPEX financiado con deuda
    tasa_interes_deuda: float = 0.12       # interés anual simple sobre saldo
    anos_amortizacion_deuda: int = 10      # amortización lineal
    deuda_inicial: float = 0.0

    # Iniciales de stocks académicos
    g_inicial: int = 50                   # alumnos por grado inicial
    candidatos_inicial: float = 100.0     # stock de candidatos inicial

    # Sensibilidades de calidad a inversión (normalizadores)
    k_q_inv_alumno: float = 0.20
    k_q_infra_inversion: float = 0.15
    k_q_mantenimiento_netodep: float = 0.20
    ref_inv_alumno: float = 200.0
    ref_infra: float = 200_000.0
    ref_mant: float = 100_000.0

    # Aleatoriedad
    random_seed: int = 42  # para reproducibilidad en la asignación aleatoria de bajas G3..G10

def simulate(par: Params) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    T = par.years
    G = 12
    t = np.arange(T+1)

    # RNG para reproducibilidad
    rng = np.random.default_rng(par.random_seed)

    # Stocks por tiempo
    Gk = np.zeros((T+1, G), dtype=float)   # alumnos por grado
    Div = np.zeros((T+1, G), dtype=float)  # divisiones por grado
    Cand = np.zeros(T+1, dtype=float)      # candidatos
    Act = np.zeros(T+1, dtype=float)       # activos (para depreciación)
    Caja = np.zeros(T+1, dtype=float)      # caja/colchón financiero
    Deuda = np.zeros(T+1, dtype=float)     # deuda financiera
    Demanda = np.zeros(T+1, dtype=float)   # demanda potencial que decae

    # Iniciales
    Gk[0, :] = par.g_inicial
    Div[0, :] = par.div_inicial_por_grado
    Cand[0] = par.candidatos_inicial
    Act[0] = par.activos_inicial
    Caja[0] = par.caja_inicial
    Deuda[0] = par.deuda_inicial
    Demanda[0] = par.demanda_potencial_inicial

    # Series agregadas
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
    capex_total = np.zeros(T+1)
    capex_propio = np.zeros(T+1)
    capex_financiado = np.zeros(T+1)
    interes_deuda = np.zeros(T+1)
    amortizacion_deuda = np.zeros(T+1)
    resultado_neto = np.zeros(T+1)

    # Marketing y candidatos
    cac = np.zeros(T+1)
    nuevos_candidatos = np.zeros(T+1)
    admitidos = np.zeros(T+1)     # ingresantes reales a G1
    rechazados = np.zeros(T+1)    # candidatos no admitidos (limpian el stock)

    # Flujos de salida académicos
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
        # Demanda decreciente
        if k > 0:
            Demanda[k] = Demanda[k-1] * (1.0 - par.tasa_descenso_demanda)

        # Totales y capacidades
        alumnos_k = Gk[k, :].sum()
        Cap_opt_k = cap_opt(Div[k, :])
        Cap_max_k = cap_max(Div[k, :])

        # Hacinamiento (para calidad) vs óptimo
        with np.errstate(divide='ignore', invalid='ignore'):
            hac_k = np.maximum(0.0, (Gk[k, :] - Cap_opt_k) / np.maximum(Cap_opt_k, 1.0))
        hac_prom = 0.0 if alumnos_k <= 0 else float(np.dot(Gk[k, :], hac_k) / alumnos_k)

        # Facturación y costos base
        facturacion[k] = alumnos_k * par.cuota_mensual * par.meses
        sueldos[k] = par.pct_sueldos * facturacion[k]
        inv_infra[k] = par.inversion_infra_anual
        inv_calidad_alumno[k] = par.inversion_calidad_por_alumno * alumnos_k
        mantenimiento[k] = par.mantenimiento_pct_facturacion * facturacion[k]

        # Marketing (budget) y CAC
        saturacion = 0.0 if Demanda[k] <= 0 else min(1.0, alumnos_k / Demanda[k])
        margen_prov = facturacion[k] - (sueldos[k] + inv_calidad_alumno[k] + inv_infra[k] + mantenimiento[k])
        marketing[k] = max(par.mkt_floor, par.mkt_floor + par.prop_mkt * max(margen_prov, 0.0))
        cac[k] = par.cac_base * (1.0 + par.k_saturacion * saturacion)
        nuevos_candidatos[k] = 0.0 if cac[k] <= 0 else marketing[k] / cac[k]

        # Admitidos (ingresantes reales): objetivo y política, limitados por demanda (no por capacidad)
        gap_demanda = max(Demanda[k] - alumnos_k, 0.0)
        adm_teor = min(par.alumnos_admitidos_objetivo, par.politica_seleccion * Cand[k])
        admitidos[k] = min(adm_teor, gap_demanda)

        # Rechazados: limpian el stock de candidatos (salen del sistema)
        rechazados[k] = max(Cand[k] - admitidos[k], 0.0)

        # Bajas: SOLO entre G3..G10, asignadas ALEATORIAMENTE (multinomial) según la masa en esos grados
        # Primero determinar la tasa global (depende de calidad del período previo)
        calidad_prev = calidad[k-1] if k > 0 else par.calidad_base
        tasa_bajas_total = min(1.0, par.tasa_bajas_imprevistas + (1.0 - calidad_prev) * par.tasa_bajas_max_por_calidad)

        bajas_vec = np.zeros(G, dtype=float)
        # Índices Python: G3..G10 => 2..9
        segmento = Gk[k, 2:10].copy()
        total_segmento = float(segmento.sum())
        if total_segmento > 0 and tasa_bajas_total > 0:
            # cantidad objetivo de bajas en el segmento
            bajas_obj = min(int(round(tasa_bajas_total * total_segmento)), int(total_segmento))
            # probabilidades proporcionales al tamaño de cada grado (evita sacar más de lo que hay)
            probs = segmento / total_segmento
            # muestreo multinomial entero
            bajas_seg_int = rng.multinomial(bajas_obj, probs)
            bajas_vec[2:10] = bajas_seg_int
        # En G1, G2, G11, G12 no aplicamos bajas aleatorias (quedan en 0)
        bajas_totales[k] = float(bajas_vec.sum())

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
            capex_total[k] = par.costo_construccion_aula if build else 0.0
            docentes_nuevas[k] = par.costo_docente_por_aula_nueva if build else 0.0

            # OPEX final (sumando docentes de aulas nuevas)
            costos_opex[k] += docentes_nuevas[k]
            resultado_operativo[k] = facturacion[k] - costos_opex[k]

            # Financiamiento del CAPEX
            capex_financiado[k] = capex_total[k] * par.pct_capex_financiado
            capex_propio[k] = capex_total[k] - capex_financiado[k]

            # Intereses y amortización
            interes_deuda[k] = par.tasa_interes_deuda * Deuda[k]
            if par.anos_amortizacion_deuda > 0:
                amortizacion_deuda[k] = min(Deuda[k], Deuda[k] / par.anos_amortizacion_deuda)
            else:
                amortizacion_deuda[k] = Deuda[k]  # amortiza todo si años=0

            # Resultado neto (flujo caja): op - capex propio - intereses - amortización
            resultado_neto[k] = resultado_operativo[k] - capex_propio[k] - interes_deuda[k] - amortizacion_deuda[k]

            # Evolución de stocks:
            # 1) Candidatos
            next_C = max(Cand[k] + nuevos_candidatos[k] - admitidos[k] - rechazados[k], 0.0)

            # 2) Alumnos por grado
            #   - Entradas a G1: admitidos; bajas en G1 = 0 por diseño actual
            next_G = np.zeros(G, dtype=float)
            next_G[0] = Gk[k, 0] + admitidos[k]  # sin bajas en G1

            #   - Promoción Gi-1 -> Gi para i=2..11 (G2..G11), con bajas sólo en G3..G10
            #     Nota: en Python, índices 1..10 corresponden a G2..G11
            for gi in range(1, 11):
                promo = Gk[k, gi-1] - (bajas_vec[gi-1] if 2 <= gi-1 <= 9 else 0.0)
                next_G[gi] = Gk[k, gi] + promo - (bajas_vec[gi] if 2 <= gi <= 9 else 0.0)

            #   - Promoción G11 -> G12: simple traspaso desde G11
            #     bajas en G11 ya aplicadas arriba (si gi=10, corresponde a G11)
            promo_11_12 = Gk[k, 10] - (bajas_vec[10] if 2 <= 10 <= 9 else 0.0)  # bajas en G11 son 0 por política (fuera 3..10)
            next_G[11] = Gk[k, 11] + promo_11_12  # sin bajas en G12

            #   - Egreso en 12º: restar egresados (del año anterior)
            next_G[11] = max(next_G[11] - eg_prev, 0.0)

            # 3) Divisiones
            next_D = Div[k, :].copy()
            if build:
                tramo = (k - par.pipeline_start_year) % 12 if par.pipeline_start_year >= 0 else 0
                next_D[tramo] += 1.0
                pipeline_construcciones[k] = 1.0

            # 4) Capacidad/Población — límite duro del stock
            total_next = float(next_G.sum())
            cap_total_max_next = float((next_D * par.cupo_maximo).sum())
            poblacion_max = float(Demanda[k])  # población disponible ese año
            allowed = min(cap_total_max_next, poblacion_max)
            if total_next > allowed and total_next > 0:
                factor = allowed / total_next
                next_G = next_G * factor

            # 5) Activos (capex suma; inversión_infra es OPEX)
            next_Act = Act[k] + capex_total[k] - dep

            # 6) Deuda (entra capex financiado; salen amortizaciones)
            next_Deuda = max(Deuda[k] + capex_financiado[k] - amortizacion_deuda[k], 0.0)

            # 7) Caja (flujo de resultado neto)
            next_Caja = Caja[k] + resultado_neto[k]

            # 8) Demanda del próximo paso
            next_Demanda = Demanda[k] * (1.0 - par.tasa_descenso_demanda)

            # Avances
            Gk[k+1, :] = np.maximum(0.0, next_G)
            Div[k+1, :] = next_D
            Cand[k+1] = next_C
            Act[k+1] = max(next_Act, 0.0)
            Deuda[k+1] = next_Deuda
            Caja[k+1] = next_Caja
            Demanda[k+1] = next_Demanda
        else:
            # último año: cerrar resultado neto (sin pipeline)
            capex_total[k] = 0.0
            capex_financiado[k] = 0.0
            capex_propio[k] = 0.0
            interes_deuda[k] = par.tasa_interes_deuda * Deuda[k]
            amortizacion_deuda[k] = min(Deuda[k], Deuda[k] / par.anos_amortizacion_deuda) if par.anos_amortizacion_deuda > 0 else Deuda[k]
            resultado_neto[k] = resultado_operativo[k] - interes_deuda[k] - amortizacion_deuda[k]
            # stocks no avanzan

    # Totales aulas
    aulas = Div.sum(axis=1)

    # Redondeo de presentación
    def rint(a): return np.rint(a).astype(int)

    df = pd.DataFrame({
        "Año": t,
        "DemandaPotencial": Demanda,
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
        "CAPEX_Total": capex_total,
        "CAPEX_Propio": capex_propio,
        "CAPEX_Financiado": capex_financiado,
        "InteresDeuda": interes_deuda,
        "AmortizacionDeuda": amortizacion_deuda,
        "ResultadoNeto": resultado_neto,
        "Caja": Caja,
        "Deuda": Deuda,
        "CAC": cac,
        "CandidatosStock": rint(Cand),
        "NuevosCandidatos": rint(nuevos_candidatos),
        "Admitidos": rint(admitidos),
        "Rechazados": rint(rechazados),
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
