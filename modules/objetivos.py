import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import date
from dateutil.relativedelta import relativedelta

from utils.ticker_search import widget_buscador, get_precio_actual, get_tipo_cambio_actual
from utils.comisiones import comision_desde_perfil
from utils.technical_utils import get_ohlc, resample_ohlc, sugerir_entrada_salida
from utils.db_utils import (
    save_obj_strategy, load_obj_strategies, delete_obj_strategy,
    save_obj_purchase, load_obj_purchases, delete_obj_purchase,
    save_obj_sale, load_obj_sales, delete_obj_sale, log_venta_cerrada,
)
from modules import estrategia_comun
from utils.resumen_utils import invalidar_resumen

PURPLE = "#6C63FF"
GREEN = "#1D9E75"
RED = "#A32D2D"
GOLD = "#C77F00"
BLUE = "#4F9BF0"


# ─────────────────────────────────────────────────────────────────────────────
def render_objetivos():
    st.markdown("""
    <div style="margin-bottom:20px;">
        <h2 style="font-size:20px;font-weight:600;color:#1a1a2e;margin:0;">Trading por Objetivos</h2>
        <p style="font-size:12px;color:#9DA5B8;margin:4px 0 0;">Análisis técnico — define precio de entrada y salida, y sigue tu meta</p>
    </div>
    """, unsafe_allow_html=True)
    if load_obj_strategies():
        tab_estrategias, tab_analisis = st.tabs(["📋  Mis estrategias", "📊  Análisis técnico"])
    else:
        tab_analisis, tab_estrategias = st.tabs(["📊  Análisis técnico", "📋  Mis estrategias"])
    with tab_analisis:
        _tab_analisis()
    with tab_estrategias:
        _mis_estrategias_obj()


