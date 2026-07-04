import pandas as pd
import yahooquery as yq
import yfinance as yf
import streamlit as st

CATALOGO_LOCAL = [
    # BMV
    {"ticker": "AMXL.MX",    "nombre": "América Móvil",                "mercado": "BMV"},
    {"ticker": "FEMSA.MX",   "nombre": "FEMSA",                         "mercado": "BMV"},
    {"ticker": "WALMEX.MX",  "nombre": "Walmart de México",             "mercado": "BMV"},
    {"ticker": "GFNORTEO.MX","nombre": "Banorte",                       "mercado": "BMV"},
    {"ticker": "CEMEX.MX",   "nombre": "CEMEX",                         "mercado": "BMV"},
    {"ticker": "BIMBOA.MX",  "nombre": "Bimbo",                         "mercado": "BMV"},
    {"ticker": "ALSEA.MX",   "nombre": "Alsea",                         "mercado": "BMV"},
    {"ticker": "GRUMAB.MX",  "nombre": "Gruma",                         "mercado": "BMV"},
    {"ticker": "KIMBERA.MX", "nombre": "Kimberly-Clark México",         "mercado": "BMV"},
    {"ticker": "TLEVICPO.MX","nombre": "Televisa",                      "mercado": "BMV"},
    {"ticker": "GCARSOA1.MX","nombre": "Grupo Carso",                   "mercado": "BMV"},
    {"ticker": "BOLSAA.MX",  "nombre": "Bolsa Mexicana de Valores",     "mercado": "BMV"},
    {"ticker": "GAPB.MX",    "nombre": "Grupo Aeroportuario del Pac.",  "mercado": "BMV"},
    {"ticker": "ASURB.MX",   "nombre": "Grupo Aeroportuario del Sur",   "mercado": "BMV"},
    {"ticker": "OMAB.MX",    "nombre": "Grupo Aeroportuario del Cen.",  "mercado": "BMV"},
    {"ticker": "PINFRA.MX",  "nombre": "Pinfra",                        "mercado": "BMV"},
    {"ticker": "MEGACPO.MX", "nombre": "Megacable",                     "mercado": "BMV"},
    {"ticker": "CUERVO.MX",  "nombre": "José Cuervo",                   "mercado": "BMV"},
    {"ticker": "VESTA.MX",   "nombre": "Vesta",                         "mercado": "BMV"},
    {"ticker": "VOLARA.MX",  "nombre": "Volaris",                       "mercado": "BMV"},
    {"ticker": "Q.MX",       "nombre": "Quálitas",                      "mercado": "BMV"},
    {"ticker": "GENTERA.MX", "nombre": "Gentera",                       "mercado": "BMV"},
    {"ticker": "SORIANAB.MX","nombre": "Soriana",                       "mercado": "BMV"},
    {"ticker": "CHDRAUIB.MX","nombre": "Chedraui",                      "mercado": "BMV"},
    # FIBRAs
    {"ticker": "FUNO11.MX",  "nombre": "FIBRA UNO",                     "mercado": "FIBRA"},
    {"ticker": "FIBRAMQ.MX", "nombre": "FIBRA Macquarie",               "mercado": "FIBRA"},
    {"ticker": "FSHOP13.MX", "nombre": "FIBRA Shop",                    "mercado": "FIBRA"},
    {"ticker": "FIHO12.MX",  "nombre": "FIBRA Hotel",                   "mercado": "FIBRA"},
    {"ticker": "FINN13.MX",  "nombre": "FIBRA INN",                     "mercado": "FIBRA"},
    {"ticker": "TERRA13.MX", "nombre": "FIBRA Terra",                   "mercado": "FIBRA"},
    {"ticker": "DANHOS13.MX","nombre": "FIBRA Danhos",                  "mercado": "FIBRA"},
    # SIC
    {"ticker": "AAPL",  "nombre": "Apple Inc.",                         "mercado": "SIC/NASDAQ"},
    {"ticker": "MSFT",  "nombre": "Microsoft Corporation",              "mercado": "SIC/NASDAQ"},
    {"ticker": "NVDA",  "nombre": "NVIDIA Corporation",                 "mercado": "SIC/NASDAQ"},
    {"ticker": "GOOGL", "nombre": "Alphabet (Google)",                  "mercado": "SIC/NASDAQ"},
    {"ticker": "AMZN",  "nombre": "Amazon.com Inc.",                    "mercado": "SIC/NASDAQ"},
    {"ticker": "META",  "nombre": "Meta Platforms",                     "mercado": "SIC/NASDAQ"},
    {"ticker": "TSLA",  "nombre": "Tesla Inc.",                         "mercado": "SIC/NASDAQ"},
    {"ticker": "AVGO",  "nombre": "Broadcom Inc.",                      "mercado": "SIC/NASDAQ"},
    {"ticker": "NFLX",  "nombre": "Netflix Inc.",                       "mercado": "SIC/NASDAQ"},
    {"ticker": "AMD",   "nombre": "Advanced Micro Devices",             "mercado": "SIC/NASDAQ"},
    {"ticker": "JPM",   "nombre": "JPMorgan Chase",                     "mercado": "SIC/NYSE"},
    {"ticker": "V",     "nombre": "Visa Inc.",                          "mercado": "SIC/NYSE"},
    {"ticker": "JNJ",   "nombre": "Johnson & Johnson",                  "mercado": "SIC/NYSE"},
    {"ticker": "WMT",   "nombre": "Walmart Inc.",                       "mercado": "SIC/NYSE"},
    {"ticker": "KO",    "nombre": "Coca-Cola Company",                  "mercado": "SIC/NYSE"},
    {"ticker": "BAC",   "nombre": "Bank of America",                    "mercado": "SIC/NYSE"},
    {"ticker": "PG",    "nombre": "Procter & Gamble",                   "mercado": "SIC/NYSE"},
    {"ticker": "DIS",   "nombre": "Walt Disney Company",                "mercado": "SIC/NYSE"},
    {"ticker": "NKE",   "nombre": "Nike Inc.",                          "mercado": "SIC/NYSE"},
    {"ticker": "LLY",   "nombre": "Eli Lilly",                          "mercado": "SIC/NYSE"},
    # ETFs
    {"ticker": "SPY",   "nombre": "SPDR S&P 500 ETF",                   "mercado": "ETF"},
    {"ticker": "VOO",   "nombre": "Vanguard S&P 500 ETF",               "mercado": "ETF"},
    {"ticker": "VTI",   "nombre": "Vanguard Total Stock Market ETF",    "mercado": "ETF"},
    {"ticker": "QQQ",   "nombre": "Invesco QQQ (NASDAQ-100)",           "mercado": "ETF"},
    {"ticker": "SCHD",  "nombre": "Schwab US Dividend Equity ETF",      "mercado": "ETF"},
    {"ticker": "VYM",   "nombre": "Vanguard High Dividend Yield ETF",   "mercado": "ETF"},
    {"ticker": "JEPI",  "nombre": "JPMorgan Equity Premium Income ETF", "mercado": "ETF"},
    {"ticker": "JEPQ",  "nombre": "JPMorgan Nasdaq Equity Prem. ETF",   "mercado": "ETF"},
    {"ticker": "GLD",   "nombre": "SPDR Gold Shares ETF",               "mercado": "ETF"},
    {"ticker": "IWM",   "nombre": "iShares Russell 2000 ETF",           "mercado": "ETF"},
    {"ticker": "VIG",   "nombre": "Vanguard Dividend Appreciation ETF", "mercado": "ETF"},
    {"ticker": "XLK",   "nombre": "Technology Select Sector SPDR ETF",  "mercado": "ETF"},
    {"ticker": "ARKK",  "nombre": "ARK Innovation ETF",                 "mercado": "ETF"},
    {"ticker": "IVV",   "nombre": "iShares Core S&P 500 ETF",           "mercado": "ETF"},
    {"ticker": "AGG",   "nombre": "iShares Core US Aggregate Bond ETF", "mercado": "ETF"},
]

