import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta

from utils.ticker_search import (
    widget_buscador, get_precio_actual, get_tipo_cambio_actual, buscar_tickers,
)
from utils.comisiones import comision_desde_perfil
from utils.dividends_utils import (
    RECOMENDADAS_SIC, get_dividend_series, get_dividend_summary, get_dividends_since,
    analizar_salud_dividendo,
)
from utils.db_utils import (
    save_div_strategy, load_div_strategies, delete_div_strategy,
    save_div_purchase, load_div_purchases, delete_div_purchase,
    titulos_vendidos,
)
from modules import estrategia_comun
from utils.resumen_utils import invalidar_resumen

PURPLE = "#6C63FF"
GREEN = "#1D9E75"
BLUE = "#4F9BF0"
GOLD = "#C77F00"
RED = "#A32D2D"
FILL = {"#6C63FF": "rgba(108,99,255,0.08)", "#1D9E75": "rgba(29,158,117,0.08)",
        "#4F9BF0": "rgba(79,155,240,0.08)"}


# ─────────────────────────────────────────────────────────────────────────────
def render_dividendos():
    st.markdown("""
    <div style="margin-bottom:20px;">
        <h2 style="font-size:20px;font-weight:600;color:#1a1a2e;margin:0;">Dividendos</h2>
        <p style="font-size:12px;color:#9DA5B8;margin:4px 0 0;">Acciones que reparten dividendos — analiza, agrega a tu estrategia y registra tus compras</p>
    </div>
    """, unsafe_allow_html=True)
    if load_div_strategies():
        tab_estrategias, tab_buscar = st.tabs(["📋  Mis estrategias", "🔍  Buscar acción"])
    else:
        tab_buscar, tab_estrategias = st.tabs(["🔍  Buscar acción", "📋  Mis estrategias"])
    with tab_buscar:
        _tab_buscar()
    with tab_estrategias:
        _mis_estrategias_div()


# ── Tab 1: buscar / recomendadas ─────────────────────────────────────────────
def _tab_buscar():
    estrategia_comun.boton_ayuda(
        "ayuda_div",
        "💡 Cómo usar el módulo de Dividendos",
        "Aquí encuentras acciones que te pagan dividendos (una 'renta' por ser dueño) y sigues tus ingresos. Pasos:",
        [
            ("1. Elige una acción", "Selecciónala de la tabla de recomendadas, o búscala arriba por nombre o clave (ej: KO, Coca-Cola)."),
            ("2. Revisa su análisis", "Verás su último dividendo, el yield (cuánto rinde) y su historial de pagos para decidir."),
            ("3. Agrégala a tu estrategia", "Pulsa 'Agregar a mi estrategia de Dividendos' para empezar a seguirla."),
            ("4. Registra tus compras", "En la pestaña 'Mis estrategias' anota a qué precio y cuántas compraste; la app calcula tus ingresos por dividendos."),
        ],
        nota="En 'Mis estrategias' también puedes registrar ventas y ver tu rendimiento.")
    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
    st.markdown("**Acciones recomendadas por altos dividendos (SIC)**")
    df_rec = pd.DataFrame(RECOMENDADAS_SIC)
    df_show = df_rec.rename(columns={
        "ticker": "Ticker", "nombre": "Acción", "giro": "Giro", "yield_aprox": "Dividend Yield aprox.",
    })[["Ticker", "Acción", "Giro", "Dividend Yield aprox."]]

    seleccion = st.dataframe(
        df_show, use_container_width=True, hide_index=True, height=388,
        on_select="rerun", selection_mode="single-row", key="div_rec_table",
    )
    ticker_sel = None
    rows_sel = seleccion.selection.rows if hasattr(seleccion, "selection") else []
    if rows_sel:
        ticker_sel = RECOMENDADAS_SIC[rows_sel[0]]["ticker"]

    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
    st.markdown("**¿Otra acción? Búscala aquí**")
    datos_busqueda = widget_buscador(key="div_buscar")
    if datos_busqueda:
        ticker_sel = datos_busqueda["ticker"]

    if not ticker_sel:
        st.info("Selecciona una acción recomendada de la tabla o búscala arriba para ver su análisis de dividendos.")
        return

    _panel_analisis(ticker_sel)