# ── Tab 1: análisis técnico ──────────────────────────────────────────────────
def _tab_analisis():
    estrategia_comun.boton_ayuda(
        "ayuda_obj",
        "🎯 Cómo usar el módulo Por Objetivos",
        "Aquí defines a qué precio quieres COMPRAR una acción y a qué precio quieres VENDER (tu meta), "
        "y le das seguimiento. Pasos:",
        [
            ("1. Busca una acción", "Escríbela arriba para ver su gráfica de precios de los últimos años."),
            ("2. Explora la gráfica", "Puedes cambiar entre línea y velas, y activar medias móviles, Bandas de Bollinger o RSI."),
            ("3. Define entrada y salida", "Escribe el precio al que quieres COMPRAR (entrada) y al que quieres VENDER (salida). La app te muestra la ganancia objetivo."),
            ("4. Guárdala y opera", "Pulsa 'Guardar en Mis estrategias'. Luego, en esa pestaña, registras tus compras y ventas por lote."),
        ],
        nota="El botón '🤖 Analizar gráfica' te sugiere precios de entrada/salida según el análisis técnico; puedes editarlos a tu gusto.")
    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
    st.markdown("**Selecciona la acción a analizar**")
    datos = widget_buscador(key="obj_buscar")
    if not datos:
        st.info("Busca una acción arriba para cargar su análisis técnico de los últimos 10 años.")
        return
    ticker = datos["ticker"]
    nombre = datos.get("nombre", ticker)
    precio_actual = datos.get("precio", 0)
    moneda = datos.get("moneda", "USD")

    df = get_ohlc(ticker)
    if df.empty:
        st.warning(f"No se pudo cargar el histórico de {ticker}.")
        return

    st.markdown("---")
    # Controles de la gráfica
    c1, cf = st.columns(2)
    tipo_chart = c1.radio("Tipo de gráfica", ["Área (línea)", "Velas japonesas"],
                          key=f"obj_tipo_{ticker}")
    freq = cf.radio("Agrupar por", ["1D", "1S", "1M"],
                    key=f"obj_freq_{ticker}",
                    help="1D = diario · 1S = semanal · 1M = mensual")
    df = resample_ohlc(df, freq)
    fmin = df["Fecha"].min().date()
    fmax = df["Fecha"].max().date()
    di_key = f"obj_di_{ticker}_{freq}"
    df_key = f"obj_df_{ticker}_{freq}"
    # Valores por defecto (últimos 10 años); un rango propio por temporalidad (1D/1S/1M)
    st.session_state.setdefault(di_key, max(fmin, fmax - relativedelta(years=10)))
    st.session_state.setdefault(df_key, fmax)

    # Temporalidad a lo ancho (el rango de tiempo que se ve en la gráfica).
    st.markdown("<div style='font-size:12px;color:#9DA5B8;font-weight:600;margin:10px 0 3px;'>"
                "Temporalidad <span style='color:#C3C9D6;font-weight:500;'>(M = meses · A = años)</span></div>",
                unsafe_allow_html=True)
    rangos = [("6M", relativedelta(months=6)), ("1A", relativedelta(years=1)),
              ("3A", relativedelta(years=3)), ("5A", relativedelta(years=5)),
              ("10A", relativedelta(years=10))]
    zc = st.columns(len(rangos))
    for i, (lbl, delta) in enumerate(rangos):
        if zc[i].button(lbl, key=f"obj_zoom_{ticker}_{freq}_{lbl}", use_container_width=True):
            # Escribimos directo en los date_input para que la gráfica SÍ se mueva
            st.session_state[di_key] = max(fmin, fmax - delta)
            st.session_state[df_key] = fmax
            st.rerun()

    # Asegurar que los valores guardados estén dentro de límites
    if not (fmin <= st.session_state[di_key] <= fmax):
        st.session_state[di_key] = max(fmin, fmax - relativedelta(years=10))
    if not (fmin <= st.session_state[df_key] <= fmax):
        st.session_state[df_key] = fmax

    cz1, cz2 = st.columns(2)
    d_ini = cz1.date_input("Desde", min_value=fmin, max_value=fmax, key=di_key)
    d_fin = cz2.date_input("Hasta", min_value=fmin, max_value=fmax, key=df_key)
    if d_ini > d_fin:
        d_ini, d_fin = fmin, fmax

    # Herramientas de análisis técnico: ocultas tras "Modo avanzado" para no
    # asustar a quien va empezando. Quien las usa lo enciende una vez y queda.
    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
    avanzado = st.toggle("⚙️ Modo avanzado (indicadores técnicos)", key="obj_avanzado",
                         help="Medias móviles, Bandas de Bollinger y RSI para análisis técnico.")
    show_ma = show_bb = show_rsi = False
    if avanzado:
        t1, t2, t3 = st.columns(3)
        show_ma = t1.checkbox("📐 Medias Móviles (200·50·20)", key=f"obj_ma_{ticker}")
        show_bb = t2.checkbox("📊 Bandas de Bollinger", key=f"obj_bb_{ticker}")
        show_rsi = t3.checkbox("⚡ RSI (Índice de Fuerza Relativa)", key=f"obj_rsi_{ticker}")

    mask = (df["Fecha"].dt.date >= d_ini) & (df["Fecha"].dt.date <= d_fin)
    dfx = df[mask]
    if dfx.empty:
        st.warning("El rango seleccionado no tiene datos.")
        return

    sug_key = f"obj_sug_{ticker}"
    sugerencia = st.session_state.get(sug_key)

    # Precios de entrada/salida del USUARIO (empiezan en 0). Se leen AQUÍ, antes de
    # dibujar la gráfica, para pintar sus líneas y que se muevan al ajustarlos abajo.
    ent_key = f"obj_ent_{ticker}"
    sal_key = f"obj_sal_{ticker}"
    st.session_state.setdefault(ent_key, 0.0)
    st.session_state.setdefault(sal_key, 0.0)
    user_ent = st.session_state.get(ent_key) or 0.0
    user_sal = st.session_state.get(sal_key) or 0.0

    st.plotly_chart(
        _chart_tecnico(dfx, ticker, tipo_chart, show_ma, show_bb,
                       user_ent if user_ent > 0 else None,
                       user_sal if user_sal > 0 else None),
        use_container_width=True, config={"displayModeBar": False})
    if show_rsi:
        st.plotly_chart(_chart_rsi(dfx), use_container_width=True, config={"displayModeBar": False})

    # ── Botón de análisis técnico (sugerencia de precios) ──
    if st.button("🤖 Analizar gráfica y sugerir precios de entrada/salida",
                 key=f"obj_ai_{ticker}", use_container_width=True,
                 help="Analiza la temporalidad y rango seleccionados (soportes/resistencias, SMA, Bollinger, RSI)"):
        res = sugerir_entrada_salida(dfx)
        if res.get("ok"):
            st.session_state[sug_key] = res
            st.session_state[f"obj_ent_{ticker}"] = float(res["entrada"])
            st.session_state[f"obj_sal_{ticker}"] = float(res["salida"])
            st.rerun()
        else:
            st.warning("No hay suficientes datos en el rango para generar una sugerencia.")

    if sugerencia and sugerencia.get("ok"):
        notas_html = "".join(f"<li style='margin-bottom:3px;'>{n}</li>" for n in sugerencia["notas"])
        st.markdown(f"""
        <div style="background:#F4F3FF;border:1px solid #D4CFFF;border-radius:12px;padding:14px 18px;margin:10px 0;">
            <div style="font-size:12px;font-weight:700;color:#6C63FF;margin-bottom:6px;">
                🤖 Análisis técnico — sugerencia</div>
            <div style="display:flex;gap:18px;flex-wrap:wrap;margin-bottom:8px;">
                <span style="font-size:13px;">Entrada sugerida: <b style="color:#1D9E75;">${sugerencia['entrada']:,.2f}</b></span>
                <span style="font-size:13px;">Salida sugerida: <b style="color:#C77F00;">${sugerencia['salida']:,.2f}</b></span>
                <span style="font-size:13px;">Ganancia objetivo: <b style="color:#6C63FF;">{sugerencia['gan_pct']:+.2f}%</b></span>
            </div>
            <ul style="font-size:12px;color:#4A5066;margin:0;padding-left:18px;">{notas_html}</ul>
            <div style="font-size:10.5px;color:#9DA5B8;font-style:italic;margin-top:8px;">
                Sugerencia automática basada en análisis técnico. No es asesoría financiera — úsala como punto de partida.</div>
        </div>
        """, unsafe_allow_html=True)
        st.caption("✏️ Los precios de abajo ya se ajustaron a la sugerencia; puedes editarlos a tu criterio.")

    # ── Precio de entrada / salida (los 2 recuadros principales) ──
    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
    st.markdown(f"""
    <div style="font-size:13px;font-weight:600;color:#1a1a2e;margin-bottom:8px;">
        🎯 Define tu objetivo de trading (precios en {moneda})
    </div>
    """, unsafe_allow_html=True)
    st.caption("💡 Empiezan en $0. Al escribir tu precio de entrada y de salida, verás sus "
               "líneas moverse en la gráfica de arriba.")
    ce1, ce2 = st.columns(2)
    with ce1:
        st.markdown(f"""<div style="background:#E8FBF4;border:1.5px solid {GREEN};border-radius:12px;padding:14px 18px;">
            <div style="font-size:12px;font-weight:600;color:{GREEN};text-transform:uppercase;letter-spacing:.05em;">▼ Precio de ENTRADA (compra)</div>
        </div>""", unsafe_allow_html=True)
        precio_entrada = st.number_input(f"Entrada ({moneda})", min_value=0.0, step=0.5,
                                         format="%.2f", key=ent_key, label_visibility="collapsed")
    with ce2:
        st.markdown(f"""<div style="background:#FFF6E5;border:1.5px solid {GOLD};border-radius:12px;padding:14px 18px;">
            <div style="font-size:12px;font-weight:600;color:{GOLD};text-transform:uppercase;letter-spacing:.05em;">▲ Precio de SALIDA (venta)</div>
        </div>""", unsafe_allow_html=True)
        precio_salida = st.number_input(f"Salida ({moneda})", min_value=0.0, step=0.5,
                                        format="%.2f", key=sal_key, label_visibility="collapsed")

    # Ganancia objetivo (solo con ambos precios definidos)
    tiene_obj = precio_entrada > 0 and precio_salida > 0
    gan_usd = precio_salida - precio_entrada
    gan_pct = (gan_usd / precio_entrada * 100) if precio_entrada > 0 else 0
    col_g = (GREEN if gan_usd >= 0 else RED) if tiene_obj else "#9DA5B8"
    gan_usd_txt = f"${gan_usd:,.2f} {moneda}" if tiene_obj else "—"
    gan_pct_txt = f"{gan_pct:+.2f}%" if tiene_obj else "—"
    st.markdown(f"""
    <div style="background:#fff;border:0.5px solid #E8ECF4;border-radius:12px;padding:14px 20px;margin-top:12px;
                display:flex;justify-content:space-around;align-items:center;text-align:center;">
        <div><div style="font-size:11px;color:#9DA5B8;">Precio actual</div>
             <div style="font-size:18px;font-weight:600;color:#1a1a2e;">${precio_actual:,.2f}</div></div>
        <div style="font-size:22px;color:#D0D4DE;">→</div>
        <div><div style="font-size:11px;color:#9DA5B8;">Ganancia por acción</div>
             <div style="font-size:18px;font-weight:600;color:{col_g};">{gan_usd_txt}</div></div>
        <div style="font-size:22px;color:#D0D4DE;">·</div>
        <div><div style="font-size:11px;color:#9DA5B8;">Rendimiento objetivo</div>
             <div style="font-size:22px;font-weight:700;color:{col_g};">{gan_pct_txt}</div></div>
    </div>
    """, unsafe_allow_html=True)

    if tiene_obj and precio_salida <= precio_entrada:
        st.caption("⚠️ El precio de salida es menor o igual al de entrada — revisa tu objetivo.")

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
    st.caption("Solo necesitas definir tu punto de entrada y de salida. "
               "El tipo de cambio se aplicará al momento de registrar la compra o la venta.")
    objetivo_valido = tiene_obj and precio_salida > precio_entrada
    if st.button("🎯 Guardar en Mis estrategias", type="primary", key=f"obj_save_{ticker}",
                 use_container_width=True, disabled=not objetivo_valido):
        save_obj_strategy(ticker, nombre, precio_entrada, precio_salida, get_tipo_cambio_actual())
        st.success(f"✅ Estrategia de {ticker} guardada — entrada \\${precio_entrada:,.2f} / "
                   f"salida \\${precio_salida:,.2f} {moneda}. Ve a 'Mis estrategias'.")
    if not objetivo_valido:
        st.caption("Define un precio de entrada y de salida (salida mayor que entrada) para guardar.")


