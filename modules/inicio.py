import streamlit as st

from datetime import date

import plotly.graph_objects as go

from utils import nav
from utils.db_utils import (get_perfil, save_perfil, get_modo, load_strategies,
                            load_historial_realizado, set_comision_pct, set_meta_anual,
                            set_meta_monto, guardar_snapshot_patrimonio, leer_historial_patrimonio)
from utils.resumen_utils import resumen_global, invalidar_resumen, invertido_en_anio
import streamlit.components.v1 as components
from modules.resultados_export import export_excel, export_pdf, exportar_json, cartera_payload
from utils.revisor_utils import generar_html
from utils.demo_seed import generar_datos_demo
from modules.bienvenida import cerrar_sesion
from utils.seguridad import esc

PURPLE = "#6C63FF"
GREEN = "#1D9E75"
RED = "#A32D2D"

# Versión visible para confirmar qué código está corriendo en la nube.
# Súbela cada vez que despliegues algo que quieras verificar en el celular.
APP_VERSION = "VestPlan · v6"

ESLOGAN = "Invierte con un plan. No con emociones."

# Frases que refuerzan la filosofía de VestPlan (una distinta por cada apertura).
FRASES_FILOSOFIA = [
    "Invierte con un plan. No con emociones.",
    "La disciplina vence a la improvisación.",
    "Las mejores inversiones empiezan con una estrategia.",
    "El tiempo recompensa la constancia.",
    "No adivines el mercado. Sigue tu plan.",
    "La paciencia también genera rendimientos.",
    "Una estrategia vale más que una corazonada.",
]


def _frase_filosofia():
    """Una frase por apertura de la app (fija durante la sesión, cambia al reabrir)."""
    import random
    if "_frase_idx" not in st.session_state:
        st.session_state["_frase_idx"] = random.randrange(len(FRASES_FILOSOFIA))
    return FRASES_FILOSOFIA[st.session_state["_frase_idx"]]

TARJETAS = [
    {"icono": "📊", "titulo": "DCA", "destino": nav.DCA,
     "desc": "Compras recurrentes automáticas. Invierte poco a poco y reduce el riesgo de elegir el mal momento."},
    {"icono": "💰", "titulo": "Dividendos", "destino": nav.DIV,
     "desc": "Acciones que reparten dividendos. Analiza su historial y sigue tus ingresos pasivos."},
    {"icono": "🎯", "titulo": "Por Objetivos", "destino": nav.OBJ,
     "desc": "Análisis técnico. Define precio de entrada y de salida y sigue tu meta de trading."},
    {"icono": "🏢", "titulo": "FIBRAs", "destino": nav.FIB,
     "desc": "Bienes raíces mexicanos. Compara FIBRAs y su rendimiento por distribuciones."},
    {"icono": "👥", "titulo": "Copy Trading", "destino": nav.COPY,
     "desc": "Replica las carteras de los grandes inversionistas del mundo."},
]

MODULO_ICON = {"DCA": "📊", "Dividendos": "💰", "Por Objetivos": "🎯",
               "FIBRAs": "🏢", "Copy Trading": "👥"}
# Gama de color por estrategia (paleta VestPlan)
MODULO_COLOR = {"DCA": "#22C55E",          # verde
                "Por Objetivos": "#8B5CF6",  # morado
                "Dividendos": "#F4B400",     # dorado
                "FIBRAs": "#2563EB",         # azul
                "Copy Trading": "#F97316"}   # naranja
MODULO_TAG = {"DCA": "Compras recurrentes", "Dividendos": "Ingresos pasivos",
              "Por Objetivos": "Trading por metas", "FIBRAs": "Bienes raíces",
              "Copy Trading": "Réplica de expertos"}
MODULO_DEST = {"DCA": nav.DCA, "Dividendos": nav.DIV, "Por Objetivos": nav.OBJ,
               "FIBRAs": nav.FIB, "Copy Trading": nav.COPY}

