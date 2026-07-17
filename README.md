# 📈 VestPlan — *Invierte con un plan. No con emociones.*

**Proyecto Integrador · Módulo 8 — Inteligencia Artificial Aplicada al Análisis Financiero**
Autor: **Diego Mejía**

🔗 **App en vivo:** https://vestplan.streamlit.app

---

## 1. La problemática

Cuando alguien empieza a invertir en México se topa con dos muros:

1. **Todo suena complicado e intimidante.** Jerga financiera, comisiones que no entiendes,
   y la sensación de que "esto es para expertos". Muchos ni lo intentan.
2. **Y quien sí se anima, no le da seguimiento.** Las compras terminan anotadas en el
   celular, en un Excel o en la cabeza. Al final **nadie sabe cómo va realmente**:
   ¿voy ganando?, ¿me conviene más que dejarlo en CETES?, ¿estoy siendo constante?

Además, el mercado mexicano tiene reglas propias que las apps genéricas ignoran:
comisión + **16% de IVA**, operaciones en **pesos**, y en el SIC **solo acciones enteras**.

> **VestPlan resuelve el seguimiento:** armas tus estrategias, registras tus compras y
> ventas, y la app te dice en todo momento cuánto llevas invertido, cuánto vale hoy y
> cómo vas — con números reales, sin adornos.

---

## 2. La herramienta: una **webapp** (Streamlit + Python)

App **mobile-first** estilo neobank. Cinco estrategias, cada una con su asistente
paso a paso (**1. Emisora → 2. Análisis → 3. Confirmar**):

| Estrategia | Qué hace |
|---|---|
| 📊 **DCA** | Compras recurrentes: misma cantidad cada periodo, con proyección y recordatorios |
| 💰 **Dividendos** | Acciones que pagan "renta", con análisis de salud del dividendo y ex-dates |
| 🏢 **FIBRAs** | Bienes raíces desde la BMV, en pesos, con calificación automática |
| 🎯 **Por Objetivos** | Análisis técnico + **entrada escalonada**: varios puntos de compra (cada uno con sus acciones) hacia una meta de salida |
| 👥 **Copy Trading** | Replica carteras de inversionistas famosos (reportes 13F públicos) |

**Además:** 📈 Mis Resultados (con comparativa **vs CETES y S&P 500**), 📚 Aprende a
invertir (lecciones + glosario), logros y rachas que premian la constancia, tarjeta
para compartir por WhatsApp, y un **agente de voz** (ElevenLabs) integrado.

### Principios de diseño (lo que la distingue)
- **Honestidad financiera:** comisión **+ IVA del 16%** en cada operación, precios de
  mercado en vivo, **acciones enteras** (regla SIC), y **cero cifras inventadas**.
- **Límites declarados:** los datos 13F son públicos y llegan con ~45 días de retraso;
  la app lo dice, no lo esconde.
- **No es asesoría financiera:** informa y organiza; **tú decides**.

---

## 3. Skill utilizada 🧠 → [`.claude/skills/revisor-de-cartera/`](.claude/skills/revisor-de-cartera/)

**`revisor-de-cartera`** — skill de Claude que convierte la cartera exportada en un
**diagnóstico ejecutivo de inversionista**.

- **`SKILL.md`** — instrucciones del agente: metodología, estructura del informe y
  reglas (tono claro, sin inventar números, cierre obligatorio de "no es asesoría").
- **`scripts/analizar_cartera.py`** — script Python que lee `exports/cartera_export.json`
  y calcula: diversificación, **índice de concentración HHI**, mayor posición,
  ganadoras/perdedoras y banderas de riesgo frente al perfil.

**Está integrada dentro de la app:** en *Resultados → 🤖 Analizar mi cartera*, VestPlan
genera el export y produce el diagnóstico al instante (ver `utils/revisor_utils.py`).

---

## 4. Python en toda la herramienta 🐍

100% Python. Lógica separada de la interfaz:

```
app.py                → punto de entrada, navegación, estilos, agente de voz
modules/              → una vista por módulo (5 estrategias + inicio, resultados, aprende…)
utils/                → el motor:
   db_utils.py           SQLite (esquema, migraciones, CRUD de las 5 estrategias)
   resumen_utils.py      cálculo del portafolio consolidado (con caché por modo)
   comisiones.py         comisión + IVA (regla mexicana)
   benchmark.py          simulación vs CETES y S&P 500 con tus flujos reales
   technical_utils.py    OHLC, medias móviles, Bollinger, RSI, soportes/resistencias
   dividends_utils.py    series de dividendos, yield TTM, salud del dividendo
   copytrading_utils.py  carteras 13F, riesgo (HHI), encaje con tu perfil
   excel_io.py           importar/exportar Excel (plantilla con validaciones)
   compartir.py          tarjeta de logros en PNG (PIL, dibujada en vector)
   pipeline.py           validación y auditoría de cada guardado
   demo_seed.py          generador de datos sintéticos
```

**Librerías:** streamlit · pandas · numpy · plotly · yfinance · yahooquery · openpyxl ·
reportlab · pillow · python-dateutil · google-api-python-client

---

## 5. Descargables que genera la herramienta 📥

| Descargable | Dónde | Qué trae |
|---|---|---|
| **PDF** `Mis_Resultados_*.pdf` | Resultados | Informe: totales, resumen por estrategia y detalle de cada compra |
| **Excel** `Mis_Resultados_*.xlsx` | Resultados | Hoja Resumen + una hoja por estrategia |
| **Imagen** `vestplan_mis_logros.png` | Resultados | Tarjeta de logros para compartir (sin exponer tu dinero) |
| **HTML** `Revisor_Cartera_*.html` | Resultados | Diagnóstico generado por la skill |
| **JSON** `cartera_export.json` | Resultados | Export estructurado que consume la skill |
| **Plantilla** `Plantilla_SSE_*.xlsx` | Resultados → Cargar Excel | Plantilla con listas desplegables para carga masiva |

---

## 6. Datos sintéticos (privacidad) 🧪

Para no exponer información real, la app trae un **modo Demostración** con una
inversionista ficticia (*Ana Demo*): perfil, 5 estrategias, compras, ventas cerradas
e histórico de patrimonio de 120 días.

**Cómo usarlo:** *Perfil → Modo de datos → 🧪 Demostración → "🔄 Generar datos sintéticos"*.

Vive en una base **separada** (`db/sse_demo.db`), así que tus datos reales nunca se tocan.
Generador: [`utils/demo_seed.py`](utils/demo_seed.py).

---

## 7. Prompts utilizados

Ver **[`PROMPTS.md`](PROMPTS.md)** — incluye el prompt de la skill, el del agente de voz
y el enfoque de construcción del proyecto.

---

## 8. Cómo correrlo localmente

Requiere **Python 3.12** (recomendado; en 3.14 varias librerías aún fallan).

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # Mac/Linux
pip install -r requirements.txt
streamlit run app.py
```

Abre **http://localhost:8501** → *Perfil → Modo Demostración → Generar datos sintéticos*.

---

*Herramienta educativa. **No es asesoría financiera.** Los rendimientos pasados no
garantizan resultados futuros.*
