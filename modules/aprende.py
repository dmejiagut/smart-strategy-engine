"""Sección 'Aprende' 📚 — mini-lecciones y glosario para principiantes.

Objetivo: que alguien que nunca ha invertido entienda los conceptos ANTES de
tocar una estrategia, con el lenguaje de la app (es-MX) y ligas directas a
cada módulo para practicar lo aprendido.
"""
import streamlit as st

from utils import nav

PURPLE = "#6C63FF"

# ── Mini-lecciones (una por estrategia + fundamentos) ─────────────────────────
LECCIONES = [
    {
        "icono": "🏁", "titulo": "Antes de invertir tu primer peso",
        "resumen": "Lo mínimo que necesitas para empezar bien.",
        "puntos": [
            ("Abre una cuenta en una casa de bolsa", "Es como un banco, pero para invertir (GBM, Kuspit, Bursanet…). Sin ella no puedes comprar acciones."),
            ("Ten un guardadito aparte", "Nunca inviertas el dinero de la renta o la comida. Invierte solo lo que puedas dejar quieto varios años."),
            ("Define tu meta y tu plazo", "¿Para qué inviertes y cuándo lo vas a necesitar? Eso decide qué estrategia te conviene."),
            ("Empieza chiquito", "Más vale $500 al mes constantes que $10,000 una vez y abandonar. La constancia gana."),
        ],
        "destino": None,
    },
    {
        "icono": "📊", "titulo": "DCA — comprar poquito, siempre",
        "resumen": "La estrategia más tranquila para empezar.",
        "puntos": [
            ("¿Qué es?", "Comprar la MISMA cantidad cada cierto tiempo (ej. 2 acciones cada mes), suba o baje el precio."),
            ("¿Por qué funciona?", "Al comprar en las buenas y en las malas, tu precio promedio se suaviza: no dependes de 'atinarle' al mejor momento."),
            ("El enemigo es la emoción", "El DCA te protege de ti mismo: compras por calendario, no por pánico ni euforia."),
            ("Ideal para", "Principiantes y para metas de largo plazo (5+ años)."),
        ],
        "destino": nav.DCA,
    },
    {
        "icono": "💰", "titulo": "Dividendos — que tus acciones te paguen renta",
        "resumen": "Ingresos periódicos por ser dueño.",
        "puntos": [
            ("¿Qué es un dividendo?", "Una parte de las ganancias que la empresa reparte a sus dueños (tú, al tener acciones). Suele pagarse cada 3 meses."),
            ("El 'yield'", "Cuánto te paga al año como % del precio. Un yield de 3% en $10,000 son ≈ $300 al año."),
            ("Ojo con la ex-date", "Debes tener la acción ANTES de esa fecha para recibir el siguiente pago."),
            ("Yield altísimo = foco rojo", "A veces el yield es alto porque el precio se desplomó. Revisa la salud del dividendo en la app."),
        ],
        "destino": nav.DIV,
    },
    {
        "icono": "🏢", "titulo": "FIBRAs — bienes raíces desde la Bolsa",
        "resumen": "Ser 'casero' sin comprar un local.",
        "puntos": [
            ("¿Qué es una FIBRA?", "Un fideicomiso dueño de inmuebles (plazas, oficinas, naves industriales) que cotiza en la BMV. Compras CBFIs, que son como acciones."),
            ("Te pagan rentas", "Las FIBRAs están obligadas a repartir la mayor parte de sus rentas: recibes distribuciones periódicas."),
            ("Todo en pesos", "Se compran en MXN en la Bolsa Mexicana — sin tipo de cambio de por medio."),
            ("Ideal para", "Quien busca ingresos estables y quiere diversificar fuera de puras acciones."),
        ],
        "destino": nav.FIB,
    },
    {
        "icono": "🎯", "titulo": "Por Objetivos — compra abajo, vende arriba (con plan)",
        "resumen": "Trading con reglas escritas ANTES de entrar.",
        "puntos": [
            ("La regla de oro", "Decide tu precio de ENTRADA y de SALIDA antes de comprar. Sin plan escrito, las emociones deciden por ti."),
            ("Soportes y resistencias", "Zonas donde el precio históricamente rebota (soporte) o se atora (resistencia). Ayudan a elegir tus niveles."),
            ("La ganancia se planea", "Si entras en $100 y sales en $120, tu objetivo es +20%. Si eso no te alcanza, no era el trade."),
            ("Es la estrategia más activa", "Requiere revisar el mercado más seguido. Empieza con poco capital mientras aprendes."),
        ],
        "destino": nav.OBJ,
    },
    {
        "icono": "👥", "titulo": "Copy Trading — aprende copiando a los grandes",
        "resumen": "Replica carteras de inversionistas famosos.",
        "puntos": [
            ("¿De dónde salen los datos?", "Los fondos grandes de EE.UU. publican sus carteras cada trimestre (reportes '13F'). Son públicos, pero llegan con ~45 días de retraso."),
            ("Copiar ≠ garantizar", "Copias sus posiciones, no sus resultados: ellos entraron a otros precios y en otro momento."),
            ("Elige por afinidad de riesgo", "La app te dice si el estilo del experto encaja con TU perfil. Un Burry no es para un perfil conservador."),
            ("Empieza con la calculadora", "Antes de comprar, usa la 🧮 para ver cuántas acciones enteras te alcanzan con tu monto."),
        ],
        "destino": nav.COPY,
    },
    {
        "icono": "🧺", "titulo": "Riesgo y diversificación",
        "resumen": "No pongas todos los huevos en una canasta.",
        "puntos": [
            ("Diversificar", "Repartir tu dinero en varias empresas, sectores y estrategias. Si a una le va mal, las demás amortiguan."),
            ("Riesgo y rendimiento van juntos", "Lo que promete más rendimiento SIEMPRE trae más riesgo. No existe el 'mucho rendimiento sin riesgo' — eso es fraude."),
            ("Tu perfil manda", "Conservador, Moderado o Agresivo: defínelo en tu Perfil y la app te recomienda estrategias acordes."),
            ("La caída es parte del juego", "El mercado baja de vez en cuando. Tu plan (y no vender por pánico) es lo que te salva."),
        ],
        "destino": None,
    },
    {
        "icono": "🧾", "titulo": "Comisiones e impuestos — el costo de jugar",
        "resumen": "Lo que pagas por cada operación.",
        "puntos": [
            ("Comisión de la casa de bolsa", "Cada compra y venta cobra un % (típico ~0.25%). Parece poco, pero operar mucho lo multiplica."),
            ("El IVA va aparte", "A la comisión se le suma 16% de IVA. La app siempre calcula 'Comisión+IVA' con el % de tu perfil."),
            ("Ejemplo real", "Compra de $10,000 al 0.25%: $25 de comisión + $4 de IVA = $29. Ida y vuelta (comprar y vender) ≈ $58."),
            ("Impuestos sobre ganancias", "En México, las ganancias en Bolsa pagan impuestos (retención del 10% sobre la ganancia en ventas). Tu casa de bolsa emite constancia anual."),
        ],
        "destino": None,
    },
]