def _panel_analisis(ticker: str):
    st.markdown("---")
    resumen = get_dividend_summary(ticker)
    if resumen["ultimo_pago"] is None:
        st.warning(f"⚠️ **{ticker}** no tiene historial de dividendos en la fuente de datos. "
                   "Probablemente no reparte dividendos.")
        return

    # Encontrar nombre/giro si es recomendada
    nombre, giro = ticker, ""
    for r in RECOMENDADAS_SIC:
        if r["ticker"] == ticker:
            nombre, giro = r["nombre"], r["giro"]
            break

    # KPIs de dividendos
    precio = resumen["precio"]
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Último dividendo", f"${resumen['ultimo_pago']:,.2f} USD",
              delta=resumen["ultima_fecha"].strftime("%d/%m/%Y") if resumen["ultima_fecha"] else None,
              delta_color="off")
    k2.metric("Dividendo TTM", f"${resumen['ttm']:,.2f} USD", delta=f"{resumen['frecuencia']}", delta_color="off")
    k3.metric("Dividend Yield (TTM)", f"{resumen['yield_pct']:.2f}%" if resumen["yield_pct"] else "—")
    k4.metric("Precio actual", f"${precio:,.2f} USD" if precio else "—")

    # Charts estilo Macrotrends
    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
    cab1, cab2 = st.columns([3, 1])
    with cab1:
        st.markdown(f"**Histórico de dividendos — {nombre} ({ticker})**")
    with cab2:
        with st.popover("ℹ️ ¿Qué significan?"):
            st.markdown("""
            **📈 Precio de la acción** — cómo se ha movido el precio en el tiempo.

            **💵 Dividendo TTM (Trailing Twelve Months)** — suma de los dividendos
            pagados en los últimos 12 meses, en cada punto del tiempo. Si la línea
            **sube**, la empresa ha estado **aumentando** sus pagos.

            **📊 Dividend Yield TTM** — el dividendo de los últimos 12 meses dividido
            entre el precio (en %). Indica **cuánto rinde** la acción por dividendos.
            Un yield muy alto puede ser oportunidad… o señal de que el precio cayó.
            """)

    serie = get_dividend_series(ticker)
    if serie.empty:
        st.info("No hay suficientes datos históricos para graficar.")
    else:
        serie["Fecha"] = pd.to_datetime(serie["Fecha"])
        fmin = serie["Fecha"].min().date()
        fmax = serie["Fecha"].max().date()

        # Controles de rango estilo Macrotrends
        cz1, cz2, cz3 = st.columns([1.3, 1.3, 2])
        rng_key = f"div_rng_{ticker}"
        if rng_key not in st.session_state:
            st.session_state[rng_key] = (max(fmin, fmax - relativedelta(years=10)), fmax)
        with cz3:
            st.markdown("<div style='height:26px'></div>", unsafe_allow_html=True)
            zc = st.columns(4)
            for i, (lbl, yrs) in enumerate([("3A", 3), ("5A", 5), ("10A", 10), ("Todo", None)]):
                if zc[i].button(lbl, key=f"zoom_{ticker}_{lbl}", use_container_width=True):
                    desde = fmin if yrs is None else max(fmin, fmax - relativedelta(years=yrs))
                    st.session_state[rng_key] = (desde, fmax)
        d_ini = cz1.date_input("Desde", value=st.session_state[rng_key][0],
                               min_value=fmin, max_value=fmax, key=f"di_{ticker}")
        d_fin = cz2.date_input("Hasta", value=st.session_state[rng_key][1],
                               min_value=fmin, max_value=fmax, key=f"df_{ticker}")
        st.session_state[rng_key] = (d_ini, d_fin)

        mask = (serie["Fecha"].dt.date >= d_ini) & (serie["Fecha"].dt.date <= d_fin)
        sf = serie[mask]
        if sf.empty:
            st.warning("El rango seleccionado no tiene datos.")
        else:
            st.plotly_chart(_chart_linea(sf, "Precio", "Precio de la acción (USD)", BLUE, "$"),
                            use_container_width=True, config={"displayModeBar": False})
            st.plotly_chart(_chart_linea(sf, "Dividendo TTM", "Dividendo TTM (USD por acción)", GREEN, "$"),
                            use_container_width=True, config={"displayModeBar": False})
            st.plotly_chart(_chart_linea(sf, "Yield TTM", "Dividend Yield TTM (%)", PURPLE, "", "%"),
                            use_container_width=True, config={"displayModeBar": False})

    # ── Análisis de salud del dividendo ──
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    if st.button("🤖 Analizar salud del dividendo", key=f"div_health_{ticker}", use_container_width=True):
        st.session_state[f"div_health_res_{ticker}"] = analizar_salud_dividendo(ticker)
    salud = st.session_state.get(f"div_health_res_{ticker}")
    if salud:
        if not salud.get("ok"):
            st.info("No hay suficiente historial de dividendos para analizar esta acción.")
        else:
            cmap = {"verde": GREEN, "amarillo": GOLD, "rojo": RED}
            bg = {"verde": "#E3F7EF", "amarillo": "#FFF6E0", "rojo": "#FCEBEB"}
            col = cmap[salud["color"]]
            motivos = "".join(f"<li style='margin-bottom:2px;'>{m}</li>" for m in salud["motivos"])
            cagr_txt = f"{salud['cagr']:+.1f}%/año" if salud["cagr"] is not None else "—"
            st.markdown(f"""
            <div style="background:{bg[salud['color']]};border:1px solid {col};border-radius:12px;padding:14px 18px;margin-top:8px;">
                <div style="font-size:13px;font-weight:700;color:{col};">
                    {salud['veredicto']} · Score {salud['score']}/100</div>
                <div style="display:flex;gap:18px;flex-wrap:wrap;margin:6px 0;font-size:12px;color:#4A5066;">
                    <span>Crecimiento: <b>{cagr_txt}</b></span>
                    <span>Años aumentando: <b>{salud['anios_aumentando']}</b></span>
                    <span>Historial: <b>{salud['anios_pagando']} años</b></span>
                </div>
                <ul style="font-size:12px;color:#4A5066;margin:4px 0 0;padding-left:18px;">{motivos}</ul>
                <div style="font-size:10.5px;color:#9DA5B8;font-style:italic;margin-top:8px;">
                    Análisis informativo automático, no es asesoría financiera.</div>
            </div>
            """, unsafe_allow_html=True)

    # Botón agregar a estrategia
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    if st.button("➕ Agregar a mi estrategia de Dividendos", type="primary", key=f"add_div_{ticker}"):
        save_div_strategy(ticker, nombre, giro)
        st.success(f"✅ **{ticker}** agregada a tu estrategia de dividendos. "
                   "Ve a la pestaña 'Mis estrategias' para registrar compras.")


