import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from utils.ticker_search import widget_buscador
from utils.calendar_utils import create_calendar_events
from utils.db_utils import (save_strategy, load_strategies, save_purchase, load_purchases,
                            delete_strategy, set_cal_creado, titulos_disponibles,
                            registrar_venta, load_ventas_cerradas)
from utils.ticker_search import get_precio_actual, get_tipo_cambio_actual
from utils.comisiones import calcular_comision, comision_desde_perfil
from utils.resumen_utils import invalidar_resumen
from modules import estrategia_comun

FRECUENCIAS = {
    "Semanal":    {"meses": 0, "dias": 7},
    "Quincenal":  {"meses": 0, "dias": 15},
    "Mensual":    {"meses": 1, "dias": 0},
    "Bimestral":  {"meses": 2, "dias": 0},
    "Trimestral": {"meses": 3, "dias": 0},
    "Semestral":  {"meses": 6, "dias": 0},
    "Anual":      {"meses": 12,"dias": 0},
}
ANTICIPACION_OPTS = {
    "Mismo día de compra": 0,
    "1 día antes": 1,
    "2 días antes": 2,
    "3 días antes": 3,
    "1 semana antes": 7,
}
HORA_OPTS = ["7:00 AM", "9:00 AM", "12:00 PM", "6:00 PM", "8:00 PM"]
TIPO_CAMBIO_DEFAULT = 17.15

def generar_fechas_dca(fecha_inicio, fecha_fin, frecuencia):
    fechas = []
    cfg = FRECUENCIAS[frecuencia]
    current = fecha_inicio
    while current <= fecha_fin:
        fechas.append(current)
        if cfg["meses"] > 0:
            current = current + relativedelta(months=cfg["meses"])
        else:
            current = current + timedelta(days=cfg["dias"])
    return fechas

def calcular_proyeccion(fechas, titulos_por_compra, precio_actual, tipo_cambio, aplicar_comision, comision_pct):
    rows = []
    titulos_acum = 0
    capital_acum = 0.0
    for i, f in enumerate(fechas):
        precio_mxn = precio_actual * tipo_cambio
        costo_bruto = titulos_por_compra * precio_mxn
        comision_total = calcular_comision(costo_bruto, comision_pct) if aplicar_comision else 0.0
        total_pagar = costo_bruto + comision_total
        titulos_acum += titulos_por_compra
        capital_acum += total_pagar
        valor_actual = titulos_acum * precio_mxn
        rows.append({
            "Fecha": f, "Compra #": i + 1, "Títulos": titulos_por_compra,
            "Precio (MXN)": round(precio_mxn, 2), "Costo": round(costo_bruto, 2),
            "Comisión+IVA": round(comision_total, 2), "Total pagado": round(total_pagar, 2),
            "Títulos acum.": titulos_acum, "Capital acum.": round(capital_acum, 2),
            "Valor portafolio": round(valor_actual, 2),
        })
    return pd.DataFrame(rows)

def _metric_card(label, value, badge="", color="white"):
    bg = "linear-gradient(135deg,#7B6CF5,#5A4FD1)" if color == "purple" else "#FFFFFF"
    txt = "white" if color == "purple" else "#1a1a2e"
    badge_bg = "rgba(255,255,255,0.2)" if color == "purple" else "#E8FBF4"
    badge_color = "white" if color == "purple" else "#1D9E75"
    st.markdown(f"""
    <div style="background:{bg};border-radius:12px;border:0.5px solid #E8ECF4;padding:16px 18px;height:100%;">
        <div style="font-size:11px;color:{'rgba(255,255,255,.7)' if color=='purple' else '#9DA5B8'};margin-bottom:6px;">{label}</div>
        <div style="font-size:22px;font-weight:600;color:{txt};line-height:1.2;">{value}</div>
        {"" if not badge else f'<div style="display:inline-block;background:{badge_bg};color:{badge_color};font-size:11px;border-radius:20px;padding:2px 8px;margin-top:6px;">{badge}</div>'}
    </div>
    """, unsafe_allow_html=True)

def _grafica_dca(df):
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["Fecha"], y=df["Capital acum."], name="Capital invertido",
        line=dict(color="#B5D4F4", width=2, dash="dot"),
        fill="tozeroy", fillcolor="rgba(181,212,244,0.1)", mode="lines",
    ))
    fig.add_trace(go.Scatter(
        x=df["Fecha"], y=df["Valor portafolio"], name="Valor del portafolio",
        line=dict(color="#6C63FF", width=2.5),
        fill="tozeroy", fillcolor="rgba(108,99,255,0.08)",
        mode="lines+markers", marker=dict(size=5, color="#6C63FF"),
    ))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=10, b=0), height=220,
        legend=dict(orientation="h", y=-0.25, font=dict(size=11, color="#9DA5B8"), bgcolor="rgba(0,0,0,0)"),
        xaxis=dict(showgrid=False, showline=False, tickfont=dict(size=11, color="#9DA5B8")),
        yaxis=dict(gridcolor="#F0F2F8", gridwidth=0.5, showline=False,
                   tickfont=dict(size=11, color="#9DA5B8"), tickprefix="$"),
        hovermode="x unified",
    )
    return fig

@st.cache_data(ttl=3600, show_spinner=False)
def get_rendimientos_historicos(ticker: str) -> dict:
    """CAGR histórico de 1 y 5 años del ticker (None si no hay datos suficientes)."""
    import yfinance as yf
    out = {"cagr_1y": None, "cagr_5y": None}
    try:
        hist = yf.Ticker(ticker).history(period="5y")["Close"].dropna()
        if len(hist) < 30:
            return out
        ultimo = float(hist.iloc[-1])
        # 1 año ≈ 252 días hábiles
        if len(hist) > 252:
            hace_1y = float(hist.iloc[-253])
            out["cagr_1y"] = ultimo / hace_1y - 1
        # 5 años: anualizado sobre el periodo real disponible
        primero = float(hist.iloc[0])
        anios = (hist.index[-1] - hist.index[0]).days / 365.25
        if anios >= 1:
            out["cagr_5y"] = (ultimo / primero) ** (1 / anios) - 1
    except Exception:
        pass
    return out

def proyectar_escenarios(df, fechas, titulos, precio_mxn, cagr_1y, cagr_5y):
    """Agrega columnas de valor proyectado del portafolio bajo cada escenario."""
    inicio = fechas[0]
    val_1y, val_5y = [], []
    for f, tit_acum in zip(df["Fecha"], df["Títulos acum."]):
        anios = (f - inicio).days / 365.25
        if cagr_1y is not None:
            val_1y.append(round(tit_acum * precio_mxn * (1 + cagr_1y) ** anios, 2))
        if cagr_5y is not None:
            val_5y.append(round(tit_acum * precio_mxn * (1 + cagr_5y) ** anios, 2))
    if val_1y:
        df["Proyección (CAGR 1A)"] = val_1y
    if val_5y:
        df["Proyección (CAGR 5A)"] = val_5y
    return df

