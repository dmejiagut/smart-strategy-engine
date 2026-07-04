"""
Catálogo y métricas de las FIBRAs mexicanas (BMV).
Datos en vivo: precio, dividend yield, rendimiento YTD y valor de mercado.
Las métricas operativas profundas (NOI, FFO, ocupación, LTV, precio objetivo)
provienen de boletines de analistas y no se obtienen de APIs públicas.
"""
import pandas as pd
import yfinance as yf
import streamlit as st

# Principales FIBRAs que cotizan en la BMV
FIBRAS_MX = [
    {"ticker": "FUNO11.MX",    "nombre": "Fibra Uno",        "sector": "Diversificado"},
    {"ticker": "DANHOS13.MX",  "nombre": "Fibra Danhos",     "sector": "Comercial/Oficinas"},
    {"ticker": "FMTY14.MX",    "nombre": "Fibra Monterrey",  "sector": "Diversificado"},
    {"ticker": "FIBRAPL14.MX", "nombre": "Fibra Prologis",   "sector": "Industrial"},
    {"ticker": "FIBRAMQ12.MX", "nombre": "Fibra Macquarie",  "sector": "Industrial"},
    {"ticker": "FNOVA17.MX",   "nombre": "Fibra Nova",       "sector": "Industrial"},
    {"ticker": "FSHOP13.MX",   "nombre": "Fibra Shop",       "sector": "Comercial"},
    {"ticker": "FIHO12.MX",    "nombre": "Fibra Hotel",      "sector": "Hotelero"},
    {"ticker": "FINN13.MX",    "nombre": "Fibra Inn",        "sector": "Hotelero"},
    {"ticker": "EDUCA18.MX",   "nombre": "Fibra Educa",      "sector": "Educativo"},
    {"ticker": "FSITES20.MX",  "nombre": "Fibra Telesites",  "sector": "Telecom/Torres"},
    {"ticker": "FIBRAHD15.MX", "nombre": "Fibra HD",         "sector": "Diversificado"},
    {"ticker": "FPLUS16.MX",   "nombre": "Fibra Plus",       "sector": "Diversificado"},
    {"ticker": "FIBRAUP18.MX", "nombre": "Fibra Upsite",     "sector": "Industrial"},
    {"ticker": "NEXT25.MX",    "nombre": "Fibra Next",       "sector": "Industrial"},
]


@st.cache_data(ttl=1800, show_spinner="Cargando datos de la FIBRA…")
def get_fibra_metrics(ticker: str) -> dict:
    """Métricas de mercado de una FIBRA. Campos None si no hay datos."""
    out = {"ticker": ticker, "precio": None, "market_cap": None,
           "div_yield": None, "ytd": None}
    try:
        t = yf.Ticker(ticker)
        info = t.info
        out["precio"] = info.get("regularMarketPrice") or info.get("currentPrice")
        out["market_cap"] = info.get("marketCap")
        dy = info.get("dividendYield")
        # yfinance a veces da yield como fracción (0.08) o como % (8.0)
        if dy is not None:
            out["div_yield"] = dy if dy > 1 else dy * 100
        h = t.history(period="ytd")["Close"].dropna()
        if len(h) > 1:
            out["ytd"] = (h.iloc[-1] / h.iloc[0] - 1) * 100
    except Exception:
        pass
    return out


def analizar_fibra(m: dict) -> dict:
    """
    Puntúa una FIBRA (0-100) con los datos de mercado disponibles y la clasifica.
    Inspirado en el enfoque de análisis de FIBRAs: rendimiento por dividendo,
    momentum del precio y tamaño/solidez.
    Devuelve {score, recomendacion, color, motivos}.
    """
    score = 0.0
    motivos = []
    dy = m.get("div_yield")
    ytd = m.get("ytd")
    mc = m.get("market_cap")

    # 1) Dividend yield (peso 45): zona ideal 6%-9%
    if dy is not None:
        if 6 <= dy <= 9:
            score += 45; motivos.append(f"Dividend yield atractivo ({dy:.1f}%).")
        elif 4 <= dy < 6:
            score += 30; motivos.append(f"Dividend yield moderado ({dy:.1f}%).")
        elif dy > 9:
            score += 28; motivos.append(f"Yield muy alto ({dy:.1f}%) — atractivo pero revisa el riesgo.")
        else:
            score += 12; motivos.append(f"Dividend yield bajo ({dy:.1f}%).")
    else:
        motivos.append("Sin dato de dividend yield.")

    # 2) Momentum YTD (peso 35)
    if ytd is not None:
        if ytd >= 8:
            score += 35; motivos.append(f"Buen momentum en 2026 ({ytd:+.1f}%).")
        elif ytd >= 0:
            score += 22; motivos.append(f"Rendimiento positivo en 2026 ({ytd:+.1f}%).")
        elif ytd >= -8:
            score += 10; motivos.append(f"Ligeramente negativo en 2026 ({ytd:+.1f}%).")
        else:
            score += 0; motivos.append(f"Débil en 2026 ({ytd:+.1f}%).")
    else:
        motivos.append("Sin dato de rendimiento YTD.")

    # 3) Tamaño / liquidez (peso 20)
    if mc is not None:
        if mc >= 50e9:
            score += 20; motivos.append("FIBRA grande y líquida.")
        elif mc >= 20e9:
            score += 13; motivos.append("Tamaño mediano.")
        else:
            score += 6; motivos.append("FIBRA pequeña (menor liquidez).")

    if score >= 66:
        rec, color = "Compra", "verde"
    elif score >= 42:
        rec, color = "Neutral", "amarillo"
    else:
        rec, color = "Evitar", "rojo"
    return {"score": round(score), "recomendacion": rec, "color": color, "motivos": motivos}