# Explicaciones amplias para gente que no sabe de finanzas (modal "Detalles")
EXPLICACIONES = {
    "DCA": {
        "parrafos": [
            "El <b>DCA</b> (compras promedio) consiste en invertir la misma cantidad cada cierto tiempo —por ejemplo cada mes— sin importar si el precio subió o bajó ese día.",
            "Como compras siempre, a veces te toca caro y a veces barato, y con el tiempo tu precio promedio se suaviza. Así te quitas el estrés de adivinar cuál es el 'mejor momento' para entrar.",
            "<b>Qué esperar:</b> es una estrategia tranquila y de largo plazo. No te hará rico de la noche a la mañana, pero reduce mucho el riesgo de equivocarte en el momento de compra.",
        ],
        "riesgo": "Bajo", "horizonte": "Largo plazo", "ideal": "Principiantes y constancia",
    },
    "Dividendos": {
        "parrafos": [
            "Algunas empresas reparten una parte de sus ganancias a quienes tienen sus acciones; eso es un <b>dividendo</b>, como una 'renta' por ser dueño de un pedacito de la empresa.",
            "Esta estrategia busca acciones que pagan dividendos de forma constante (normalmente cada trimestre) para generar <b>ingresos pasivos</b> que llegan periódicamente.",
            "<b>Qué esperar:</b> ingresos que caen poco a poco más que grandes saltos de precio. Es popular para quienes quieren un flujo estable y reinvertir esos pagos.",
        ],
        "riesgo": "Medio", "horizonte": "Medio-largo", "ideal": "Ingresos pasivos",
    },
    "Por Objetivos": {
        "parrafos": [
            "Defines un precio al que quieres <b>comprar</b> (entrada) y un precio al que quieres <b>vender</b> (tu meta), y sigues si el mercado llega a esos niveles.",
            "Se apoya en análisis técnico: observar el comportamiento del precio para tomar decisiones de compra y venta más activas.",
            "<b>Qué esperar:</b> más movimiento y atención de tu parte. Puede dar ganancias más rápidas, pero también implica <b>más riesgo</b> y estar pendiente del mercado.",
        ],
        "riesgo": "Alto", "horizonte": "Corto-medio", "ideal": "Inversores activos",
    },
    "FIBRAs": {
        "parrafos": [
            "Las <b>FIBRAs</b> son una forma de invertir en bienes raíces (centros comerciales, oficinas, naves industriales) comprando en la bolsa, sin tener que comprar una propiedad tú mismo.",
            "Por ley reparten la mayor parte de sus rentas a los inversionistas, así que suelen pagar <b>distribuciones</b> periódicas, parecido a los dividendos.",
            "<b>Qué esperar:</b> ingresos por rentas y exposición a bienes raíces mexicanos. Su precio puede moverse con las tasas de interés.",
        ],
        "riesgo": "Medio", "horizonte": "Medio-largo", "ideal": "Ingresos + bienes raíces",
    },
    "Copy Trading": {
        "parrafos": [
            "El <b>Copy Trading</b> consiste en replicar las carteras de grandes inversionistas: lo que ellos tienen, lo armas tú en proporción a tu dinero.",
            "Aprovechas las decisiones de gente con experiencia, sin tener que analizar todo por tu cuenta desde cero.",
            "<b>Qué esperar:</b> seguir el estilo de alguien más. Recuerda que los rendimientos pasados no garantizan los futuros, y tú decides cuánto seguir.",
        ],
        "riesgo": "Variable", "horizonte": "Medio-largo", "ideal": "Aprender de expertos",
    },
}
_RIESGO_COLOR = {"Bajo": "#1D9E75", "Medio": "#EF9F27", "Alto": "#E24B4A", "Variable": "#888780"}


# ─── Inicio ──────────────────────────────────────────────────────────────────
def render_inicio():
    perfil = get_perfil()
    nombre = esc(perfil.get("nombre") or "Inversionista")
    res = resumen_global()
    rend = res["total_rend_pct"]
    items = res["items"]

    # Guarda el valor del portafolio de hoy (1 vez al día) para el histórico.
    if items and st.session_state.get("_snap_dia") != date.today().isoformat():
        guardar_snapshot_patrimonio(res["total_invertido"], res["total_valor"])
        st.session_state["_snap_dia"] = date.today().isoformat()
    hist = leer_historial_patrimonio()

    vencidas = [p for p in _proximas_compras() if p["delta"] <= 0]

    # ── Header: marca + campanita (pendientes) + avatar (perfil) ──
    with st.container(key="topbar"):
        hL, hB, hA = st.columns([6, 1.1, 1.1])
        hL.markdown(f"""
            <div style="font-size:22px;font-weight:700;letter-spacing:-.3px;color:#1a1a2e;line-height:1.05;">
                <span style="color:{PURPLE};">Vest</span>Plan</div>
            <div style="font-size:11px;color:#9DA5B8;margin-top:3px;">
                <span style="color:{GREEN};">●</span> Sincronizado · precios al momento</div>
        """, unsafe_allow_html=True)
        if hB.button(f"🔔 {len(vencidas)}" if vencidas else "🔔", key="tb_bell", help="Pendientes"):
            nav.goto(nav.AGENDA)
        inicial = (perfil.get("nombre") or "U").strip()[:1].upper() or "U"
        if hA.button(inicial, key="tb_perfil", help="Tu perfil"):
            nav.goto(nav.PERFIL)

    st.markdown(f"""
        <div style="font-size:22px;font-weight:700;color:#1a1a2e;margin:10px 0 2px;">Hola, {nombre} 👋</div>
        <div style="font-size:11px;color:#9DA5B8;margin-bottom:12px;font-style:italic;">{esc(ESLOGAN)} · {APP_VERSION}</div>
    """, unsafe_allow_html=True)

    if get_modo() == "demo":
        st.markdown("""
        <div style="background:#FFF6E5;border:1px solid #F2D9A0;border-radius:10px;padding:8px 12px;margin-bottom:10px;">
            <b style="color:#C77F00;font-size:12px;">🧪 Modo demostración</b>
            <span style="color:#9DA5B8;font-size:11px;"> — datos sintéticos.</span>
        </div>
        """, unsafe_allow_html=True)

    # ── Mensaje del copiloto (frase distinta por apertura + estado real) ──
    _mensaje_estado(res, items, vencidas)

    # ── Tarjeta de patrimonio (oscura, con gráfica de evolución y KPIs) ──
    _tarjeta_patrimonio(res, rend, hist)

    # ── Pendientes: SOLO compras de HOY o vencidas (nunca a futuro) ──
    if vencidas:
        p = vencidas[0]  # la más urgente
        estado, color = _estado_compra_txt(p["delta"])
        extra = f" · +{len(vencidas) - 1} más" if len(vencidas) > 1 else ""
        st.markdown("<div style='font-size:15px;font-weight:600;color:#1a1a2e;margin:2px 0 6px;'>Pendientes</div>",
                    unsafe_allow_html=True)
        with st.container(border=True):
            st.markdown(
                f"<div style='font-size:12px;color:#9DA5B8;'>Compra pendiente{extra}</div>"
                f"<div style='font-size:14px;'><b style='color:#1a1a2e;'>{esc(p['ticker'])}</b> "
                f"<span style='color:#9DA5B8;font-size:12px;'>· {p['fecha'].strftime('%d/%m/%Y')}</span> "
                f"<b style='color:{color};font-size:12.5px;'> {estado}</b></div>",
                unsafe_allow_html=True)

    # ── Meta anual de inversión (monto) ──
    _tarjeta_meta_anual(perfil)

    # ── Mis estrategias (top 3 + ver todas) ──
    st.markdown(
        "<div style='font-weight:600;font-size:15px;color:#1a1a2e;margin:2px 0 8px;'>Mis estrategias</div>",
        unsafe_allow_html=True)
    if not items:
        st.info("Aún no tienes inversiones. Abre una estrategia y registra tu primera compra.")
        if st.button("Explorar estrategias →", type="primary", use_container_width=True, key="ini_explorar"):
            nav.goto(nav.ESTRATEGIAS)
    else:
        activas = _estrategias_activas(items)
        for i, f in enumerate(activas[:3]):
            _fila_estrategia_activa(f, key=f"act_{i}")
        if len(activas) > 3:
            with st.expander(f"Ver todas mis estrategias ({len(activas)})"):
                for i, f in enumerate(activas[3:], start=3):
                    _fila_estrategia_activa(f, key=f"act_{i}")


