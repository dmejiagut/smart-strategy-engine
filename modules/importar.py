"""Vista para importar compras/ventas masivamente desde un Excel."""
from datetime import date
import streamlit as st

from utils import excel_io
from utils.resumen_utils import invalidar_resumen


def render_importar():
    st.markdown("""
    <div style="margin-bottom:12px;">
        <h2 style="font-size:20px;font-weight:600;color:#1a1a2e;margin:0;">📥 Cargar desde Excel</h2>
        <p style="font-size:12px;color:#9DA5B8;margin:4px 0 0;">Carga muchas compras y ventas de una sola vez desde un Excel</p>
    </div>
    """, unsafe_allow_html=True)

    # ── Paso 1: descargar plantilla ──
    with st.container(border=True):
        st.markdown("**1. Descarga la plantilla**")
        st.caption("Trae una pestaña por cada estrategia que tienes guardada. Llénala con calma.")
        try:
            plantilla = excel_io.generar_plantilla()
            st.download_button(
                "⬇ Descargar plantilla Excel", data=plantilla,
                file_name=f"Plantilla_SSE_{date.today()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True)
        except Exception as exc:
            st.error(f"No se pudo generar la plantilla: {exc}")

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    # ── Paso 2: subir Excel lleno ──
    with st.container(border=True):
        st.markdown("**2. Sube tu Excel lleno**")
        st.caption("Se cargarán todas las compras y ventas que hayas escrito.")
        archivo = st.file_uploader("Sube el Excel", type=["xlsx"],
                                   label_visibility="collapsed", key="up_excel")
        if archivo is not None:
            if st.button("📤 Cargar movimientos", type="primary", use_container_width=True):
                with st.spinner("Procesando tu Excel..."):
                    res = excel_io.importar_excel(archivo)
                invalidar_resumen()  # recalcula el resumen (los precios siguen cacheados)
                if res["insertadas"]:
                    st.success(f"✅ {res['insertadas']} movimientos cargados.")
                    for hoja, n in res["por_estrategia"].items():
                        st.caption(f"• {hoja}: {n} movimiento(s)")
                else:
                    st.info("No se cargó ningún movimiento. Revisa que llenaste las tablas.")
                if res["errores"]:
                    st.warning("Algunas filas no se cargaron:")
                    for e in res["errores"][:25]:
                        st.caption(f"⚠️ {e}")

    st.caption("Copy Trading no se importa por aquí; se registra dentro de la app.")
