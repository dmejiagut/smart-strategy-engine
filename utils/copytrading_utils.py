"""
Copy Trading: catálogo de inversionistas famosos y sus posiciones representativas
(basadas en reportes 13F públicos). El rendimiento del último año se calcula en
vivo con los precios reales de cada posición, ponderado por su peso en la cartera.
"""
import pandas as pd
import yfinance as yf
import streamlit as st

# Carteras representativas (pesos relativos; se normalizan en código).
# Basadas en reportes 13F públicos — pueden no reflejar el trimestre más reciente.
INVERSIONISTAS = [
    {"id": "buffett", "nombre": "Warren Buffett", "fondo": "Berkshire Hathaway",
     "estilo": "Value investing de largo plazo", "destacado": True,
     "holdings": [("AAPL", 26), ("AXP", 16), ("BAC", 11), ("KO", 9), ("CVX", 7),
                  ("OXY", 6), ("MCO", 4), ("KHC", 4), ("CB", 4), ("KR", 3)]},
    {"id": "wood", "nombre": "Cathie Wood", "fondo": "ARK Invest",
     "estilo": "Innovación disruptiva y tecnología", "destacado": True,
     "holdings": [("TSLA", 12), ("COIN", 10), ("ROKU", 8), ("PLTR", 7), ("HOOD", 7),
                  ("RKLB", 6), ("CRSP", 6), ("PATH", 6), ("TEM", 5), ("DKNG", 5)]},
    {"id": "lilu", "nombre": "Li Lu", "fondo": "Himalaya Capital",
     "estilo": "Value concentrado (discípulo de Munger)", "destacado": True,
     "holdings": [("GOOGL", 28), ("BAC", 24), ("BRK-B", 20), ("BABA", 18), ("OXY", 10)]},
    {"id": "dalio", "nombre": "Ray Dalio", "fondo": "Bridgewater Associates",
     "estilo": "Diversificación global / all weather", "destacado": True,
     "holdings": [("IVV", 8), ("GLD", 7), ("IEMG", 6), ("SPY", 6), ("PG", 5),
                  ("JNJ", 5), ("KO", 5), ("WMT", 5), ("COST", 5), ("META", 5)]},
    {"id": "ackman", "nombre": "Bill Ackman", "fondo": "Pershing Square",
     "estilo": "Activista concentrado", "destacado": True,
     "holdings": [("UBER", 18), ("BN", 17), ("HLT", 15), ("CMG", 14), ("QSR", 11),
                  ("GOOG", 11), ("NKE", 8), ("HHH", 6)]},
    {"id": "munger", "nombre": "Charlie Munger", "fondo": "Daily Journal (legado)",
     "estilo": "Value extremo, cartera mínima", "destacado": True,
     "holdings": [("BAC", 38), ("WFC", 28), ("BABA", 18), ("USB", 12), ("POST", 4)]},
    {"id": "burry", "nombre": "Michael Burry", "fondo": "Scion Asset Management",
     "estilo": "Contrarian / deep value (cartera muy cambiante)", "destacado": True,
     "holdings": [("BABA", 22), ("JD", 18), ("BIDU", 14), ("HCA", 12), ("CI", 10),
                  ("MOH", 8), ("BP", 8), ("REAL", 8)]},
    {"id": "fisher", "nombre": "Ken Fisher", "fondo": "Fisher Investments",
     "estilo": "Crecimiento de gran capitalización", "destacado": True,
     "holdings": [("AAPL", 14), ("MSFT", 14), ("NVDA", 13), ("AMZN", 12), ("GOOGL", 11),
                  ("META", 10), ("AVGO", 9), ("V", 6), ("MA", 6), ("ASML", 5)]},
    {"id": "blackrock", "nombre": "BlackRock", "fondo": "BlackRock (fondos equity)",
     "estilo": "Mega-cap diversificado", "destacado": True,
     "holdings": [("AAPL", 13), ("MSFT", 13), ("NVDA", 13), ("AMZN", 11), ("GOOGL", 10),
                  ("META", 10), ("AVGO", 9), ("BRK-B", 7), ("JPM", 7), ("LLY", 7)]},
    # ── No destacados: solo aparecen al buscar ──
    {"id": "klarman", "nombre": "Seth Klarman", "fondo": "Baupost Group",
     "estilo": "Value con enfoque en riesgo", "destacado": False,
     "holdings": [("LNG", 20), ("WBD", 16), ("LBTYA", 14), ("FI", 13), ("CRM", 12),
                  ("FLEX", 11), ("VEON", 8), ("WMB", 6)]},
    {"id": "tepper", "nombre": "David Tepper", "fondo": "Appaloosa Management",
     "estilo": "Oportunista / tecnología y China", "destacado": False,
     "holdings": [("BABA", 16), ("NVDA", 14), ("AMZN", 12), ("META", 12), ("MSFT", 10),
                  ("PDD", 10), ("GOOG", 10), ("ORCL", 8), ("UBER", 8)]},
    {"id": "druckenmiller", "nombre": "Stanley Druckenmiller", "fondo": "Duquesne Family Office",
     "estilo": "Macro y crecimiento", "destacado": False,
     "holdings": [("NVDA", 14), ("MSFT", 11), ("COHR", 10), ("NTRA", 9), ("TER", 9),
                  ("FLUT", 9), ("WMT", 8), ("MU", 8), ("KVYO", 7), ("TEVA", 7)]},
    {"id": "icahn", "nombre": "Carl Icahn", "fondo": "Icahn Enterprises",
     "estilo": "Activista", "destacado": False,
     "holdings": [("IEP", 48), ("CVI", 20), ("SWX", 12), ("BHC", 10), ("IFF", 10)]},
    {"id": "terry_smith", "nombre": "Terry Smith", "fondo": "Fundsmith",
     "estilo": "Calidad de gran capitalización", "destacado": False,
     "holdings": [("MSFT", 12), ("META", 11), ("PM", 10), ("SYK", 9), ("NVO", 9),
                  ("ADP", 8), ("IDXX", 8), ("WAT", 8), ("OTIS", 7), ("MCO", 7)]},
    {"id": "coleman", "nombre": "Chase Coleman", "fondo": "Tiger Global",
     "estilo": "Crecimiento tecnológico global", "destacado": False,
     "holdings": [("MSFT", 14), ("META", 13), ("NVDA", 12), ("SE", 10), ("AMZN", 10),
                  ("GOOG", 9), ("NU", 9), ("FLUT", 8), ("SPOT", 8)]},
    {"id": "loeb", "nombre": "Daniel Loeb", "fondo": "Third Point",
     "estilo": "Event-driven / activista", "destacado": False,
     "holdings": [("PCG", 12), ("AMZN", 11), ("META", 10), ("MSFT", 10), ("KKR", 9),
                  ("BABA", 8), ("TSM", 8), ("GOOG", 8), ("JCI", 8)]},
]