def _mensaje_estado(res, items, vencidas):
    """Copiloto de VestPlan: primero el ESTADO del plan, luego (opcional) el detalle.
    La filosofía va antes que los números. Cambia según la situación real."""
    frase = _frase_filosofia()
    if vencidas:
        # Hay algo que hacer HOY: la app pide una acción concreta.
        dot = "#EF9F27"
        titulo = "Hoy tu plan necesita una acción."
        mas = f" (+{len(vencidas) - 1} más)" if len(vencidas) > 1 else ""
        detalle = f"Comprar <b style='color:#1a1a2e;'>{esc(vencidas[0]['ticker'])}</b>.{mas}"
    elif not items:
        dot = PURPLE
        titulo = "Empieza tu plan hoy."
        detalle = esc(frase)
    else:
        # Todo en orden: reforzamos disciplina + frase de filosofía (rota por apertura).
        dot = GREEN
        titulo = "Todo va conforme a tu plan."
        activas = _estrategias_activas(items)
        mejor = max(activas, key=lambda x: x["rend_pct"]) if activas else None
        if mejor and mejor["rend_pct"] > 0 and st.session_state.get("_frase_idx", 0) % 2 == 0:
            detalle = (f"🏆 Tu mejor estrategia: <b style='color:#1a1a2e;'>{esc(mejor['modulo'])}</b> "
                       f"({mejor['rend_pct']:+.1f}%)")
        else:
            detalle = esc(frase)
    st.markdown(f"""
    <div style="background:#fff;border:0.5px solid #E8ECF4;border-radius:12px;padding:12px 14px;
                margin-bottom:14px;box-shadow:0 1px 3px rgba(16,24,40,.04);
                display:flex;align-items:center;justify-content:space-between;gap:10px;">
        <div>
            <div style="font-size:13.5px;color:#1a1a2e;"><span style="color:{dot};">●</span> <b>{titulo}</b></div>
            <div style="font-size:11px;color:#9DA5B8;margin-top:3px;">{detalle}</div>
        </div>
        <div style="font-size:18px;color:#C3C9D6;">›</div>
    </div>
    """, unsafe_allow_html=True)


def _kpi_chip(label, valor, color):
    return (f"<div style='background:rgba(255,255,255,.08);border-radius:12px;padding:9px 8px;text-align:center;'>"
            f"<div style='font-size:10px;color:rgba(255,255,255,.55);'>{label}</div>"
            f"<div style='font-size:13.5px;font-weight:700;color:{color};margin-top:2px;'>{valor}</div></div>")