@st.cache_data(ttl=86400)
def _get_catalogo() -> pd.DataFrame:
    return pd.DataFrame(CATALOGO_LOCAL)

def buscar_local(query: str) -> list[dict]:
    if not query or len(query) < 1:
        return []
    q = query.strip().upper()
    df = _get_catalogo()
    mask = (
        df["ticker"].str.upper().str.contains(q, na=False) |
        df["nombre"].str.upper().str.contains(q, na=False)
    )
    return df[mask].to_dict("records")

def buscar_yahoo(query: str, max_results: int = 8) -> list[dict]:
    if not query or len(query) < 2:
        return []
    try:
        data = yq.search(query)
        quotes = data.get("quotes", [])
        resultados = []
        for q in quotes[:max_results]:
            tipo = q.get("typeDisp", q.get("quoteType", ""))
            mercado = q.get("exchange", q.get("exchDisp", "—"))
            resultados.append({
                "ticker": q.get("symbol", ""),
                "nombre": q.get("longname") or q.get("shortname") or q.get("symbol", ""),
                "mercado": f"{mercado} · {tipo}",
            })
        return resultados
    except Exception:
        return []

def buscar_tickers(query: str, max_results: int = 10) -> list[dict]:
    locales = buscar_local(query)
    tickers_vistos = {r["ticker"] for r in locales}
    yahoo = buscar_yahoo(query, max_results=max_results)
    for r in yahoo:
        if r["ticker"] and r["ticker"] not in tickers_vistos:
            locales.append(r)
            tickers_vistos.add(r["ticker"])
    return locales[:max_results]