# Aproximación de cuánto representa el TOP 10 sobre el portafolio total de cada
# gestor (según su nivel de concentración conocido). Para fondos muy diversificados
# (Fisher, BlackRock) el top 10 es una fracción pequeña; para carteras concentradas
# (Ackman, Munger, Icahn) es casi todo.
COBERTURA_TOP10 = {
    "buffett": 90, "wood": 60, "lilu": 98, "dalio": 30, "ackman": 100,
    "munger": 100, "burry": 90, "fisher": 22, "blackrock": 10,
    "klarman": 80, "tepper": 75, "druckenmiller": 70, "icahn": 95,
    "terry_smith": 65, "coleman": 70, "loeb": 70,
}

# ── Historial de reportes 13F (para detectar "movimientos del experto") ──
# El reporte ACTUAL de cada inversionista es su lista `holdings` de arriba.
# Aquí guardamos el reporte del trimestre ANTERIOR; comparando ambos se ve qué
# compró, vendió o reajustó entre sus posiciones principales.
# NOTA: datos REPRESENTATIVOS con fines ilustrativos (basados en reportes 13F
# públicos, que se publican cada trimestre con retraso). Verifica en fuentes
# oficiales (SEC EDGAR) antes de operar. Un feed 13F en vivo es Fase 2.
TRIMESTRE_ACTUAL = "Q1 2026"
TRIMESTRE_ANTERIOR = "Q4 2025"

