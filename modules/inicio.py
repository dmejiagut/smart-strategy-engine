import streamlit as st

from datetime import date

import plotly.graph_objects as go

from utils import nav
from utils.db_utils import (get_perfil, save_perfil, get_modo, load_strategies,
                            load_historial_realizado, set_comision_pct, set_meta_anual,
                            set_meta_monto, set_casa_bolsa,
                            guardar_snapshot_patrimonio, leer_historial_patrimonio)
from utils.resumen_utils import resumen_global, invalidar_resumen, invertido_en_anio
import streamlit.components.v1 as components
from modules.resultados_export import export_excel, export_pdf, exportar_json, cartera_payload
from utils.revisor_utils import generar_html
from utils.demo_seed import generar_datos_demo
from modules.bienvenida import cerrar_sesion, CASAS_BOLSA
from utils.seguridad import esc

PURPLE = "#6C63FF"
GREEN = "#1D9E75"
RED = "#A32D2D"

# Versión visible para confirmar qué código está corriendo en la nube.
# Súbela cada vez que despliegues algo que quieras verificar en el celular.
APP_VERSION = "VestPlan · v36"

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


def _alertas_objetivos():
    """Estrategias 'Por Objetivos' cuyo precio actual ya tocó tu punto de
    entrada (compra) o de salida (venta). Usa el precio cacheado (máx 5 min)."""
    from utils.db_utils import load_obj_strategies
    from utils.ticker_search import get_precio_actual
    alertas = []
    for e in load_obj_strategies():
        q = get_precio_actual(e["ticker"])
        px = q.get("precio") if q else None
        if not px:
            continue
        ent = float(e.get("precio_entrada") or 0)
        sal = float(e.get("precio_salida") or 0)
        if sal > 0 and px >= sal:
            alertas.append({"ticker": e["ticker"], "tipo": "salida", "precio": px, "objetivo": sal})
        elif ent > 0 and px <= ent:
            alertas.append({"ticker": e["ticker"], "tipo": "entrada", "precio": px, "objetivo": ent})
    return alertas


def _alertas_copy():
    """Carteras copiadas ACTIVAS cuyo experto tuvo movimientos en su reporte más
    reciente. Solo interesan las que el cliente tiene guardadas."""
    from utils.db_utils import load_copy_strategies
    from utils.copytrading_utils import INVERSIONISTAS, movimientos_experto
    inv_by_id = {i["id"]: i for i in INVERSIONISTAS}
    out = []
    for e in load_copy_strategies():
        inv = inv_by_id.get(e["investor_id"])
        if not inv:
            continue
        mv = movimientos_experto(inv, e.get("reporte_base"))
        if mv and mv["hay"]:
            n = (len(mv["anadidas"]) + len(mv["quitadas"])
                 + len(mv["subieron"]) + len(mv["bajaron"]))
            out.append({"nombre": e.get("nombre") or inv["nombre"],
                        "investor_id": e["investor_id"],
                        "trimestre": mv["trimestre"], "n": n})
    return out


def _racha_dca():
    """Compras DCA seguidas hechas A TIEMPO (a más tardar 3 días después de su
    fecha planeada). Premia la disciplina: se rompe con una compra tardía."""
    from modules.dca import generar_fechas_dca, _parse_fecha, FRECUENCIAS
    from utils.db_utils import load_purchases
    marcas = []  # (fecha_compra, a_tiempo) de todas las estrategias
    for e in load_strategies():
        f_ini = _parse_fecha(e.get("fecha_inicio"))
        f_fin = _parse_fecha(e.get("fecha_fin"))
        frec = e.get("frecuencia")
        if not (f_ini and f_fin and frec in FRECUENCIAS):
            continue
        plan = generar_fechas_dca(f_ini, f_fin, frec)
        compras = sorted(load_purchases(e["id"]), key=lambda c: str(c.get("fecha")))
        for i, c in enumerate(compras):
            if i >= len(plan):
                break
            f = _parse_fecha(c.get("fecha"))
            if f is None:
                continue
            marcas.append((f, (f - plan[i]).days <= 3))
    marcas.sort(key=lambda m: m[0])
    racha = 0
    for _, a_tiempo in reversed(marcas):
        if not a_tiempo:
            break
        racha += 1
    return racha