def _chart_tecnico(df, ticker, tipo_chart, show_ma, show_bb, user_ent=None, user_sal=None):
    fig = go.Figure()
    if show_bb:
        fig.add_trace(go.Scatter(x=df["Fecha"], y=df["BB_up"], name="BB superior",
                                 line=dict(color="rgba(108,99,255,0.35)", width=1), showlegend=False))
        fig.add_trace(go.Scatter(x=df["Fecha"], y=df["BB_low"], name="Bandas de Bollinger",
                                 line=dict(color="rgba(108,99,255,0.35)", width=1),
                                 fill="tonexty", fillcolor="rgba(108,99,255,0.06)"))
        fig.add_trace(go.Scatter(x=df["Fecha"], y=df["BB_mid"], name="BB media (20)",
                                 line=dict(color="rgba(108,99,255,0.5)", width=1, dash="dot")))
    if tipo_chart == "Velas japonesas":
        fig.add_trace(go.Candlestick(
            x=df["Fecha"], open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"],
            name="Precio", increasing_line_color=GREEN, decreasing_line_color=RED,
        ))
    else:
        fig.add_trace(go.Scatter(
            x=df["Fecha"], y=df["Close"], name="Precio", mode="lines",
            line=dict(color=BLUE, width=2),
            fill="tozeroy", fillcolor="rgba(79,155,240,0.07)",
        ))
    if show_ma:
        fig.add_trace(go.Scatter(x=df["Fecha"], y=df["SMA20"], name="SMA 20",
                                 line=dict(color="#1D9E75", width=1.3)))
        fig.add_trace(go.Scatter(x=df["Fecha"], y=df["SMA50"], name="SMA 50",
                                 line=dict(color="#C77F00", width=1.3)))
        fig.add_trace(go.Scatter(x=df["Fecha"], y=df["SMA200"], name="SMA 200",
                                 line=dict(color="#A32D2D", width=1.5)))
    # Líneas del usuario: se mueven en vivo al ajustar los precios de entrada/salida.
    if user_ent is not None:
        fig.add_hline(y=user_ent, line=dict(color=GREEN, width=2, dash="dash"),
                      annotation_text=f"▼ Tu entrada ${user_ent:,.2f}",
                      annotation_font_color=GREEN, annotation_position="bottom right")
    if user_sal is not None:
        fig.add_hline(y=user_sal, line=dict(color=GOLD, width=2, dash="dash"),
                      annotation_text=f"▲ Tu salida ${user_sal:,.2f}",
                      annotation_font_color=GOLD, annotation_position="top right")
    # El eje Y siempre debe INCLUIR tus líneas de entrada/salida, sin importar la
    # temporalidad que muestres (si no, la línea quedaría fuera de vista y "desaparece").
    lows = [df["Low"].min()]
    highs = [df["High"].max()]
    if show_bb and "BB_low" in df.columns:
        lows.append(df["BB_low"].min())
        highs.append(df["BB_up"].max())
    for v in (user_ent, user_sal):
        if v:
            lows.append(v)
            highs.append(v)
    lo, hi = float(min(lows)), float(max(highs))
    pad = (hi - lo) * 0.06 if hi > lo else max(hi * 0.06, 1.0)
    yrange = [max(0.0, lo - pad), hi + pad]

    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=30, b=0), height=420,
        title=dict(text=f"Análisis técnico — {ticker}", font=dict(size=13, color="#1a1a2e"), x=0),
        legend=dict(orientation="h", y=1.06, font=dict(size=10, color="#9DA5B8"), bgcolor="rgba(0,0,0,0)"),
        xaxis=dict(showgrid=False, rangeslider=dict(visible=False), fixedrange=True, tickfont=dict(size=10, color="#9DA5B8")),
        yaxis=dict(gridcolor="#F0F2F8", gridwidth=0.5, fixedrange=True, range=yrange,
                   tickfont=dict(size=10, color="#9DA5B8"), tickprefix="$"),
        dragmode=False, hovermode="x unified",
    )
    return fig


