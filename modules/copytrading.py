import streamlit as st
import pandas as pd
from datetime import date

from utils.ticker_search import get_tipo_cambio_actual
from utils.db_utils import get_perfil
from utils.copytrading_utils import (
    INVERSIONISTAS, get_price_return, normalizar_holdings, rendimiento_inversionista,
    pesos_portafolio, analizar_inversionista, riesgo_cartera, match_perfil,
    movimientos_experto,
)
from utils.db_utils import (
    save_copy_strategy, load_copy_strategies, delete_copy_strategy,
    save_copy_purchase, load_copy_purchases, delete_copy_purchase,
    posiciones_copy, registrar_venta_copy,
)
from utils.comisiones import comision_desde_perfil
from utils.resumen_utils import invalidar_resumen
from modules import estrategia_comun

GREEN = "#1D9E75"
RED = "#A32D2D"
PURPLE = "#6C63FF"
GOLD = "#C77F00"


def render_copytrading():
    st.markdown("""
    <div style="margin-bottom:20px;">
        <h2 style="font-size:20px;font-weight:600;color:#1a1a2e;margin:0;">Copy Trading</h2>
        <p style="font-size:12px;color:#9DA5B8;margin:4px 0 0;">Replica las carteras de los grandes inversionistas del mundo</p>
    </div>
    """, unsafe_allow_html=True)
    if load_copy_strategies():
        tab_estrategias, tab_inv = st.tabs(["📋  Mis estrategias", "⭐  Inversionistas"])
    else:
        tab_inv, tab_estrategias = st.tabs(["⭐  Inversionistas", "📋  Mis estrategias"])
    with tab_inv:
        _tab_inversionistas()
    with tab_estrategias:
        _mis_estrategias_copy()