def _desde_cache(cache: dict) -> dict:
    return {
        "ticker": cache["ticker"],
        "nombre": cache.get("nombre") or cache["ticker"],
        "precio": cache["precio"],
        "moneda": cache.get("moneda") or "USD",
        "mercado": cache.get("mercado") or "—",
        "cambio_pct": cache.get("cambio_pct") or 0.0,
    }


@st.cache_data(ttl=300, show_spinner=False)
def get_precio_actual(ticker: str) -> dict | None:
    from utils import db_utils  # import local para evitar dependencias circulares

    # 1) Si hay un precio guardado y fresco (<5 min), úsalo YA — instantáneo,
    #    incluso justo después de reiniciar la app (sin tocar internet).
    cache = db_utils.leer_precio(ticker)
    if cache and db_utils.edad_precio_segundos(cache["actualizado"]) < 300:
        return _desde_cache(cache)

    # 2) Bajar el precio en vivo y guardarlo para la próxima.
    try:
        p = yq.Ticker(ticker).price
        if not p or ticker not in p or isinstance(p[ticker], str):
            raise ValueError("sin datos")
        d = p[ticker]
        res = {
            "ticker": ticker,
            "nombre": d.get("longName") or d.get("shortName") or ticker,
            "precio": round(d.get("regularMarketPrice", 0), 2),
            "moneda": d.get("currency", "USD"),
            "mercado": d.get("exchangeName", "—"),
            "cambio_pct": round(d.get("regularMarketChangePercent", 0) * 100, 2),
        }
        db_utils.guardar_precio(res)
        return res
    except Exception:
        try:
            info = yf.Ticker(ticker).fast_info
            res = {"ticker": ticker, "nombre": ticker,
                   "precio": round(info.last_price, 2),
                   "moneda": "USD", "mercado": "—", "cambio_pct": 0.0}
            db_utils.guardar_precio(res)
            return res
        except Exception:
            # 3) Sin internet o error: mejor mostrar el último precio conocido que nada.
            return _desde_cache(cache) if cache else None