def _chart_rsi(df):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df["Fecha"], y=df["RSI"], name="RSI(14)",
                             line=dict(color=PURPLE, width=1.6)))
    fig.add_hline(y=70, line=dict(color=RED, width=1, dash="dash"), annotation_text="Sobrecompra 70")
    fig.add_hline(y=30, line=dict(color=GREEN, width=1, dash="dash"), annotation_text="Sobreventa 30")
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=24, b=0), height=180,
        title=dict(text="RSI — Índice de Fuerza Relativa", font=dict(size=12, color="#1a1a2e"), x=0),
        xaxis=dict(showgrid=False, fixedrange=True, tickfont=dict(size=10, color="#9DA5B8")),
        yaxis=dict(range=[0, 100], gridcolor="#F0F2F8", fixedrange=True, tickfont=dict(size=10, color="#9DA5B8")),
        dragmode=False, hovermode="x unified", showlegend=False,
    )
    return fig


# ── Tab 2: mis estrategias ───────────────────────────────────────────────────
def _mis_estrategias_obj():
    estrategias = load_obj_strategies()
    if not estrategias:
        st.markdown("""
        <div style="text-align:center;padding:48px 24px;color:#9DA5B8;">
            <div style="font-size:32px;margin-bottom:12px;">🎯</div>
            <div style="font-size:14px;font-weight:500;color:#4A5066;">Sin estrategias de trading</div>
            <div style="font-size:12px;margin-top:6px;">Ve a "Análisis técnico", define entrada y salida, y guárdala</div>
        </div>
        """, unsafe_allow_html=True)
        return
    for e in estrategias:
        sub = (f"— entrada ${e['precio_entrada']:,.2f} / salida ${e['precio_salida']:,.2f}")
        estrategia_comun.card(e, "Por Objetivos", "🎯", e["ticker"], sub,
                              _detalle_obj, _obj_form_compra, delete_obj_strategy,
                              venta_fn=_obj_vender)