REPORTE_ANTERIOR = {
    "buffett": [("AAPL", 30), ("AXP", 15), ("BAC", 13), ("KO", 9), ("CVX", 8),
                ("OXY", 4), ("MCO", 4), ("KHC", 4), ("HPQ", 3), ("CB", 3), ("KR", 3)],
    "wood": [("TSLA", 15), ("COIN", 8), ("ROKU", 9), ("PLTR", 5), ("HOOD", 5),
             ("RKLB", 6), ("CRSP", 7), ("PATH", 6), ("ZM", 6), ("DKNG", 4)],
    "lilu": [("GOOGL", 30), ("BAC", 22), ("BRK-B", 20), ("BABA", 20), ("OXY", 8)],
    "dalio": [("IVV", 7), ("GLD", 6), ("IEMG", 6), ("SPY", 8), ("PG", 5),
              ("JNJ", 5), ("KO", 5), ("WMT", 4), ("COST", 5), ("GOOGL", 5)],
    "ackman": [("BN", 18), ("HLT", 16), ("CMG", 16), ("QSR", 12), ("GOOG", 12),
               ("NKE", 10), ("HHH", 6)],
    "burry": [("BKNG", 18), ("GOOGL", 16), ("MOH", 12), ("CI", 12), ("HCA", 12),
              ("PHM", 10), ("BABA", 10), ("JD", 10)],
    "fisher": [("AAPL", 15), ("MSFT", 14), ("NVDA", 11), ("AMZN", 12), ("GOOGL", 11),
               ("META", 9), ("AVGO", 8), ("V", 6), ("MA", 6), ("TSM", 5)],
    "blackrock": [("AAPL", 14), ("MSFT", 14), ("NVDA", 11), ("AMZN", 11), ("GOOGL", 10),
                  ("META", 10), ("AVGO", 8), ("BRK-B", 7), ("JPM", 7), ("V", 8)],
    # Munger (Daily Journal) es un legado: no se rebalancea → sin reporte anterior.
}


def movimientos_experto(inv: dict):
    """Compara el reporte 13F ACTUAL (inv['holdings']) con el ANTERIOR y devuelve
    qué AÑADIÓ, QUITÓ, AUMENTÓ o REDUJO el experto entre sus posiciones top.
    Devuelve None si no hay reporte anterior cargado."""
    prev = REPORTE_ANTERIOR.get(inv["id"])
    if not prev:
        return None
    cur = dict(normalizar_holdings(inv["holdings"]))
    old = dict(normalizar_holdings(prev))
    UMBRAL = 2.0  # puntos porcentuales para considerar un ajuste "relevante"
    anadidas, quitadas, subieron, bajaron = [], [], [], []
    for t in set(cur) | set(old):
        c, o = cur.get(t, 0.0), old.get(t, 0.0)
        if o < 0.5 <= c:
            anadidas.append((t, c))
        elif c < 0.5 <= o:
            quitadas.append((t, o))
        elif c - o >= UMBRAL:
            subieron.append((t, o, c))
        elif o - c >= UMBRAL:
            bajaron.append((t, o, c))
    return {
        "hay": bool(anadidas or quitadas or subieron or bajaron),
        "trimestre": TRIMESTRE_ACTUAL, "anterior": TRIMESTRE_ANTERIOR,
        "anadidas": sorted(anadidas, key=lambda x: -x[1]),
        "quitadas": sorted(quitadas, key=lambda x: -x[1]),
        "subieron": sorted(subieron, key=lambda x: -(x[2] - x[1])),
        "bajaron": sorted(bajaron, key=lambda x: -(x[1] - x[2])),
    }


def pesos_portafolio(inv: dict):
    """
    Devuelve (lista de (ticker, % del portafolio total), cobertura_total%).
    Escala los pesos relativos del top 10 por la cobertura estimada del gestor.
    """
    cob = COBERTURA_TOP10.get(inv["id"], 100)
    norm = normalizar_holdings(inv["holdings"])
    return [(t, w * cob / 100) for t, w in norm], cob


@st.cache_data(ttl=1800, show_spinner=False)
def get_price_return(ticker: str) -> dict:
    """Precio actual y rendimiento a 1 año de un ticker."""
    out = {"precio": None, "ret1y": None}
    try:
        h = yf.Ticker(ticker).history(period="1y")["Close"].dropna()
        if len(h) > 1:
            out["precio"] = float(h.iloc[-1])
            out["ret1y"] = (h.iloc[-1] / h.iloc[0] - 1) * 100
    except Exception:
        pass
    return out