def _grafica_acumulacion(df):
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["Fecha"], y=df["Capital acum."], name="Capital invertido (MXN)",
        line=dict(color="#6C63FF", width=2.5),
        fill="tozeroy", fillcolor="rgba(108,99,255,0.08)",
        mode="lines+markers", marker=dict(size=5, color="#6C63FF"),
        yaxis="y",
        hovertemplate="<b>%{x|%d %b %Y}</b><br>Capital: $%{y:,.0f} MXN<extra></extra>",
    ))
    if "Proyección (CAGR 1A)" in df.columns:
        fig.add_trace(go.Scatter(
            x=df["Fecha"], y=df["Proyección (CAGR 1A)"], name="Valor proyectado (rend. 1 año)",
            line=dict(color="#F5A623", width=2, dash="dash"), mode="lines",
            hovertemplate="<b>%{x|%d %b %Y}</b><br>Proy. 1A: $%{y:,.0f} MXN<extra></extra>",
        ))
    if "Proyección (CAGR 5A)" in df.columns:
        fig.add_trace(go.Scatter(
            x=df["Fecha"], y=df["Proyección (CAGR 5A)"], name="Valor proyectado (rend. 5 años)",
            line=dict(color="#1D9E75", width=2, dash="dot"), mode="lines",
            hovertemplate="<b>%{x|%d %b %Y}</b><br>Proy. 5A: $%{y:,.0f} MXN<extra></extra>",
        ))
    fig.add_trace(go.Scatter(
        x=df["Fecha"], y=df["Títulos acum."], name="Títulos acumulados",
        line=dict(color="#9DA5B8", width=1.5, shape="hv"),
        mode="lines", yaxis="y2", visible="legendonly",
        hovertemplate="<b>%{x|%d %b %Y}</b><br>Títulos: %{y:,}<extra></extra>",
    ))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=10, b=0), height=300,
        legend=dict(orientation="h", y=-0.22, font=dict(size=11, color="#9DA5B8"), bgcolor="rgba(0,0,0,0)"),
        xaxis=dict(showgrid=False, showline=False, tickfont=dict(size=11, color="#9DA5B8")),
        yaxis=dict(
            title=dict(text="Capital (MXN)", font=dict(size=11, color="#6C63FF")),
            gridcolor="#F0F2F8", gridwidth=0.5, showline=False,
            tickfont=dict(size=11, color="#9DA5B8"), tickprefix="$",
        ),
        yaxis2=dict(
            title=dict(text="Títulos", font=dict(size=11, color="#1D9E75")),
            overlaying="y", side="right", showgrid=False,
            tickfont=dict(size=11, color="#9DA5B8"),
        ),
        hovermode="x unified",
    )
    return fig

def render_dca():
    if "dca_step" not in st.session_state:
        st.session_state.dca_step = 1
    if "dca_data" not in st.session_state:
        st.session_state.dca_data = {}
    st.markdown("""
    <div style="margin-bottom:20px;">
        <h2 style="font-size:20px;font-weight:600;color:#1a1a2e;margin:0;">DCA — Dollar Cost Averaging</h2>
        <p style="font-size:12px;color:#9DA5B8;margin:4px 0 0;">Compras recurrentes automáticas en títulos completos</p>
    </div>
    """, unsafe_allow_html=True)
    tab_nueva, tab_estrategias = st.tabs(["➕  Nueva estrategia", "📋  Mis estrategias"])
    with tab_nueva:
        _wizard_dca()
    with tab_estrategias:
        _mis_estrategias()

def _wizard_dca():
    estrategia_comun.boton_ayuda(
        "ayuda_dca",
        "📊 Cómo usar el módulo de DCA",
        "El DCA consiste en comprar la misma cantidad cada cierto tiempo, sin importar el precio. "
        "Lo armas en 4 pasos:",
        [
            ("1. Emisora", "Busca y elige la acción, ETF o FIBRA que quieres comprar (ej: NVDA, Apple, FUNO)."),
            ("2. Estrategia", "Define cada cuánto compras (frecuencia), cuántos títulos por compra y por cuánto tiempo."),
            ("3. Calendario", "Opcional: crea recordatorios automáticos en tu Google Calendar."),
            ("4. Confirmar", "Revisa el resumen y guarda la estrategia."),
            ("Después: registra tus compras", "En la pestaña 'Mis estrategias' anotas cada compra real (precio y cantidad) y sigues tu avance, con los botones Detalles, Compra y Venta."),
        ],
        nota="Los botones 'Rendimiento 1 año / 5 años' del paso 2 muestran cómo le fue a la acción en el pasado, "
             "para estimar tu inversión. Rendimientos pasados no garantizan futuros.")
    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
    step = st.session_state.dca_step
    cols_steps = st.columns(4)
    pasos = ["1. Emisora", "2. Estrategia", "3. Calendario", "4. Confirmar"]
    for i, (col, nombre) in enumerate(zip(cols_steps, pasos), start=1):
        with col:
            color = "#6C63FF" if i <= step else "#9DA5B8"
            bg = "#F0EEFF" if i <= step else "#F8F9FC"
            border = "#D4CFFF" if i <= step else "#E8ECF4"
            st.markdown(f"""
            <div style="text-align:center;background:{bg};border-radius:8px;
                        padding:8px 4px;border:0.5px solid {border};">
                <span style="font-size:12px;font-weight:500;color:{color};">{nombre}</span>
            </div>
            """, unsafe_allow_html=True)
    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
    if step == 1:
        _paso_emisora()
    elif step == 2:
        _paso_estrategia()
    elif step == 3:
        _paso_calendario()
    elif step == 4:
        _paso_confirmacion()

def _paso_emisora():
    st.markdown("""
    <div style="background:#fff;border-radius:12px;border:0.5px solid #E8ECF4;padding:20px 22px;">
        <div style="font-size:10px;color:#9DA5B8;font-weight:500;letter-spacing:.08em;
                    text-transform:uppercase;margin-bottom:6px;">Buscar emisora</div>
        <div style="font-size:11px;color:#B0B6C3;margin-bottom:14px;">
            BMV · SIC · ETFs · FIBRAs · cualquier mercado del mundo
        </div>
    """, unsafe_allow_html=True)
    datos = widget_buscador(key="dca_emisora")
    st.markdown("</div>", unsafe_allow_html=True)
    if datos:
        st.session_state.dca_data.update({
            "ticker": datos["ticker"], "precio_usd": datos["precio"],
            "nombre": datos["nombre"], "moneda": datos["moneda"], "mercado": datos["mercado"],
        })
        st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
        if st.button("Continuar →", type="primary", use_container_width=True, key="paso1_next"):
            st.session_state.dca_step = 2
            st.rerun()