def _chart_linea(df, col, titulo, color, prefix="", suffix=""):
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["Fecha"], y=df[col], mode="lines",
        line=dict(color=color, width=2.2),
        fill="tozeroy", fillcolor=FILL.get(color, "rgba(108,99,255,0.08)"),
        hovertemplate="<b>%{x|%b %Y}</b><br>" + f"{prefix}" + "%{y:,.2f}" + f"{suffix}<extra></extra>",
    ))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=28, b=0), height=210,
        title=dict(text=titulo, font=dict(size=12, color="#1a1a2e"), x=0, xanchor="left"),
        xaxis=dict(showgrid=False, showline=False, tickfont=dict(size=10, color="#9DA5B8")),
        yaxis=dict(gridcolor="#F0F2F8", gridwidth=0.5, showline=False,
                   tickfont=dict(size=10, color="#9DA5B8"), tickprefix=prefix, ticksuffix=suffix),
        hovermode="x unified",
    )
    return fig


# ── Tab 2: mis estrategias de dividendos ─────────────────────────────────────
def _mis_estrategias_div():
    estrategias = load_div_strategies()
    if not estrategias:
        st.markdown("""
        <div style="text-align:center;padding:48px 24px;color:#9DA5B8;">
            <div style="font-size:32px;margin-bottom:12px;">💰</div>
            <div style="font-size:14px;font-weight:500;color:#4A5066;">Sin acciones en tu estrategia de dividendos</div>
            <div style="font-size:12px;margin-top:6px;">Ve a "Buscar acción", elige una y pulsa "Agregar a mi estrategia"</div>
        </div>
        """, unsafe_allow_html=True)
        return
    for e in estrategias:
        sub = f"— {e.get('nombre') or e['ticker']}"
        if e.get("giro"):
            sub += f" · {e['giro']}"
        estrategia_comun.card(e, "Dividendos", "💰", e["ticker"], sub,
                              _detalle_div, _div_form_compra, delete_div_strategy)


