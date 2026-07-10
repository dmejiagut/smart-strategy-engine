"""Componentes compartidos para las tarjetas de estrategia (todos los módulos):
tarjeta con 4 botones (Detalles · Compra · Venta · 🗑), formulario de venta unificado
y la sección de 'Ventas registradas' con su % de rendimiento.
"""
from datetime import date
import streamlit as st

from utils.comisiones import comision_desde_perfil
from utils import db_utils
from utils.resumen_utils import invalidar_resumen
from utils.seguridad import esc

GREEN = "#1D9E75"
RED = "#A32D2D"


def seccion(label: str):
    st.markdown(f"""
    <div style="border-top:1px solid #E8ECF4;margin:16px 0 8px;padding-top:12px;
                font-size:11px;font-weight:600;color:#6C63FF;
                letter-spacing:.07em;text-transform:uppercase;">{label}</div>
    """, unsafe_allow_html=True)


def barra_pasos(step: int, pasos: list):
    """Barra de progreso del wizard (mismo estilo en todas las estrategias).

    step: número del paso actual (1-based). pasos: lista de nombres, ej.
    ["1. Emisora", "2. Análisis", "3. Confirmar"].
    """
    cols = st.columns(len(pasos))
    for i, (col, nombre) in enumerate(zip(cols, pasos), start=1):
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


def venta_form(modulo: str, eid: int, ticker: str):
    disp = db_utils.titulos_disponibles(modulo, eid)
    st.markdown(f"Disponibles para vender: **{disp}** título(s)")
    if disp <= 0:
        st.info("No tienes títulos disponibles. Registra una compra primero.")
        return
    with st.form(f"vform_{modulo}_{eid}", clear_on_submit=True):
        c1, c2 = st.columns(2)
        fecha_v = c1.date_input("Fecha de venta", value=date.today(),
                                max_value=date.today(), key=f"vf_{modulo}_{eid}")
        tit_v = c2.number_input("Acciones a vender", min_value=1, max_value=int(disp),
                                value=1, step=1, key=f"vt_{modulo}_{eid}")
        precio_v = st.number_input("Precio de venta (MXN)", min_value=0.01, value=100.0,
                                   step=0.01, format="%.2f", key=f"vp_{modulo}_{eid}")
        st.caption("La comisión se calcula automáticamente con el % de tu perfil.")
        ok = st.form_submit_button("➖ Registrar venta", type="primary", use_container_width=True)
    if ok:
        com = comision_desde_perfil(int(tit_v) * float(precio_v))
        r = db_utils.registrar_venta(modulo, eid, ticker, fecha_v, int(tit_v),
                                     float(precio_v), comision=com)
        if r["ok"]:
            invalidar_resumen()
            g = r["ganancia"]
            signo = "ganancia" if g >= 0 else "pérdida"
            st.success(f"✅ Venta: {int(tit_v)} de {ticker} a ${precio_v:,.2f} MXN · "
                       f"{signo} de ${abs(g):,.2f} MXN")
            st.rerun()
        else:
            st.error(r["msg"])


def ventas_registradas(modulo: str, eid: int):
    """Historial de ventas de la estrategia con su % de rendimiento (reusable)."""
    ventas = db_utils.load_ventas_cerradas(modulo, eid)
    if not ventas:
        return
    seccion("Ventas registradas")
    enc = st.columns([1.3, 0.9, 1.2, 1.3, 1.0])
    for c, h in zip(enc, ["Fecha", "Tít.", "Precio", "Ganancia", "Rend."]):
        c.markdown(f"<div style='font-size:11px;color:#9DA5B8;font-weight:600;'>{h}</div>",
                   unsafe_allow_html=True)
    tot_gan = 0.0
    for v in ventas:
        tot_gan += v["ganancia"]
        rc = GREEN if v["ganancia"] >= 0 else RED
        rend = (v["ganancia"] / v["costo_base"] * 100) if v["costo_base"] else 0.0
        cols = st.columns([1.3, 0.9, 1.2, 1.3, 1.0])
        cols[0].markdown(f"<div style='font-size:12.5px;padding:3px 0;'>{str(v['fecha'])[:10]}</div>", unsafe_allow_html=True)
        cols[1].markdown(f"<div style='font-size:12.5px;padding:3px 0;'>{v['titulos']}</div>", unsafe_allow_html=True)
        cols[2].markdown(f"<div style='font-size:12.5px;padding:3px 0;'>${v['precio']:,.2f}</div>", unsafe_allow_html=True)
        cols[3].markdown(f"<div style='font-size:12.5px;font-weight:600;color:{rc};padding:3px 0;'>${v['ganancia']:,.2f}</div>", unsafe_allow_html=True)
        cols[4].markdown(f"<div style='font-size:12.5px;font-weight:600;color:{rc};padding:3px 0;'>{rend:+.1f}%</div>", unsafe_allow_html=True)
    col_t = GREEN if tot_gan >= 0 else RED
    st.markdown(f"<div style='font-size:12px;margin-top:6px;'>Ganancia realizada total: "
                f"<b style='color:{col_t};'>${tot_gan:,.2f} MXN</b></div>", unsafe_allow_html=True)