def _dlg_ayuda_estrategia():
    @st.dialog("❓ Cómo armar tu estrategia DCA", width="large")
    def _d():
        st.markdown("<p style='font-size:14px;color:#4A5066;line-height:1.6;'>El <b>DCA</b> consiste en "
                    "comprar la misma cantidad cada cierto tiempo, sin importar el precio. Así te quitas el "
                    "estrés de adivinar el mejor momento. Aquí defines los detalles:</p>", unsafe_allow_html=True)
        campos = [
            ("🔁 Frecuencia de compra", "Cada cuánto compras: semanal, quincenal, mensual… La clave del DCA es que sea constante."),
            ("🔢 Títulos por compra", "Cuántas acciones (enteras) compras cada vez. Ejemplo: 2 acciones cada mes."),
            ("📅 Fecha de inicio", "Desde cuándo arranca tu plan de compras."),
            ("⏳ Duración", "Por cuánto tiempo mantienes el plan (1, 5, 10 años…). El DCA rinde mejor a largo plazo."),
        ]
        for titulo, desc in campos:
            st.markdown(
                f"<div style='margin-bottom:10px;'><b style='font-size:13px;color:#1a1a2e;'>{titulo}</b>"
                f"<div style='font-size:12.5px;color:#7B8494;line-height:1.5;'>{desc}</div></div>",
                unsafe_allow_html=True)
        st.markdown("<div style='border-top:1px solid #E8ECF4;margin:8px 0;'></div>", unsafe_allow_html=True)
        st.markdown("<p style='font-size:13px;color:#4A5066;line-height:1.6;'>"
                    "<b>Botones «Rendimiento 1 año / 5 años»:</b> muestran cómo le fue a esta acción en el "
                    "pasado, para estimar cómo podría crecer tu inversión. Ojo: los rendimientos pasados "
                    "no garantizan los futuros.</p>", unsafe_allow_html=True)
        st.caption("Herramienta educativa, no es asesoría financiera.")
    _d()


