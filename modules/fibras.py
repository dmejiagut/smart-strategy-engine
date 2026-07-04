import streamlit as st
import pandas as pd
from datetime import date

from utils.ticker_search import get_precio_actual
from utils.comisiones import comision_desde_perfil
from utils.fibras_utils import FIBRAS_MX, get_fibra_metrics, analizar_fibra
from utils.dividends_utils import get_dividend_summary, get_dividends_since
from utils.db_utils import (
    save_fibra_strategy, load_fibra_strategies, delete_fibra_strategy,
    save_fibra_purchase, load_fibra_purchases, delete_fibra_purchase,
    titulos_vendidos,
)
from modules import estrategia_comun
from utils.resumen_utils import invalidar_resumen

GREEN = "#1D9E75"
GOLD = "#C77F00"
RED = "#A32D2D"
PURPLE = "#6C63FF"

COLOR_BG = {"verde": "#E3F7EF", "amarillo": "#FFF6E0", "rojo": "#FCEBEB"}
COLOR_TXT = {"verde": GREEN, "amarillo": GOLD, "rojo": RED}


def render_fibras():
    st.markdown("""
    <div style="margin-bottom:20px;">
        <h2 style="font-size:20px;font-weight:600;color:#1a1a2e;margin:0;">FIBRAs</h2>
        <p style="font-size:12px;color:#9DA5B8;margin:4px 0 0;">Análisis de Fideicomisos de Inversión en Bienes Raíces mexicanos — todo en pesos (MXN)</p>
    </div>
    """, unsafe_allow_html=True)
    tab_analisis, tab_estrategias = st.tabs(["🏢  Análisis de FIBRAs", "📋  Mis estrategias"])
    with tab_analisis:
        _tab_analisis()
    with tab_estrategias:
        _mis_estrategias_fibra()


# ── Tab 1: análisis ──────────────────────────────────────────────────────────
@st.cache_data(ttl=1800, show_spinner="Cargando FIBRAs del mercado mexicano...")
def _cargar_tabla() -> pd.DataFrame:
    filas = []
    for f in FIBRAS_MX:
        m = get_fibra_metrics(f["ticker"])
        if m["precio"] is None:
            continue  # omitir las que no devuelven datos
        filas.append({
            "ticker": f["ticker"], "Fibra": f["nombre"], "Sector": f["sector"],
            "Precio (MXN)": m["precio"],
            "Div. Yield (%)": m["div_yield"],
            "Rend. 2026 (%)": m["ytd"],
            "Valor Mcdo (mdp)": m["market_cap"] / 1e6 if m["market_cap"] else None,
        })
    return pd.DataFrame(filas)