def _div_form_compra(e: dict):
    eid = e["id"]
    ticker = e["ticker"]
    es_mx = ticker.upper().endswith(".MX")
    fx_hoy = get_tipo_cambio_actual()
    with st.form(f"form_div_{eid}", clear_on_submit=True):
        c1, c2 = st.columns(2)
        fecha_c = c1.date_input("Fecha", value=date.today(), max_value=date.today(), key=f"dfc_{eid}")
        titulos_c = c2.number_input("Cantidad de acciones", min_value=1, value=1, step=1, key=f"dtc_{eid}")
        precio_c = st.number_input("Precio de compra (MXN)", min_value=0.01, value=100.0,
                                   step=0.01, format="%.2f", key=f"dpc_{eid}")
        if es_mx:
            fx_c = 1.0
        else:
            fx_c = st.number_input("Tipo de cambio (MXN/USD)", min_value=1.0, value=fx_hoy,
                                   step=0.01, format="%.4f", key=f"dfx_{eid}",
                                   help="Solo informativo; el precio ya va en pesos.")
        st.caption("La comisión se calcula automáticamente con el % de tu perfil.")
        registrar = st.form_submit_button("➕ Registrar compra", type="primary", use_container_width=True)
    if registrar:
        importe = int(titulos_c) * float(precio_c)
        comision_mxn = comision_desde_perfil(importe)
        save_div_purchase(eid, fecha_c, int(titulos_c), float(precio_c), float(fx_c), comision_mxn)
        invalidar_resumen()
        st.success(f"✅ Compra registrada: {int(titulos_c)} acciones de {ticker} a ${precio_c:,.2f} MXN")
        st.rerun()


def _seccion(label):
    st.markdown(f"""
    <div style="border-top:1px solid #E8ECF4;margin:16px 0 8px;padding-top:12px;
                font-size:11px;font-weight:600;color:#6C63FF;
                letter-spacing:.07em;text-transform:uppercase;">{label}</div>
    """, unsafe_allow_html=True)


