# 📈 Smart Strategy Engine

Dashboard de estrategias de inversión hecho 100% en Python con **Streamlit**.
Incluye 5 módulos: **DCA, Dividendos, Trading por Objetivos, FIBRAs y Copy Trading**,
más una página de **Inicio**, **Mis Resultados** y un **Revisor de Cartera** con análisis automático.

---

## ✅ Opción A — Correr en una computadora (lo más fiel a como se ve)

Requisitos: tener **Python 3.10 o superior** instalado.

1. Abre una terminal dentro de la carpeta del proyecto (donde está `app.py`).
2. (Opcional pero recomendado) crea un entorno virtual:
   ```bash
   python -m venv .venv
   # Windows:
   .venv\Scripts\activate
   # Mac/Linux:
   source .venv/bin/activate
   ```
3. Instala todas las librerías:
   ```bash
   pip install -r requirements.txt
   ```
4. Ejecuta el dashboard:
   ```bash
   streamlit run app.py
   ```
5. Se abrirá solo en el navegador. Si no, entra a **http://localhost:8501**

> 💡 En el menú lateral, cambia a **Modo: 🧪 Demostración** y pulsa
> **"Generar datos sintéticos"** para ver el dashboard lleno de datos de ejemplo.

---

## ✅ Opción B — Correr en Google Colab

Colab no muestra Streamlit directamente, así que se usa un **túnel** que genera un
link público temporal. Ya está todo automatizado en el notebook incluido:

1. Sube este proyecto a Colab:
   - Comprime la carpeta en un `.zip` (o usa el `.zip` que ya viene).
2. Abre el notebook **`Correr_en_Colab.ipynb`** en Google Colab.
3. Ejecuta las celdas en orden:
   - La 1 sube y descomprime el proyecto.
   - La 2 instala las librerías (`requirements.txt`).
   - La 3 lanza Streamlit y muestra un **link `https://...trycloudflare.com`**.
4. Abre ese link → verás el dashboard igual que en local.

> ⚠️ En Colab, el botón de **Google Calendar no funciona** (necesita abrir un
> navegador local). Todo lo demás funciona normal. Usa el **Modo Demostración**
> para la presentación.

---

## 📂 Estructura del proyecto
```
app.py                  → punto de entrada (menú y navegación)
requirements.txt        → librerías necesarias
.streamlit/config.toml  → tema visual
modules/                → los 5 módulos + inicio + exportaciones
utils/                  → lógica de datos, análisis e indicadores
db/                     → bases SQLite (real y demo) — se crean solas
```

## 🔧 Librerías principales
streamlit · plotly · pandas · numpy · yfinance · yahooquery ·
openpyxl · reportlab · python-dateutil · google-api-python-client

*Herramienta educativa, no es asesoría financiera.*