def _tab_analisis():
    estrategia_comun.boton_ayuda(
        "ayuda_fib",
        "🏢 Cómo usar el módulo de FIBRAs",
        "Las FIBRAs son bienes raíces (centros comerciales, oficinas) que compras en la Bolsa Mexicana, "
        "todo en pesos. Pasos:",
        [
            ("1. Mira la tabla", "Son las FIBRAs del mercado mexicano. Pulsa 'Analizar y calificar FIBRAs' para colorearlas según su atractivo (verde = mejor)."),
            ("2. Elige una FIBRA", "Selecciónala abajo para ver su precio, su dividend yield y su rendimiento del año."),
            ("3. Agrégala", "Pulsa 'Agregar a mi estrategia de FIBRAs'."),
            ("4. Registra tus compras", "En 'Mis estrategias' anota cuántos CBFIs (títulos) compraste y a qué precio. La app sigue tus rentas y plusvalía."),
        ],
        nota="Un 'CBFI' es cada título de una FIBRA, parecido a una acción. Todo se maneja en pesos (MXN).")
    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
    st.markdown("**FIBRAs que cotizan en la Bolsa Mexicana de Valores**")
    df = _cargar_tabla()
    if df.empty:
        st.warning("No se pudieron cargar datos de las FIBRAs en este momento. Intenta de nuevo en unos minutos.")
        return

    cbtn1, cbtn2 = st.columns([1.4, 3])
    if cbtn1.button("🔍 Analizar y calificar FIBRAs", type="primary", key="fib_analizar"):
        analisis = {}
        for _, row in df.iterrows():
            m = {"div_yield": row["Div. Yield (%)"], "ytd": row["Rend. 2026 (%)"],
                 "market_cap": (row["Valor Mcdo (mdp)"] or 0) * 1e6}
            analisis[row["ticker"]] = analizar_fibra(m)
        st.session_state["fib_analisis"] = analisis
    if st.button("Limpiar análisis", key="fib_limpiar"):
        st.session_state.pop("fib_analisis", None)

    analisis = st.session_state.get("fib_analisis")
    df_show = df.drop(columns=["ticker"]).copy()
    if analisis:
        df_show["Recomendación"] = df["ticker"].map(lambda t: analisis[t]["recomendacion"])
        df_show["Score"] = df["ticker"].map(lambda t: analisis[t]["score"])

    fmt = {"Precio (MXN)": "${:,.2f}", "Div. Yield (%)": "{:.1f}%",
           "Rend. 2026 (%)": "{:+.1f}%", "Valor Mcdo (mdp)": "${:,.0f}"}
    styler = df_show.style.format(fmt, na_rep="—")

    if analisis:
        colores = df["ticker"].map(lambda t: analisis[t]["color"]).tolist()
        def _row_style(row):
            c = COLOR_BG.get(colores[row.name], "")
            return [f"background-color:{c}"] * len(row)
        styler = styler.apply(_row_style, axis=1)

    st.dataframe(styler, use_container_width=True, hide_index=True,
                 height=min(40 * (len(df_show) + 1), 520))

    if analisis:
        st.markdown(f"""<div style="display:flex;gap:14px;font-size:12px;margin:4px 0 10px;">
            <span style="color:{GREEN};">🟢 Compra (sólida)</span>
            <span style="color:{GOLD};">🟡 Neutral</span>
            <span style="color:{RED};">🔴 Evitar</span>
        </div>""", unsafe_allow_html=True)
        st.caption("Calificación basada en datos de mercado: dividend yield, momentum del año y tamaño/liquidez. "
                   "Las métricas operativas (NOI, FFO, ocupación, LTV) provienen de boletines de analistas.")
    else:
        st.caption("Pulsa **Analizar y calificar FIBRAs** para colorear la tabla según su atractivo.")

    # Detalle / agregar
    st.markdown("---")
    st.markdown("**Selecciona una FIBRA para ver su detalle y agregarla a tu estrategia**")
    opciones = {f"{r['Fibra']} ({r['ticker']}) · {r['Sector']}": r["ticker"]
                for _, r in df.iterrows()}
    sel_label = st.selectbox("FIBRA", list(opciones.keys()), key="fib_sel")
    ticker_sel = opciones[sel_label]
    fila = df[df["ticker"] == ticker_sel].iloc[0]
    nombre_sel = fila["Fibra"]
    sector_sel = fila["Sector"]

    cI1, cI2, cI3, cI4 = st.columns(4)
    cI1.metric("Precio", f"${fila['Precio (MXN)']:,.2f} MXN")
    cI2.metric("Dividend Yield", f"{fila['Div. Yield (%)']:.1f}%" if pd.notna(fila["Div. Yield (%)"]) else "—")
    cI3.metric("Rend. 2026", f"{fila['Rend. 2026 (%)']:+.1f}%" if pd.notna(fila["Rend. 2026 (%)"]) else "—")
    cI4.metric("Valor de mercado", f"${fila['Valor Mcdo (mdp)']:,.0f} mdp" if pd.notna(fila["Valor Mcdo (mdp)"]) else "—")

    if analisis and ticker_sel in analisis:
        a = analisis[ticker_sel]
        col = COLOR_TXT[a["color"]]
        motivos_html = "".join(f"<li style='margin-bottom:2px;'>{mo}</li>" for mo in a["motivos"])
        st.markdown(f"""
        <div style="background:{COLOR_BG[a['color']]};border:1px solid {col};border-radius:12px;padding:14px 18px;margin-top:8px;">
            <div style="font-size:13px;font-weight:700;color:{col};">
                {a['recomendacion']} · Score {a['score']}/100</div>
            <ul style="font-size:12px;color:#4A5066;margin:6px 0 0;padding-left:18px;">{motivos_html}</ul>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    if st.button(f"➕ Agregar {nombre_sel} a mi estrategia de FIBRAs", type="primary", key=f"fib_add_{ticker_sel}"):
        save_fibra_strategy(ticker_sel, nombre_sel, sector_sel)
        st.success(f"✅ **{nombre_sel}** agregada. Ve a la pestaña 'Mis estrategias' para registrar compras.")


# ── Tab 2: mis estrategias ───────────────────────────────────────────────────
def _mis_estrategias_fibra():
    estrategias = load_fibra_strategies()
    if not estrategias:
        st.markdown("""
        <div style="text-align:center;padding:48px 24px;color:#9DA5B8;">
            <div style="font-size:32px;margin-bottom:12px;">🏢</div>
            <div style="font-size:14px;font-weight:500;color:#4A5066;">Sin FIBRAs en tu estrategia</div>
            <div style="font-size:12px;margin-top:6px;">Ve a "Análisis de FIBRAs", elige una y agrégala</div>
        </div>
        """, unsafe_allow_html=True)
        return
    for e in estrategias:
        sub = f"— {e.get('nombre') or e['ticker']}"
        if e.get("sector"):
            sub += f" · {e['sector']}"
        estrategia_comun.card(e, "FIBRAs", "🏢", e["ticker"], sub,
                              _detalle_fibra, _fib_form_compra, delete_fibra_strategy)


def _fib_form_compra(e: dict):
    eid = e["id"]
    ticker = e["ticker"]
    precio_hoy = get_fibra_metrics(ticker)["precio"]
    with st.form(f"form_fib_{eid}", clear_on_submit=True):
        c1, c2 = st.columns(2)
        fecha_c = c1.date_input("Fecha", value=date.today(), max_value=date.today(), key=f"ffc_{eid}")
        titulos_c = c2.number_input("Títulos (CBFIs)", min_value=1, value=1, step=1, key=f"ftc_{eid}")
        precio_c = st.number_input("Precio de compra (MXN)", min_value=0.01,
                                   value=round(float(precio_hoy or 100), 2), step=0.01,
                                   format="%.2f", key=f"fpc_{eid}")
        st.caption("La comisión se calcula automáticamente con el % de tu perfil.")
        registrar = st.form_submit_button("➕ Registrar compra", type="primary", use_container_width=True)
    if registrar:
        importe = int(titulos_c) * float(precio_c)
        comision_mxn = comision_desde_perfil(importe)
        save_fibra_purchase(eid, fecha_c, int(titulos_c), float(precio_c), comision_mxn)
        invalidar_resumen()
        st.success(f"✅ Compra registrada: {int(titulos_c)} CBFIs a ${precio_c:,.2f} MXN")
        st.rerun()


def _seccion(label, color=PURPLE):
    st.markdown(f"""
    <div style="border-top:1px solid #E8ECF4;margin:16px 0 8px;padding-top:12px;
                font-size:11px;font-weight:600;color:{color};
                letter-spacing:.07em;text-transform:uppercase;">{label}</div>
    """, unsafe_allow_html=True)


def _detalle_fibra(e: dict):
    st.markdown("""
    <style>
    div[data-testid="stExpanderDetails"] [data-testid="stMetricValue"] { font-size: 1.15rem !important; }
    div[data-testid="stExpanderDetails"] [data-testid="stMetricLabel"] { font-size: 0.72rem !important; }
    div[data-testid="stExpanderDetails"] [data-testid="stMetricDelta"] { font-size: 0.72rem !important; }
    </style>
    """, unsafe_allow_html=True)
    eid = e["id"]
    ticker = e["ticker"]
    m = get_fibra_metrics(ticker)
    precio_hoy = m["precio"]

    compras = load_fibra_purchases(eid)
    comprados = sum(c["titulos"] for c in compras)
    capital_compras = sum(c["titulos"] * c["precio"] + (c.get("comision") or 0.0) for c in compras)
    vendidos = titulos_vendidos("FIBRAs", eid)
    titulos_tot = comprados - vendidos  # posición actual (descontando ventas)
    prom = capital_compras / comprados if comprados else 0.0
    capital_mxn = prom * titulos_tot

    _seccion("Compras registradas", GREEN)
    if compras:
        _tabla_compras(compras)

    # ── Resumen ──
    _seccion("Resumen de la posición", PURPLE)
    if not compras:
        st.caption("Registra una compra para ver tu resumen.")
    else:
        valor_actual = titulos_tot * precio_hoy if precio_hoy else None
        plusvalia = (valor_actual - capital_mxn) if valor_actual is not None else None
        precio_prom = capital_mxn / titulos_tot if titulos_tot else 0
        if precio_hoy:
            extra = f" · yield {m['div_yield']:.1f}%" if m.get("div_yield") else ""
            st.caption(f"Precio actual de {ticker}: \\${precio_hoy:,.2f} MXN{extra}")
        r1, r2, r3, r4 = st.columns(4)
        r1.metric("CBFIs acumulados", f"{titulos_tot:,}")
        r2.metric("Precio promedio", f"${precio_prom:,.2f} MXN")
        r3.metric("Capital invertido", f"${capital_mxn:,.2f} MXN")
        r4.metric("Valor actual", f"${valor_actual:,.2f} MXN" if valor_actual is not None else "—",
                  delta=f"{(plusvalia/capital_mxn*100) if capital_mxn else 0:+.2f}% plusvalía" if plusvalia is not None else None,
                  delta_color="off")

        # ── Distribuciones (CBFIs en MXN) ──
        _seccion("Distribuciones y rentabilidad total", GREEN)
        dsum = get_dividend_summary(ticker)
        ult = dsum.get("ultimo_pago") or 0.0     # MXN por CBFI
        ttm = dsum.get("ttm") or 0.0             # MXN por CBFI (12m)
        # Distribuciones acumuladas desde cada compra
        acum_por_cbfi = 0.0
        for c in compras:
            acum_por_cbfi += get_dividends_since(ticker, str(c["fecha"])[:10]) * c["titulos"]
        dist_acum = acum_por_cbfi                # MXN totales recibidos
        ult_pos = ult * titulos_tot
        ttm_pos = ttm * titulos_tot

        if dsum.get("ultima_fecha"):
            ex = dsum.get("ex_date")
            nxt = dsum.get("next_pay_date")
            partes = [f"Última distribución: {dsum['ultima_fecha'].strftime('%d/%m/%Y')}"]
            if ex:
                partes.append(f"Próxima ex-date: {ex.strftime('%d/%m/%Y')}")
            if nxt:
                partes.append(f"Próximo pago: {nxt.strftime('%d/%m/%Y')}")
            st.caption(" · ".join(partes))

        d1, d2, d3 = st.columns(3)
        pct_ult = (ult / precio_hoy * 100) if precio_hoy else 0
        d1.metric("Última distribución", f"${ult_pos:,.2f} MXN",
                  delta=f"${ult:,.4f}/CBFI · {pct_ult:.2f}% del precio", delta_color="off")
        d2.metric("Distribución TTM (anual)", f"${ttm_pos:,.2f} MXN",
                  delta=f"yield {dsum['yield_pct']:.2f}%" if dsum.get("yield_pct") else None, delta_color="off")
        pct_acum = (dist_acum / capital_mxn * 100) if capital_mxn else 0
        d3.metric("Distribuciones acumuladas", f"${dist_acum:,.2f} MXN",
                  delta=f"{pct_acum:.2f}% de tu capital", delta_color="off")

        # ── Rentabilidad TOTAL (plusvalía + distribuciones) ──
        retorno_total_mxn = (plusvalia or 0) + dist_acum
        retorno_total_pct = (retorno_total_mxn / capital_mxn * 100) if capital_mxn else 0
        col_tot = GREEN if retorno_total_mxn >= 0 else RED
        st.markdown(f"""
        <div style="background:#fff;border:1.5px solid {col_tot};border-radius:12px;padding:14px 20px;margin-top:6px;
                    display:flex;justify-content:space-around;align-items:center;text-align:center;flex-wrap:wrap;gap:12px;">
            <div><div style="font-size:11px;color:#9DA5B8;">Plusvalía (precio)</div>
                 <div style="font-size:16px;font-weight:600;color:#1a1a2e;">${(plusvalia or 0):,.2f} MXN</div></div>
            <div style="font-size:20px;color:#D0D4DE;">+</div>
            <div><div style="font-size:11px;color:#9DA5B8;">Distribuciones cobradas</div>
                 <div style="font-size:16px;font-weight:600;color:{GREEN};">${dist_acum:,.2f} MXN</div></div>
            <div style="font-size:20px;color:#D0D4DE;">=</div>
            <div><div style="font-size:11px;color:#9DA5B8;">Rentabilidad TOTAL</div>
                 <div style="font-size:20px;font-weight:700;color:{col_tot};">${retorno_total_mxn:,.2f} MXN · {retorno_total_pct:+.2f}%</div></div>
        </div>
        """, unsafe_allow_html=True)
        st.caption("La rentabilidad total combina lo que ha subido el precio de tus CBFIs **más** las distribuciones que has "
                   "cobrado (incluyen tanto el reparto de rentas como los reembolsos de capital).")

    # ── Ventas registradas (historial de rendimiento) ──
    estrategia_comun.ventas_registradas("FIBRAs", eid)


def _tabla_compras(compras):
    cols_h = st.columns([1.4, 1, 1.4, 1.4, 1.4, 0.5])
    for c, h in zip(cols_h, ["Fecha", "CBFIs", "Precio MXN", "Comisión+IVA", "Total MXN", ""]):
        c.markdown(f"<div style='font-size:11px;color:#9DA5B8;font-weight:600;'>{h}</div>",
                   unsafe_allow_html=True)
    for cp in compras:
        com = cp.get("comision") or 0.0
        total = cp["titulos"] * cp["precio"] + com
        cols = st.columns([1.4, 1, 1.4, 1.4, 1.4, 0.5])
        vals = [str(cp["fecha"])[:10], str(cp["titulos"]),
                f"${cp['precio']:,.2f}", f"${com:,.2f}", f"${total:,.2f}"]
        for c, v in zip(cols[:-1], vals):
            c.markdown(f"<div style='font-size:13px;color:#1a1a2e;padding:3px 0;'>{v}</div>",
                       unsafe_allow_html=True)
        if cols[-1].button("🗑️", key=f"fdelrow_{cp['id']}", help="Borrar esta compra"):
            delete_fibra_purchase(cp["id"])
            st.rerun()
