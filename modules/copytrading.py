import streamlit as st
import pandas as pd
from datetime import date

from utils.ticker_search import get_tipo_cambio_actual
from utils.db_utils import get_perfil
from utils.copytrading_utils import (
    INVERSIONISTAS, get_price_return, normalizar_holdings, rendimiento_inversionista,
    pesos_portafolio, analizar_inversionista, riesgo_cartera, match_perfil,
    movimientos_experto, REPORTE_ANTERIOR, TRIMESTRE_ACTUAL, TRIMESTRE_ANTERIOR,
)
from utils.db_utils import (
    save_copy_strategy, load_copy_strategies, delete_copy_strategy,
    save_copy_purchase, load_copy_purchases, delete_copy_detalle,
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


def _plan_copy(eid, inv, fx):
    """(filas, valor_total_usd). Cada fila: ticker, pesoQ1, pesoQ2 (meta), tienes,
    tu_peso, mov (+comprar/−vender en acciones ENTERAS), precio. La MISMA base
    la usan la tabla informativa y el rebalanceo, así van siempre consistentes."""
    posiciones = {p["ticker"]: p for p in posiciones_copy(eid) if p["titulos"] > 0}
    cur = dict(normalizar_holdings(inv["holdings"]))
    prev = REPORTE_ANTERIOR.get(inv["id"])
    old = dict(normalizar_holdings(prev)) if prev else {}
    tickers = set(cur) | set(posiciones)
    precios = {tk: (get_price_return(tk)["precio"] or posiciones.get(tk, {}).get("avg_cost_usd") or 0)
               for tk in tickers}
    total_val = sum(posiciones[tk]["titulos"] * precios[tk] for tk in posiciones)
    filas = []
    for tk in tickers:
        px = precios[tk]
        held = posiciones.get(tk, {}).get("titulos", 0)
        tu_peso = (held * px / total_val * 100) if total_val > 0 else 0.0
        tgt_w = cur.get(tk, 0.0)
        tgt_shares = int(round(total_val * tgt_w / 100 / px)) if (tgt_w > 0 and px > 0 and total_val > 0) else 0
        filas.append({"ticker": tk, "pesoQ1": old.get(tk), "pesoQ2": tgt_w,
                      "tienes": held, "tu_peso": tu_peso, "mov": tgt_shares - held, "precio": px})
    filas.sort(key=lambda f: (-f["pesoQ2"], -f["tienes"]))
    return filas, total_val


def _tabla_copy(inv, filas):
    """Una sola tabla informativa: pesos del experto (antes/ahora), lo que tienes
    y el MOVIMIENTO que te toca (verde=comprar, rojo=vender, gris=nada)."""
    col_q1, col_q2 = f"Peso {TRIMESTRE_ANTERIOR}", f"Peso {TRIMESTRE_ACTUAL}"
    data = [{
        "Acción": f["ticker"],
        col_q1: f["pesoQ1"] if f["pesoQ1"] is not None else float("nan"),
        col_q2: f["pesoQ2"],
        "Tienes": f["tienes"],
        "Tu peso": f["tu_peso"],
        "Movimiento": f["mov"],
    } for f in filas]
    df = pd.DataFrame(data)

    def _color_mov(col):
        out = []
        for v in col:
            if v > 0:
                out.append("background-color:#E3F7EF;color:#1D9E75;font-weight:700")
            elif v < 0:
                out.append("background-color:#FDECEC;color:#A32D2D;font-weight:700")
            else:
                out.append("color:#C3C9D6")
        return out

    def _fmt_mov(v):
        return f"+{int(v)}" if v > 0 else (f"{int(v)}" if v < 0 else "—")

    styler = (df.style
              .format({col_q1: "{:.0f}%", col_q2: "{:.0f}%", "Tu peso": "{:.0f}%",
                       "Movimiento": _fmt_mov}, na_rep="—")
              .apply(_color_mov, subset=["Movimiento"]))
    st.dataframe(styler, hide_index=True, use_container_width=True,
                 height=min(38 * (len(df) + 1), 460))


@st.dialog("💵 Invertir un monto")
def _dialog_invertir(e, inv, fx):
    """Reparte un monto entre las posiciones del experto (acciones ENTERAS) y
    guarda la compra. Para arrancar o agregar dinero a la cartera."""
    eid = e["id"]
    holds = normalizar_holdings(inv["holdings"])
    c1, c2 = st.columns(2)
    monto_mxn = c1.number_input("¿Cuánto invertir? (MXN)", min_value=100.0, value=50000.0,
                                step=500.0, format="%.2f", key=f"inv_m_{eid}")
    tc = c2.number_input("Tipo de cambio", min_value=1.0, value=fx, step=0.01,
                         format="%.4f", key=f"inv_tc_{eid}")
    monto_usd = monto_mxn / tc
    detalle, filas = [], []
    for tk, peso in holds:
        px = get_price_return(tk)["precio"]
        acc = int(monto_usd * peso / 100 // px) if px else 0
        if acc > 0:
            detalle.append({"ticker": tk, "titulos": acc, "precio_usd": px})
        filas.append({"Acción": tk, "Peso": f"{peso:.0f}%",
                      "Precio USD": f"${px:,.2f}" if px else "—", "Acciones": acc,
                      "≈ MXN": f"${acc * (px or 0) * tc:,.0f}"})
    usado = sum(d["titulos"] * d["precio_usd"] for d in detalle)
    st.dataframe(pd.DataFrame(filas), hide_index=True, use_container_width=True,
                 height=min(38 * (len(filas) + 1), 360))
    st.caption(f"Solo **acciones enteras** (SIC). Usarás ≈ ${usado * tc:,.0f} MXN; "
               f"sobrante ≈ ${(monto_usd - usado) * tc:,.0f} MXN. El precio real de cada compra "
               "lo puedes ajustar después, acción por acción.")
    if st.button("💾 Guardar compra", type="primary", use_container_width=True):
        if not detalle:
            st.warning("El monto no alcanza ni para una acción entera. Aumenta el monto.")
        else:
            save_copy_purchase(eid, date.today(), monto_mxn, tc, detalle)
            invalidar_resumen()
            st.success("✅ Compra guardada.")
            st.rerun()


@st.dialog("🔄 Rebalancear a la meta")
def _dialog_rebalanceo(e, inv, fx):
    """TODAS las órdenes (acciones enteras) para igualar los pesos del experto,
    en un solo paso. Ventas → Resultados."""
    eid = e["id"]
    filas, total_val = _plan_copy(eid, inv, fx)
    if total_val <= 0:
        st.info("Aún no tienes posiciones. Usa 'Invertir un monto' primero.")
        return
    ordenes = [(f["ticker"], f["mov"], f["precio"]) for f in filas if f["mov"] != 0]
    if not ordenes:
        st.success("✅ Ya estás alineado con la meta del experto. Nada que rebalancear.")
        return
    st.caption(f"Órdenes para igualar a {inv['nombre']} (acciones enteras · SIC). "
               "**Se ejecutan TODAS al confirmar** — no tienes que picarle varias veces.")
    for tk, mov, px in ordenes:
        verbo, col = ("Comprar", GREEN) if mov > 0 else ("Vender", RED)
        st.markdown(
            f"<div style='padding:6px 0;border-bottom:1px solid #F0F2F8;font-size:13px;'>"
            f"<b style='color:{col};'>{verbo} {abs(mov)}</b> {tk} "
            f"<span style='color:#9DA5B8;'>≈ ${abs(mov) * px * fx:,.0f} MXN</span></div>",
            unsafe_allow_html=True)
    st.caption("Precios de mercado hoy. Las ganancias/pérdidas de las ventas van a Resultados.")
    if st.button("✅ Confirmar todas las órdenes", type="primary", use_container_width=True):
        for tk, mov, px in ordenes:
            if mov < 0:
                registrar_venta_copy(eid, tk, date.today(), -mov, px, fx,
                                     comision_desde_perfil(-mov * px * fx))
            else:
                save_copy_purchase(eid, date.today(), mov * px * fx, fx,
                                   [{"ticker": tk, "titulos": mov, "precio_usd": px}])
        invalidar_resumen()
        st.success("✅ Rebalanceo aplicado (todas las órdenes). Revisa tus posiciones y Resultados.")
        st.rerun()


def _detalle_ticker(eid, tk, held, pos, compras, fx):
    """Dentro del desplegable de un ticker: tus compras (con borrar) + comprar/vender."""
    px_now = get_price_return(tk)["precio"] or (pos["avg_cost_usd"] if pos else 0)
    hay = False
    for cp in compras:
        for d in cp["detalle"]:
            if d["ticker"] != tk:
                continue
            hay = True
            rend = (px_now / d["precio_usd"] - 1) * 100 if d["precio_usd"] else 0
            col = GREEN if rend >= 0 else RED
            cc1, cc2 = st.columns([5, 1])
            cc1.markdown(
                f"<div style='font-size:12.5px;padding-top:6px;'>{str(cp['fecha'])[:10]} · "
                f"{d['titulos']} acc · ${d['precio_usd']:,.2f} USD · "
                f"<b style='color:{col};'>{rend:+.1f}%</b></div>", unsafe_allow_html=True)
            if cc2.button("🗑️", key=f"delc_{eid}_{d['id']}", help="Borrar esta compra"):
                delete_copy_detalle(d["id"])
                invalidar_resumen()
                st.rerun()
    if not hay:
        st.caption("Aún no tienes compras de esta acción.")

    tab_c, tab_v = st.tabs(["➕ Comprar", "➖ Vender"])
    with tab_c:
        with st.form(f"buy_{eid}_{tk}", clear_on_submit=True):
            b1, b2 = st.columns(2)
            f_b = b1.date_input("Fecha", value=date.today(), max_value=date.today(), key=f"bf_{eid}_{tk}")
            n_b = b2.number_input("Acciones (enteras)", min_value=1, value=1, step=1, key=f"bn_{eid}_{tk}")
            p_b = b1.number_input("Precio (USD)", min_value=0.01,
                                  value=round(px_now, 2) if px_now else 1.0, step=0.01,
                                  format="%.2f", key=f"bp_{eid}_{tk}")
            tc_b = b2.number_input("TC (MXN/USD)", min_value=1.0, value=fx, step=0.01,
                                   format="%.4f", key=f"btc_{eid}_{tk}")
            if st.form_submit_button(f"➕ Comprar {tk}", use_container_width=True):
                save_copy_purchase(eid, f_b, int(n_b) * float(p_b) * float(tc_b), float(tc_b),
                                   [{"ticker": tk, "titulos": int(n_b), "precio_usd": float(p_b)}])
                invalidar_resumen()
                st.success(f"✅ Compraste {int(n_b)} de {tk}.")
                st.rerun()
    with tab_v:
        if held <= 0:
            st.caption("No tienes acciones de esta para vender.")
        else:
            with st.form(f"sell_{eid}_{tk}", clear_on_submit=True):
                s1, s2 = st.columns(2)
                f_v = s1.date_input("Fecha", value=date.today(), max_value=date.today(), key=f"sf_{eid}_{tk}")
                n_v = s2.number_input("Acciones", min_value=1, max_value=int(held), value=int(held),
                                      step=1, key=f"sn_{eid}_{tk}")
                p_v = s1.number_input("Precio (USD)", min_value=0.01, value=round(px_now, 2),
                                      step=0.01, format="%.2f", key=f"sp_{eid}_{tk}")
                tc_v = s2.number_input("TC (MXN/USD)", min_value=1.0, value=fx, step=0.01,
                                       format="%.4f", key=f"stc_{eid}_{tk}")
                st.caption("La comisión se calcula con el % de tu perfil.")
                if st.form_submit_button(f"➖ Vender {tk}", type="primary", use_container_width=True):
                    com = comision_desde_perfil(int(n_v) * float(p_v) * float(tc_v))
                    r = registrar_venta_copy(eid, tk, f_v, int(n_v), float(p_v), float(tc_v), com)
                    if r["ok"]:
                        invalidar_resumen()
                        g = r["ganancia"]
                        signo = "ganancia" if g >= 0 else "pérdida"
                        st.success(f"✅ Vendiste {int(n_v)} de {tk} · {signo} ${abs(g):,.2f} MXN → Resultados.")
                        st.rerun()
                    else:
                        st.warning(r["msg"])


def _operar_tickers(e, inv, fx):
    """Lista de las acciones de la cartera; cada una se despliega para operar."""
    eid = e["id"]
    _seccion("Opera cada acción", PURPLE)
    st.caption("Toca una acción para ver tus compras y comprar o vender solo esa.")
    posiciones = {p["ticker"]: p for p in posiciones_copy(eid)}
    orden_tks = [t for t, _ in normalizar_holdings(inv["holdings"])]
    for tk, p in posiciones.items():
        if p["titulos"] > 0 and tk not in orden_tks:
            orden_tks.append(tk)
    compras = load_copy_purchases(eid)
    for tk in orden_tks:
        p = posiciones.get(tk)
        held = p["titulos"] if p else 0
        extra = ""
        if p and held > 0:
            px = get_price_return(tk)["precio"] or p["avg_cost_usd"]
            rp = (px / p["avg_cost_usd"] - 1) * 100 if p["avg_cost_usd"] else 0
            extra = f" · {rp:+.0f}%"
        etiqueta = f"{tk} · {held} acción(es){extra}" if held > 0 else f"{tk} · sin comprar"
        with st.expander(etiqueta):
            _detalle_ticker(eid, tk, held, p, compras, fx)


def _detalle_copy(e: dict):
    eid = e["id"]
    inv = _get_investor(e["investor_id"])
    if not inv:
        st.warning("No se encontró la cartera de este inversionista.")
        return
    fx = get_tipo_cambio_actual()

    mv = movimientos_experto(inv)
    if mv and mv["hay"]:
        st.markdown(
            f"<div style='font-size:12.5px;color:{PURPLE};font-weight:600;'>"
            f"🔔 {inv['nombre']} ajustó su cartera en el reporte {TRIMESTRE_ACTUAL} "
            f"(vs {TRIMESTRE_ANTERIOR}).</div>"
            "<div style='font-size:11px;color:#9DA5B8;margin-bottom:6px;'>"
            "La columna <b>Movimiento</b> te dice qué comprar (verde) o vender (rojo) para seguir replicándolo.</div>",
            unsafe_allow_html=True)

    # 1) Tabla informativa (todo comparado en un solo lugar)
    filas, _total = _plan_copy(eid, inv, fx)
    _tabla_copy(inv, filas)
    st.caption("Pesos 13F representativos/ilustrativos (trimestrales, con retraso). "
               "El 'Movimiento' reparte tu valor actual en acciones enteras (SIC).")

    # 2) Acciones globales (en modales, para no alargar la pantalla)
    a1, a2 = st.columns(2)
    if a1.button("💵 Invertir un monto", key=f"inv_btn_{eid}", use_container_width=True):
        _dialog_invertir(e, inv, fx)
    if a2.button("🔄 Rebalancear a la meta", key=f"reb_btn_{eid}", use_container_width=True,
                 help="Todas las compras/ventas para igualar sus pesos, en un solo paso"):
        _dialog_rebalanceo(e, inv, fx)

    # 3) Operar acción por acción (desplegables compactos)
    _operar_tickers(e, inv, fx)

    # 4) Quitar la cartera
    st.markdown("---")
    if st.button("🗑️ Quitar esta cartera de mis estrategias", key=f"copy_del_{eid}"):
        delete_copy_strategy(eid)
        st.rerun()