@st.dialog("🔔 Notificaciones")
def _dialog_notificaciones(proximas, alertas, movs_copy=None):
    """Panel de notificaciones: movimientos de expertos + objetivos + compras."""
    movs_copy = movs_copy or []
    vencidas = [p for p in proximas if p["delta"] <= 0]
    futuras = [p for p in proximas if p["delta"] > 0]
    if not proximas and not alertas and not movs_copy:
        st.success("Todo al día. No tienes compras pendientes. ✅")
    if movs_copy:
        st.markdown("<div style='font-size:13px;font-weight:700;color:#1a1a2e;margin-bottom:2px;'>"
                    "📊 Un experto movió su cartera</div>", unsafe_allow_html=True)
        for m in movs_copy:
            st.markdown(
                f"<div style='padding:8px 0;border-bottom:1px solid #F0F2F8;'>"
                f"<b style='color:#1a1a2e;'>{esc(m['nombre'])}</b> "
                f"<span style='color:{PURPLE};font-size:12.5px;font-weight:600;'>ajustó su cartera "
                f"({esc(m['trimestre'])})</span><br>"
                f"<span style='color:#9DA5B8;font-size:12px;'>{m['n']} movimiento(s) · "
                f"ábrela en Estrategias › Copy Trading para ver qué comprar/vender</span></div>",
                unsafe_allow_html=True)
    if alertas:
        st.markdown("<div style='font-size:13px;font-weight:700;color:#1a1a2e;margin-bottom:2px;'>"
                    "🎯 Objetivos alcanzados</div>", unsafe_allow_html=True)
        for a in alertas:
            if a["tipo"] == "salida":
                txt, col = "tocó tu precio de SALIDA — podrías vender", GREEN
            else:
                txt, col = "tocó tu precio de ENTRADA — podrías comprar", PURPLE
            st.markdown(
                f"<div style='padding:8px 0;border-bottom:1px solid #F0F2F8;'>"
                f"<b style='color:#1a1a2e;'>{esc(a['ticker'])}</b> "
                f"<span style='color:{col};font-size:12.5px;font-weight:600;'>{txt}</span><br>"
                f"<span style='color:#9DA5B8;font-size:12px;'>Precio actual ${a['precio']:,.2f} · "
                f"tu objetivo ${a['objetivo']:,.2f}</span></div>",
                unsafe_allow_html=True)
        st.caption("Sugerencia según tu plan — no es asesoría financiera.")
    if vencidas:
        st.markdown("<div style='font-size:13px;font-weight:700;color:#1a1a2e;margin-bottom:2px;'>"
                    "🛒 Te toca comprar</div>", unsafe_allow_html=True)
        for p in vencidas:
            estado, color = _estado_compra_txt(p["delta"])
            st.markdown(
                f"<div style='padding:8px 0;border-bottom:1px solid #F0F2F8;'>"
                f"<b style='color:#1a1a2e;'>{esc(p['ticker'])}</b> "
                f"<span style='color:#9DA5B8;font-size:12px;'>· {p['fecha'].strftime('%d/%m/%Y')} · DCA</span><br>"
                f"<span style='color:{color};font-size:12.5px;font-weight:600;'>{estado}</span> "
                f"<span style='color:#9DA5B8;font-size:12px;'>· {p['titulos']} título(s)</span></div>",
                unsafe_allow_html=True)
    if futuras:
        st.markdown("<div style='font-size:13px;font-weight:700;color:#1a1a2e;margin:12px 0 2px;'>"
                    "⏳ Próximas</div>", unsafe_allow_html=True)
        for p in futuras[:3]:
            st.markdown(
                f"<div style='padding:6px 0;color:#4A5066;font-size:13px;'>"
                f"<b>{esc(p['ticker'])}</b> · {p['fecha'].strftime('%d/%m/%Y')} "
                f"<span style='color:#9DA5B8;'>(en {p['delta']} día(s))</span></div>",
                unsafe_allow_html=True)
    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
    if st.button("Ver agenda completa", use_container_width=True):
        nav.goto(nav.AGENDA)


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

    # Pipeline periódico (pasos 6-8): condiciones, estadísticas y optimizaciones.
    # Corre 1 vez al día (candado en BD + sesión); sus resultados van al log de auditoría.
    if st.session_state.get("_pipe_dia") != date.today().isoformat():
        try:
            from utils.pipeline import pipeline_periodico
            pipeline_periodico()
        except Exception:
            pass  # nunca debe tirar el Inicio; el detalle queda en los logs
        st.session_state["_pipe_dia"] = date.today().isoformat()

    proximas = _proximas_compras()
    vencidas = [p for p in proximas if p["delta"] <= 0]
    alertas = _alertas_objetivos()
    movs_copy = _alertas_copy()

    # Campanita = NOTIFICACIONES: el número solo cuenta lo que NO has visto.
    # Al abrirla se marca como leído (el número se apaga); si llega algo nuevo,
    # se vuelve a encender. El copiloto, en cambio, insiste hasta que resuelvas.
    firmas = ({f"v:{p['ticker']}:{p['fecha']}" for p in vencidas}
              | {f"a:{a['ticker']}:{a['tipo']}" for a in alertas}
              | {f"cm:{m['investor_id']}:{m['trimestre']}" for m in movs_copy})
    vistas = st.session_state.setdefault("_notif_vistas", set())
    n_notif = len(firmas - vistas)

    # Logros: evalúa, guarda los nuevos y los celebra (una sola vez) 🎈
    from utils.logros import evaluar_logros
    racha = _racha_dca()
    _, logros_nuevos = evaluar_logros(res, racha, perfil)
    if logros_nuevos:
        st.session_state["_logro_nuevo"] = logros_nuevos[0]
        _confeti()

    # ── Header: marca + campanita (notificaciones) + avatar (perfil) ──
    from datetime import datetime
    try:
        # El servidor de la nube corre en UTC: mostrar hora de México.
        from zoneinfo import ZoneInfo
        hora = datetime.now(ZoneInfo("America/Mexico_City")).strftime("%H:%M")
    except Exception:
        hora = datetime.now().strftime("%H:%M")
    with st.container(key="topbar"):
        hL, hB, hA = st.columns([6, 1.1, 1.1])
        hL.markdown(f"""
            <div style="font-size:22px;font-weight:700;letter-spacing:-.3px;color:#1a1a2e;line-height:1.05;">
                <span style="color:{PURPLE};">Vest</span>Plan</div>
            <div style="font-size:11px;color:#9DA5B8;margin-top:3px;">
                <span style="color:{GREEN};">●</span> Precios al corte de las {hora}</div>
        """, unsafe_allow_html=True)
        if hB.button(f"🔔 {n_notif}" if n_notif else "🔔", key="tb_bell", help="Notificaciones"):
            st.session_state["_notif_vistas"] = vistas | firmas   # marcar como leídas
            _dialog_notificaciones(proximas, alertas, movs_copy)
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

    # ── Mensaje del copiloto (estado del plan; toca para ver el detalle) ──
    # La tarjeta ES el acceso al detalle: sin sección 'Pendientes' duplicada.
    _mensaje_estado(res, items, vencidas, alertas, racha, proximas, movs_copy)

    # ── Tarjeta de patrimonio (oscura, con gráfica de evolución y KPIs) ──
    _tarjeta_patrimonio(res, rend, hist)

    # ── Meta anual de inversión (toca la tarjeta para ver tu ahorro mes a mes) ──
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
        # Se agrupan por módulo, así que nunca hay más de 5 tarjetas: se muestran
        # TODAS (esconder posiciones activas tras un botón era pura fricción).
        for i, f in enumerate(_estrategias_activas(items)):
            _fila_estrategia_activa(f, key=f"act_{i}")