def _tabla_compras_div(compras, es_mx):
    """Tabla de compras con botón de borrar por fila."""
    # Encabezados
    if es_mx:
        cols_h = st.columns([1.3, 1, 1.3, 1.3, 1.3, 0.5])
        headers = ["Fecha", "Acciones", "Precio MXN", "Comisión+IVA", "Total MXN", ""]
    else:
        cols_h = st.columns([1.2, 0.9, 1.2, 0.9, 1.1, 1.2, 1.3, 0.5])
        headers = ["Fecha", "Acciones", "Precio MXN", "TC", "Precio USD", "Comisión+IVA", "Total MXN", ""]
    for c, h in zip(cols_h, headers):
        c.markdown(f"<div style='font-size:11px;color:#9DA5B8;font-weight:600;'>{h}</div>",
                   unsafe_allow_html=True)
    for cp in compras:
        com = cp.get("comision") or 0.0
        total = cp["titulos"] * cp["precio"] + com
        if es_mx:
            cols = st.columns([1.3, 1, 1.3, 1.3, 1.3, 0.5])
            vals = [str(cp["fecha"])[:10], str(cp["titulos"]),
                    f"${cp['precio']:,.2f}", f"${com:,.2f}", f"${total:,.2f}"]
        else:
            tc = cp.get("tipo_cambio") or 1.0
            cols = st.columns([1.2, 0.9, 1.2, 0.9, 1.1, 1.2, 1.3, 0.5])
            vals = [str(cp["fecha"])[:10], str(cp["titulos"]), f"${cp['precio']:,.2f}",
                    f"{tc:.4f}", f"${cp['precio']/tc:,.2f}", f"${com:,.2f}", f"${total:,.2f}"]
        for c, v in zip(cols[:-1], vals):
            c.markdown(f"<div style='font-size:13px;color:#1a1a2e;padding:3px 0;'>{v}</div>",
                       unsafe_allow_html=True)
        if cols[-1].button("🗑️", key=f"delrow_div_{cp['id']}", help="Borrar esta compra"):
            delete_div_purchase(cp["id"])
            st.rerun()