def normalizar_holdings(holdings: list) -> list:
    """Convierte pesos relativos en porcentajes que suman 100."""
    total = sum(w for _, w in holdings)
    if total <= 0:
        return [(t, 0.0) for t, _ in holdings]
    return [(t, w / total * 100) for t, w in holdings]


@st.cache_data(ttl=1800, show_spinner=False)
def riesgo_cartera(holdings_tuple: tuple) -> dict:
    """Clasifica el nivel de riesgo de una cartera: concentración + dispersión + nº posiciones."""
    import statistics
    holds = normalizar_holdings(list(holdings_tuple))
    rets = []
    for tk, _w in holds:
        r = get_price_return(tk)["ret1y"]
        if r is not None:
            rets.append(r)
    dispersion = statistics.pstdev(rets) if len(rets) > 1 else 0.0
    hhi = sum((w / 100) ** 2 for _, w in holds)
    n = len(holds)
    score = 0
    if dispersion > 40:
        score += 2
    elif dispersion > 20:
        score += 1
    if hhi > 0.20:
        score += 2
    elif hhi > 0.12:
        score += 1
    if n <= 5:
        score += 1
    nivel = "Agresivo" if score >= 4 else "Moderado" if score >= 2 else "Conservador"
    return {"nivel": nivel, "hhi": round(hhi, 3), "n": n, "dispersion": round(dispersion, 1)}


def match_perfil(nivel: str, perfil_riesgo: str | None) -> tuple:
    """Devuelve (texto, color, orden) del encaje de un nivel de cartera con el perfil del usuario."""
    orden = {"Conservador": 0, "Moderado": 1, "Agresivo": 2}
    if perfil_riesgo not in orden:
        return ("Define tu perfil en Inicio para comparar", "amarillo", 1)
    diff = abs(orden[nivel] - orden[perfil_riesgo])
    if diff == 0:
        return ("✅ Encaja con tu perfil", "verde", 0)
    if diff == 1:
        return ("🟡 Encaje parcial con tu perfil", "amarillo", 1)
    return ("🔴 No encaja con tu perfil", "rojo", 2)


def analizar_inversionista(inv: dict, perfil_riesgo: str | None) -> dict:
    """
    Clasifica el nivel de riesgo de la cartera del inversionista y la compara con el perfil.
    """
    ri = riesgo_cartera(tuple(inv["holdings"]))
    nivel, hhi, n, dispersion = ri["nivel"], ri["hhi"], ri["n"], ri["dispersion"]
    ret_prom = rendimiento_inversionista(tuple(inv["holdings"]))
    match, match_color, _orden = match_perfil(nivel, perfil_riesgo)

    motivos = [
        f"Cartera de {n} posiciones; concentración {'alta' if hhi>0.2 else 'media' if hhi>0.12 else 'baja'} (HHI={hhi:.2f}).",
        f"Dispersión de rendimientos entre sus acciones: {dispersion:.0f} pts "
        f"({'muy volátil' if dispersion>40 else 'moderada' if dispersion>20 else 'estable'}).",
        f"Nivel de riesgo estimado de esta cartera: <b>{nivel}</b>.",
    ]
    _ord = {"Conservador": 0, "Moderado": 1, "Agresivo": 2}
    if perfil_riesgo in _ord and nivel != perfil_riesgo:
        if _ord[nivel] > _ord[perfil_riesgo]:
            motivos.append(f"Es más agresiva que tu perfil ({perfil_riesgo}); considera ponderarla menos o combinarla con algo más estable.")
        else:
            motivos.append(f"Es más conservadora que tu perfil ({perfil_riesgo}); podrías complementarla con algo de más crecimiento.")
    return {"nivel": nivel, "hhi": round(hhi, 3), "n": n, "dispersion": round(dispersion, 1),
            "ret_1y": ret_prom, "match": match, "match_color": match_color, "motivos": motivos}


@st.cache_data(ttl=1800, show_spinner=False)
def rendimiento_inversionista(holdings_tuple: tuple) -> float | None:
    """Rendimiento ponderado a 1 año de la cartera (None si no hay datos)."""
    hold = normalizar_holdings(list(holdings_tuple))
    suma = 0.0
    peso_valido = 0.0
    for tk, peso in hold:
        r = get_price_return(tk)["ret1y"]
        if r is not None:
            suma += r * peso
            peso_valido += peso
    if peso_valido == 0:
        return None
    return suma / peso_valido  # renormalizado por pesos con dato