def _obj_form_compra(e: dict):
    eid = e["id"]
    ticker = e["ticker"]
    es_mx = ticker.upper().endswith(".MX")
    fx_hoy = get_tipo_cambio_actual()
    tc = 1.0 if es_mx else fx_hoy
    p_ent_mxn = e["precio_entrada"] * tc
    with st.form(f"form_obj_{eid}", clear_on_submit=True):
        c1, c2 = st.columns(2)
        fecha_c = c1.date_input("Fecha", value=date.today(), max_value=date.today(), key=f"ofc_{eid}")
        titulos_c = c2.number_input("Acciones", min_value=1, value=1, step=1, key=f"otc_{eid}")
        precio_c = st.number_input("Precio de compra (MXN)", min_value=0.01,
                                   value=round(p_ent_mxn, 2), step=0.01, format="%.2f", key=f"opc_{eid}")
        if es_mx:
            fx_c = 1.0
        else:
            fx_c = st.number_input("Tipo de cambio (MXN/USD)", min_value=1.0, value=fx_hoy,
                                   step=0.01, format="%.4f", key=f"ofx_{eid}",
                                   help="Solo informativo; el precio ya va en pesos.")
        st.caption("La comisión se calcula automáticamente con el % de tu perfil.")
        registrar = st.form_submit_button("➕ Registrar compra", type="primary", use_container_width=True)
    if registrar:
        importe = int(titulos_c) * float(precio_c)
        comision_mxn = comision_desde_perfil(importe)
        save_obj_purchase(eid, fecha_c, int(titulos_c), float(precio_c), float(fx_c), comision_mxn)
        invalidar_resumen()
        st.success(f"✅ Compra registrada: {int(titulos_c)} acciones a ${precio_c:,.2f} MXN")
        st.rerun()


def _obj_vender(e: dict):
    """Vista de venta por lote: muestra los lotes abiertos para vender."""
    eid = e["id"]
    ticker = e["ticker"]
    es_mx = ticker.upper().endswith(".MX")
    fx_hoy = get_tipo_cambio_actual()
    quote = get_precio_actual(ticker)
    precio_usd = quote["precio"] if quote else None
    p_sal = e["precio_salida"]
    compras = load_obj_purchases(eid)
    ventas = {v["compra_id"]: v for v in load_obj_sales(eid)}
    abiertos = [c for c in compras if c["id"] not in ventas]
    if not abiertos:
        st.info("No tienes lotes abiertos para vender. Registra una compra primero.")
        return
    st.caption("En Por Objetivos vendes por lote. Elige el lote y registra su venta:")
    for cp in abiertos:
        _fila_compra(cp, None, eid, ticker, es_mx, precio_usd, p_sal, fx_hoy)


def _seccion(label, color="#6C63FF"):
    st.markdown(f"""
    <div style="border-top:1px solid #E8ECF4;margin:16px 0 8px;padding-top:12px;
                font-size:11px;font-weight:600;color:{color};
                letter-spacing:.07em;text-transform:uppercase;">{label}</div>
    """, unsafe_allow_html=True)