def _detalle_div(e: dict):
    st.markdown("""
    <style>
    div[data-testid="stExpanderDetails"] [data-testid="stMetricValue"] { font-size: 1.15rem !important; }
    div[data-testid="stExpanderDetails"] [data-testid="stMetricLabel"] { font-size: 0.72rem !important; }
    div[data-testid="stExpanderDetails"] [data-testid="stMetricDelta"] { font-size: 0.72rem !important; }
    </style>
    """, unsafe_allow_html=True)
    eid = e["id"]
    ticker = e["ticker"]
    es_mx = ticker.upper().endswith(".MX")
    fx_hoy = get_tipo_cambio_actual()
    resumen = get_dividend_summary(ticker)
    precio_usd = resumen["precio"]

    compras = load_div_purchases(eid)
    comprados = sum(c["titulos"] for c in compras)
    capital_compras = sum(c["titulos"] * c["precio"] + (c.get("comision") or 0.0) for c in compras)
    vendidos = titulos_vendidos("Dividendos", eid)
    titulos_tot = comprados - vendidos  # posición actual (descontando ventas)
    prom = capital_compras / comprados if comprados else 0.0
    capital_mxn = prom * titulos_tot

    _seccion("Compras registradas")
    if compras:
        _tabla_compras_div(compras, es_mx)

    # ── Resumen de dividendos ──
    _seccion("Ingreso por dividendos")
    if not compras:
        st.caption("Registra al menos una compra para ver tus ingresos por dividendos.")
        return

    ultimo = resumen["ultimo_pago"] or 0.0      # USD por acción
    ttm = resumen["ttm"] or 0.0                 # USD por acción (12m)
    yield_pct = resumen["yield_pct"]

    # Dividendos acumulados: por cada compra, dividendos pagados desde su fecha × acciones
    acum_por_accion_total = 0.0
    for c in compras:
        div_desde = get_dividends_since(ticker, str(c["fecha"])[:10])
        acum_por_accion_total += div_desde * c["titulos"]
    acum_usd = acum_por_accion_total                       # total USD recibido
    acum_mxn = acum_usd * fx_hoy

    # Próximo / último pago estimado para la posición completa
    ultimo_pos_usd = ultimo * titulos_tot
    ttm_pos_usd = ttm * titulos_tot
    valor_pos_usd = (precio_usd or 0) * titulos_tot
    valor_pos_mxn = valor_pos_usd * fx_hoy

    if precio_usd:
        st.caption(f"Precio actual de {ticker}: \\${precio_usd:,.2f} USD · TC hoy: {fx_hoy:.4f} · "
                   f"tus {titulos_tot} acciones valen ≈ \\${valor_pos_mxn:,.2f} MXN")

    # Fechas clave de dividendos
    ult_fecha = resumen["ultima_fecha"].strftime("%d/%m/%Y") if resumen["ultima_fecha"] else "—"
    ex_date = resumen.get("ex_date")
    next_pay = resumen.get("next_pay_date")
    ex_str = ex_date.strftime("%d/%m/%Y") if ex_date else "—"
    next_str = next_pay.strftime("%d/%m/%Y") if next_pay else "—"
    dias_ex = ""
    if ex_date:
        delta = (ex_date - date.today()).days
        if delta > 0:
            dias_ex = f" · en {delta} día{'s' if delta != 1 else ''}"
        elif delta == 0:
            dias_ex = " · ¡hoy!"
    st.markdown(f"""
    <div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:10px;">
        <div style="flex:1;min-width:160px;background:#F8F9FC;border:0.5px solid #E2E6EE;
                    border-radius:8px;padding:8px 12px;">
            <div style="font-size:10px;color:#9DA5B8;text-transform:uppercase;letter-spacing:.06em;">Último pago</div>
            <div style="font-size:14px;font-weight:600;color:#1a1a2e;">{ult_fecha}</div>
        </div>
        <div style="flex:1;min-width:160px;background:#FFF6E5;border:0.5px solid #F2D9A0;
                    border-radius:8px;padding:8px 12px;">
            <div style="font-size:10px;color:#C77F00;text-transform:uppercase;letter-spacing:.06em;">Próxima ex-date{dias_ex}</div>
            <div style="font-size:14px;font-weight:600;color:#1a1a2e;">{ex_str}</div>
        </div>
        <div style="flex:1;min-width:160px;background:#E8FBF4;border:0.5px solid #B6E8D6;
                    border-radius:8px;padding:8px 12px;">
            <div style="font-size:10px;color:#1D9E75;text-transform:uppercase;letter-spacing:.06em;">Próximo pago</div>
            <div style="font-size:14px;font-weight:600;color:#1a1a2e;">{next_str}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    if ex_date:
        st.caption("ℹ️ Debes tener la acción **antes** de la ex-date para recibir el siguiente dividendo.")

    r1, r2, r3 = st.columns(3)
    pct_ultimo = (ultimo / precio_usd * 100) if precio_usd else 0
    r1.metric("Último pago de dividendo", f"${ultimo_pos_usd:,.2f} USD",
              delta=f"{pct_ultimo:.2f}% del precio", delta_color="off")
    r2.metric("Dividendo TTM (tu posición)", f"${ttm_pos_usd:,.2f} USD",
              delta=f"yield {yield_pct:.2f}%" if yield_pct else None, delta_color="off")
    pct_acum_vs_capital = (acum_mxn / capital_mxn * 100) if capital_mxn else 0
    r3.metric("Dividendos acumulados", f"${acum_usd:,.2f} USD",
              delta=f"≈ ${acum_mxn:,.2f} MXN", delta_color="off")

    r4, r5, r6 = st.columns(3)
    r4.metric("Acumulado vs capital invertido", f"{pct_acum_vs_capital:.2f}%",
              delta=f"capital: ${capital_mxn:,.0f} MXN", delta_color="off")
    pct_acum_vs_valor = (acum_mxn / valor_pos_mxn * 100) if valor_pos_mxn else 0
    r5.metric("Acumulado vs valor actual", f"{pct_acum_vs_valor:.2f}%",
              delta=f"valor: ${valor_pos_mxn:,.0f} MXN", delta_color="off")
    yield_costo = (ttm_pos_usd * fx_hoy / capital_mxn * 100) if capital_mxn else 0
    r6.metric("Yield sobre costo (YoC)", f"{yield_costo:.2f}%",
              delta="dividendo anual / lo que pagaste", delta_color="off")

    # ── Ventas registradas (historial de rendimiento) ──
    estrategia_comun.ventas_registradas("Dividendos", eid)