def _mensaje_estado(res, items, vencidas, alertas, racha=0, proximas=None, movs_copy=None):
    """Copiloto de VestPlan: primero el ESTADO del plan, luego (opcional) el detalle.
    TODA la tarjeta es tocable y abre el panel de notificaciones (por eso la ›)."""
    frase = _frase_filosofia()
    logro_nuevo = st.session_state.get("_logro_nuevo")
    if vencidas:
        # Hay algo que hacer HOY: la app pide una acción concreta.
        dot = "#EF9F27"
        titulo = "Hoy tu plan necesita una acción."
        mas = f" (+{len(vencidas) - 1} más)" if len(vencidas) > 1 else ""
        detalle = f"Comprar <b style='color:#1a1a2e;'>{esc(vencidas[0]['ticker'])}</b>.{mas}"
    elif logro_nuevo:
        # Acabas de desbloquear un logro: ¡celebrarlo!
        dot = GREEN
        titulo = "🏅 ¡Nuevo logro desbloqueado!"
        detalle = (f"<b style='color:#1a1a2e;'>{esc(logro_nuevo)}</b> — "
                   f"míralo en tu perfil (avatar arriba a la derecha).")
    elif alertas:
        # Un objetivo tocó su precio: celebrarlo y avisar.
        a = alertas[0]
        dot = GREEN
        titulo = "🎉 Objetivo alcanzado."
        accion = "salida (venta)" if a["tipo"] == "salida" else "entrada (compra)"
        detalle = (f"<b style='color:#1a1a2e;'>{esc(a['ticker'])}</b> tocó tu precio de "
                   f"{accion}: ${a['objetivo']:,.2f}. Revisa la campanita 🔔")
    elif not items:
        dot = PURPLE
        titulo = "Empieza tu plan hoy."
        detalle = esc(frase)
    else:
        # Todo en orden: disciplina primero (racha), luego mejor estrategia o frase.
        dot = GREEN
        titulo = "Todo va conforme a tu plan."
        activas = _estrategias_activas(items)
        mejor = max(activas, key=lambda x: x["rend_pct"]) if activas else None
        if racha >= 2:
            detalle = (f"🔥 Excelente disciplina: <b style='color:#1a1a2e;'>{racha} compras "
                       f"seguidas a tiempo</b>. {esc(frase)}")
        elif mejor and mejor["rend_pct"] > 0 and st.session_state.get("_frase_idx", 0) % 2 == 0:
            detalle = (f"🏆 Tu mejor estrategia: <b style='color:#1a1a2e;'>{esc(mejor['modulo'])}</b> "
                       f"({mejor['rend_pct']:+.1f}%)")
        else:
            detalle = esc(frase)
    with st.container(key="card_estado"):
        st.markdown(f"""
        <div style="background:#fff;border:0.5px solid #E8ECF4;border-radius:12px;padding:12px 14px;
                    box-shadow:0 1px 3px rgba(16,24,40,.04);
                    display:flex;align-items:center;justify-content:space-between;gap:10px;">
            <div>
                <div style="font-size:13.5px;color:#1a1a2e;"><span style="color:{dot};">●</span> <b>{titulo}</b></div>
                <div style="font-size:11px;color:#9DA5B8;margin-top:3px;">{detalle}</div>
            </div>
            <div style="font-size:18px;color:#C3C9D6;">›</div>
        </div>
        """, unsafe_allow_html=True)
        # Botón invisible sobre toda la tarjeta (CSS .st-key-card_) → notificaciones.
        if st.button("Ver detalle", key="estado_detalle", use_container_width=True):
            _dialog_notificaciones(proximas or [], alertas or [], movs_copy or [])
    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)


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
    """Barra de progreso de la meta anual de INVERSIÓN. Toda la tarjeta es
    clickable: abre el detalle de tu ahorro por mes y por año."""
    anio = date.today().year
    meta = float(perfil.get("meta_monto") or 0)
    with st.container(key="card_meta"):
        if meta <= 0:
            # Aún no define su meta → invitación (también abre el detalle al tocar).
            st.markdown("""
            <div style="background:#F7F6FF;border:1px dashed #D4CFFF;border-radius:14px;padding:14px 16px;">
                <div style="font-size:13px;font-weight:600;color:#1a1a2e;">🎯 Ponte una meta anual</div>
                <div style="font-size:11px;color:#9DA5B8;margin-top:3px;">
                    Define cuánto quieres invertir este año en <b>Perfil</b>. Toca aquí para ver tu ahorro.</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            invertido = invertido_en_anio(anio)
            pct = min(100.0, (invertido / meta * 100) if meta else 0)
            falta = max(0.0, meta - invertido)
            st.markdown(f"""
            <div style="background:#fff;border:0.5px solid #E8ECF4;border-radius:14px;padding:14px 16px;">
                <div style="display:flex;justify-content:space-between;align-items:baseline;">
                    <div style="font-size:13px;font-weight:600;color:#1a1a2e;">Tu meta anual {anio}</div>
                    <div style="font-size:16px;font-weight:700;color:{PURPLE};">${meta:,.0f} <span style="color:#C3C9D6;font-weight:400;">›</span></div>
                </div>
                <div style="font-size:11px;color:#9DA5B8;margin:6px 0;">
                    Llevas ${invertido:,.0f} ({pct:.0f}%) · te faltan ${falta:,.0f} · toca para ver tu ahorro</div>
                <div style="background:#EDEBFB;border-radius:20px;height:8px;overflow:hidden;">
                    <div style="background:{PURPLE};height:8px;width:{pct:.0f}%;border-radius:20px;"></div>
                </div>
            </div>
            """, unsafe_allow_html=True)
        # Botón invisible que cubre la tarjeta (CSS .st-key-card_) → abre el detalle.
        if st.button("Ver mi ahorro", key="meta_detalle", use_container_width=True):
            _dialog_ahorro(perfil)
    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)


_MESES_CORTOS = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
                 "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]


def _confeti():
    """Lluvia de confeti sobre toda la pantalla (colores VestPlan), ~4 segundos.
    Streamlit no trae confeti nativo; se anima un canvas sobre la página padre
    desde un iframe oculto (mismo patrón que el script del calendario)."""
    with st.container(key="confeti"):
        components.html("""
<script>
(function(){
  var d = window.parent.document;
  if (d.getElementById('vp-confeti')) return;   // no duplicar si hay rerun
  var c = d.createElement('canvas');
  c.id = 'vp-confeti';
  c.style.cssText = 'position:fixed;inset:0;pointer-events:none;z-index:99999;';
  d.body.appendChild(c);
  c.width = d.documentElement.clientWidth;
  c.height = d.documentElement.clientHeight;
  var ctx = c.getContext('2d');
  var colores = ['#6C63FF','#22C55E','#F4B400','#F97316','#2563EB','#EC4899','#8B5CF6'];
  var piezas = [];
  for (var i = 0; i < 160; i++){
    piezas.push({
      x: Math.random() * c.width,
      y: -20 - Math.random() * c.height * 0.6,
      w: 5 + Math.random() * 6,
      h: 8 + Math.random() * 9,
      vy: 2.2 + Math.random() * 3.2,
      vx: -1.2 + Math.random() * 2.4,
      rot: Math.random() * Math.PI,
      vr: -0.14 + Math.random() * 0.28,
      color: colores[(Math.random() * colores.length) | 0]
    });
  }
  var inicio = Date.now();
  (function cuadro(){
    var t = Date.now() - inicio;
    ctx.clearRect(0, 0, c.width, c.height);
    piezas.forEach(function(p){
      p.y += p.vy;
      p.x += p.vx + Math.sin(t / 280 + p.rot) * 0.8;   // vaivén al caer
      p.rot += p.vr;
      ctx.save(); ctx.translate(p.x, p.y); ctx.rotate(p.rot);
      ctx.fillStyle = p.color;
      ctx.fillRect(-p.w / 2, -p.h / 2, p.w, p.h);
      ctx.restore();
    });
    if (t < 4200) requestAnimationFrame(cuadro);
    else c.remove();
  })();
})();
</script>
""", height=0)


@st.dialog("💰 Tu ahorro invertido")
def _dialog_ahorro(perfil):
    """Detalle del dinero que has metido a invertir: por mes (año actual) y por año."""
    from utils.resumen_utils import aportaciones_por_mes
    ap = aportaciones_por_mes()
    if not ap:
        st.info("Aún no registras compras. Cuando lo hagas, aquí verás tu ahorro mes a mes.")
        return
    anio = date.today().year

    # Barras por mes del año actual
    vals = [ap.get(f"{anio:04d}-{m:02d}", 0.0) for m in range(1, 13)]
    st.markdown(f"<div style='font-size:13px;font-weight:700;color:#1a1a2e;'>"
                f"Aportaciones por mes · {anio}</div>", unsafe_allow_html=True)
    fig = go.Figure(go.Bar(x=_MESES_CORTOS, y=vals, marker_color=PURPLE,
                           hovertemplate="%{x}: $%{y:,.0f} MXN<extra></extra>"))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=6, b=0), height=200, showlegend=False, dragmode=False,
        xaxis=dict(showgrid=False, fixedrange=True, tickfont=dict(size=10, color="#9DA5B8")),
        yaxis=dict(gridcolor="#F0F2F8", fixedrange=True, tickprefix="$",
                   tickfont=dict(size=10, color="#9DA5B8")))
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    # Totales por año + total histórico
    anios = {}
    for ym, v in ap.items():
        anios[ym[:4]] = anios.get(ym[:4], 0.0) + v
    st.markdown("<div style='font-size:13px;font-weight:700;color:#1a1a2e;margin-top:4px;'>"
                "Por año</div>", unsafe_allow_html=True)
    for a in sorted(anios, reverse=True):
        pct_meta = ""
        meta = float(perfil.get("meta_monto") or 0)
        if meta > 0 and int(a) == anio:
            pct_meta = (f" <span style='color:{PURPLE};font-weight:600;'>"
                        f"({anios[a] / meta * 100:.0f}% de tu meta)</span>")
        st.markdown(
            f"<div style='display:flex;justify-content:space-between;padding:7px 0;"
            f"border-bottom:1px solid #F0F2F8;font-size:13.5px;'>"
            f"<span style='color:#4A5066;'>{a}</span>"
            f"<span style='font-weight:700;color:#1a1a2e;'>${anios[a]:,.0f}{pct_meta}</span></div>",
            unsafe_allow_html=True)
    total = sum(anios.values())
    st.markdown(
        f"<div style='display:flex;justify-content:space-between;padding:9px 0;font-size:14px;'>"
        f"<span style='font-weight:700;color:#1a1a2e;'>Total histórico</span>"
        f"<span style='font-weight:800;color:{GREEN};'>${total:,.0f} MXN</span></div>",
        unsafe_allow_html=True)
    st.caption("💪 Cada peso que aportas es tu disciplina trabajando. Sigue así.")


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

    _seccion_logros(perfil)

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
        casa_bolsa = st.selectbox("Casa de bolsa", CASAS_BOLSA,
                                  index=_idx(CASAS_BOLSA, perfil.get("casa_bolsa")))
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
            set_casa_bolsa(casa_bolsa)
            st.success("✅ Perfil actualizado.")
            st.rerun()

    # ── Modo de datos ──
    st.markdown("---")
    st.markdown("**Modo de datos**")
    modo_actual = st.session_state.get("_modo_actual", "real")
    modo = st.radio("Modo de datos", ["🔵 Real", "🧪 Demostración"],
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

    # ── Auditoría del pipeline (OCULTA para clientes) ──
    # El pipeline sigue registrando todo en la BD; este visor solo aparece si
    # se abre la app con ?auditoria=1 en la URL (herramienta del dueño/desarrollo).
    if st.query_params.get("auditoria") == "1":
        st.markdown("---")
        with st.expander("🧾 Auditoría del pipeline de estrategias"):
            st.caption("Cada validación, métrica y revisión periódica queda registrada aquí. "
                       "Ningún paso se repite para la misma versión de una estrategia.")
            from utils.pipeline import leer_logs, PASOS
            logs = leer_logs(30)
            if not logs:
                st.info("Aún no hay registros. Se generan al crear estrategias y en la revisión diaria.")
            for lg in logs:
                color = {"ok": GREEN, "advertencia": "#C77F00",
                         "error": RED, "omitido": "#9DA5B8"}.get(lg["resultado"], "#9DA5B8")
                st.markdown(
                    f"<div style='padding:6px 0;border-bottom:1px solid #F0F2F8;font-size:12px;'>"
                    f"<span style='color:#9DA5B8;'>{lg['creado_en'][:16]}</span> · "
                    f"<b style='color:#1a1a2e;'>{esc(lg['modulo'])}</b> · "
                    f"{PASOS.get(lg['paso'], lg['paso'])} → "
                    f"<b style='color:{color};'>{lg['resultado']}</b><br>"
                    f"<span style='color:#4A5066;'>{esc(lg['detalle'] or '')}</span></div>",
                    unsafe_allow_html=True)

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


def _seccion_logros(perfil):
    """Vitrina de logros en Perfil: los ganados a color, los pendientes en gris."""
    from utils.logros import evaluar_logros
    res = resumen_global()
    badges, _ = evaluar_logros(res, _racha_dca(), perfil)
    ganados = sum(1 for b in badges if b["ganado"])
    celdas = ""
    for b in badges:
        if b["ganado"]:
            estilo, em_op = "background:#fff;border:1px solid #E0DBFA;", ""
        else:
            estilo = "background:#F6F6F9;border:1px dashed #E2E6EE;"
            em_op = "filter:grayscale(1);opacity:.35;"
        celdas += (
            f"<div style='{estilo}border-radius:12px;padding:10px 6px;text-align:center;"
            f"width:calc(25% - 6px);' title='{esc(b['desc'])}'>"
            f"<div style='font-size:24px;{em_op}'>{b['emoji']}</div>"
            f"<div style='font-size:9.5px;color:{'#1a1a2e' if b['ganado'] else '#9DA5B8'};"
            f"font-weight:600;margin-top:3px;line-height:1.2;'>{esc(b['titulo'])}</div></div>")
    st.markdown(f"""
    <div style="background:#fff;border:0.5px solid #E8ECF4;border-radius:14px;padding:14px 14px 10px;margin-bottom:16px;">
        <div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:10px;">
            <div style="font-size:14px;font-weight:700;color:#1a1a2e;">🏅 Mis logros</div>
            <div style="font-size:11px;color:#9DA5B8;">{ganados} de {len(badges)}</div>
        </div>
        <div style="display:flex;flex-wrap:wrap;gap:8px;">{celdas}</div>
        <div style="font-size:10.5px;color:#C3C9D6;margin-top:8px;">Se desbloquean con tu disciplina, no con la suerte del mercado.</div>
    </div>
    """, unsafe_allow_html=True)


# ─── Mis Resultados ──────────────────────────────────────────────────────────
def _estrategia_mas_larga():
    """(etiqueta, meses) de la estrategia con la primera compra más antigua —
    la que llevas más tiempo sosteniendo. (None, 0) si no hay compras."""
    from utils.db_utils import (
        load_strategies, load_purchases,
        load_div_strategies, load_div_purchases,
        load_obj_strategies, load_obj_purchases,
        load_fibra_strategies, load_fibra_purchases,
        load_copy_strategies, load_copy_purchases,
    )
    candidatos = []  # (fecha_min 'YYYY-MM-DD', modulo, nombre)

    def _scan(estrategias, load_p, modulo, name_key="ticker"):
        for e in estrategias:
            fechas = [str(c["fecha"])[:10] for c in load_p(e["id"]) if c.get("fecha")]
            if fechas:
                nombre = e.get(name_key) or e.get("nombre") or e.get("ticker") or ""
                candidatos.append((min(fechas), modulo, nombre))

    _scan(load_strategies(), load_purchases, "DCA")
    _scan(load_div_strategies(), load_div_purchases, "Dividendos")
    _scan(load_obj_strategies(), load_obj_purchases, "Por Objetivos")
    _scan(load_fibra_strategies(), load_fibra_purchases, "FIBRAs")
    for e in load_copy_strategies():
        fechas = [str(c["fecha"])[:10] for c in load_copy_purchases(e["id"]) if c.get("fecha")]
        if fechas:
            candidatos.append((min(fechas), "Copy Trading",
                               e.get("nombre") or e.get("investor_id") or ""))
    if not candidatos:
        return None, 0
    f0, modulo, nombre = min(candidatos, key=lambda x: x[0])
    try:
        y, m, dd = (int(x) for x in f0.split("-"))
        hoy = date.today()
        meses = (hoy.year - y) * 12 + (hoy.month - m) - (1 if hoy.day < dd else 0)
        meses = max(meses, 0)
    except Exception:
        meses = 0
    etiqueta = f"{modulo} · {nombre}" if nombre else modulo
    return etiqueta, meses


def render_resultados():
    st.markdown("""
    <div style="margin-bottom:16px;">
        <h2 style="font-size:20px;font-weight:600;color:#1a1a2e;margin:0;">📈 Mis Resultados</h2>
        <p style="font-size:12px;color:#9DA5B8;margin:4px 0 0;">Resumen de todas tus estrategias — inversión y rendimiento en pesos</p>
    </div>
    """, unsafe_allow_html=True)

    res = resumen_global()
    items = res["items"]
    perfil = get_perfil()

    # Sub-navegación controlable (st.tabs siempre abre en la 1ª; con segmented_control
    # podemos abrir en "Posiciones actuales" aunque "Cargar Excel" quede primero).
    # El reset a Posiciones al ENTRAR a Resultados se hace en app.py.
    TAB_IMP = "📥 Cargar Excel"
    TAB_POS = "📊 Posiciones actuales"
    TAB_REAL = "🏁 Rendimiento realizado"
    st.session_state.setdefault("res_view", TAB_POS)
    vista = st.segmented_control("Vista", [TAB_IMP, TAB_POS, TAB_REAL],
                                 key="res_view", label_visibility="collapsed")
    if vista is None:
        vista = TAB_POS

    if vista == TAB_IMP:
        from modules.importar import render_importar
        render_importar()
    elif vista == TAB_REAL:
        _rendimiento_realizado()
    else:
        _resultados_posiciones(res, items, perfil)


def _resultados_posiciones(res, items, perfil):
    if not items:
        st.info("Aún no tienes posiciones. Registra una compra en cualquier estrategia.")
        return
    rend = res["total_rend_pct"]
    gan = res["total_valor"] - res["total_invertido"]
    k1, k2 = st.columns(2)
    k1.metric("Capital invertido", f"${res['total_invertido']:,.2f}")
    k2.metric("Valor actual", f"${res['total_valor']:,.2f}", delta=f"{rend:+.2f}%")
    st.metric("Ganancia / pérdida no realizada", f"${gan:,.2f} MXN")

    # Tarjeta de LOGROS para compartir: celebra disciplina y metas, NUNCA
    # muestra montos ni el patrimonio del usuario (para compartir sin exponer dinero).
    from utils.compartir import generar_tarjeta_resultados
    from utils.logros import evaluar_logros
    activas = _estrategias_activas(items)
    racha = _racha_dca()
    badges, _ = evaluar_logros(res, racha, perfil)
    lg_g = sum(1 for b in badges if b["ganado"])
    mejor_label, mejor_meses = _estrategia_mas_larga()
    meta = float(perfil.get("meta_monto") or 0)
    meta_pct = None
    meta_cumplida = False
    if meta > 0:
        inv_anio = invertido_en_anio(date.today().year)
        meta_cumplida = inv_anio >= meta
        meta_pct = None if meta_cumplida else min(inv_anio / meta * 100, 999)
    datos_tarjeta = {
        "nombre": perfil.get("nombre") or "",
        "anio": date.today().year,
        "rend_pct": rend,
        "n_estrategias": len(activas),
        "logros_ganados": lg_g, "logros_total": len(badges),
        "racha": racha,
        "mejor_label": mejor_label, "mejor_meses": mejor_meses,
        "meta_pct": meta_pct, "meta_cumplida": meta_cumplida,
    }
    png = generar_tarjeta_resultados(datos_tarjeta)
    st.download_button("📤 Compartir mis logros (imagen)", data=png,
                       file_name="vestplan_mis_logros.png", mime="image/png",
                       use_container_width=True,
                       help="Una tarjeta con tus logros y tu disciplina (sin mostrar tu dinero) "
                            "para compartir por WhatsApp o redes.")

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
