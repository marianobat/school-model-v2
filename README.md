# 🏫 School System Dynamics Simulator

Un modelo de **Dinámica de Sistemas** que simula la sostenibilidad de un colegio a lo largo del tiempo, considerando las interacciones entre **alumnos**, **calidad percibida**, **capacidad (aulas)**, **inversión**, **marketing** y **finanzas**.

Diseñado con un enfoque **pedagógico** para talleres de **toma de decisiones basadas en datos (DDDM)**.

---

## 🎯 Objetivo

Este simulador permite **visualizar loops de refuerzo y balanceo** en la gestión de una escuela.  
Muestra cómo las decisiones (por ejemplo, aumentar la inversión en marketing, construir aulas o mejorar la calidad) impactan en la matrícula, los costos y la sostenibilidad del sistema.

---

## 🔁 Principales bucles del sistema

| Tipo | Loop | Descripción |
|------|------|--------------|
| ♻️ Refuerzo | **R1 – Reputación / atracción** | Calidad ↑ → Ingresantes ↑ → Alumnos ↑ (si no hay hacinamiento) |
| ♻️ Refuerzo | **R2 – Marketing endógeno** | Resultado ↑ → Presupuesto de marketing ↑ → Candidatos ↑ → Alumnos ↑ |
| ♻️ Refuerzo | **R3 – Expansión (pipeline)** | Resultado ↑ → Nuevas aulas → Capacidad ↑ → Calidad ↑ → Alumnos ↑ |
| ⚖️ Balanceo | **B1 – Saturación de mercado** | Alumnos ↑ → Mercado disponible ↓ → Ingresantes ↓ |
| ⚖️ Balanceo | **B2 – Hacinamiento** | Alumnos ↑ → Hacinamiento ↑ → Calidad ↓ → Alumnos ↓ |
| ⚖️ Balanceo | **B3 – CAC creciente** | Saturación ↑ → CAC ↑ → Candidatos ↓ → Ingresantes ↓ |
| ⚖️ Balanceo | **B4 – Restricción financiera** | Resultado ↓ → sin inversión → Capacidad constante → frena crecimiento |

---

## 🧠 Escenarios sugeridos para la sesión pedagógica

| Escenario | Qué demuestra | Qué loops se activan |
|------------|----------------|----------------------|
| **S0 – Base** | Condiciones normales, sin shocks | Control |
| **S1 – Alta calidad** | Mejora inicial de calidad +0.1 | R1, R2 |
| **S2 – Shock reputacional** | Caída temporal de calidad −0.15 | B2, B4 |
| **S3 – Mercado saturado** | Menor demanda potencial | B1, B3 |
| **S4 – Más marketing** | Aumento del presupuesto (prop_mkt=0.25) | R2 vs B3 |
| **S5 – Menos capacidad** | Reducción de aulas o cupo | B2 fuerte |
| **S6 – Activar pipeline** | Construcción 12 años | R3 |
| **S7 – Restricción financiera** | Menor cuota o aumento de costos | B4 |
| **S8 – Gasto→Calidad (opcional)** | Retroalimentación positiva por inversión | R4 |

---

## 🧩 Estructura del proyecto

streamlit_school_sd/
├── app.py                        # Interfaz principal de Streamlit
├── requirements.txt              # Dependencias
├── model/
│   └── simulate.py               # Motor de simulación (stocks, flujos, loops)
├── ui/
│   └── charts.py                 # Funciones de gráficos
└── data/
└── samples/
└── preset_base.json      # Parámetros base del modelo

---

## 🚀 Publicación en Streamlit Cloud

1. Subir esta carpeta a un repositorio en **GitHub** (por ejemplo `streamlit_school_sd`).
2. Entrar en [https://share.streamlit.io](https://share.streamlit.io) e iniciar sesión con GitHub.
3. Hacer clic en **New app** y configurar:
   - **Repository:** `usuario/streamlit_school_sd`
   - **Branch:** `main`
   - **Main file path:** `app.py`
4. Pulsar **Deploy**.

Streamlit instalará automáticamente las dependencias desde `requirements.txt`.

---

## 🧭 Uso dentro de la app

### 📊 Simulación
Ajustar la **calidad base** y la **tasa de captación**.  
Observar cómo evoluciona el número de alumnos y la calidad percibida.

### 📣 Marketing & Captación
Modificar el **presupuesto de marketing** o el **CAC base**.  
Observar cómo el costo de adquisición crece con la saturación del mercado.

### ⚙️ Políticas de expansión
Activar el **pipeline de aulas (12 años)** para ver cómo se incrementa gradualmente la capacidad.  
Definir si el modelo puede financiar inversión externa o no.

### 📥 Exportar
Descargar los resultados en CSV o JSON para análisis posteriores.

---

## 📈 Requisitos técnicos

- Python ≥ 3.10  
- Streamlit, Numpy, Pandas, Matplotlib (instaladas automáticamente en la nube)

---

## 👤 Autor

**Mariano Batistelli**
