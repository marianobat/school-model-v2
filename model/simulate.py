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

    # Sensibilidad de bajas al precio (cuota vs referencia)
    k_bajas_precio: float = 0.20
    ref_precio: float = 500.0

    # Capacidad (12 grados)
    div_inicial_por_grado: int = 2
    cupo_optimo: int = 25
    cupo_maximo: int = 30

    # Marketing (budget) y CAC
    prop_mkt: float = 0.10
    mkt_floor: float = 30_000.0
    cac_base: float = 800.0
    k_saturacion: float = 2.0

    # Admisión (valor absoluto deseado por año)
    admitidos_deseados: int = 300

    # Finanzas (ingresos y costos operativos)
    cuota_mensual: float = 500.0
    meses: int = 12

    # Sueldos fijos
    costo_docente_por_aula: float = 100_000.0
    sueldos_no_docentes: float = 200_000.0

    # "Deseos" de inversión (sujetas a tope por rentabilidad)
    inversion_infra_anual: float = 200_000.0   # target
    inversion_calidad_por_alumno: float = 200.0  # target por alumno
    mantenimiento_pct_facturacion: float = 0.08  # "obligatorio"

    # Activos / depreciación
    activos_inicial: float = 2_000_000.0
    tasa_depreciacion_anual: float = 0.05

    # Pipeline (1 división por grado durante 12 años a partir del año elegido)
    pipeline_start_year: int = -1  # -1 desactiva; >=0 activa
    costo_construccion_aula: float = 100_000.0

    # Financiamiento / caja / deuda
    caja_inicial: float = 500_000.0
    pct_capex_financiado: float = 0.60
    tasa_interes_deuda: float = 0.12
    anos_amortizacion_deuda: int = 10
    deuda_inicial: float = 0.0

    # Iniciales académicos
    g_inicial: int = 50
    candidatos_inicial: float = 100.0  # (solo para compatibilidad de salida)

    # Sensibilidades de calidad
    k_q_inv_alumno: float = 0.20
    k_q_infra_inversion: float = 0.15
    k_q_mantenimiento_netodep: float = 0.20
    k_q_selectividad: float = 0.20  # resta calidad si admitidos/nuevos es alto

    # Normalizadores
    ref_inv_alumno: float = 200.0
    ref_infra: float = 200_000.0
    ref_mant: float = 100_000.0

    # NUEVO: candidatos orgánicos por calidad (parámetros fijos razonables)
    qref_candidatos: float = 0.60      # umbral de calidad para activar orgánicos
    alpha_candidatos_q: float = 0.30   # cands por alumno por punto de calidad (>qref)
    lag_calidad_candidatos: int = 1    # usar calidad(t-1)

    # Aleatoriedad (para bajas aleatorias G3..G10)
    random_seed: int = 42