# ── Glosario (términos con definición simple) ─────────────────────────────────
GLOSARIO = [
    ("Acción", "Un pedacito de una empresa. Al comprarla te vuelves dueño de esa fracción."),
    ("Ticker (clave)", "Las letras con las que se identifica una acción en la Bolsa (AAPL = Apple, KO = Coca-Cola)."),
    ("BMV", "Bolsa Mexicana de Valores: el mercado donde se compran y venden acciones en México."),
    ("SIC", "Sistema Internacional de Cotizaciones: la sección de la BMV donde compras acciones extranjeras (Apple, Tesla…) desde México, en pesos, solo en acciones ENTERAS."),
    ("Casa de bolsa", "El intermediario con el que abres tu cuenta para invertir (GBM, Kuspit, Bursanet…)."),
    ("ETF", "Una canasta de muchas acciones que se compra como si fuera una sola (ej. SPY trae a las 500 empresas del S&P 500)."),
    ("FIBRA", "Fideicomiso de bienes raíces que cotiza en la BMV y reparte rentas. Sus títulos se llaman CBFIs."),
    ("CBFI", "Cada título de una FIBRA — el equivalente a una acción."),
    ("Dividendo", "Dinero que la empresa reparte a sus accionistas, normalmente cada trimestre."),
    ("Dividend yield", "Cuánto paga de dividendos al año como % del precio de la acción."),
    ("Ex-date", "Fecha límite: debes tener la acción ANTES de ese día para recibir el siguiente dividendo."),
    ("DCA", "Dollar Cost Averaging: invertir la misma cantidad cada cierto tiempo, sin importar el precio."),
    ("Precio promedio", "Lo que en promedio te ha costado cada acción, contando todas tus compras."),
    ("Plusvalía", "Lo que ha subido el valor de tu inversión y aún no cobras (ganancia 'en papel')."),
    ("Ganancia realizada", "La ganancia (o pérdida) que ya es real porque VENDISTE. En la app vive en Resultados."),
    ("Rendimiento", "Cuánto ha crecido tu dinero, en %. Si metiste $1,000 y vale $1,100, llevas +10%."),
    ("Comisión + IVA", "El cobro de tu casa de bolsa por operar (≈0.25%) más el 16% de IVA sobre esa comisión."),
    ("Tipo de cambio", "Cuántos pesos cuesta un dólar. Afecta tus acciones del SIC: si el dólar sube, tu inversión en pesos vale más."),
    ("Diversificar", "Repartir tu dinero en varias inversiones para no depender de una sola."),
    ("Perfil de riesgo", "Qué tanta variación aguantas sin vender por pánico: Conservador, Moderado o Agresivo."),
    ("Soporte / Resistencia", "Zonas de precio donde históricamente rebota (soporte) o se atora (resistencia). Base del análisis técnico."),
    ("Reporte 13F", "Documento trimestral público donde los fondos grandes de EE.UU. revelan su cartera (con ~45 días de retraso)."),
    ("Rebalancear", "Comprar/vender para regresar tu cartera a los pesos que planeaste (o a los del experto que copias)."),
    ("CETES", "Certificados de la Tesorería: le prestas al gobierno mexicano a una tasa fija. El punto de comparación 'sin riesgo' en México."),
]