def get_precios_varios(tickers: list):
    """#3 · Pide en UNA sola petición los precios que hagan falta y los guarda en la base.

    Los que ya están frescos (<5 min) no se vuelven a pedir. No devuelve nada:
    solo 'precalienta' la base para que cada get_precio_actual la lea al instante.
    """
    from utils import db_utils
    unicos = list(dict.fromkeys([t for t in tickers if t]))  # sin repetir ni vacíos
    pendientes = []
    for t in unicos:
        c = db_utils.leer_precio(t)
        if not (c and db_utils.edad_precio_segundos(c["actualizado"]) < 300):
            pendientes.append(t)
    if not pendientes:
        return  # todo está fresco, ni un viaje a internet
    try:
        data = yq.Ticker(pendientes).price  # {ticker: {...}} en una sola petición
        if not isinstance(data, dict):
            return
        for t in pendientes:
            d = data.get(t)
            if not d or isinstance(d, str):
                continue
            db_utils.guardar_precio({
                "ticker": t,
                "nombre": d.get("longName") or d.get("shortName") or t,
                "precio": round(d.get("regularMarketPrice", 0), 2),
                "moneda": d.get("currency", "USD"),
                "mercado": d.get("exchangeName", "—"),
                "cambio_pct": round(d.get("regularMarketChangePercent", 0) * 100, 2),
            })
    except Exception:
        pass  # si el lote falla, cada precio individual hará su intento/último-conocido


@st.cache_data(ttl=300, show_spinner=False)
def get_tipo_cambio_actual() -> float:
    """Tipo de cambio USD/MXN actual (pesos por dólar). Fallback 17.15."""
    try:
        info = yf.Ticker("MXN=X").fast_info
        fx = float(info.last_price)
        if fx > 1:
            return round(fx, 4)
    except Exception:
        pass
    return 17.15


def widget_buscador(key: str = "ticker_search") -> dict | None:
    query = st.text_input(
        label="Buscar emisora",
        placeholder="Escribe ticker o nombre — ej: NVDA, Apple, FUNO, Femsa...",
        label_visibility="collapsed",
        key=f"{key}_input",
    )
    if not query or len(query.strip()) < 2:
        st.caption("Mínimo 2 caracteres · BMV · SIC · ETFs · FIBRAs · mercados globales")
        return None
    with st.spinner("Buscando..."):
        resultados = buscar_tickers(query.strip())
    if not resultados:
        st.warning(f"No se encontraron resultados para '{query}'")
        return None
    opciones = {
        f"{r['ticker']}  —  {r['nombre']}  [{r['mercado']}]": r["ticker"]
        for r in resultados
    }
    seleccion_label = st.selectbox(
        "Selecciona la emisora", list(opciones.keys()), key=f"{key}_select",
    )
    ticker_sel = opciones[seleccion_label]
    with st.spinner(f"Obteniendo precio de {ticker_sel}..."):
        datos = get_precio_actual(ticker_sel)
    if not datos:
        st.error(f"No se pudo obtener el precio de {ticker_sel}.")
        return None
    from utils.seguridad import esc
    cambio_color = "#1D9E75" if datos["cambio_pct"] >= 0 else "#A32D2D"
    cambio_signo = "+" if datos["cambio_pct"] >= 0 else ""
    # Escapar datos externos (Yahoo) antes de meterlos al HTML (anti-XSS)
    tk_s, nom_s = esc(datos["ticker"]), esc(datos["nombre"])
    mer_s, mon_s = esc(datos["mercado"]), esc(datos["moneda"])
    st.markdown(f"""
    <div style="background:#F8F9FC;border:0.5px solid #E2E6EE;border-radius:10px;
                padding:12px 16px;margin:10px 0;display:flex;align-items:center;gap:14px;">
        <div style="width:38px;height:38px;background:#6C63FF;border-radius:9px;
                    display:flex;align-items:center;justify-content:center;
                    color:white;font-size:12px;font-weight:600;flex-shrink:0;">
            {esc(ticker_sel[:2].upper())}
        </div>
        <div style="flex:1;">
            <div style="font-size:14px;font-weight:600;color:#1a1a2e;">{tk_s}</div>
            <div style="font-size:11px;color:#9DA5B8;">{nom_s} · {mer_s}</div>
        </div>
        <div style="text-align:right;">
            <div style="font-size:15px;font-weight:600;color:#1D9E75;">
                {datos['precio']:,.2f} {mon_s}
            </div>
            <div style="font-size:11px;color:{cambio_color};">
                {cambio_signo}{datos['cambio_pct']:.2f}% hoy
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    return datos