def simulate(par: Params) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    T = par.years
    G = 12
    t = np.arange(T+1)

    rng = np.random.default_rng(par.random_seed)

    # Stocks
    Gk = np.zeros((T+1, G), dtype=float)   # alumnos por grado
    Div = np.zeros((T+1, G), dtype=float)  # divisiones por grado
    Cand = np.zeros(T+1, dtype=float)      # (salida/compat)
    Act = np.zeros(T+1, dtype=float)       # activos
    Caja = np.zeros(T+1, dtype=float)      # caja
    Deuda = np.zeros(T+1, dtype=float)     # deuda
    Demanda = np.zeros(T+1, dtype=float)   # demanda potencial

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
    inv_infra = np.zeros(T+1)               # realizadas (limitadas)
    inv_calidad_alumno = np.zeros(T+1)      # realizadas (limitadas)
    mantenimiento = np.zeros(T+1)
    marketing = np.zeros(T+1)               # realizado (limitado)
    costos_opex = np.zeros(T+1)

    resultado_operativo = np.zeros(T+1)
    capex_total = np.zeros(T+1)
    capex_propio = np.zeros(T+1)
    capex_financiado = np.zeros(T+1)
    interes_deuda = np.zeros(T+1)
    amortizacion_deuda = np.zeros(T+1)
    resultado_neto = np.zeros(T+1)

    # Marketing y candidatos (flujos)
    cac = np.zeros(T+1)
    nuevos_candidatos = np.zeros(T+1)
    nuevos_candidatos_mkt = np.zeros(T+1)  # NUEVO
    nuevos_candidatos_q = np.zeros(T+1)    # NUEVO orgánicos
    admitidos = np.zeros(T+1)
    rechazados = np.zeros(T+1)
    selectividad = np.zeros(T+1)

    # Flujos académicos
    bajas_totales = np.zeros(T+1)
    egresados = np.zeros(T+1)

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
        aulas_k = float(Div[k, :].sum())

        # Hacinamiento (para calidad) vs óptimo
        with np.errstate(divide='ignore', invalid='ignore'):
            hac_k = np.maximum(0.0, (Gk[k, :] - Cap_opt_k) / np.maximum(Cap_opt_k, 1.0))
        hac_prom = 0.0 if alumnos_k <= 0 else float(np.dot(Gk[k, :], hac_k) / alumnos_k)

        # Facturación
        facturacion[k] = alumnos_k * par.cuota_mensual * par.meses

        # Costos "obligatorios": sueldos y mantenimiento
        sueldos[k] = par.costo_docente_por_aula * aulas_k + par.sueldos_no_docentes
        mantenimiento[k] = par.mantenimiento_pct_facturacion * facturacion[k]

        # Targets de inversión (discrecionales): infra, calidad por alumno, marketing
        target_infra = par.inversion_infra_anual
        target_calidad = par.inversion_calidad_por_alumno * alumnos_k
        margen_prov = facturacion[k] - (sueldos[k] + mantenimiento[k])
        saturacion = 0.0 if Demanda[k] <= 0 else min(1.0, alumnos_k / Demanda[k])
        cac[k] = par.cac_base * (1.0 + par.k_saturacion * saturacion)
        target_mkt = max(par.mkt_floor, par.mkt_floor + par.prop_mkt * max(margen_prov, 0.0))

        # Asignación con restricción presupuestaria para discrecionales
        disponible = max(margen_prov, 0.0)
        deseos = np.array([target_infra, target_calidad, target_mkt], dtype=float)
        total_deseos = float(deseos.sum())
        if total_deseos <= disponible + 1e-9:
            inv_infra[k], inv_calidad_alumno[k], marketing[k] = deseos
        else:
            if total_deseos > 0:
                ratio = disponible / total_deseos
                inv_infra[k], inv_calidad_alumno[k], marketing[k] = deseos * ratio
            else:
                inv_infra[k] = inv_calidad_alumno[k] = marketing[k] = 0.0

        # Nuevos candidatos (suma de marketing + efecto calidad)
        # 1) pagados por mkt
        nuevos_candidatos_mkt[k] = 0.0 if cac[k] <= 0 else marketing[k] / cac[k]

        # 2) orgánicos por calidad percibida (con lag y saturación por pool)
        q_driver = calidad[k-1] if (k > 0 and par.lag_calidad_candidatos >= 1) else calidad[k]
        excedente_q = max(q_driver - par.qref_candidatos, 0.0)
        pool_satur = 0.0
        if Demanda[k] > 1e-9:
            pool_satur = max(0.0, 1.0 - (alumnos_k / Demanda[k]))  # 0..1
        nuevos_candidatos_q[k] = par.alpha_candidatos_q * excedente_q * alumnos_k * pool_satur

        nuevos_candidatos[k] = nuevos_candidatos_mkt[k] + nuevos_candidatos_q[k]

        # Admitidos: valor absoluto deseado, limitado por nuevos candidatos, demanda y capacidad de G1
        gap_demanda = max(Demanda[k] - alumnos_k, 0.0)
        capacidad_g1_max = float(Div[k, 0] * par.cupo_maximo)
        admitidos[k] = min(float(par.admitidos_deseados), nuevos_candidatos[k], gap_demanda, capacidad_g1_max)

        # Rechazados: lo que no se admite se pierde
        rechazados[k] = max(nuevos_candidatos[k] - admitidos[k], 0.0)

        # Reporte "stock" como los candidatos del año
        Cand[k] = nuevos_candidatos[k]

        # Selectividad del año
        selectividad[k] = float(admitidos[k] / nuevos_candidatos[k]) if nuevos_candidatos[k] > 0 else 0.0

        # Bajas aleatorias SOLO en G3..G10 (con presión de precio)
        calidad_prev = calidad[k-1] if k > 0 else par.calidad_base
        presion_precio = par.k_bajas_precio * max((par.cuota_mensual / max(par.ref_precio, 1e-9)) - 1.0, 0.0)
        tasa_bajas_total = min(
            1.0,
            par.tasa_bajas_imprevistas
            + (1.0 - calidad_prev) * par.tasa_bajas_max_por_calidad
            + presion_precio
        )
        bajas_vec = np.zeros(G, dtype=float)
        segmento = Gk[k, 2:10].copy()  # G3..G10
        total_segmento = float(segmento.sum())
        if total_segmento > 0 and tasa_bajas_total > 0:
            bajas_obj = min(int(round(tasa_bajas_total * total_segmento)), int(total_segmento))
            probs = segmento / total_segmento
            bajas_seg_int = rng.multinomial(bajas_obj, probs)
            bajas_vec[2:10] = bajas_seg_int
        bajas_totales[k] = float(bajas_vec.sum())

        # Egresados(t) = G12(t)
        egresados[k] = Gk[k, 11]

        # Calidad (con inversiones realizadas, mantenimiento vs depreciación y selectividad)
        dep = par.tasa_depreciacion_anual * Act[k]
        inv_alum_norm = ((inv_calidad_alumno[k] / max(alumnos_k, 1e-9)) / max(par.ref_inv_alumno, 1e-9)) if alumnos_k > 0 else 0.0
        infra_norm = (inv_infra[k] / max(par.ref_infra, 1e-9))
        mant_norm = ((mantenimiento[k] - dep) / max(par.ref_mant, 1e-9))
        efecto_selectividad = - par.k_q_selectividad * selectividad[k]

        calidad_raw = (par.calidad_base
                       - par.beta_hacinamiento * hac_prom
                       + par.k_q_inv_alumno * inv_alum_norm
                       + par.k_q_infra_inversion * infra_norm
                       + par.k_q_mantenimiento_netodep * mant_norm
                       + efecto_selectividad)
        calidad[k] = float(np.clip(calidad_raw, 0.0, 1.0))

        # OPEX y resultados
        costos_opex[k] = sueldos[k] + mantenimiento[k] + inv_infra[k] + inv_calidad_alumno[k] + marketing[k]
        resultado_operativo[k] = facturacion[k] - costos_opex[k]

        if k < T:
            # Pipeline: un aula nueva por año durante 12 años desde pipeline_start_year
            build = construir_en_anio(k)
            capex_total[k] = par.costo_construccion_aula if build else 0.0

            # Financiamiento del CAPEX del año
            capex_financiado[k] = capex_total[k] * par.pct_capex_financiado
            capex_propio[k] = capex_total[k] - capex_financiado[k]

            # Intereses y amortización sobre saldo de deuda
            interes_deuda[k] = par.tasa_interes_deuda * Deuda[k]
            if par.anos_amortizacion_deuda > 0:
                amortizacion_deuda[k] = min(Deuda[k], Deuda[k] / par.anos_amortizacion_deuda)
            else:
                amortizacion_deuda[k] = 0.0

            # Resultado neto (flujo de caja)
            resultado_neto[k] = resultado_operativo[k] - capex_propio[k] - interes_deuda[k] - amortizacion_deuda[k]

            # Evolución de stocks:
            # 1) Candidatos: se vacía (admitidos + rechazados)
            next_C = 0.0

            # 2) Alumnos por grado (avance completo anual)
            next_G = np.zeros(G, dtype=float)
            next_G[0] = admitidos[k]  # G1(t+1)
            for gi in range(1, 11):   # G2..G11
                bajas_prev = bajas_vec[gi-1] if 2 <= gi-1 <= 9 else 0.0
                next_G[gi] = max(Gk[k, gi-1] - bajas_prev, 0.0)
            # G12(t+1) = G11(t)
            next_G[11] = max(Gk[k, 10], 0.0)

            # 3) Divisiones
            next_D = Div[k, :].copy()
            if build:
                tramo = (k - par.pipeline_start_year) % 12 if par.pipeline_start_year >= 0 else 0
                next_D[tramo] += 1.0
                pipeline_construcciones[k] = 1.0

            # 4) Capacidad/Población — límite duro del stock
            total_next = float(next_G.sum())
            cap_total_max_next = float((next_D * par.cupo_maximo).sum())
            poblacion_max = float(Demanda[k])
            allowed = min(cap_total_max_next, poblacion_max)
            if total_next > allowed and total_next > 0:
                factor = allowed / total_next
                next_G = next_G * factor

            # 5) Activos (capex suma; inversión_infra es OPEX)
            dep = par.tasa_depreciacion_anual * Act[k]
            next_Act = Act[k] + capex_total[k] - dep

            # 6) Deuda (entra capex financiado; salen amortizaciones)
            next_Deuda = max(Deuda[k] + capex_financiado[k] - amortizacion_deuda[k], 0.0)

            # 7) Caja (flujo de resultado neto)
            next_Caja = Caja[k] + resultado_neto[k]

            # 8) Demanda(t+1)
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
            amortizacion_deuda[k] = min(Deuda[k], Deuda[k] / par.anos_amortizacion_deuda) if par.anos_amortizacion_deuda > 0 else 0.0
            resultado_neto[k] = resultado_operativo[k] - interes_deuda[k] - amortizacion_deuda[k]

    # Totales aulas
    aulas = Div.sum(axis=1)

    # Redondeo de presentación
    def rint(a): return np.rint(a).astype(int)

    # KPIs de rentabilidad
    margen_operativo = np.where(facturacion > 0, resultado_operativo / facturacion, 0.0)
    margen_neto = np.where(facturacion > 0, resultado_neto / facturacion, 0.0)
    costos_totales_cash = costos_opex + capex_propio + interes_deuda + amortizacion_deuda

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
        "Marketing": marketing,
        "CostosOPEX": costos_opex,
        "CostosTotalesCash": costos_totales_cash,
        "ResultadoOperativo": resultado_operativo,
        "CAPEX_Total": capex_total,
        "CAPEX_Propio": capex_propio,
        "CAPEX_Financiado": capex_financiado,
        "InteresDeuda": interes_deuda,
        "AmortizacionDeuda": amortizacion_deuda,
        "ResultadoNeto": resultado_neto,
        "Caja": Caja,
        "Deuda": Deuda,
        "MargenOperativo": margen_operativo,
        "MargenNeto": margen_neto,
        "CAC": cac,
        "CandidatosStock": rint(Cand),             # reporta los candidatos del año
        "NuevosCandidatos": rint(nuevos_candidatos),
        "NuevosCandidatosMkt": rint(nuevos_candidatos_mkt),  # NUEVO
        "NuevosCandidatosQ": rint(nuevos_candidatos_q),      # NUEVO
        "Admitidos": rint(admitidos),
        "Rechazados": rint(rechazados),
        "Selectividad": selectividad,              # 0..1
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