def _tarjeta_patrimonio(res, rend, hist):
    """Tarjeta oscura con el patrimonio, selector de periodo, gráfica y KPIs."""
    pill_bg, pill_tx = ("#E1F5EE", GREEN) if rend >= 0 else ("#FCEBEB", RED)
    gan_hoy = (hist[-1]["valor"] - hist[-2]["valor"]) if len(hist) >= 2 else None
    st.session_state.setdefault("ini_periodo", 365)
    with st.container(key="patricard"):
        st.markdown(f"""
        <div style="font-size:12px;color:rgba(255,255,255,.6);">Tu patrimonio</div>
        <div style="font-size:28px;font-weight:700;color:#fff;margin:2px 0 6px;">${res['total_valor']:,.2f} MXN</div>
        <div><span style="background:{pill_bg};color:{pill_tx};font-size:12px;font-weight:600;padding:3px 10px;border-radius:20px;">{rend:+.2f}% total</span>
        <span style="color:rgba(255,255,255,.55);font-size:12px;margin-left:8px;">Invertido ${res['total_invertido']:,.0f}</span></div>
        """, unsafe_allow_html=True)
        pc = st.columns(5)
        for i, (lbl, dias) in enumerate([("1M", 30), ("3M", 90), ("6M", 180), ("1A", 365), ("Todo", 99999)]):
            if pc[i].button(lbl, key=f"per_{lbl}", use_container_width=True):
                st.session_state.ini_periodo = dias
        fig = _grafica_patrimonio(hist, st.session_state.ini_periodo)
        if fig is not None:
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        else:
            st.markdown(
                "<div style='color:rgba(255,255,255,.5);font-size:12px;padding:16px 0;text-align:center;'>"
                "📈 Tu evolución se empieza a registrar hoy. Vuelve mañana para ver tu gráfica crecer.</div>",
                unsafe_allow_html=True)
        gh = f"${gan_hoy:+,.2f}" if gan_hoy is not None else "—"
        gh_col = (GREEN if gan_hoy >= 0 else RED) if gan_hoy is not None else "rgba(255,255,255,.85)"
        k = st.columns(3)
        k[0].markdown(_kpi_chip("Invertido total", f"${res['total_invertido']:,.0f}", "rgba(255,255,255,.9)"), unsafe_allow_html=True)
        k[1].markdown(_kpi_chip("Ganancia hoy", gh, gh_col), unsafe_allow_html=True)
        k[2].markdown(_kpi_chip("Rendimiento", f"{rend:+.2f}%", GREEN if rend >= 0 else RED), unsafe_allow_html=True)


def _grafica_patrimonio(hist, dias):
    """Línea blanca de la evolución del patrimonio (o None si aún no hay suficientes datos)."""
    if len(hist) < 2:
        return None
    hoy = date.today()
    puntos = [h for h in hist if (hoy - date.fromisoformat(h["fecha"])).days <= dias]
    if len(puntos) < 2:
        puntos = hist  # si el periodo elegido no alcanza, muestra todo lo que hay
    xs = [h["fecha"] for h in puntos]
    ys = [h["valor"] for h in puntos]
    fig = go.Figure(go.Scatter(
        x=xs, y=ys, mode="lines", line=dict(color="#fff", width=2.5),
        fill="tozeroy", fillcolor="rgba(255,255,255,0.12)",
        hovertemplate="%{x|%d %b}<br>$%{y:,.0f} MXN<extra></extra>"))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=6, b=0), height=150, dragmode=False, showlegend=False,
        xaxis=dict(showgrid=False, showline=False, fixedrange=True,
                   tickfont=dict(size=10, color="rgba(255,255,255,.6)")),
        yaxis=dict(visible=False, fixedrange=True))
    return fig