def _detalle_obj(e: dict):
    st.markdown("""
    <style>
    div[data-testid="stExpanderDetails"] [data-testid="stMetricValue"] { font-size: 1.1rem !important; }
    div[data-testid="stExpanderDetails"] [data-testid="stMetricLabel"] { font-size: 0.72rem !important; }
    div[data-testid="stExpanderDetails"] [data-testid="stMetricDelta"] { font-size: 0.72rem !important; }
    </style>
    """, unsafe_allow_html=True)
    eid = e["id"]
    ticker = e["ticker"]
    es_mx = ticker.upper().endswith(".MX")
    p_ent = e["precio_entrada"]
    p_sal = e["precio_salida"]
    fx_hoy = get_tipo_cambio_actual()

    quote = get_precio_actual(ticker)
    precio_usd = quote["precio"] if quote else None

    # ── Resumen de la estrategia ──
    _seccion("Objetivo de la estrategia")
    if es_mx:
        tc = 1.0
    else:
        ctc = st.columns([1.4, 2.6])
        tc = ctc[0].number_input(
            "Tipo de cambio actual (MXN/USD)", min_value=1.0, value=fx_hoy,
            step=0.01, format="%.4f", key=f"otcd_{eid}",
            help="Solo para mostrar tus precios objetivo en pesos al cambio de hoy.",
        )
    m1, m2, m3 = st.columns(3)
    m1.metric("Precio de entrada", f"${p_ent:,.2f} USD",
              delta=(f"${p_ent*tc:,.2f} MXN" if not es_mx else None), delta_color="off")
    m2.metric("Precio de salida", f"${p_sal:,.2f} USD",
              delta=(f"${p_sal*tc:,.2f} MXN" if not es_mx else None), delta_color="off")
    obj_pct = (p_sal - p_ent) / p_ent * 100 if p_ent else 0
    m3.metric("Rendimiento objetivo", f"{obj_pct:+.2f}%",
              delta=f"${p_sal-p_ent:,.2f}/acción", delta_color="off")
    if precio_usd:
        st.caption(f"Precio actual de {ticker}: \\${precio_usd:,.2f} {'MXN' if es_mx else 'USD'}")

    # ── Historial de compras ──
    compras = load_obj_purchases(eid)
    ventas = {v["compra_id"]: v for v in load_obj_sales(eid)}
    if not compras:
        st.caption("Aún no registras compras en esta estrategia.")
    else:
        _seccion("Seguimiento de la estrategia", PURPLE)
        fig = _chart_estrategia(ticker, compras, list(ventas.values()), p_ent, p_sal, es_mx)
        if fig is not None:
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
            st.caption("🟢 Triángulos verdes = tus compras (entradas) · 🔻 Triángulos rojos = tus ventas (salidas) · "
                       "línea verde = entrada objetivo · línea dorada = salida objetivo")
        for cp in compras:
            _fila_compra(cp, ventas.get(cp["id"]), eid, ticker, es_mx, precio_usd, p_sal, fx_hoy)

    # ── Ventas registradas (historial permanente) ──
    estrategia_comun.ventas_registradas("Por Objetivos", eid)


def _chart_estrategia(ticker, compras, ventas, p_ent, p_sal, es_mx):
    """Gráfica de la acción con marcadores de entradas (compras) y salidas (ventas)."""
    df = get_ohlc(ticker)
    if df.empty:
        return None
    fechas = [pd.to_datetime(str(c["fecha"])[:10]) for c in compras] + \
             [pd.to_datetime(str(v["fecha"])[:10]) for v in ventas]
    if fechas:
        inicio = min(fechas) - pd.Timedelta(days=180)
        dfx = df[df["Fecha"] >= inicio]
    else:
        dfx = df.tail(252)
    if dfx.empty:
        dfx = df.tail(252)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dfx["Fecha"], y=dfx["Close"], mode="lines", name="Precio",
        line=dict(color=BLUE, width=1.8),
        fill="tozeroy", fillcolor="rgba(79,155,240,0.06)",
        hovertemplate="<b>%{x|%d %b %Y}</b><br>$%{y:,.2f}<extra></extra>",
    ))
    fig.add_hline(y=p_ent, line=dict(color=GREEN, width=1, dash="dash"),
                  annotation_text=f"Entrada objetivo ${p_ent:,.0f}", annotation_font_color=GREEN,
                  annotation_position="top left")
    fig.add_hline(y=p_sal, line=dict(color=GOLD, width=1, dash="dash"),
                  annotation_text=f"Salida objetivo ${p_sal:,.0f}", annotation_font_color=GOLD,
                  annotation_position="bottom left")

    def _pu(rec):
        tc = rec.get("tipo_cambio") or 1.0
        return rec["precio"] if es_mx else rec["precio"] / tc

    if compras:
        fig.add_trace(go.Scatter(
            x=[pd.to_datetime(str(c["fecha"])[:10]) for c in compras],
            y=[_pu(c) for c in compras],
            mode="markers", name="Compras (entrada)",
            marker=dict(color=GREEN, size=13, symbol="triangle-up", line=dict(color="white", width=1.5)),
            hovertemplate="Compra<br>%{x|%d %b %Y}<br>$%{y:,.2f}<extra></extra>",
        ))
    if ventas:
        fig.add_trace(go.Scatter(
            x=[pd.to_datetime(str(v["fecha"])[:10]) for v in ventas],
            y=[_pu(v) for v in ventas],
            mode="markers", name="Ventas (salida)",
            marker=dict(color=RED, size=13, symbol="triangle-down", line=dict(color="white", width=1.5)),
            hovertemplate="Venta<br>%{x|%d %b %Y}<br>$%{y:,.2f}<extra></extra>",
        ))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=10, b=0), height=280,
        legend=dict(orientation="h", y=-0.18, font=dict(size=10, color="#9DA5B8"), bgcolor="rgba(0,0,0,0)"),
        xaxis=dict(showgrid=False, tickfont=dict(size=10, color="#9DA5B8")),
        yaxis=dict(gridcolor="#F0F2F8", gridwidth=0.5, tickfont=dict(size=10, color="#9DA5B8"), tickprefix="$"),
        hovermode="closest",
    )
    return fig


