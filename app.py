from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components
from utils import nav
from utils import db_utils
from modules.inicio import (render_inicio, render_resultados, render_estrategias,
                            render_perfil, render_agenda)
from modules.importar import render_importar
from modules.dca import render_dca
from modules.dividendos import render_dividendos
from modules.objetivos import render_objetivos
from modules.fibras import render_fibras
from modules.copytrading import render_copytrading
from modules.bienvenida import necesita_bienvenida, render_bienvenida

# Ícono/favicon de la app: el logo VestPlan (con respaldo a emoji si falta).
_ICONO = Path(__file__).parent / "assets" / "vestplan_icon.png"

st.set_page_config(
    page_title="VestPlan",
    page_icon=str(_ICONO) if _ICONO.exists() else "📈",
    layout="wide",
    # "auto" = en computadora se muestra el menú lateral abierto,
    # y en celular se colapsa solo en el botón ☰ (mejor para pantallas chicas).
    initial_sidebar_state="auto"
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
/* Sin menú lateral: la navegación es la barra inferior */
section[data-testid="stSidebar"] { display: none !important; }
[data-testid="stSidebarCollapsedControl"] { display: none !important; }
/* Escenario B: la app vive en una columna centrada, como un celular */
.main .block-container,
[data-testid="stMainBlockContainer"] {
    background-color: #F4F6FA;
    padding: 1.2rem 1.4rem 95px !important;  /* top compacto, bottom justo para la barra */
    max-width: 600px;
}

/* Barra de navegación inferior FLOTANTE (fija, como app nativa) */
.st-key-bottomnav {
    position: fixed; bottom: 0; left: 50%; transform: translateX(-50%);
    width: 100%; max-width: 600px;
    background: #FFFFFF;
    border-top: 0.5px solid #E8ECF4;
    border-radius: 18px 18px 0 0;
    box-shadow: 0 -4px 18px rgba(26,26,46,0.07);
    padding: 10px 14px calc(10px + env(safe-area-inset-bottom));
    z-index: 999;
}

/* Accesos rápidos y barra inferior: SIEMPRE en fila, con columnas de ancho parejo
   (evita que se apilen o se salgan de la pantalla en el celular). */
.st-key-quicktiles [data-testid="stHorizontalBlock"],
.st-key-bottomnav [data-testid="stHorizontalBlock"] {
    flex-wrap: nowrap !important; gap: 4px !important;
}
.st-key-quicktiles [data-testid="stColumn"],
.st-key-bottomnav [data-testid="stColumn"] {
    flex: 1 1 0 !important; min-width: 0 !important; width: auto !important;
}

/* Inputs y selects redondeados (look neobank) */
.stTextInput input, .stNumberInput input, .stDateInput input { border-radius: 10px !important; }
.stSelectbox [data-baseweb="select"] > div { border-radius: 10px !important; }
/* Ventanas sobrepuestas con esquinas suaves */
div[role="dialog"] { border-radius: 18px !important; }
.stButton > button {
    border-radius: 10px;
    font-size: 13px;
    font-weight: 500;
    border: 0.5px solid #E2E6EE;
    background: #FFFFFF;
    color: #4A5066;
    padding: 9px 14px;
}
.stButton > button:hover { border-color: #6C63FF; color: #6C63FF; }
/* Botón primario relleno (morado de marca) */
.stButton > button[kind="primary"] { background: #6C63FF; color: #fff; border: none; }
.stButton > button[kind="primary"]:hover { background: #5A4FD1; color: #fff; }
/* Tarjetas con borde (st.container border) más redondeadas */
[data-testid="stVerticalBlockBorderWrapper"] { border-radius: 14px !important; }
/* Métricas tipo tarjeta neobank */
[data-testid="stMetric"] {
    background: #FFFFFF; border: 0.5px solid #E8ECF4;
    border-radius: 12px; padding: 12px 14px;
}
.stTabs [data-baseweb="tab-list"] { gap: 4px; background: transparent; }
.stTabs [data-baseweb="tab"] {
    border-radius: 8px; font-size: 12px; color: #7B8494;
    background: transparent; padding: 6px 16px; border: none;
}
.stTabs [aria-selected="true"] {
    background: #6C63FF !important; color: white !important; font-weight: 500;
}
#MainMenu, footer, header { visibility: hidden; }
.stDeployButton { display: none; }
/* Ocultar overlays de Streamlit Cloud (badge del dueño, botón Manage app) que
   estorban la barra inferior en el celular. */
[data-testid="stStatusWidget"] { display: none !important; }
[data-testid="stToolbar"] { display: none !important; }
[class*="viewerBadge"] { display: none !important; }
[data-testid="manage-app-button"] { display: none !important; }
/* Quitar espacio vacío extra al final de la app */
[data-testid="stAppViewContainer"] > .main { min-height: 0 !important; }

/* Accesos rápidos (tiles cuadrados con ícono) */
.qa-tile {
    width: 52px; height: 52px; border-radius: 15px; margin: 0 auto 6px;
    display: flex; align-items: center; justify-content: center; font-size: 22px;
}
.qa-wrap { text-align: center; font-size: 11px; color: #7B8494; }
/* Etiquetas de los accesos rápidos: texto limpio, sin aspecto de botón */
[class*="st-key-qa_"] button {
    border: none !important; background: transparent !important;
    color: #4A5066 !important; font-size: 11px !important;
    padding: 0 !important; min-height: 0 !important; margin-top: -4px;
}
[class*="st-key-qa_"] button:hover { color: #6C63FF !important; background: transparent !important; }
/* Título de cada estrategia activa: texto clicable, no botón */
[class*="st-key-go_act_"] button {
    border: none !important; background: transparent !important;
    color: #1a1a2e !important; font-weight: 600 !important; font-size: 14px !important;
    padding: 0 !important; min-height: 0 !important; justify-content: flex-start !important;
}
[class*="st-key-go_act_"] button:hover { color: #6C63FF !important; background: transparent !important; }
/* Barra de navegación inferior: solo ícono + etiqueta, sin caja de botón */
[class*="st-key-navx_"] button, [class*="st-key-navA_"] button {
    border: none !important; background: transparent !important;
    padding: 0 !important; min-height: 0 !important; margin-top: -8px;
    font-size: 11.5px !important; font-weight: 500 !important;
}
[class*="st-key-navx_"] button { color: #7B8494 !important; }
[class*="st-key-navA_"] button { color: #6C63FF !important; }
[class*="st-key-navx_"] button:hover, [class*="st-key-navA_"] button:hover {
    color: #6C63FF !important; background: transparent !important;
}

/* Botones de rango de la gráfica (1A/3A/5A/10A): texto en una sola línea */
[class*="st-key-obj_zoom_"] button {
    white-space: nowrap !important; padding-left: 4px !important; padding-right: 4px !important;
}

/* Barra de navegación inferior */
.bottom-spacer { height: 8px; }
div[data-testid="stHorizontalBlock"].navbar { border-top: 0.5px solid #E8ECF4; padding-top: 8px; }

/* ====== RESPONSIVO: ajustes para CELULAR (pantallas <= 640px) ====== */
@media (max-width: 640px) {
    /* Menos relleno para aprovechar el ancho del teléfono */
    .main .block-container,
    [data-testid="stMainBlockContainer"] {
        padding: 0.8rem 0.9rem 95px !important;  /* top compacto, bottom justo a la barra */
        max-width: 100% !important;
    }
    /* En celular: columnas horizontales que se ENCOGEN para caber (no apiladas ni desbordadas). */
    div[data-testid="stHorizontalBlock"] { flex-wrap: nowrap !important; gap: 4px !important; }
    div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] {
        min-width: 0 !important; width: auto !important; flex-shrink: 1 !important;
    }
    /* Métricas y títulos más compactos */
    [data-testid="stMetricValue"] { font-size: 1.4rem !important; }
    h1 { font-size: 1.5rem !important; }
    h2 { font-size: 1.25rem !important; }
    /* Botones cómodos para tocar con el dedo */
    .stButton > button { width: 100%; padding: 10px 12px; font-size: 14px; }
    /* Las pestañas se pueden deslizar de lado sin romperse */
    .stTabs [data-baseweb="tab-list"] { overflow-x: auto; flex-wrap: nowrap; }
    /* Tablas y gráficos no se salen de la pantalla */
    [data-testid="stDataFrame"], .stPlotlyChart { width: 100% !important; }
    /* Tarjetas de resumen (métricas): en celular NO caben 4 en fila y los
       números se parten feo. Las acomodamos en 2x2 para que cada número quepa
       completo en su recuadro. Aplica a las tarjetas propias (.sse-metric-card)
       y a los st.metric nativos. */
    div[data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]),
    div[data-testid="stHorizontalBlock"]:has(.sse-metric-card) {
        flex-wrap: wrap !important;
        gap: 8px !important;
    }
    div[data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]) > div[data-testid="stColumn"],
    div[data-testid="stHorizontalBlock"]:has(.sse-metric-card) > div[data-testid="stColumn"] {
        flex: 1 1 calc(50% - 8px) !important;
        min-width: calc(50% - 8px) !important;
        width: calc(50% - 8px) !important;
    }
    /* Número del st.metric un poco más chico para que no se parta */
    [data-testid="stMetricValue"] { font-size: 1.2rem !important; }
}
/* Ocultar los iframes de scripts auxiliares (cierra-calendario, confeti) */
.st-key-dpfix, .st-key-confeti { display: none !important; }

/* Header superior de Inicio: campanita (pendientes) + avatar (perfil) */
.st-key-topbar [data-testid="stHorizontalBlock"] { align-items: center !important; gap: 2px !important; }
.st-key-tb_bell button {
    background: transparent !important; border: none !important; box-shadow: none !important;
    font-size: 15px !important; padding: 2px !important; min-height: 0 !important; color: #64748B !important;
}
.st-key-tb_perfil button {
    background: linear-gradient(135deg, #7B6CF5, #5A4FD1) !important;
    color: #fff !important; border: none !important; box-shadow: none !important;
    border-radius: 50% !important; width: 38px !important; height: 38px !important;
    min-height: 0 !important; padding: 0 !important; font-weight: 700 !important;
    font-size: 15px !important; margin-left: auto !important;
}

/* Tarjeta de patrimonio (oscura, con degradado morado tipo VestPlan) */
.st-key-patricard {
    background: linear-gradient(135deg, #2D1B8F 0%, #24126A 100%) !important;
    border-radius: 18px !important;
    padding: 16px 18px !important;
    margin-bottom: 14px !important;
    box-shadow: 0 8px 24px rgba(45,27,143,.18);
}
/* Selector de periodo (1M/3M/6M/1A/Todo): pastillas translúcidas dentro de la tarjeta */
.st-key-patricard .stButton > button {
    background: rgba(255,255,255,.10) !important;
    color: rgba(255,255,255,.85) !important;
    border: none !important;
    font-size: 11px !important;
    font-weight: 600 !important;
    padding: 4px 0 !important;
    min-height: 0 !important;
    border-radius: 8px !important;
}
.st-key-patricard .stButton > button:hover {
    background: rgba(255,255,255,.22) !important;
    color: #fff !important;
}
/* Menos separación entre los elementos internos de la tarjeta */
.st-key-patricard [data-testid="stHorizontalBlock"] { gap: 6px !important; }

/* Tarjeta de estrategia activa (Inicio): TODO el recuadro es clickable.
   Un botón transparente se estira para cubrir toda la tarjeta. */
[class*="st-key-card_"] { position: relative !important; cursor: pointer; }
[class*="st-key-card_"] div[data-testid="stElementContainer"]:has(button) {
    position: absolute !important;
    inset: 0 !important;
    margin: 0 !important;
    z-index: 3;
}
[class*="st-key-card_"] .stButton,
[class*="st-key-card_"] .stButton > button {
    width: 100% !important;
    height: 100% !important;
    min-height: 0 !important;
    opacity: 0 !important;
    padding: 0 !important;
    border: none !important;
    box-shadow: none !important;
}
</style>
""", unsafe_allow_html=True)

# Ayudas para el calendario de st.date_input (Streamlit no las trae de fábrica):
#  1) Deshabilita sábados y domingos: los mercados no abren, así que no deben
#     poder elegirse en ningún calendario de la app.
#  2) Al elegir un día hábil, cierra el calendario solo para pasar a lo siguiente
#     (Streamlit no lo cierra dentro de un modal en celular).
# El calendario vive en un portal fuera del modal, así que el "click fuera" que
# usamos para cerrarlo no cierra el modal. Se inyecta una sola vez.
with st.container(key="dpfix"):
    components.html(
        """
<script>
(function(){
  var w = window.parent, d = w.document;
  if (w.__sseDatePickerFix) return;   // no duplicar entre reruns
  w.__sseDatePickerFix = true;

  function esFinDeSemana(lbl){
    return lbl.indexOf('Saturday') !== -1 || lbl.indexOf('Sunday') !== -1;
  }

  // Bloquea visual y funcionalmente los fines de semana del calendario abierto.
  function bloquearFinesDeSemana(){
    var cal = d.querySelector('[data-baseweb="calendar"]');
    if (!cal) return;
    var cells = cal.querySelectorAll('[role="gridcell"]');
    for (var i = 0; i < cells.length; i++){
      var c = cells[i];
      if (esFinDeSemana(c.getAttribute('aria-label') || '')){
        c.style.pointerEvents = 'none';
        c.style.opacity = '0.28';
        c.style.cursor = 'not-allowed';
        c.setAttribute('aria-disabled', 'true');
      }
    }
  }

  // Reaplica cada vez que el calendario aparece o cambia de mes.
  new MutationObserver(bloquearFinesDeSemana)
      .observe(d.body, {childList: true, subtree: true});

  d.addEventListener('click', function(e){
    var day = e.target.closest('[data-baseweb="calendar"] [role="gridcell"]');
    if (!day || !day.innerText.trim()) return;                 // solo días reales
    if (esFinDeSemana(day.getAttribute('aria-label') || '')) return;  // finde: no seleccionar
    setTimeout(function(){
      if (!d.querySelector('[data-baseweb="calendar"]')) return;  // ya se cerró solo
      d.body.dispatchEvent(new MouseEvent('mousedown', {bubbles:true, cancelable:true}));
      d.body.dispatchEvent(new MouseEvent('mouseup',   {bubbles:true, cancelable:true}));
    }, 60);
  }, true);
})();
</script>
""",
        height=0,
    )

# Compuerta de bienvenida: login con Google o invitado + datos básicos.
# Mientras no haya entrado, mostramos la bienvenida y detenemos el resto.
if necesita_bienvenida():
    render_bienvenida()
    st.stop()

_SVG_OPEN = ('<svg width="26" height="26" viewBox="0 0 24 24" fill="none" '
             'stroke="currentColor" stroke-width="1.8" stroke-linecap="round" '
             'stroke-linejoin="round">')
NAV_ICONS = {
    nav.INICIO: _SVG_OPEN + '<path d="M5 12l-2 0l9 -9l9 9l-2 0"/>'
                '<path d="M5 12v7a2 2 0 0 0 2 2h10a2 2 0 0 0 2 -2v-7"/>'
                '<path d="M9 21v-6a2 2 0 0 1 2 -2h2a2 2 0 0 1 2 2v6"/></svg>',
    nav.ESTRATEGIAS: _SVG_OPEN + '<rect x="4" y="4" width="6" height="6" rx="1"/>'
                '<rect x="14" y="4" width="6" height="6" rx="1"/>'
                '<rect x="4" y="14" width="6" height="6" rx="1"/>'
                '<rect x="14" y="14" width="6" height="6" rx="1"/></svg>',
    nav.RESULTADOS: _SVG_OPEN + '<path d="M3 17l6 -6l4 4l8 -8"/>'
                '<path d="M14 7l7 0l0 7"/></svg>',
    nav.PERFIL: _SVG_OPEN + '<path d="M8 7a4 4 0 1 0 8 0a4 4 0 0 0 -8 0"/>'
                '<path d="M6 21v-2a4 4 0 0 1 4 -4h4a4 4 0 0 1 4 4v2"/></svg>',
}
NAV_LABELS = {nav.INICIO: "Inicio", nav.ESTRATEGIAS: "Estrategias",
              nav.RESULTADOS: "Resultados", nav.PERFIL: "Perfil"}
NAV_SLUG = {nav.INICIO: "inicio", nav.ESTRATEGIAS: "estrategias",
            nav.RESULTADOS: "resultados", nav.PERFIL: "perfil"}


def _barra_inferior(activo):
    """Barra de navegación inferior FLOTANTE (fija abajo, como app nativa)."""
    grupo = nav.ESTRATEGIAS if activo in nav.MODULOS_ESTRATEGIA else activo
    with st.container(key="bottomnav"):
        # Perfil ya NO va aquí: se llega por el avatar (arriba a la derecha).
        cols = st.columns(3)
        for col, destino in zip(cols, [nav.INICIO, nav.ESTRATEGIAS, nav.RESULTADOS]):
            es_activo = (grupo == destino)
            color = "#6C63FF" if es_activo else "#7B8494"
            col.markdown(
                f"<div style='text-align:center;color:{color};line-height:1;'>{NAV_ICONS[destino]}</div>",
                unsafe_allow_html=True)
            slug = NAV_SLUG[destino]
            key = f"navA_{slug}" if es_activo else f"navx_{slug}"
            if col.button(NAV_LABELS[destino], key=key, use_container_width=True):
                # Navegar si no estás EXACTAMENTE en esa página (aunque el grupo esté resaltado).
                if activo != destino:
                    nav.goto(destino)


# ── Estado de navegación ──
st.session_state.setdefault("nav", nav.INICIO)
if "_goto" in st.session_state:
    st.session_state["nav"] = st.session_state.pop("_goto")
modulo = st.session_state["nav"]

# Al ENTRAR a Resultados (cambio de página, no reruns internos), abre siempre en
# "Posiciones actuales" — no en "Cargar Excel". Dentro de la vista, la pestaña que
# elijas se respeta.
if modulo != st.session_state.get("_modulo_previo"):
    if modulo == nav.RESULTADOS:
        st.session_state["res_view"] = "📊 Posiciones actuales"
st.session_state["_modulo_previo"] = modulo

# Aplicar el modo (real/demo) guardado a la capa de datos
db_utils.set_modo(st.session_state.get("_modo_actual", "real"))

# ── Enrutado de vistas ──
if modulo == nav.INICIO:
    render_inicio()
elif modulo == nav.ESTRATEGIAS:
    render_estrategias()
elif modulo == nav.DCA:
    render_dca()
elif modulo == nav.DIV:
    render_dividendos()
elif modulo == nav.OBJ:
    render_objetivos()
elif modulo == nav.FIB:
    render_fibras()
elif modulo == nav.COPY:
    render_copytrading()
elif modulo == nav.RESULTADOS:
    render_resultados()
elif modulo == nav.PERFIL:
    render_perfil()
elif modulo == nav.AGENDA:
    render_agenda()
elif modulo == nav.IMPORTAR:
    render_importar()
else:
    render_inicio()

# ── Barra de navegación inferior ──
_barra_inferior(modulo)