def _paso_estrategia():
    tipo_cambio = TIPO_CAMBIO_DEFAULT
    ticker = st.session_state.dca_data.get("ticker", "—")
    precio_usd = st.session_state.dca_data.get("precio_usd", 0)
    st.markdown(f"""
    <div style="background:#F8F9FC;border:0.5px solid #E2E6EE;border-radius:10px;
                padding:11px 16px;margin-bottom:16px;display:flex;
                align-items:center;justify-content:space-between;">
        <span style="font-size:14px;font-weight:600;color:#1a1a2e;">{ticker}</span>
        <span style="font-size:13px;font-weight:600;color:#1D9E75;">${precio_usd:,.2f} USD</span>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<div style='font-size:15px;font-weight:600;color:#1a1a2e;'>🧩 Arma tu estrategia</div>"
                "<div style='font-size:12px;color:#9DA5B8;'>Define cómo y cuándo vas a comprar</div>",
                unsafe_allow_html=True)
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        frecuencia = st.selectbox("Frecuencia de compra", list(FRECUENCIAS.keys()), index=2)
    with col2:
        titulos = st.number_input("Títulos por compra (enteros)", min_value=1, max_value=1000, value=2, step=1)
    col4, col5 = st.columns(2)
    with col4:
        fecha_inicio = st.date_input("Fecha de inicio", value=date.today())
    with col5:
        duracion = st.selectbox("Duración", ["1 año","2 años","3 años","5 años","10 años","Fecha personalizada"], index=3)
    if duracion == "Fecha personalizada":
        fecha_fin = st.date_input("Fecha final", value=date.today() + relativedelta(years=5))
    else:
        anios = int(duracion.split()[0])
        fecha_fin = fecha_inicio + relativedelta(years=anios)
    st.markdown("---")
    # La comisión e IVA se aplican al registrar cada compra real;
    # para la proyección se usa el estándar 0.25% + IVA como estimado.
    aplicar_comision = True
    comision_pct = 0.25
    fechas = generar_fechas_dca(fecha_inicio, fecha_fin, frecuencia)
    precio_mxn = precio_usd * tipo_cambio
    costo_titulo = calcular_comision(precio_mxn * titulos, comision_pct) if aplicar_comision else 0
    total_por_compra = precio_mxn * titulos + costo_titulo
    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
    df_prev = calcular_proyeccion(fechas, titulos, precio_usd, tipo_cambio, aplicar_comision, comision_pct)
    with st.spinner("Calculando rendimientos históricos..."):
        rend = get_rendimientos_historicos(ticker)
    cagr_1y, cagr_5y = rend["cagr_1y"], rend["cagr_5y"]
    df_prev = proyectar_escenarios(df_prev, fechas, titulos, precio_mxn, cagr_1y, cagr_5y)
    capital_total = df_prev["Capital acum."].iloc[-1]

    # ── Selector de escenario de proyección (por botones) ──
    esc_key = f"dca_esc_{ticker}"
    if esc_key not in st.session_state:
        st.session_state[esc_key] = None   # por default NO se grafica proyección
    be1, be2, be3, _ = st.columns([1.4, 1.4, 1.0, 1.2])
    if be1.button("📈 Rendimiento 1 año", key=f"dca_b1y_{ticker}", use_container_width=True):
        st.session_state[esc_key] = "1A"
    be1.caption(f"último año: **{cagr_1y*100:+.1f}%**" if cagr_1y is not None else "sin histórico")
    if be2.button("📈 Rendimiento 5 años", key=f"dca_b5y_{ticker}", use_container_width=True):
        st.session_state[esc_key] = "5A"
    be2.caption(f"anualizado 5 años: **{cagr_5y*100:+.1f}%**" if cagr_5y is not None else "sin histórico")
    if be3.button("Ocultar", key=f"dca_boff_{ticker}", use_container_width=True):
        st.session_state[esc_key] = None
    escenario = st.session_state[esc_key]
    if escenario == "1A":
        cagr_sel, col_sel, label_sel = cagr_1y, "Proyección (CAGR 1A)", "último año"
    elif escenario == "5A":
        cagr_sel, col_sel, label_sel = cagr_5y, "Proyección (CAGR 5A)", "anualizado 5 años"
    else:
        cagr_sel, col_sel, label_sel = None, None, None

    c1, c2, c3, c4 = st.columns(4)
    with c1: _metric_card("Total de compras", str(len(fechas)), "eventos en Calendar", "purple")
    with c2: _metric_card("Títulos totales", f"{len(fechas) * titulos:,}", f"{titulos}/compra")
    with c3: _metric_card("Capital total", f"${capital_total:,.0f}", "a invertir con precio actual")
    with c4:
        if escenario and cagr_sel is not None and col_sel in df_prev.columns:
            _metric_card("Valor proyectado", f"${df_prev[col_sel].iloc[-1]:,.0f}",
                         f"rend. {label_sel} {cagr_sel*100:+.1f}%/año")
        else:
            _metric_card("Valor proyectado", "—", "elige un escenario")

    # Graficar solo el escenario elegido (o ninguno por default)
    df_chart = df_prev.copy()
    for c in ["Proyección (CAGR 1A)", "Proyección (CAGR 5A)"]:
        if c != col_sel and c in df_chart.columns:
            df_chart = df_chart.drop(columns=[c])

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    if escenario and cagr_sel is not None:
        activo = f'<span style="background:#F0EEFF;color:#6C63FF;border-radius:20px;padding:2px 10px;font-size:11px;font-weight:600;">Mostrando proyección: rendimiento {label_sel} ({cagr_sel*100:+.1f}%/año)</span>'
    elif escenario and cagr_sel is None:
        activo = '<span style="font-size:11px;color:#9DA5B8;">Sin histórico suficiente para este escenario.</span>'
    else:
        activo = '<span style="font-size:11px;color:#9DA5B8;">Pulsa <b>Rendimiento 1 año</b> o <b>Rendimiento 5 años</b> para ver la proyección sobre tu estrategia.</span>'
    st.markdown(f"""
    <div style="background:#fff;border-radius:12px;border:0.5px solid #E8ECF4;padding:18px 22px 8px;">
    <div style="font-size:13px;font-weight:600;color:#1a1a2e;margin-bottom:4px;">Proyección a través del tiempo</div>
    <div style="font-size:11px;color:#9DA5B8;margin-bottom:8px;">Capital invertido vs valor estimado del portafolio. Elige arriba el escenario de rendimiento histórico (1 o 5 años).</div>
    <div style="margin-bottom:10px;">{activo}</div>
    """, unsafe_allow_html=True)
    st.plotly_chart(_grafica_acumulacion(df_chart), use_container_width=True)
    st.markdown("""
    <div style="font-size:10.5px;color:#9DA5B8;font-style:italic;text-align:center;padding:4px 0 10px;">
        ⚠️ Los rendimientos pasados no garantizan rendimientos futuros. Esta proyección es solo una estimación con fines ilustrativos.
    </div>
    </div>""", unsafe_allow_html=True)
    st.session_state.dca_data.update({
        "frecuencia": frecuencia, "titulos": titulos,
        "fecha_inicio": fecha_inicio, "fecha_fin": fecha_fin,
        "aplicar_comision": aplicar_comision, "comision_pct": comision_pct, "fechas": fechas,
    })
    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    col_back, _, col_next = st.columns([1, 4, 1])
    with col_back:
        if st.button("← Atrás", key="back2"):
            st.session_state.dca_step = 1; st.rerun()
    with col_next:
        if st.button("Continuar →", type="primary", key="next2"):
            st.session_state.dca_step = 3; st.rerun()

def _paso_calendario():
    d = st.session_state.dca_data
    ticker = d.get("ticker", "—")
    titulos = d.get("titulos", 0)
    fechas = d.get("fechas", [])
    frec = d.get("frecuencia", "—")
    st.markdown(f"""
    <div style="background:#F8F9FC;border:0.5px solid #E2E6EE;border-radius:10px;
                padding:11px 16px;margin-bottom:16px;display:flex;
                align-items:center;justify-content:space-between;">
        <div>
            <span style="font-size:14px;font-weight:600;color:#1a1a2e;">{ticker}</span>
            <span style="font-size:11px;color:#9DA5B8;margin-left:8px;">{titulos} títulos · {frec} · {len(fechas)} compras</span>
        </div>
        <span style="font-size:12px;font-weight:500;color:#6C63FF;background:#F0EEFF;
                     padding:3px 10px;border-radius:20px;">{len(fechas)} eventos</span>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("""
    <div style="background:#fff;border-radius:12px;border:0.5px solid #E8ECF4;padding:20px 22px;">
    <div style="font-size:10px;color:#9DA5B8;font-weight:500;letter-spacing:.08em;
                text-transform:uppercase;margin-bottom:14px;">Recordatorios de compra</div>
    """, unsafe_allow_html=True)
    col_icon, col_text, col_toggle = st.columns([0.08, 0.78, 0.14])
    with col_icon:
        st.markdown("<div style='font-size:24px;margin-top:6px;'>📅</div>", unsafe_allow_html=True)
    with col_text:
        st.markdown("""
        <div style='margin-top:4px;'>
            <div style='font-size:13px;font-weight:500;color:#1a1a2e;'>Google Calendar</div>
            <div style='font-size:11px;color:#9DA5B8;'>Evento recurrente en tu calendario</div>
        </div>
        """, unsafe_allow_html=True)
    with col_toggle:
        activar_cal = st.toggle("", key="activar_gcal", label_visibility="collapsed")
    st.markdown("</div>", unsafe_allow_html=True)
    if activar_cal:
        st.markdown("""
        <div style="background:#F0EEFF;border:0.5px solid #D4CFFF;border-radius:12px;
                    padding:16px 20px;margin-top:10px;">
        <div style="font-size:10px;color:#6C63FF;font-weight:500;letter-spacing:.08em;
                    text-transform:uppercase;margin-bottom:14px;">Configuración del recordatorio</div>
        """, unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            anticipacion = st.selectbox("Recordar con anticipación", list(ANTICIPACION_OPTS.keys()), index=1, key="cal_anticipacion")
        with col2:
            hora = st.selectbox("Hora del recordatorio", HORA_OPTS, index=1, key="cal_hora")
        dias_antes = ANTICIPACION_OPTS[anticipacion]
        st.markdown("""
        <div style="background:#fff;border:0.5px solid #D4CFFF;border-radius:9px;padding:12px 14px;margin-top:6px;">
        <div style="font-size:10px;color:#9DA5B8;letter-spacing:.06em;text-transform:uppercase;margin-bottom:10px;">Vista previa de eventos</div>
        """, unsafe_allow_html=True)
        for i, f in enumerate(fechas[:3]):
            f_rec = f - timedelta(days=dias_antes)
            opacidad = "1" if i == 0 else "0.5"
            st.markdown(f"""
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;opacity:{opacidad};">
                <div style="width:9px;height:9px;border-radius:2px;background:{'#6C63FF' if i==0 else '#B5D4F4'};flex-shrink:0;"></div>
                <div>
                    <div style="font-size:12px;font-weight:500;color:#1a1a2e;">📈 Compra DCA — {ticker} · {titulos} títulos</div>
                    <div style="font-size:11px;color:#9DA5B8;">{f_rec.strftime('%d %b %Y')} · {hora}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
        st.markdown(f"""
        <div style="border-top:0.5px solid #F0F2F8;padding-top:8px;margin-top:4px;">
            <span style="background:#6C63FF;color:white;font-size:10px;font-weight:500;border-radius:20px;padding:2px 8px;">+{len(fechas)-3} eventos más</span>
            <span style="font-size:11px;color:#9DA5B8;margin-left:6px;">hasta {fechas[-1].strftime('%b %Y')} · todos creados de una sola vez</span>
        </div>
        """, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
        st.info("⚡ Solo conectas Google **una vez**. Los recordatorios quedan guardados permanentemente en tu calendario.")
        st.markdown("</div>", unsafe_allow_html=True)
        st.session_state.dca_data.update({"cal_activado": True, "cal_anticip": dias_antes, "cal_hora": hora})
    else:
        st.session_state.dca_data["cal_activado"] = False
    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    col_back, _, col_next = st.columns([1, 4, 1])
    with col_back:
        if st.button("← Atrás", key="back3"):
            st.session_state.dca_step = 2; st.rerun()
    with col_next:
        lbl = "Crear eventos y confirmar →" if activar_cal else "Confirmar →"
        if st.button(lbl, type="primary", key="next3"):
            st.session_state.dca_step = 4; st.rerun()

def _paso_confirmacion():
    d = st.session_state.dca_data
    ticker = d.get("ticker","—"); titulos = d.get("titulos",0)
    frecuencia = d.get("frecuencia","—"); fechas = d.get("fechas",[])
    precio_usd = d.get("precio_usd",0)
    aplicar = d.get("aplicar_comision",True); comision = d.get("comision_pct",0.25)
    cal_on = d.get("cal_activado",False); cal_hora = d.get("cal_hora","9:00 AM")
    cal_dias = d.get("cal_anticip",1)
    st.markdown(f"""
    <div style="background:#F8F9FC;border:0.5px solid #E2E6EE;border-radius:10px;
                padding:11px 16px;margin-bottom:16px;display:flex;
                align-items:center;justify-content:space-between;">
        <span style="font-size:14px;font-weight:600;color:#1a1a2e;">{ticker}</span>
        <span style="font-size:11px;color:#9DA5B8;">{titulos} títulos · {frecuencia} · {len(fechas)} compras</span>
    </div>
    """, unsafe_allow_html=True)
    tipo_cambio = st.number_input(
        "Tipo de cambio actual (MXN/USD)",
        min_value=1.0,
        value=float(d.get("tipo_cambio", TIPO_CAMBIO_DEFAULT)),
        step=0.01,
        format="%.2f",
        help="Ingresa el tipo de cambio del día en que vas a registrar la compra"
    )
    d["tipo_cambio"] = tipo_cambio
    df = calcular_proyeccion(fechas, titulos, precio_usd, tipo_cambio, aplicar, comision)
    st.markdown("### Resumen de tu estrategia DCA")
    ganancia_est = df["Valor portafolio"].iloc[-1] - df["Capital acum."].iloc[-1]
    c1, c2, c3, c4 = st.columns(4)
    with c1: _metric_card("Capital invertido", f"${df['Capital acum.'].iloc[-1]:,.0f} MXN", f"{len(fechas)} compras", "purple")
    with c2: _metric_card("Valor estimado", f"${df['Valor portafolio'].iloc[-1]:,.0f} MXN", "al precio actual")
    with c3: _metric_card("Títulos totales", f"{df['Títulos acum.'].iloc[-1]:,}", f"{titulos}/compra · {frecuencia.lower()}")
    with c4: _metric_card("Ganancia estimada", f"${ganancia_est:,.0f} MXN", "al precio actual")
    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    st.markdown("""
    <div style="background:#fff;border-radius:12px;border:0.5px solid #E8ECF4;padding:18px 22px;margin-bottom:16px;">
    <div style="font-size:13px;font-weight:600;color:#1a1a2e;margin-bottom:4px;">Capital invertido vs Valor del portafolio</div>
    <div style="font-size:11px;color:#9DA5B8;margin-bottom:12px;">Proyección al precio actual</div>
    """, unsafe_allow_html=True)
    st.plotly_chart(_grafica_dca(df), use_container_width=True, config={"displayModeBar": False})
    st.markdown("</div>", unsafe_allow_html=True)
    cols_show = ["Fecha","Títulos","Precio (MXN)","Total pagado","Títulos acum.","Capital acum."]
    st.dataframe(
        df[cols_show].head(5).style.format({"Precio (MXN)":"${:,.2f}","Total pagado":"${:,.2f}","Capital acum.":"${:,.0f}"}),
        use_container_width=True, hide_index=True,
    )
    if cal_on:
        st.success(f"📅 Se crearán **{len(fechas)} eventos** en Google Calendar — {cal_dias} día(s) antes a las {cal_hora}")
    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    col_back, col_export, col_guardar = st.columns([1, 2, 2])
    with col_back:
        if st.button("← Atrás", key="back4"):
            st.session_state.dca_step = 3; st.rerun()
    with col_export:
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button("⬇ Exportar a CSV", data=csv, file_name=f"DCA_{ticker}_{date.today()}.csv", mime="text/csv", use_container_width=True)
    with col_guardar:
        if st.button("✅ Guardar estrategia", type="primary", use_container_width=True):
            save_strategy(d)
            if cal_on:
                create_calendar_events(ticker=ticker, titulos=titulos, fechas=fechas, hora=cal_hora, dias_antes=cal_dias)
            st.success(f"✅ Estrategia DCA '{ticker}' guardada.")
            st.session_state.dca_step = 1; st.session_state.dca_data = {}; st.rerun()

def _mis_estrategias():
    estrategias = load_strategies()
    if not estrategias:
        st.markdown("""
        <div style="text-align:center;padding:48px 24px;color:#9DA5B8;">
            <div style="font-size:32px;margin-bottom:12px;">📋</div>
            <div style="font-size:14px;font-weight:500;color:#4A5066;">Sin estrategias guardadas</div>
            <div style="font-size:12px;margin-top:6px;">Crea tu primera estrategia DCA en la pestaña "Nueva estrategia"</div>
        </div>
        """, unsafe_allow_html=True)
        return
    for e in estrategias:
        _tarjeta_estrategia_lista(e)


def _estado_proxima_compra(e: dict, hechas: int):
    """Calcula el estado de la próxima compra: días que faltan o de retraso."""
    f_ini = _parse_fecha(e.get("fecha_inicio"))
    f_fin = _parse_fecha(e.get("fecha_fin"))
    frecuencia = e.get("frecuencia")
    if not (f_ini and f_fin and frecuencia in FRECUENCIAS):
        return None
    plan = generar_fechas_dca(f_ini, f_fin, frecuencia)
    if not plan:
        return None
    hoy = date.today()
    if hechas >= len(plan):
        return {"pct": 1.0, "color": "#1D9E75", "label": "✅ Estrategia completada", "sub": ""}
    prox = plan[hechas]
    prev = plan[hechas - 1] if hechas >= 1 else f_ini
    delta = (prox - hoy).days
    if delta < 0:
        return {"pct": 1.0, "color": "#E24B4A",
                "label": f"⚠️ {-delta} día(s) de retraso",
                "sub": f"pendiente del {prox.strftime('%d/%m/%Y')}"}
    interval = max((prox - prev).days, 1)
    elapsed = max((hoy - prev).days, 0)
    pct = min(elapsed / interval, 1.0)
    color = "#EF9F27" if delta <= 3 else "#6C63FF"
    return {"pct": pct, "color": color,
            "label": f"⏳ Faltan {delta} día(s) para la próxima compra",
            "sub": f"próxima: {prox.strftime('%d/%m/%Y')}"}


def _barra_estado_html(info: dict) -> str:
    if not info:
        return ""
    pct = int(round(info["pct"] * 100))
    sub = f"<span style='color:#9DA5B8;font-weight:400;'> · {info['sub']}</span>" if info["sub"] else ""
    return f"""
    <div style="margin:8px 0 2px;">
      <div style="background:#E8ECF4;border-radius:20px;height:8px;overflow:hidden;">
        <div style="width:{pct}%;height:100%;background:{info['color']};border-radius:20px;"></div>
      </div>
      <div style="font-size:11.5px;color:{info['color']};margin-top:5px;font-weight:600;">{info['label']}{sub}</div>
    </div>
    """


def _tarjeta_estrategia_lista(e: dict):
    eid = e["id"]
    ticker = e["ticker"]
    frecuencia = e.get("frecuencia", "—")
    titulos = int(e.get("titulos") or 0)

    compras = load_purchases(eid)
    n_reg = len(compras)
    acciones = sum(int(c["titulos"]) for c in compras)
    disp = titulos_disponibles("DCA", eid)
    if acciones > 0:
        acc_txt = f"🛒 {acciones} compradas · {disp} disponibles"
        acc_color = "#1D9E75"
    else:
        acc_txt = "🛒 Sin compras aún"
        acc_color = "#9DA5B8"

    with st.container(border=True):
        st.markdown(
            f"<div style='font-size:15px;'>📈 "
            f"<b style='color:#1a1a2e;'>{estrategia_comun.esc(ticker)}</b> "
            f"<span style='color:#9DA5B8;font-size:13px;'>— {frecuencia} · {titulos} títulos</span></div>"
            f"<div style='font-size:12px;color:{acc_color};font-weight:600;margin-top:3px;'>{acc_txt}</div>",
            unsafe_allow_html=True)
        st.markdown(_barra_estado_html(_estado_proxima_compra(e, n_reg)), unsafe_allow_html=True)

        b1, b2, b3, b4 = st.columns([1.3, 1.2, 1.2, 0.6])
        if b1.button("Detalles", key=f"det_{eid}", use_container_width=True):
            _dlg_detalle(e)
        if b2.button("Compra", key=f"cmp_{eid}", use_container_width=True):
            _dlg_compra(e)
        if b3.button("Venta", key=f"vta_{eid}", use_container_width=True):
            _dlg_venta(e)
        if b4.button("🗑", key=f"del_{eid}", use_container_width=True, help="Borrar estrategia"):
            _dlg_borrar(e)


# ── Ventanas (modales) de la estrategia ──────────────────────────────────────
def _dlg_detalle(e):
    @st.dialog(f"📈 {e['ticker']}", width="large")
    def _d():
        with st.spinner("Cargando datos…"):
            _detalle_estrategia(e)
    _d()


def _dlg_compra(e):
    @st.dialog(f"Registrar compra · {e['ticker']}")
    def _d():
        _dca_form_compra(e)
    _d()


def _dlg_venta(e):
    @st.dialog(f"Registrar venta · {e['ticker']}")
    def _d():
        _dca_form_venta(e)
    _d()


def _dlg_borrar(e):
    @st.dialog("Borrar estrategia")
    def _d():
        st.warning(f"¿Borrar la estrategia **{e['ticker']}**?")
        st.caption("Se eliminan sus compras y ventas registradas. No se puede deshacer.")
        if st.button("Sí, borrar", type="primary", use_container_width=True, key=f"delok_{e['id']}"):
            delete_strategy(e["id"])
            invalidar_resumen()
            st.rerun()
    _d()


def _dca_form_compra(e):
    eid = e["id"]
    ticker = e["ticker"]
    titulos_x_compra = int(e.get("titulos") or 0)
    es_mx = ticker.upper().endswith(".MX")
    fx_hoy = get_tipo_cambio_actual()
    with st.form(f"form_compra_{eid}", clear_on_submit=True):
        c1, c2 = st.columns(2)
        fecha_c = c1.date_input("Fecha", value=date.today(), max_value=date.today(), key=f"fc_{eid}")
        titulos_c = c2.number_input("Cantidad de acciones", min_value=1,
                                    value=titulos_x_compra or 1, step=1, key=f"tc_{eid}")
        precio_c = st.number_input("Precio de compra (MXN)", min_value=0.01, value=100.0,
                                   step=0.01, format="%.2f", key=f"pc_{eid}")
        if es_mx:
            fx_c = 1.0
        else:
            fx_c = st.number_input("Tipo de cambio (MXN/USD)", min_value=1.0, value=fx_hoy,
                                   step=0.01, format="%.4f", key=f"fx_{eid}",
                                   help="Solo informativo; el precio ya va en pesos.")
        st.caption("La comisión se calcula automáticamente con el % de tu perfil.")
        registrar = st.form_submit_button("➕ Registrar compra", type="primary", use_container_width=True)
    if registrar:
        importe = int(titulos_c) * float(precio_c)
        comision_mxn = comision_desde_perfil(importe)
        save_purchase(eid, fecha_c, int(titulos_c), float(precio_c), float(fx_c), comision_mxn)
        invalidar_resumen()
        st.success(f"✅ Compra registrada: {int(titulos_c)} de {ticker} a ${precio_c:,.2f} MXN")
        st.rerun()


def _dca_form_venta(e):
    eid = e["id"]
    ticker = e["ticker"]
    disp = titulos_disponibles("DCA", eid)
    st.markdown(f"Disponibles para vender: **{disp}** título(s)")
    if disp <= 0:
        st.info("No tienes títulos disponibles. Registra una compra primero.")
        return
    with st.form(f"form_venta_{eid}", clear_on_submit=True):
        c1, c2 = st.columns(2)
        fecha_v = c1.date_input("Fecha de venta", value=date.today(), max_value=date.today(), key=f"vf_{eid}")
        tit_v = c2.number_input("Acciones a vender", min_value=1, max_value=int(disp),
                                value=1, step=1, key=f"vt_{eid}")
        precio_v = st.number_input("Precio de venta (MXN)", min_value=0.01, value=100.0,
                                   step=0.01, format="%.2f", key=f"vp_{eid}")
        st.caption("La comisión se calcula automáticamente con el % de tu perfil.")
        registrar = st.form_submit_button("➖ Registrar venta", type="primary", use_container_width=True)
    if registrar:
        importe = int(tit_v) * float(precio_v)
        com = comision_desde_perfil(importe)
        r = registrar_venta("DCA", eid, ticker, fecha_v, int(tit_v), float(precio_v), comision=com)
        if r["ok"]:
            invalidar_resumen()
            g = r["ganancia"]
            signo = "ganancia" if g >= 0 else "pérdida"
            st.success(f"✅ Venta registrada: {int(tit_v)} de {ticker} a ${precio_v:,.2f} MXN · "
                       f"{signo} de ${abs(g):,.2f} MXN")
            st.rerun()
        else:
            st.error(r["msg"])

MESES_ES = ["enero","febrero","marzo","abril","mayo","junio",
            "julio","agosto","septiembre","octubre","noviembre","diciembre"]
DIAS_ES = ["lunes","martes","miércoles","jueves","viernes","sábado","domingo"]

def _parse_fecha(s):
    try:
        return date.fromisoformat(str(s)[:10])
    except Exception:
        return None

def _dia_compra_str(frecuencia: str, fecha_inicio) -> str:
    f = _parse_fecha(fecha_inicio)
    if not f:
        return "—"
    dia = f.day
    if frecuencia == "Semanal":
        return f"cada {DIAS_ES[f.weekday()]}"
    if frecuencia == "Quincenal":
        dia2 = dia + 15 if dia + 15 <= 30 else dia + 15 - 30
        return f"días {min(dia, dia2)} y {max(dia, dia2)} de cada mes"
    if frecuencia == "Mensual":
        return f"día {dia} de cada mes"
    if frecuencia == "Bimestral":
        return f"día {dia} cada 2 meses"
    if frecuencia == "Trimestral":
        return f"día {dia} cada 3 meses"
    if frecuencia == "Semestral":
        return f"día {dia} cada 6 meses"
    if frecuencia == "Anual":
        return f"cada {dia} de {MESES_ES[f.month - 1]}"
    return "—"

def _seccion_detalle(label: str):
    st.markdown(f"""
    <div style="border-top:1px solid #E8ECF4;margin:16px 0 8px;padding-top:12px;
                font-size:11px;font-weight:600;color:#6C63FF;
                letter-spacing:.07em;text-transform:uppercase;">{label}</div>
    """, unsafe_allow_html=True)


def _ventas_registradas_detalle(modulo: str, estrategia_id: int):
    """Sección reusable: historial de ventas de la estrategia con su % de rendimiento."""
    ventas = load_ventas_cerradas(modulo, estrategia_id)
    if not ventas:
        return
    _seccion_detalle("Ventas registradas")
    enc = st.columns([1.3, 0.9, 1.2, 1.3, 1.0])
    for c, h in zip(enc, ["Fecha", "Tít.", "Precio", "Ganancia", "Rend."]):
        c.markdown(f"<div style='font-size:11px;color:#9DA5B8;font-weight:600;'>{h}</div>",
                   unsafe_allow_html=True)
    tot_gan = 0.0
    for v in ventas:
        tot_gan += v["ganancia"]
        rc = "#1D9E75" if v["ganancia"] >= 0 else "#A32D2D"
        rend = (v["ganancia"] / v["costo_base"] * 100) if v["costo_base"] else 0.0
        cols = st.columns([1.3, 0.9, 1.2, 1.3, 1.0])
        cols[0].markdown(f"<div style='font-size:12.5px;padding:3px 0;'>{str(v['fecha'])[:10]}</div>", unsafe_allow_html=True)
        cols[1].markdown(f"<div style='font-size:12.5px;padding:3px 0;'>{v['titulos']}</div>", unsafe_allow_html=True)
        cols[2].markdown(f"<div style='font-size:12.5px;padding:3px 0;'>${v['precio']:,.2f}</div>", unsafe_allow_html=True)
        cols[3].markdown(f"<div style='font-size:12.5px;font-weight:600;color:{rc};padding:3px 0;'>${v['ganancia']:,.2f}</div>", unsafe_allow_html=True)
        cols[4].markdown(f"<div style='font-size:12.5px;font-weight:600;color:{rc};padding:3px 0;'>{rend:+.1f}%</div>", unsafe_allow_html=True)
    col_t = "#1D9E75" if tot_gan >= 0 else "#A32D2D"
    st.markdown(f"<div style='font-size:12px;margin-top:6px;'>Ganancia realizada total: "
                f"<b style='color:{col_t};'>${tot_gan:,.2f} MXN</b></div>", unsafe_allow_html=True)

def _detalle_estrategia(e: dict):
    # Letra más compacta en las métricas de este panel
    st.markdown("""
    <style>
    div[data-testid="stExpanderDetails"] [data-testid="stMetricValue"] { font-size: 1.15rem !important; }
    div[data-testid="stExpanderDetails"] [data-testid="stMetricLabel"] { font-size: 0.72rem !important; }
    div[data-testid="stExpanderDetails"] [data-testid="stMetricDelta"] { font-size: 0.72rem !important; }
    </style>
    """, unsafe_allow_html=True)
    eid = e["id"]
    ticker = e["ticker"]
    titulos_x_compra = int(e.get("titulos") or 0)
    frecuencia = e.get("frecuencia", "—")
    f_ini = _parse_fecha(e.get("fecha_inicio"))
    f_fin = _parse_fecha(e.get("fecha_fin"))
    n_total = int(e.get("n_fechas") or 0)
    titulos_meta = n_total * titulos_x_compra

    # ── Compras registradas (precios en MXN) ──
    compras = load_purchases(eid)
    titulos_comprados = sum(c["titulos"] for c in compras)
    capital_invertido = sum(
        c["titulos"] * c["precio"] + (c.get("comision") or 0.0) for c in compras
    )  # MXN, incluye comisiones e IVA
    titulos_faltantes = max(titulos_meta - titulos_comprados, 0)
    es_mx = ticker.upper().endswith(".MX")
    fx_hoy = get_tipo_cambio_actual()

    # Plan de compras y retraso
    fechas_plan = []
    if f_ini and f_fin and frecuencia in FRECUENCIAS:
        fechas_plan = generar_fechas_dca(f_ini, f_fin, frecuencia)
    fechas_vencidas = [f for f in fechas_plan if f <= date.today()]
    compras_esperadas = len(fechas_vencidas)
    retraso_dias = 0
    if compras_esperadas > len(compras):
        primera_pendiente = fechas_vencidas[len(compras)]
        retraso_dias = (date.today() - primera_pendiente).days

    # ── Datos generales ──
    _seccion_detalle("Datos generales")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Frecuencia de compra", frecuencia)
    c2.metric("Títulos por compra", str(titulos_x_compra))
    c3.metric("Inicio", str(e.get("fecha_inicio","—")))
    c4.metric("Fin", str(e.get("fecha_fin","—")))
    c5.metric("Compras totales", str(n_total))

    if retraso_dias > 0:
        estado_html = (f'<div style="margin-top:5px;color:#A32D2D;font-size:12px;">'
                       f'⚠️ <b>{retraso_dias} día{"s" if retraso_dias != 1 else ""} de retraso</b> — '
                       f'compra pendiente del {primera_pendiente.strftime("%d/%m/%Y")}</div>')
    else:
        estado_html = '<div style="margin-top:5px;color:#1D9E75;font-size:12px;">✅ Al corriente con las compras</div>'
    st.markdown(f"""
    <div style="background:#F0EEFF;border:0.5px solid #D4CFFF;border-radius:8px;
                padding:8px 14px;margin:4px 0 10px;font-size:12.5px;color:#4A4099;">
        🗓 <b>Día de compra:</b> {_dia_compra_str(frecuencia, e.get("fecha_inicio"))}
        {estado_html}
    </div>
    """, unsafe_allow_html=True)

    # Barra de progreso de la estrategia
    pct = min(len(compras) / n_total, 1.0) if n_total else 0.0
    st.progress(pct, text=f"Progreso: {len(compras)} de {n_total} compras realizadas ({pct*100:.0f}%)")

    # Botón Google Calendar (por si no se hizo al crear la estrategia)
    fechas_futuras = [f for f in fechas_plan if f >= date.today()]
    if fechas_futuras:
        if e.get("cal_creado"):
            st.button("✅ Recordatorios ya agregados a Google Calendar",
                      key=f"gcal_{eid}", disabled=True, use_container_width=True)
            st.caption("Ya creaste estos recordatorios; el botón se deshabilitó para no duplicarlos.")
        else:
            if st.button(f"📅 Agregar {len(fechas_futuras)} recordatorios a Google Calendar",
                         key=f"gcal_{eid}", use_container_width=True):
                ok = create_calendar_events(
                    ticker=ticker, titulos=titulos_x_compra, fechas=fechas_futuras,
                    hora=e.get("cal_hora") or "9:00 AM", dias_antes=int(e.get("cal_anticip") or 1),
                )
                if ok:
                    set_cal_creado(eid)
                    st.rerun()

    # ── Compras registradas ──
    _seccion_detalle("Compras registradas")
    if compras:
        df_c = pd.DataFrame(compras)[["fecha", "titulos", "precio", "tipo_cambio", "comision"]]
        df_c["comision"] = df_c["comision"].fillna(0.0)
        df_c["total"] = df_c["titulos"] * df_c["precio"] + df_c["comision"]
        if es_mx:
            df_c = df_c[["fecha", "titulos", "precio", "comision", "total"]]
            df_c.columns = ["Fecha", "Acciones", "Precio MXN", "Comisión+IVA", "Total MXN"]
            fmt = {"Precio MXN": "${:,.2f}", "Comisión+IVA": "${:,.2f}", "Total MXN": "${:,.2f}"}
        else:
            df_c["precio_usd"] = df_c["precio"] / df_c["tipo_cambio"]
            df_c = df_c[["fecha", "titulos", "precio", "tipo_cambio", "precio_usd", "comision", "total"]]
            df_c.columns = ["Fecha", "Acciones", "Precio MXN", "TC", "Precio USD", "Comisión+IVA", "Total MXN"]
            fmt = {"Precio MXN": "${:,.2f}", "TC": "{:.4f}", "Precio USD": "${:,.2f}",
                   "Comisión+IVA": "${:,.2f}", "Total MXN": "${:,.2f}"}
        st.dataframe(
            df_c.style.format(fmt),
            use_container_width=True, hide_index=True, height=min(38 * (len(df_c) + 1), 220),
        )

    # ── Ventas registradas (historial de rendimiento realizado) ──
    _ventas_registradas_detalle("DCA", eid)

    # ── Resumen de la estrategia ──
    _seccion_detalle("Resumen de la estrategia")
    quote = get_precio_actual(ticker)
    precio_hoy = quote["precio"] if quote else None
    moneda = quote["moneda"] if quote else ""
    # Convertir el precio actual a MXN si el ticker cotiza en USD
    if precio_hoy is not None and not es_mx and moneda != "MXN":
        precio_hoy_mxn = precio_hoy * fx_hoy
    else:
        precio_hoy_mxn = precio_hoy
    valor_actual = titulos_comprados * precio_hoy_mxn if precio_hoy_mxn else None
    ganancia = (valor_actual - capital_invertido) if valor_actual is not None and compras else None
    if precio_hoy is not None:
        detalle_fx = f" · TC hoy: {fx_hoy:.4f}" if not es_mx else ""
        st.caption(f"Precio actual de {ticker}: \\${precio_hoy:,.2f} {moneda}"
                   + (f" ≈ \\${precio_hoy_mxn:,.2f} MXN" if not es_mx else "") + detalle_fx)

    r1, r2, r3, r4, r5 = st.columns(5)
    r1.metric("Acciones acumuladas", f"{titulos_comprados:,}",
              delta=f"plan a hoy: {compras_esperadas * titulos_x_compra:,}", delta_color="off")
    r2.metric("Acciones faltantes", f"{titulos_faltantes:,}",
              delta=f"meta: {titulos_meta:,}", delta_color="off")
    r3.metric("Capital invertido", f"${capital_invertido:,.2f} MXN")
    r4.metric("Valor actual", f"${valor_actual:,.2f} MXN" if valor_actual is not None else "—")
    if ganancia is not None:
        r5.metric("Ganancia / Pérdida", f"${ganancia:,.2f}",
                  delta=f"{(ganancia / capital_invertido * 100) if capital_invertido else 0:+.2f}%")
    else:
        r5.metric("Ganancia / Pérdida", "—")
    if not compras:
        st.caption("Aún no has registrado compras en esta estrategia — usa el formulario de arriba para empezar.")