def _fila_compra(cp, venta, eid, ticker, es_mx, precio_usd, p_sal_usd, fx_hoy):
    cid = cp["id"]
    tc_compra = cp.get("tipo_cambio") or 1.0
    com_compra = cp.get("comision") or 0.0
    titulos = cp["titulos"]
    compra_total_mxn = titulos * cp["precio"] + com_compra
    precio_compra_usd = cp["precio"] / tc_compra if not es_mx else None

    # Valor actual / objetivo en MXN
    if es_mx:
        precio_hoy_mxn = precio_usd if precio_usd else cp["precio"]
        p_sal_mxn = p_sal_usd  # para .MX el "USD" en realidad es MXN nativo
    else:
        precio_hoy_mxn = (precio_usd or 0) * fx_hoy
        p_sal_mxn = p_sal_usd * fx_hoy
    valor_actual_mxn = titulos * precio_hoy_mxn
    pl_actual = valor_actual_mxn - compra_total_mxn
    pl_pct = (pl_actual / compra_total_mxn * 100) if compra_total_mxn else 0
    falta_meta_mxn = titulos * p_sal_mxn - valor_actual_mxn
    col_pl = GREEN if pl_actual >= 0 else RED

    with st.container():
        st.markdown(f"""
        <div style="background:#F8F9FC;border:0.5px solid #E2E6EE;border-radius:10px;padding:10px 14px;margin-bottom:4px;">
            <div style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px;font-size:12.5px;">
                <span><b>{str(cp['fecha'])[:10]}</b> · {titulos} acción(es) · compra ${cp['precio']:,.2f} MXN
                    {'' if es_mx else f'(${precio_compra_usd:,.2f} USD · TC {tc_compra:.4f})'}</span>
                <span style="color:#9DA5B8;">Costo total: ${compra_total_mxn:,.2f} MXN</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        if venta:
            _bloque_venta_realizada(venta, cp, es_mx, compra_total_mxn)
        else:
            cM1, cM2, cM3 = st.columns(3)
            cM1.metric("P&L actual", f"${pl_actual:,.2f} MXN", delta=f"{pl_pct:+.2f}%")
            cM2.metric("Valor actual", f"${valor_actual_mxn:,.2f} MXN")
            cM3.metric("Falta para la meta", f"${falta_meta_mxn:,.2f} MXN",
                       delta=f"meta: ${titulos*p_sal_mxn:,.2f}", delta_color="off")

            # Registrar venta (toggle)
            vkey = f"showventa_{cid}"
            if st.button("💵 Registrar venta de este lote", key=f"btnventa_{cid}",
                         help="Vende este lote y calcula tu ganancia real (venta − compra)"):
                st.session_state[vkey] = not st.session_state.get(vkey, False)
            if st.session_state.get(vkey, False):
                _form_venta(cp, eid, ticker, es_mx, precio_hoy_mxn, fx_hoy)

        # Botones de acción agrupados
        if venta:
            ba, bb = st.columns(2)
            if ba.button("↩️ Deshacer venta", key=f"undoventa_{venta['id']}",
                         help="Elimina el registro de venta y vuelve a dejar esta compra como posición abierta"):
                delete_obj_sale(venta["id"])
                st.rerun()
            if bb.button("🗑️ Borrar compra", key=f"odelc_{cid}",
                         help="Elimina por completo esta compra (y su venta, si existe) del historial"):
                delete_obj_purchase(cid)
                st.rerun()
        else:
            ba, _ = st.columns(2)
            if ba.button("🗑️ Borrar compra", key=f"odelc_{cid}",
                         help="Elimina por completo esta compra del historial"):
                delete_obj_purchase(cid)
                st.rerun()
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)


def _form_venta(cp, eid, ticker, es_mx, precio_hoy_mxn, fx_hoy):
    cid = cp["id"]
    st.markdown(f"""<div style="border-left:3px solid {GOLD};padding-left:12px;">
        <div style="font-size:11px;font-weight:600;color:{GOLD};text-transform:uppercase;">Registrar venta</div></div>""",
                unsafe_allow_html=True)
    with st.form(f"form_venta_{cid}", clear_on_submit=True):
        if es_mx:
            cv1, cv2, cv3, cv4 = st.columns([1.2, 1, 1.2, 0.9])
            fxv = 1.0
        else:
            cv1, cv2, cv3, cv5, cv4 = st.columns([1.1, 0.9, 1.1, 1, 0.9])
        fecha_v = cv1.date_input("Fecha venta", value=date.today(), max_value=date.today(), key=f"vfc_{cid}")
        titulos_v = cv2.number_input("Acciones", min_value=1, max_value=cp["titulos"],
                                     value=cp["titulos"], step=1, key=f"vtc_{cid}")
        precio_v = cv3.number_input("Precio de venta (MXN)", min_value=0.01,
                                    value=round(precio_hoy_mxn, 2), step=0.01, format="%.2f", key=f"vpc_{cid}")
        if not es_mx:
            fxv = cv5.number_input("Tipo de cambio (MXN/USD)", min_value=1.0, value=fx_hoy,
                                   step=0.01, format="%.4f", key=f"vfx_{cid}")
        cv4.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
        vender = cv4.form_submit_button("💵 Confirmar venta", use_container_width=True)
    st.caption("La comisión se calcula automáticamente con el % de tu perfil.")
    if vender:
        importe = int(titulos_v) * float(precio_v)
        comision_mxn = comision_desde_perfil(importe)
        save_obj_sale(cid, eid, fecha_v, int(titulos_v), float(precio_v), float(fxv), comision_mxn)
        # Guardar también en el historial permanente (sobrevive aunque borres la estrategia)
        frac = int(titulos_v) / cp["titulos"] if cp["titulos"] else 1
        costo_base = (cp["titulos"] * cp["precio"] + (cp.get("comision") or 0.0)) * frac
        log_venta_cerrada("Por Objetivos", eid, ticker, fecha_v, int(titulos_v),
                          float(precio_v), comision_mxn, costo_base, float(fxv))
        st.session_state[f"showventa_{cid}"] = False
        invalidar_resumen()
        st.success(f"✅ Venta registrada: {int(titulos_v)} acciones a ${precio_v:,.2f} MXN")
        st.rerun()


def _bloque_venta_realizada(venta, cp, es_mx, compra_total_mxn):
    com_v = venta.get("comision") or 0.0
    venta_total_mxn = venta["titulos"] * venta["precio"] - com_v   # neto recibido
    # Proporcional si vendió menos acciones que compró
    frac = venta["titulos"] / cp["titulos"] if cp["titulos"] else 1
    costo_proporcional = compra_total_mxn * frac
    ganancia = venta_total_mxn - costo_proporcional
    gan_pct = (ganancia / costo_proporcional * 100) if costo_proporcional else 0
    col = GREEN if ganancia >= 0 else RED
    st.markdown(f"""
    <div style="background:{'#E8FBF4' if ganancia>=0 else '#FCEDED'};border:0.5px solid {col};
                border-radius:10px;padding:10px 14px;margin-bottom:4px;">
        <div style="font-size:11px;font-weight:600;color:{col};text-transform:uppercase;letter-spacing:.05em;">
            ✓ Venta realizada — {str(venta['fecha'])[:10]}</div>
        <div style="display:flex;justify-content:space-around;text-align:center;margin-top:8px;flex-wrap:wrap;gap:10px;">
            <div><div style="font-size:11px;color:#9DA5B8;">Vendiste</div>
                 <div style="font-size:14px;font-weight:600;color:#1a1a2e;">{venta['titulos']} acc · ${venta['precio']:,.2f} MXN</div></div>
            <div><div style="font-size:11px;color:#9DA5B8;">Recibiste (neto)</div>
                 <div style="font-size:14px;font-weight:600;color:#1a1a2e;">${venta_total_mxn:,.2f} MXN</div></div>
            <div><div style="font-size:11px;color:#9DA5B8;">Ganancia (venta − compra)</div>
                 <div style="font-size:16px;font-weight:700;color:{col};">${ganancia:,.2f} MXN</div></div>
            <div><div style="font-size:11px;color:#9DA5B8;">Rendimiento</div>
                 <div style="font-size:18px;font-weight:700;color:{col};">{gan_pct:+.2f}%</div></div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown(
        "<div style='font-size:10.5px;color:#9DA5B8;font-style:italic;margin:-2px 0 4px 2px;'>"
        "Este rendimiento ya considera lo que pagaste de comisiones al comprar y al vender, "
        "para que veas tu ganancia real.</div>",
        unsafe_allow_html=True,
    )