# ── Tab 1: inversionistas ────────────────────────────────────────────────────
def _tab_inversionistas():
    estrategia_comun.boton_ayuda(
        "ayuda_copy",
        "👥 Cómo usar el módulo de Copy Trading",
        "Aquí replicas las carteras de inversionistas famosos: lo que ellos tienen, lo armas tú en "
        "proporción a tu dinero. Pasos:",
        [
            ("1. Elige un inversionista", "Míralos en la lista con el rendimiento de su cartera en el último año, o búscalos por nombre (ej: Buffett, Icahn)."),
            ("2. Revisa su cartera", "Verás en qué acciones invierte y en qué porcentaje, su nivel de riesgo y qué tanto encaja con tu perfil."),
            ("3. Replica con tu monto", "Registra cuánto dinero quieres poner y la app arma la canasta proporcional (cuántas acciones de cada una)."),
            ("4. Sigue tu resultado", "En la pestaña 'Mis estrategias' ves el valor y el rendimiento de tu réplica."),
        ],
        nota="Recuerda: los rendimientos pasados no garantizan los futuros, y tú decides cuánto seguir.")
    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
    st.markdown("**Inversionistas y fondos más famosos · rendimiento de su cartera en el último año**")

    query = st.text_input(
        "Buscar otro portafolio",
        placeholder="Busca otros inversionistas — ej: Tepper, Klarman, Icahn, Tiger Global...",
        label_visibility="collapsed", key="copy_search",
    ).strip().lower()

    perfil = get_perfil()
    riesgo = perfil.get("perfil_riesgo")

    if query:
        lista = [inv for inv in INVERSIONISTAS
                 if query in inv["nombre"].lower() or query in inv["fondo"].lower()]
        if not lista:
            st.warning(f"No se encontró ningún portafolio para '{query}'.")
            return
        st.caption(f"{len(lista)} resultado(s) para '{query}'")
    else:
        lista = [inv for inv in INVERSIONISTAS if inv.get("destacado")]

    # Enriquecer con nivel de riesgo y encaje con el perfil, y ordenar por mejor match
    enriquecidos = []
    for inv in lista:
        ri = riesgo_cartera(tuple(inv["holdings"]))
        match, color, orden = match_perfil(ri["nivel"], riesgo)
        enriquecidos.append({"inv": inv, "nivel": ri["nivel"], "match": match,
                             "color": color, "orden": orden})
    if riesgo:
        enriquecidos.sort(key=lambda x: x["orden"])  # los que encajan primero

    # Banner de recomendación según perfil
    if not query:
        if riesgo:
            recom = [e["inv"]["nombre"] for e in enriquecidos if e["color"] == "verde"]
            if recom:
                st.markdown(f"""
                <div style="background:#E3F7EF;border:1px solid {GREEN};border-radius:10px;padding:10px 14px;margin-bottom:10px;">
                    <b style="color:{GREEN};">🎯 Recomendados para tu perfil {riesgo}:</b>
                    <span style="color:#1a1a2e;font-size:13px;"> {', '.join(recom)}</span>
                    <div style="font-size:11px;color:#9DA5B8;margin-top:3px;">Ordenados abajo: primero los que más encajan con tu nivel de riesgo.</div>
                </div>""", unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div style="background:#FFF6E0;border:1px solid {GOLD};border-radius:10px;padding:10px 14px;margin-bottom:10px;">
                    <b style="color:{GOLD};">Tu perfil es {riesgo}.</b>
                    <span style="color:#1a1a2e;font-size:13px;"> Ninguno de los destacados encaja perfecto; abajo van ordenados del más al menos compatible.</span>
                </div>""", unsafe_allow_html=True)
        else:
            st.info("💡 Define tu **perfil de riesgo** en Inicio y te recomendaré los inversionistas que mejor encajan contigo.")

    cmap = {"verde": GREEN, "amarillo": GOLD, "rojo": RED}
    emap = {"verde": "✅", "amarillo": "🟡", "rojo": "🔴"}
    for e in enriquecidos:
        inv = e["inv"]
        r = rendimiento_inversionista(tuple(inv["holdings"]))
        r_txt = f"{r:+.1f}%" if r is not None else "—"
        r_emoji = "🟢" if (r or 0) >= 0 else "🔴"
        match_tag = f"   ·   {emap[e['color']]} {e['nivel']}" if riesgo else f"   ·   riesgo {e['nivel']}"
        with st.expander(f"⭐ {inv['nombre']} — {inv['fondo']}   ·   {r_emoji} {r_txt} (1 año){match_tag}"):
            st.markdown(f"""
            <div style="font-size:12px;color:#9DA5B8;margin-bottom:8px;">{inv['estilo']}</div>
            """, unsafe_allow_html=True)

            holds, cobertura = pesos_portafolio(inv)
            filas = []
            for tk, peso in holds:
                pr = get_price_return(tk)
                filas.append({
                    "Acción": tk, "Peso del portafolio": peso,
                    "Precio (USD)": pr["precio"], "Rend. 1 año": pr["ret1y"],
                })
            filas.append({"Acción": f"TOTAL ({len(holds)} posiciones)",
                          "Peso del portafolio": cobertura, "Precio (USD)": None, "Rend. 1 año": None})
            df = pd.DataFrame(filas)

            def _bold_total(row):
                if str(row["Acción"]).startswith("TOTAL"):
                    return ["font-weight:700;background-color:#F0EEFF;color:#1a1a2e"] * len(row)
                return [""] * len(row)

            styler = (df.style
                      .format({"Peso del portafolio": "{:.1f}%", "Precio (USD)": "${:,.2f}",
                               "Rend. 1 año": "{:+.1f}%"}, na_rep="—")
                      .apply(_bold_total, axis=1))
            st.dataframe(styler, use_container_width=True, hide_index=True,
                         height=min(38 * (len(df) + 1), 460))
            st.caption(f"Top 10 posiciones representativas (basadas en reportes 13F públicos). "
                       f"El peso es el % **aproximado del portafolio total** de cada acción: "
                       f"estas {len(holds)} posiciones representan en conjunto ≈ **{cobertura:.0f}%** de su cartera "
                       f"(el resto está repartido en muchas posiciones más pequeñas).")
            # ── Análisis: ¿encaja con mi perfil? ──
            if st.button(f"🤖 ¿La cartera de {inv['nombre']} encaja con mi perfil?",
                         key=f"copy_match_{inv['id']}", use_container_width=True):
                perfil = get_perfil()
                st.session_state[f"copy_match_res_{inv['id']}"] = analizar_inversionista(
                    inv, perfil.get("perfil_riesgo"))
            mres = st.session_state.get(f"copy_match_res_{inv['id']}")
            if mres:
                cmap = {"verde": GREEN, "amarillo": GOLD, "rojo": RED}
                bg = {"verde": "#E3F7EF", "amarillo": "#FFF6E0", "rojo": "#FCEBEB"}
                col = cmap[mres["match_color"]]
                ret_txt = f"{mres['ret_1y']:+.1f}%" if mres["ret_1y"] is not None else "—"
                motivos = "".join(f"<li style='margin-bottom:2px;'>{m}</li>" for m in mres["motivos"])
                st.markdown(f"""
                <div style="background:{bg[mres['match_color']]};border:1px solid {col};border-radius:12px;padding:14px 18px;margin:6px 0;">
                    <div style="font-size:13px;font-weight:700;color:{col};">{mres['match']}</div>
                    <div style="display:flex;gap:18px;flex-wrap:wrap;margin:6px 0;font-size:12px;color:#4A5066;">
                        <span>Nivel de riesgo: <b>{mres['nivel']}</b></span>
                        <span>Rendimiento 1 año: <b>{ret_txt}</b></span>
                        <span>Posiciones: <b>{mres['n']}</b></span>
                    </div>
                    <ul style="font-size:12px;color:#4A5066;margin:4px 0 0;padding-left:18px;">{motivos}</ul>
                    <div style="font-size:10.5px;color:#9DA5B8;font-style:italic;margin-top:8px;">
                        Análisis informativo automático, no es asesoría financiera.</div>
                </div>
                """, unsafe_allow_html=True)

            if st.button(f"➕ Copiar la cartera de {inv['nombre']} a mi estrategia",
                         type="primary", key=f"copy_add_{inv['id']}"):
                save_copy_strategy(inv["id"], inv["nombre"], inv["fondo"])
                st.success(f"✅ Cartera de **{inv['nombre']}** agregada. Ve a 'Mis estrategias' para invertir.")


# ── Tab 2: mis estrategias ───────────────────────────────────────────────────
def _mis_estrategias_copy():
    estrategias = load_copy_strategies()
    if not estrategias:
        st.markdown("""
        <div style="text-align:center;padding:48px 24px;color:#9DA5B8;">
            <div style="font-size:32px;margin-bottom:12px;">⭐</div>
            <div style="font-size:14px;font-weight:500;color:#4A5066;">Sin carteras copiadas</div>
            <div style="font-size:12px;margin-top:6px;">Ve a "Inversionistas", elige uno y copia su cartera</div>
        </div>
        """, unsafe_allow_html=True)
        return
    for e in estrategias:
        with st.expander(f"⭐ {e.get('nombre') or e['investor_id']} — {e.get('fondo') or ''}"):
            _detalle_copy(e)


def _seccion(label, color=PURPLE):
    st.markdown(f"""
    <div style="border-top:1px solid #E8ECF4;margin:16px 0 8px;padding-top:12px;
                font-size:11px;font-weight:600;color:{color};
                letter-spacing:.07em;text-transform:uppercase;">{label}</div>
    """, unsafe_allow_html=True)


def _get_investor(investor_id):
    for inv in INVERSIONISTAS:
        if inv["id"] == investor_id:
            return inv
    return None


def _detalle_copy(e: dict):
    st.markdown("""
    <style>
    div[data-testid="stExpanderDetails"] [data-testid="stMetricValue"] { font-size: 1.1rem !important; }
    div[data-testid="stExpanderDetails"] [data-testid="stMetricLabel"] { font-size: 0.72rem !important; }
    div[data-testid="stExpanderDetails"] [data-testid="stMetricDelta"] { font-size: 0.72rem !important; }
    </style>
    """, unsafe_allow_html=True)
    eid = e["id"]
    inv = _get_investor(e["investor_id"])
    if not inv:
        st.warning("No se encontró la cartera de este inversionista.")
        return
    holds = normalizar_holdings(inv["holdings"])
    fx_hoy = get_tipo_cambio_actual()

    # ── Movimientos del experto (nuevo reporte trimestral) ──
    _seccion_movimientos_experto(inv)

    # ── Configurar inversión ──
    _seccion("Invertir en esta cartera", GREEN)
    c1, c2 = st.columns(2)
    monto_mxn = c1.number_input("¿Cuánto quieres invertir? (MXN)", min_value=100.0,
                                value=50000.0, step=500.0, format="%.2f", key=f"cm_{eid}")
    tc = c2.number_input("Tipo de cambio (MXN/USD)", min_value=1.0, value=fx_hoy,
                         step=0.01, format="%.4f", key=f"ctc_{eid}")
    monto_usd = monto_mxn / tc
    st.caption(f"Equivale a ≈ \\${monto_usd:,.2f} USD para distribuir entre las 10 posiciones.")

    # Distribución por peso → acciones enteras
    filas = []
    total_usado_usd = 0.0
    detalle = []
    for tk, peso in holds:
        pr = get_price_return(tk)
        precio = pr["precio"]
        if not precio:
            filas.append({"Acción": tk, "Peso": f"{peso:.1f}%", "Precio USD": "—", "Precio MXN": "—",
                          "Acciones": 0, "Inversión USD": "—", "Inversión MXN": "—",
                          "Precio compra (MXN)": None})
            continue
        alloc_usd = monto_usd * peso / 100
        acciones = int(alloc_usd // precio)
        costo_usd = acciones * precio
        total_usado_usd += costo_usd
        detalle.append({"ticker": tk, "titulos": acciones, "precio_usd": precio})
        filas.append({"Acción": tk, "Peso": f"{peso:.1f}%",
                      "Precio USD": f"${precio:,.2f}", "Precio MXN": f"${precio*tc:,.2f}",
                      "Acciones": acciones, "Inversión USD": f"${costo_usd:,.2f}",
                      "Inversión MXN": f"${costo_usd*tc:,.2f}",
                      "Precio compra (MXN)": round(precio * tc, 2)})
    df = pd.DataFrame(filas)
    col_cfg = {
        "Acciones": st.column_config.NumberColumn("Acciones", format="%d"),
        "Precio compra (MXN)": st.column_config.NumberColumn(
            "✏️ Precio compra (MXN)", format="%.2f", min_value=0.0,
            help="Edítalo con el precio REAL al que compraste cada acción (en pesos)"),
    }
    edited = st.data_editor(
        df, column_config=col_cfg, hide_index=True, use_container_width=True,
        height=min(38 * (len(df) + 1), 420), key=f"editor_copy_{eid}",
        disabled=["Acción", "Peso", "Precio USD", "Precio MXN", "Acciones",
                  "Inversión USD", "Inversión MXN"],
    )
    st.caption("✏️ Solo la columna **Precio compra (MXN)** es editable: pon el precio real al que "
               "compraste cada acción (una cosa es la teoría y otra tu ejecución real). Por defecto trae "
               "el precio actual en pesos; ese valor es el que se guarda como tu costo.")

    # Recalcular detalle y total con el precio de compra real editado
    edit_map = {row["Acción"]: row["Precio compra (MXN)"] for _, row in edited.iterrows()}
    detalle_real = []
    total_real_usd = 0.0
    for d in detalle:
        pc_mxn = edit_map.get(d["ticker"])
        pc_usd = (pc_mxn / tc) if (pc_mxn and not pd.isna(pc_mxn) and pc_mxn > 0) else d["precio_usd"]
        detalle_real.append({"ticker": d["ticker"], "titulos": d["titulos"], "precio_usd": pc_usd})
        total_real_usd += d["titulos"] * pc_usd
    detalle = detalle_real

    sobrante_usd = monto_usd - total_real_usd
    cS1, cS2, cS3 = st.columns(3)
    cS1.metric("Total a invertir", f"${total_real_usd*tc:,.2f} MXN", delta=f"${total_real_usd:,.2f} USD", delta_color="off")
    cS2.metric("Sobrante (sin asignar)", f"${sobrante_usd*tc:,.2f} MXN", delta=f"${sobrante_usd:,.2f} USD", delta_color="off")
    cS3.metric("Posiciones a comprar", f"{sum(1 for d in detalle if d['titulos']>0)}")

    if st.button("💾 Guardar y realizar la compra de todas las acciones en tu casa de bolsa",
                 type="primary", key=f"copy_save_{eid}", use_container_width=True):
        if not detalle or total_real_usd <= 0:
            st.warning("El monto no alcanza para comprar al menos una acción. Aumenta la inversión.")
        else:
            save_copy_purchase(eid, date.today(), monto_mxn, tc, detalle)
            st.success("✅ Compra guardada con tus precios reales. Recuerda ejecutar estas órdenes en tu casa de bolsa.")
            st.rerun()

    # ── Tus posiciones + rebalanceo + venta por posición ──
    _seccion_posiciones_rebalanceo(e, inv, fx_hoy)

    # ── Historial ──
    _seccion("Historial de compras", PURPLE)
    compras = load_copy_purchases(eid)
    if not compras:
        st.caption("Aún no has guardado ninguna compra de esta cartera.")
    else:
        for cp in compras:
            _bloque_compra(cp)

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
    if st.button("🗑️ Quitar de mi estrategia", key=f"copy_del_{eid}",
                 help="Borra esta cartera con todo su historial de compras"):
        delete_copy_strategy(eid)
        st.rerun()


def _seccion_movimientos_experto(inv):
    """Muestra qué movió el experto en su último reporte 13F (compró/vendió/ajustó)
    y qué haría el cliente para seguir replicándolo. El cliente decide."""
    mv = movimientos_experto(inv)
    if not mv or not mv["hay"]:
        return
    nombre = inv["nombre"]

    def _chips(items, fmt):
        return " ".join(
            f"<span style='display:inline-block;background:{'#E3F7EF' if fmt=='buy' else '#FDECEC'};"
            f"color:{GREEN if fmt=='buy' else RED};font-size:12px;font-weight:600;"
            f"border-radius:8px;padding:2px 8px;margin:2px 3px 2px 0;'>{x}</span>"
            for x in items)

    comprar = [f"{t} · nueva" for t, _ in mv["anadidas"]] + \
              [f"{t} {o:.0f}%→{c:.0f}%" for t, o, c in mv["subieron"]]
    vender = [f"{t} · salió" for t, _ in mv["quitadas"]] + \
             [f"{t} {o:.0f}%→{c:.0f}%" for t, o, c in mv["bajaron"]]

    bloques = ""
    if comprar:
        bloques += (f"<div style='margin-top:8px;'><span style='font-size:12px;font-weight:700;color:{GREEN};'>"
                    f"🟢 Compró / aumentó</span><div style='margin-top:3px;'>{_chips(comprar, 'buy')}</div>"
                    f"<div style='font-size:11px;color:#9DA5B8;'>→ para replicarlo, considera comprar estas.</div></div>")
    if vender:
        bloques += (f"<div style='margin-top:10px;'><span style='font-size:12px;font-weight:700;color:{RED};'>"
                    f"🔴 Vendió / redujo</span><div style='margin-top:3px;'>{_chips(vender, 'sell')}</div>"
                    f"<div style='font-size:11px;color:#9DA5B8;'>→ para replicarlo, considera vender/recortar estas.</div></div>")

    st.markdown(f"""
    <div style="background:#F4F3FF;border:1px solid #C9C2FF;border-radius:12px;padding:14px 16px;margin:4px 0 10px;">
        <div style="font-size:13px;font-weight:700;color:{PURPLE};">
            🔔 {nombre} ajustó su cartera · nuevo reporte {mv['trimestre']}
            <span style="font-weight:400;color:#9DA5B8;">(vs {mv['anterior']})</span></div>
        {bloques}
        <div style="font-size:11px;color:#4A5066;margin-top:10px;">
            <b>Tú decides si rebalancear.</b> Usa "Invertir" para comprar y "Vender una posición" (abajo) para vender.</div>
        <div style="font-size:10px;color:#9DA5B8;font-style:italic;margin-top:6px;">
            Movimientos representativos con fines ilustrativos, basados en reportes 13F públicos
            (trimestrales, con retraso). Verifica en fuentes oficiales antes de operar.</div>
    </div>
    """, unsafe_allow_html=True)


def _seccion_posiciones_rebalanceo(e, inv, fx):
    """Vista AGREGADA por acción: cuánto tienes, tu peso vs el peso meta del
    experto (rebalanceo) y venta posición por posición → va a Resultados."""
    eid = e["id"]
    posiciones = [p for p in posiciones_copy(eid) if p["titulos"] > 0]
    if not posiciones:
        return
    _seccion("Tus posiciones y rebalanceo", GOLD)

    target = dict(normalizar_holdings(inv["holdings"]))  # ticker → peso meta %

    # Valor actual de cada posición (para calcular tu peso real)
    datos, total_val = [], 0.0
    for p in posiciones:
        pr = get_price_return(p["ticker"])
        px = pr["precio"] or p["avg_cost_usd"]
        val_usd = p["titulos"] * px
        total_val += val_usd
        datos.append({"p": p, "px": px, "val_usd": val_usd})

    filas, sugerencias = [], []
    for d in datos:
        p = d["p"]
        cur_w = (d["val_usd"] / total_val * 100) if total_val else 0
        tgt_w = target.get(p["ticker"], 0.0)
        drift = cur_w - tgt_w
        pl_pct = (d["px"] / p["avg_cost_usd"] - 1) * 100 if p["avg_cost_usd"] else 0
        if tgt_w == 0:
            sug = "El experto ya no la pondera → considera vender"
            sugerencias.append(f"revisa {p['ticker']}")
        elif drift > 5:
            sug = "Sobreponderada → recorta un poco"
            sugerencias.append(f"recorta {p['ticker']}")
        elif drift < -5:
            sug = "Subponderada → aumenta"
            sugerencias.append(f"aumenta {p['ticker']}")
        else:
            sug = "En línea ✓"
        filas.append({"Acción": p["ticker"], "Tienes": p["titulos"],
                      "Tu peso": cur_w, "Peso meta": tgt_w,
                      "Rend.": pl_pct, "Sugerencia": sug})
    df = pd.DataFrame(filas)
    st.dataframe(
        df.style.format({"Tu peso": "{:.1f}%", "Peso meta": "{:.1f}%", "Rend.": "{:+.1f}%"}),
        hide_index=True, use_container_width=True, height=min(38 * (len(df) + 1), 460))

    nombre_exp = e.get("nombre") or "el experto"
    if sugerencias:
        st.info(f"🔄 **Para seguir replicando a {nombre_exp}:** " + " · ".join(sugerencias)
                + ". El 'peso meta' viene de su último reporte 13F (trimestral).")
    else:
        st.success(f"✅ Tu cartera está alineada con la de {nombre_exp}.")

    # ── Venta posición por posición ──
    st.markdown("**Vender una posición** — la ganancia o pérdida se registra en tus Resultados.")
    tickers = [p["ticker"] for p in posiciones]
    tk_sel = st.selectbox("¿Qué acción quieres vender?", tickers, key=f"copy_sell_tk_{eid}")
    psel = next(p for p in posiciones if p["ticker"] == tk_sel)
    px_now = get_price_return(tk_sel)["precio"] or psel["avg_cost_usd"]
    with st.form(f"copy_sell_form_{eid}", clear_on_submit=True):
        cs1, cs2, cs3 = st.columns(3)
        fecha_v = cs1.date_input("Fecha", value=date.today(), max_value=date.today(), key=f"cs_f_{eid}")
        cant = cs2.number_input("Acciones", min_value=1, max_value=int(psel["titulos"]),
                                value=int(psel["titulos"]), step=1, key=f"cs_n_{eid}")
        precio_v = cs3.number_input("Precio venta (USD)", min_value=0.01, value=round(px_now, 2),
                                    step=0.01, format="%.2f", key=f"cs_p_{eid}")
        tc_v = st.number_input("Tipo de cambio (MXN/USD)", min_value=1.0, value=fx,
                               step=0.01, format="%.4f", key=f"cs_tc_{eid}")
        st.caption(f"Costo promedio de {tk_sel}: ≈ ${psel['avg_cost_usd']:,.2f} USD por acción. "
                   "La comisión se calcula con el % de tu perfil.")
        vender = st.form_submit_button("💵 Confirmar venta", type="primary", use_container_width=True)
    if vender:
        com = comision_desde_perfil(int(cant) * float(precio_v) * float(tc_v))
        r = registrar_venta_copy(eid, tk_sel, fecha_v, int(cant), float(precio_v), float(tc_v), com)
        if r["ok"]:
            invalidar_resumen()
            g = r["ganancia"]
            signo = "ganancia" if g >= 0 else "pérdida"
            st.success(f"✅ Vendiste {int(cant)} de {tk_sel} · {signo} de ${abs(g):,.2f} MXN. "
                       "Ya aparece en Resultados › Rendimiento realizado.")
            st.rerun()
        else:
            st.warning(r["msg"])


def _bloque_compra(cp):
    tc = cp["tipo_cambio"]
    invertido_usd = sum(d["titulos"] * d["precio_usd"] for d in cp["detalle"])
    # Valor actual con precios en vivo
    valor_usd = 0.0
    filas = []
    for d in cp["detalle"]:
        pr = get_price_return(d["ticker"])
        precio_hoy = pr["precio"] or d["precio_usd"]
        val = d["titulos"] * precio_hoy
        valor_usd += val
        pl_pct = (precio_hoy / d["precio_usd"] - 1) * 100 if d["precio_usd"] else 0
        filas.append({"Acción": d["ticker"], "Acciones": d["titulos"],
                      "Precio compra": d["precio_usd"], "Precio actual": precio_hoy,
                      "Valor USD": val, "Rend. %": pl_pct})
    pl_usd = valor_usd - invertido_usd
    pl_pct = (pl_usd / invertido_usd * 100) if invertido_usd else 0
    col = GREEN if pl_usd >= 0 else RED

    st.markdown(f"""
    <div style="background:#F8F9FC;border:0.5px solid #E2E6EE;border-radius:10px;padding:10px 14px;margin-bottom:4px;
                display:flex;justify-content:space-between;flex-wrap:wrap;gap:10px;align-items:center;">
        <span style="font-size:12.5px;"><b>{str(cp['fecha'])[:10]}</b> · invertido
            ${cp['monto_mxn']:,.2f} MXN (${invertido_usd:,.2f} USD · TC {tc:.4f})</span>
        <span style="font-size:13px;">Valor actual: <b>${valor_usd:,.2f} USD</b> ·
            <b style="color:{col};">{pl_pct:+.2f}%</b></span>
    </div>
    """, unsafe_allow_html=True)
    df = pd.DataFrame(filas)
    st.dataframe(
        df.style.format({"Precio compra": "${:,.2f}", "Precio actual": "${:,.2f}",
                         "Valor USD": "${:,.2f}", "Rend. %": "{:+.2f}%"}),
        use_container_width=True, hide_index=True, height=min(38 * (len(df) + 1), 420),
    )
    cP1, cP2, cP3 = st.columns(3)
    cP1.metric("Invertido", f"${invertido_usd*tc:,.2f} MXN", delta=f"${invertido_usd:,.2f} USD", delta_color="off")
    cP2.metric("Valor actual", f"${valor_usd*tc:,.2f} MXN", delta=f"${valor_usd:,.2f} USD", delta_color="off")
    cP3.metric("Ganancia / Pérdida", f"${pl_usd*tc:,.2f} MXN", delta=f"{pl_pct:+.2f}%")
    if st.button("🗑️ Borrar esta compra", key=f"copy_delc_{cp['id']}"):
        delete_copy_purchase(cp["id"])
        st.rerun()
    st.caption("El rendimiento refleja el movimiento del precio de las acciones (en USD). "
               "El valor en pesos usa el tipo de cambio que registraste al comprar.")
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