def _tarjeta_meta_anual(perfil):
    """Barra de progreso de la meta anual de INVERSIÓN (cuánto has invertido este
    año vs cuánto te propusiste). Premia la disciplina, no la suerte del mercado."""
    anio = date.today().year
    meta = float(perfil.get("meta_monto") or 0)
    if meta <= 0:
        # Aún no define su meta → invitación a ponerla en Perfil.
        st.markdown("""
        <div style="background:#F7F6FF;border:1px dashed #D4CFFF;border-radius:14px;padding:14px 16px;margin:2px 0 16px;">
            <div style="font-size:13px;font-weight:600;color:#1a1a2e;">🎯 Ponte una meta anual</div>
            <div style="font-size:11px;color:#9DA5B8;margin-top:3px;">
                Define cuánto quieres invertir este año en <b>Perfil</b> y sigue tu avance aquí.</div>
        </div>
        """, unsafe_allow_html=True)
        return
    invertido = invertido_en_anio(anio)
    pct = min(100.0, (invertido / meta * 100) if meta else 0)
    falta = max(0.0, meta - invertido)
    st.markdown(f"""
    <div style="background:#fff;border:0.5px solid #E8ECF4;border-radius:14px;padding:14px 16px;margin:2px 0 16px;">
        <div style="display:flex;justify-content:space-between;align-items:baseline;">
            <div style="font-size:13px;font-weight:600;color:#1a1a2e;">Tu meta anual {anio}</div>
            <div style="font-size:16px;font-weight:700;color:{PURPLE};">${meta:,.0f}</div>
        </div>
        <div style="font-size:11px;color:#9DA5B8;margin:6px 0;">
            Llevas ${invertido:,.0f} ({pct:.0f}%) · te faltan ${falta:,.0f} para tu meta</div>
        <div style="background:#EDEBFB;border-radius:20px;height:8px;overflow:hidden;">
            <div style="background:{PURPLE};height:8px;width:{pct:.0f}%;border-radius:20px;"></div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def _estrategias_activas(items):
    """Agrupa las posiciones por estrategia (módulo) con su total y rendimiento."""
    grupos = {}
    for it in items:
        g = grupos.setdefault(it["modulo"], {"inv": 0.0, "val": 0.0})
        g["inv"] += it["invertido"]
        g["val"] += it["valor"]
    filas = []
    for modulo, g in grupos.items():
        rend = (g["val"] / g["inv"] - 1) * 100 if g["inv"] else 0.0
        filas.append({"modulo": modulo, "valor": g["val"], "rend_pct": rend})
    filas.sort(key=lambda x: x["valor"], reverse=True)
    return filas


def _fila_estrategia_activa(f, key):
    """Tarjeta por estrategia activa: TODO el recuadro es clickable y lleva a
    'Mis estrategias' de ese módulo (blanco de toque grande, estilo neobank)."""
    rc = GREEN if f["rend_pct"] >= 0 else RED
    icono = MODULO_ICON.get(f["modulo"], "📊")
    tag = MODULO_TAG.get(f["modulo"], "")
    col = MODULO_COLOR.get(f["modulo"], PURPLE)
    destino = MODULO_DEST.get(f["modulo"], nav.ESTRATEGIAS)
    with st.container(border=True, key=f"card_{key}"):
        st.markdown(
            "<div style='display:flex;align-items:center;justify-content:space-between;'>"
            "<div style='display:flex;align-items:center;gap:10px;'>"
            f"<div style='width:38px;height:38px;border-radius:10px;background:{col}1A;color:{col};"
            f"display:flex;align-items:center;justify-content:center;font-size:18px;'>{icono}</div>"
            "<div>"
            f"<div style='font-size:15px;font-weight:600;color:#1a1a2e;'>{esc(f['modulo'])}</div>"
            f"<div style='font-size:11px;color:#9DA5B8;margin-top:1px;'>{esc(tag)}</div>"
            "</div>"
            "</div>"
            "<div style='text-align:right;display:flex;align-items:center;gap:8px;'>"
            "<div>"
            f"<div style='font-size:14px;font-weight:600;color:#1a1a2e;'>${f['valor']:,.0f}</div>"
            f"<div style='font-size:12px;font-weight:600;color:{rc};'>{f['rend_pct']:+.1f}%</div>"
            "</div>"
            "<div style='font-size:18px;color:#C3C9D6;'>›</div>"
            "</div>"
            "</div>",
            unsafe_allow_html=True)
        # Botón transparente que cubre toda la tarjeta (ver CSS .st-key-card_).
        if st.button("Abrir", key=f"go_{key}", use_container_width=True):
            nav.goto(destino)


def _quick_tile(col, icono, label, bg, fg, destino, key):
    with col:
        st.markdown(
            f"<div class='qa-tile' style='background:{bg};color:{fg};'>{icono}</div>",
            unsafe_allow_html=True)
        if st.button(label, key=key, use_container_width=True):
            if destino == "_analizar":
                # Atajo: ir a Resultados y generar el diagnóstico automáticamente
                st.session_state["_auto_analizar"] = True
                nav.goto(nav.RESULTADOS)
            else:
                nav.goto(destino)


# ─── Hub de estrategias ──────────────────────────────────────────────────────
def render_estrategias():
    st.markdown("""
    <div style="margin-bottom:14px;">
        <h2 style="font-size:20px;font-weight:600;color:#1a1a2e;margin:0;">Estrategias</h2>
        <p style="font-size:12px;color:#9DA5B8;margin:4px 0 0;">Elige una para empezar o seguir invirtiendo</p>
    </div>
    """, unsafe_allow_html=True)
    # Recomendación según el perfil (estrella amarilla en las que encajan)
    perfil = get_perfil()
    recs = _recomendar(perfil.get("perfil_riesgo"), perfil.get("objetivo")) if perfil.get("perfil_riesgo") else []
    rec_top = recs[0][0] if recs else None
    rec_destinos = {r[0] for r in recs}
    for i, t in enumerate(TARJETAS):
        if t["destino"] == rec_top:
            badge = "⭐ Más recomendada para tu perfil"
        elif t["destino"] in rec_destinos:
            badge = "⭐ Recomendada para tu perfil"
        else:
            badge = ""
        _fila_estrategia(t, key=f"hub_{i}", badge=badge)


def _fila_estrategia(t, key, badge=""):
    """Una estrategia como fila tipo neobank: ícono + nombre + descripción + detalles/abrir."""
    with st.container(border=True):
        if badge:
            st.markdown(
                f"<div style='display:inline-block;font-size:11px;font-weight:600;color:#C77F00;"
                f"background:#FFF6E0;border:0.5px solid #F2D9A0;border-radius:6px;padding:2px 8px;"
                f"margin-bottom:6px;'>{badge}</div>", unsafe_allow_html=True)
        c1, c2, c3 = st.columns([3.2, 1.4, 1.4])
        c1.markdown(
            f"<div style='font-size:20px;'>{t['icono']} "
            f"<span style='font-size:14px;font-weight:600;color:#1a1a2e;vertical-align:3px;'>{t['titulo']}</span></div>"
            f"<div style='font-size:11.5px;color:#9DA5B8;line-height:1.35;margin-top:4px;'>{t['desc']}</div>",
            unsafe_allow_html=True)
        c2.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)
        if c2.button("Detalles", key=f"det_{key}", use_container_width=True):
            _mostrar_detalles(t)
        c3.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)
        if c3.button("Abrir →", key=key, type="primary", use_container_width=True):
            nav.goto(t["destino"])


def _facts_html(info: dict) -> str:
    rc = _RIESGO_COLOR.get(info["riesgo"], "#888780")
    def box(label, valor, color="#1a1a2e"):
        return (f"<div style='flex:1;min-width:130px;background:#F8F9FC;border:0.5px solid #E8ECF4;"
                f"border-radius:10px;padding:10px 12px;'>"
                f"<div style='font-size:10px;color:#9DA5B8;text-transform:uppercase;letter-spacing:.05em;'>{label}</div>"
                f"<div style='font-size:13px;font-weight:600;color:{color};'>{valor}</div></div>")
    return ("<div style='display:flex;gap:8px;flex-wrap:wrap;margin-top:8px;'>"
            + box("Riesgo", info["riesgo"], rc)
            + box("Horizonte", info["horizonte"])
            + box("Ideal para", info["ideal"])
            + "</div>")


def _mostrar_detalles(t):
    info = EXPLICACIONES.get(t["titulo"])
    if not info:
        return

    @st.dialog(f"{t['icono']}  {t['titulo']}", width="large")
    def _dlg():
        for p in info["parrafos"]:
            st.markdown(
                f"<p style='font-size:14px;color:#4A5066;line-height:1.65;margin:0 0 12px;'>{p}</p>",
                unsafe_allow_html=True)
        st.markdown(_facts_html(info), unsafe_allow_html=True)
        st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
        if st.button(f"Abrir {t['titulo']} →", type="primary", use_container_width=True,
                     key=f"dlg_open_{t['titulo']}"):
            nav.goto(t["destino"])
        st.caption("Herramienta educativa, no es asesoría financiera.")

    _dlg()


# ─── ¿Qué me conviene? (recomendación por perfil) ────────────────────────────
_ESTRATEGIAS_INFO = {
    "DCA": (nav.DCA, "📊", "DCA",
            "Invertir la misma cantidad cada mes, sin estrés. La base más tranquila para crecer a largo plazo."),
    "DIV": (nav.DIV, "💰", "Dividendos",
            "Acciones que te pagan una 'renta' periódica. Buenas para ingresos estables."),
    "FIB": (nav.FIB, "🏢", "FIBRAs",
            "Bienes raíces en la bolsa que reparten rentas. En pesos y con ingresos periódicos."),
    "OBJ": (nav.OBJ, "🎯", "Por Objetivos",
            "Defines a qué precio comprar y vender. Más activo y con más riesgo."),
}


def _recomendar(riesgo, objetivo):
    r = riesgo or "Moderado"
    o = objetivo or ""
    if r == "Conservador":
        orden = ["DIV", "FIB", "DCA"]
    elif r == "Agresivo":
        orden = ["OBJ", "DCA", "DIV"]
    else:  # Moderado
        orden = ["DCA", "DIV", "FIB"]
    if "Ingresos" in o:
        orden = ["DIV", "FIB"] + [x for x in orden if x not in ("DIV", "FIB")]
    elif "Especulaci" in o:
        orden = ["OBJ"] + [x for x in orden if x != "OBJ"]
    elif any(k in o for k in ("Crecimiento", "Retiro", "Ahorro")):
        orden = ["DCA"] + [x for x in orden if x != "DCA"]
    vistos, res = [], []
    for k in orden:
        if k not in vistos:
            vistos.append(k)
            res.append(_ESTRATEGIAS_INFO[k])
    return res[:2]


# ─── Agenda (próximas compras + recordatorios) ───────────────────────────────
def _proximas_compras():
    """Próxima compra pendiente de cada estrategia DCA, ordenadas por urgencia."""
    from modules.dca import generar_fechas_dca, _parse_fecha, FRECUENCIAS
    from utils.db_utils import load_purchases
    filas = []
    for e in load_strategies():
        f_ini = _parse_fecha(e.get("fecha_inicio"))
        f_fin = _parse_fecha(e.get("fecha_fin"))
        frec = e.get("frecuencia")
        if not (f_ini and f_fin and frec in FRECUENCIAS):
            continue
        plan = generar_fechas_dca(f_ini, f_fin, frec)
        hechas = len(load_purchases(e["id"]))
        if hechas >= len(plan):
            continue  # estrategia completada
        prox = plan[hechas]
        filas.append({"ticker": e["ticker"], "frecuencia": frec, "fecha": prox,
                      "delta": (prox - date.today()).days, "titulos": int(e.get("titulos") or 0)})
    filas.sort(key=lambda x: x["delta"])
    return filas


def _estado_compra_txt(delta):
    if delta < 0:
        return f"⚠️ {-delta} día(s) de retraso", RED
    if delta == 0:
        return "📌 ¡Es hoy, es hoy!", "#C77F00"
    if delta <= 3:
        return f"⏳ En {delta} día(s)", "#C77F00"
    return f"⏳ En {delta} día(s)", PURPLE


def render_agenda():
    st.markdown("""
    <div style="margin-bottom:12px;">
        <h2 style="font-size:20px;font-weight:600;color:#1a1a2e;margin:0;">📅 Agenda</h2>
        <p style="font-size:12px;color:#9DA5B8;margin:4px 0 0;">Tus próximas compras programadas, con fecha exacta</p>
    </div>
    """, unsafe_allow_html=True)

    proximas = _proximas_compras()
    if not proximas:
        st.info("No tienes compras programadas. Crea una estrategia **DCA** para armar tu plan de compras.")
        if st.button("Crear una estrategia DCA →", type="primary", use_container_width=True, key="ag_nueva"):
            nav.goto(nav.DCA)
    else:
        for p in proximas:
            estado, color = _estado_compra_txt(p["delta"])
            with st.container(border=True):
                c1, c2 = st.columns([3, 2])
                c1.markdown(
                    f"<div style='font-size:15px;'>📈 <b style='color:#1a1a2e;'>{esc(p['ticker'])}</b> "
                    f"<span style='color:#9DA5B8;font-size:12px;'>· {p['titulos']} título(s) · {p['frecuencia']}</span></div>"
                    f"<div style='font-size:12px;color:#9DA5B8;margin-top:2px;'>Compra programada: "
                    f"<b style='color:#1a1a2e;'>{p['fecha'].strftime('%d/%m/%Y')}</b></div>",
                    unsafe_allow_html=True)
                c2.markdown(
                    f"<div style='text-align:right;font-size:13px;font-weight:600;color:{color};"
                    f"margin-top:10px;'>{estado}</div>",
                    unsafe_allow_html=True)

    # Recordatorios en Google Calendar (informativo)
    con_recordatorio = [e["ticker"] for e in load_strategies() if e.get("cal_creado")]
    if con_recordatorio:
        st.caption(f"🔔 Con recordatorio en Google Calendar: {', '.join(con_recordatorio)}")
    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
    st.link_button("Abrir Google Calendar", "https://calendar.google.com",
                   use_container_width=True)


# ─── Perfil (incluye modo de datos y cerrar sesión) ──────────────────────────
def render_perfil():
    perfil = get_perfil()
    st.markdown("""
    <div style="margin-bottom:12px;">
        <h2 style="font-size:20px;font-weight:600;color:#1a1a2e;margin:0;">👤 Mi perfil</h2>
        <p style="font-size:12px;color:#9DA5B8;margin:4px 0 0;">Tus datos personalizan las sugerencias</p>
    </div>
    """, unsafe_allow_html=True)

    with st.form("form_perfil"):
        nombre = st.text_input("Nombre", value=perfil.get("nombre", ""))
        c1, c2 = st.columns(2)
        edad = c1.number_input("Edad", min_value=18, max_value=100,
                               value=int(perfil.get("edad") or 30), step=1)
        horizonte = c2.number_input("Horizonte (años)", min_value=1, max_value=50,
                                    value=int(perfil.get("horizonte_anios") or 10), step=1)
        ingreso = st.number_input("Ingreso mensual (MXN)", min_value=0.0,
                                  value=float(perfil.get("ingreso_mensual") or 0),
                                  step=1000.0, format="%.2f")
        objetivo = st.selectbox("Objetivo principal",
                                ["Crecimiento de patrimonio", "Ingresos pasivos", "Retiro",
                                 "Ahorro de corto plazo", "Especulación / trading"],
                                index=_idx(["Crecimiento de patrimonio", "Ingresos pasivos", "Retiro",
                                            "Ahorro de corto plazo", "Especulación / trading"],
                                           perfil.get("objetivo")))
        riesgo = st.selectbox("Perfil de riesgo", ["Conservador", "Moderado", "Agresivo"],
                              index=_idx(["Conservador", "Moderado", "Agresivo"], perfil.get("perfil_riesgo")))
        comision = st.number_input(
            "Comisión de tu casa de bolsa (%)", min_value=0.0, max_value=2.0,
            value=float(perfil.get("comision_pct") if perfil.get("comision_pct") is not None else 0.25),
            step=0.05, format="%.2f",
            help="El % que te cobra tu broker (ej. GBM ≈ 0.25%) por cada compra o venta. La app la "
                 "calcula sola en cada operación (con IVA). Si la cambias, aplica de aquí en adelante; "
                 "no recalcula lo que ya registraste.")
        meta_monto = st.number_input(
            "Meta anual de inversión (MXN) — ¿cuánto buscas invertir al año?",
            min_value=0.0, value=float(perfil.get("meta_monto") or 0),
            step=1000.0, format="%.0f",
            help="Cuánto dinero quieres invertir a lo largo del año. La barra de 'Meta anual' "
                 "en Inicio se llena con lo que ya llevas invertido este año. Déjalo en 0 si aún "
                 "no quieres fijar una meta.")
        if st.form_submit_button("💾 Guardar perfil", type="primary"):
            save_perfil({"nombre": nombre, "edad": edad, "ingreso_mensual": ingreso,
                         "objetivo": objetivo, "perfil_riesgo": riesgo, "horizonte_anios": horizonte})
            set_comision_pct(comision)
            set_meta_monto(meta_monto)
            st.success("✅ Perfil actualizado.")
            st.rerun()

    # ── Modo de datos ──
    st.markdown("---")
    st.markdown("**Modo de datos**")
    modo_actual = st.session_state.get("_modo_actual", "real")
    modo = st.radio("", ["🔵 Real", "🧪 Demostración"],
                    index=0 if modo_actual == "real" else 1,
                    horizontal=True, label_visibility="collapsed")
    modo_val = "demo" if "Demo" in modo else "real"
    if modo_val != modo_actual:
        st.session_state["_modo_actual"] = modo_val
        invalidar_resumen()
        st.rerun()
    if modo_val == "demo":
        st.caption("🧪 Datos sintéticos — tu información real está protegida.")
        if st.button("🔄 Generar datos sintéticos", use_container_width=True):
            generar_datos_demo()
            invalidar_resumen()
            st.success("✅ Datos sintéticos generados.")
            st.rerun()

    # ── Cerrar sesión ──
    st.markdown("---")
    if st.button("🚪 Cerrar sesión", use_container_width=True):
        cerrar_sesion()


def _chip(label, value):
    return (f'<div style="background:#fff;border:0.5px solid #E8ECF4;border-radius:8px;padding:6px 12px;">'
            f'<div style="font-size:10px;color:#9DA5B8;text-transform:uppercase;letter-spacing:.05em;">{label}</div>'
            f'<div style="font-size:13px;font-weight:600;color:#1a1a2e;">{value}</div></div>')


def _idx(opciones, valor):
    try:
        return opciones.index(valor)
    except (ValueError, TypeError):
        return 0


# ─── Mis Resultados ──────────────────────────────────────────────────────────
def render_resultados():
    st.markdown("""
    <div style="margin-bottom:16px;">
        <h2 style="font-size:20px;font-weight:600;color:#1a1a2e;margin:0;">📈 Mis Resultados</h2>
        <p style="font-size:12px;color:#9DA5B8;margin:4px 0 0;">Resumen de todas tus estrategias — inversión y rendimiento en pesos</p>
    </div>
    """, unsafe_allow_html=True)

    if st.button("📥 Cargar Excel — importar tus compras y ventas", key="res_importar", use_container_width=True):
        nav.goto(nav.IMPORTAR)

    res = resumen_global()
    items = res["items"]
    perfil = get_perfil()

    tab_pos, tab_real = st.tabs(["📊 Posiciones actuales", "🏁 Rendimiento realizado"])

    with tab_pos:
        if not items:
            st.info("Aún no tienes posiciones. Registra una compra en cualquier estrategia.")
        else:
            rend = res["total_rend_pct"]
            gan = res["total_valor"] - res["total_invertido"]
            k1, k2 = st.columns(2)
            k1.metric("Capital invertido", f"${res['total_invertido']:,.2f}")
            k2.metric("Valor actual", f"${res['total_valor']:,.2f}", delta=f"{rend:+.2f}%")
            st.metric("Ganancia / pérdida no realizada", f"${gan:,.2f} MXN")

            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
            if st.session_state.pop("_auto_analizar", False) or st.button(
                    "🤖 Analizar mi cartera", type="primary", use_container_width=True,
                    help="Genera el diagnóstico del Revisor de Cartera al instante"):
                with st.spinner("Analizando tu cartera…"):
                    payload = cartera_payload(perfil)
                    exportar_json(perfil, payload)  # payload reutilizado: no se calcula 2 veces
                    st.session_state["_revisor_html"] = generar_html(payload)

            dcol1, dcol2 = st.columns(2)
            with dcol1:
                try:
                    pdf_bytes = export_pdf(perfil)
                    st.download_button("⬇ PDF", data=pdf_bytes,
                                       file_name=f"Mis_Resultados_{date.today()}.pdf",
                                       mime="application/pdf", use_container_width=True)
                except Exception as exc:
                    st.button("⬇ PDF", disabled=True, use_container_width=True)
                    st.caption(f"PDF no disponible: {exc}")
            with dcol2:
                try:
                    xlsx_bytes = export_excel(perfil)
                    st.download_button("⬇ Excel", data=xlsx_bytes,
                                       file_name=f"Mis_Resultados_{date.today()}.xlsx",
                                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                       use_container_width=True)
                except Exception as exc:
                    st.button("⬇ Excel", disabled=True, use_container_width=True)
                    st.caption(f"Excel no disponible: {exc}")

            if st.session_state.get("_revisor_html"):
                html = st.session_state["_revisor_html"]
                st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
                components.html(html, height=720, scrolling=True)
                st.download_button("⬇ Descargar diagnóstico (HTML)", data=html.encode("utf-8"),
                                   file_name=f"Revisor_Cartera_{date.today()}.html",
                                   mime="text/html")

            st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
            st.markdown("**Detalle por estrategia**")
            for i, f in enumerate(_estrategias_activas(items)):
                _fila_estrategia_activa(f, key=f"act_r{i}")
            st.caption("Valor con precios de mercado en vivo (en MXN). Ya descuenta lo que has vendido.")

    with tab_real:
        _rendimiento_realizado()


def _rendimiento_realizado():
    hist = load_historial_realizado()
    if not hist:
        st.info("Aún no has registrado ventas. Cuando vendas en una estrategia, aquí verás "
                "tu ganancia o pérdida real (a cuánto compraste vs a cuánto vendiste).")
        return
    total_gan = sum(h["ganancia"] for h in hist)
    c1, c2 = st.columns(2)
    c1.metric("Ganancia / pérdida realizada", f"${total_gan:,.2f} MXN")
    c2.metric("Ventas cerradas", str(len(hist)))
    st.caption("Esto es lo que YA ganaste o perdiste al vender — distinto de tus posiciones actuales.")
    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
    for h in hist:
        rc = GREEN if h["ganancia"] >= 0 else RED
        icono = MODULO_ICON.get(h["modulo"], "📊")
        with st.container(border=True):
            cc1, cc2 = st.columns([3, 2])
            cc1.markdown(
                f"<div style='font-size:15px;'>{icono} <b style='color:#1a1a2e;'>{esc(h['ticker'])}</b></div>"
                f"<div style='font-size:11px;color:#9DA5B8;margin-top:2px;'>{h['modulo']} · "
                f"{str(h['fecha'])[:10]} · {h['titulos']} tít. a ${h['precio']:,.2f}</div>",
                unsafe_allow_html=True)
            cc2.markdown(
                f"<div style='text-align:right;'>"
                f"<div style='font-size:14px;font-weight:600;color:{rc};'>${h['ganancia']:,.2f}</div>"
                f"<div style='font-size:11px;color:#9DA5B8;'>realizado</div></div>",
                unsafe_allow_html=True)