def _abrir(titulo: str, render_fn, large=False):
    @st.dialog(titulo, width=("large" if large else "small"))
    def _d():
        render_fn()
    _d()


def _cargando(fn, e):
    """Muestra 'Cargando datos…' mientras se preparan los datos del detalle."""
    with st.spinner("Cargando datos…"):
        fn(e)


def _abrir_ayuda(titulo, intro, items, nota=""):
    @st.dialog(titulo, width="large")
    def _d():
        if intro:
            st.markdown(f"<p style='font-size:14px;color:#4A5066;line-height:1.6;'>{intro}</p>",
                        unsafe_allow_html=True)
        for t, desc in items:
            st.markdown(
                f"<div style='margin-bottom:10px;'><b style='font-size:13px;color:#1a1a2e;'>{t}</b>"
                f"<div style='font-size:12.5px;color:#7B8494;line-height:1.5;'>{desc}</div></div>",
                unsafe_allow_html=True)
        if nota:
            st.markdown("<div style='border-top:1px solid #E8ECF4;margin:8px 0;'></div>",
                        unsafe_allow_html=True)
            st.markdown(f"<p style='font-size:12.5px;color:#4A5066;line-height:1.5;'>{nota}</p>",
                        unsafe_allow_html=True)
        st.caption("Herramienta educativa, no es asesoría financiera.")
    _d()


def boton_ayuda(key, titulo, intro, items, nota=""):
    """Botón chico '¿Cómo funciona?' que abre una ventana con las indicaciones."""
    col = st.columns([1, 2])[0]  # botón pequeño, no de ancho completo
    if col.button("❓ ¿Cómo funciona?", key=key, use_container_width=True):
        _abrir_ayuda(titulo, intro, items, nota)


def _abrir_borrar(ticker, eid, delete_fn):
    @st.dialog("Borrar estrategia")
    def _d():
        st.warning(f"¿Borrar la estrategia **{ticker}**?")
        st.caption("Se eliminan sus compras registradas. El historial de ventas se conserva.")
        if st.button("Sí, borrar", type="primary", use_container_width=True, key=f"delok_{eid}"):
            delete_fn(eid)
            invalidar_resumen()
            st.rerun()
    _d()


def card(e: dict, modulo: str, icono: str, titulo: str, subtitulo: str,
         detalle_fn, compra_fn, delete_fn, extra_html: str = "", venta_fn=None):
    """Tarjeta de estrategia con 4 botones: Detalles · Compra · Venta · 🗑.

    venta_fn opcional: si se pasa, se usa para el modal de Venta (p.ej. 'Por Objetivos'
    que vende por lote). Si no, se usa el formulario de venta unificado.
    """
    eid = e["id"]
    compras = db_utils._compras_de(modulo, eid)
    comprados = sum(int(c["titulos"]) for c in compras)
    disp = db_utils.titulos_disponibles(modulo, eid)
    if comprados > 0:
        acc_txt = f"🛒 {comprados} compradas · {disp} disponibles"
        acc_color = GREEN
    else:
        acc_txt = "🛒 Sin compras aún"
        acc_color = "#9DA5B8"

    with st.container(border=True):
        st.markdown(
            f"<div style='font-size:15px;'>{icono} "
            f"<b style='color:#1a1a2e;'>{esc(titulo)}</b> "
            f"<span style='color:#9DA5B8;font-size:13px;'>{esc(subtitulo)}</span></div>"
            f"<div style='font-size:12px;color:{acc_color};font-weight:600;margin-top:3px;'>{acc_txt}</div>",
            unsafe_allow_html=True)
        if extra_html:
            st.markdown(extra_html, unsafe_allow_html=True)
        b1, b2, b3, b4 = st.columns([1.3, 1.2, 1.2, 0.6])
        if b1.button("Detalles", key=f"det_{modulo}_{eid}", use_container_width=True):
            _abrir(f"{icono} {titulo}", lambda: _cargando(detalle_fn, e), large=True)
        if b2.button("Compra", key=f"cmp_{modulo}_{eid}", use_container_width=True):
            _abrir(f"Registrar compra · {titulo}", lambda: compra_fn(e))
        if b3.button("Venta", key=f"vta_{modulo}_{eid}", use_container_width=True):
            if venta_fn is not None:
                _abrir(f"Registrar venta · {titulo}", lambda: venta_fn(e), large=True)
            else:
                _abrir(f"Registrar venta · {titulo}", lambda: venta_form(modulo, eid, e.get("ticker", titulo)))
        if b4.button("🗑", key=f"del_{modulo}_{eid}", use_container_width=True, help="Borrar estrategia"):
            _abrir_borrar(titulo, eid, delete_fn)