def render_aprende():
    st.markdown("""
    <div style="margin-bottom:16px;">
        <h2 style="font-size:20px;font-weight:600;color:#1a1a2e;margin:0;">📚 Aprende a invertir</h2>
        <p style="font-size:12px;color:#9DA5B8;margin:4px 0 0;">Mini-lecciones y glosario — todo lo que necesitas para usar cada estrategia con confianza</p>
    </div>
    """, unsafe_allow_html=True)

    tab = st.segmented_control("Sección", ["🎓 Lecciones", "📖 Glosario"],
                               key="apr_tab", label_visibility="collapsed",
                               default="🎓 Lecciones")
    if tab == "📖 Glosario":
        _glosario()
    else:
        _lecciones()

    st.caption("Herramienta educativa, no es asesoría financiera.")


def _lecciones():
    st.caption(f"{len(LECCIONES)} lecciones de ~2 minutos. Empieza por la primera si eres nuevo.")
    for i, lec in enumerate(LECCIONES):
        with st.expander(f"{lec['icono']}  **{lec['titulo']}** — {lec['resumen']}"):
            for titulo, cuerpo in lec["puntos"]:
                st.markdown(
                    f"<div style='margin-bottom:10px;'>"
                    f"<div style='font-size:13px;font-weight:600;color:#1a1a2e;'>{titulo}</div>"
                    f"<div style='font-size:12.5px;color:#4A5066;line-height:1.55;'>{cuerpo}</div></div>",
                    unsafe_allow_html=True)
            if lec["destino"]:
                if st.button(f"Practicar en {lec['destino']} →", key=f"apr_go_{i}",
                             type="primary", use_container_width=True):
                    nav.goto(lec["destino"])


def _glosario():
    q = st.text_input("Buscar término", placeholder="Busca un término — ej: dividendo, CETES, ticker…",
                      label_visibility="collapsed", key="apr_buscar").strip().lower()
    terminos = [(t, d) for t, d in GLOSARIO
                if not q or q in t.lower() or q in d.lower()]
    if not terminos:
        st.info(f"No encontré '{q}' en el glosario. Prueba con otra palabra.")
        return
    st.caption(f"{len(terminos)} término(s)")
    for t, d in terminos:
        st.markdown(f"""
        <div style="background:#fff;border:0.5px solid #E8ECF4;border-radius:10px;
                    padding:10px 14px;margin-bottom:8px;">
            <div style="font-size:13px;font-weight:700;color:{PURPLE};">{t}</div>
            <div style="font-size:12.5px;color:#4A5066;line-height:1.5;margin-top:2px;">{d}</div>
        </div>
        """, unsafe_allow_html=True)
