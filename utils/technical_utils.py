"""
Indicadores de análisis técnico vía yfinance:
OHLC + medias móviles (20/50/200), Bandas de Bollinger y RSI(14).
Soporta reagrupado por día / semana / mes.
"""
import pandas as pd
import numpy as np
import yfinance as yf
import streamlit as st


def _add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Calcula SMA20/50/200, Bandas de Bollinger(20,2σ) y RSI(14) sobre el cierre."""
    c = df["Close"]
    df["SMA20"] = c.rolling(20).mean()
    df["SMA50"] = c.rolling(50).mean()
    df["SMA200"] = c.rolling(200).mean()
    m = c.rolling(20).mean()
    s = c.rolling(20).std()
    df["BB_mid"] = m
    df["BB_up"] = m + 2 * s
    df["BB_low"] = m - 2 * s
    delta = c.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss
    df["RSI"] = 100 - 100 / (1 + rs)
    return df


@st.cache_data(ttl=3600, show_spinner="Cargando la gráfica…")
def get_ohlc(ticker: str) -> pd.DataFrame:
    """Devuelve OHLC diario de 10 años con indicadores técnicos."""
    try:
        df = yf.Ticker(ticker).history(period="10y")[["Open", "High", "Low", "Close"]].dropna()
        if df.empty:
            return pd.DataFrame()
        df.index = pd.to_datetime(df.index).tz_localize(None)
        df = _add_indicators(df)
        df = df.reset_index().rename(columns={"index": "Fecha", "Date": "Fecha"})
        df["Fecha"] = pd.to_datetime(df["Fecha"])
        return df
    except Exception:
        return pd.DataFrame()


def sugerir_entrada_salida(df: pd.DataFrame) -> dict:
    """
    Análisis técnico heurístico sobre la ventana visible.
    Sugiere zona de compra (entrada) y objetivo de venta (salida) con su razonamiento.
    """
    out = {"ok": False}
    if df is None or df.empty or len(df) < 20:
        return out
    d = df.dropna(subset=["Close"]).copy()
    last = float(d["Close"].iloc[-1])
    # Ventana reciente para soportes/resistencias (≈ últimos 60 periodos o todo)
    win = d.tail(min(60, len(d)))
    soporte = float(win["Low"].min()) if "Low" in win else float(win["Close"].min())
    resistencia = float(win["High"].max()) if "High" in win else float(win["Close"].max())
    rango = max(resistencia - soporte, 0.01)

    sma20 = float(d["SMA20"].iloc[-1]) if not pd.isna(d["SMA20"].iloc[-1]) else None
    sma50 = float(d["SMA50"].iloc[-1]) if not pd.isna(d["SMA50"].iloc[-1]) else None
    sma200 = float(d["SMA200"].iloc[-1]) if not pd.isna(d["SMA200"].iloc[-1]) else None
    bb_low = float(d["BB_low"].iloc[-1]) if not pd.isna(d["BB_low"].iloc[-1]) else None
    bb_up = float(d["BB_up"].iloc[-1]) if not pd.isna(d["BB_up"].iloc[-1]) else None
    rsi = float(d["RSI"].iloc[-1]) if not pd.isna(d["RSI"].iloc[-1]) else None

    # Zona de compra: cerca del soporte / banda inferior, sin pasar el precio actual
    candidatos_ent = [soporte + 0.15 * rango]
    if bb_low:
        candidatos_ent.append(bb_low)
    entrada = min(last, sum(candidatos_ent) / len(candidatos_ent))

    # Objetivo de venta: cerca de la resistencia / banda superior
    candidatos_sal = [resistencia]
    if bb_up:
        candidatos_sal.append(bb_up)
    salida = max(candidatos_sal)
    if salida <= entrada:
        salida = entrada * 1.15  # margen mínimo si el rango es plano

    # Tendencia y razonamiento
    tendencia = "alcista" if (sma200 and last > sma200) else ("bajista" if sma200 else "indefinida")
    notas = []
    notas.append(f"Tendencia de fondo **{tendencia}** "
                 f"(precio {'por encima' if tendencia=='alcista' else 'por debajo'} de la SMA 200)."
                 if sma200 else "No hay suficiente historia para la SMA 200.")
    if rsi is not None:
        if rsi < 30:
            notas.append(f"RSI en **{rsi:.0f}** → zona de **sobreventa**: suele ser buen momento para comprar.")
        elif rsi > 70:
            notas.append(f"RSI en **{rsi:.0f}** → zona de **sobrecompra**: precaución, podría corregir.")
        else:
            notas.append(f"RSI en **{rsi:.0f}** → zona **neutral**.")
    notas.append(f"Soporte reciente cerca de **${soporte:,.2f}** y resistencia cerca de **${resistencia:,.2f}**.")
    if sma20 and sma50:
        cruce = "al alza (señal positiva)" if sma20 > sma50 else "a la baja (señal de debilidad)"
        notas.append(f"La SMA 20 está {('por encima' if sma20>sma50 else 'por debajo')} de la SMA 50 → momentum {cruce}.")

    gan_pct = (salida - entrada) / entrada * 100 if entrada else 0
    out.update({
        "ok": True,
        "entrada": round(entrada, 2),
        "salida": round(salida, 2),
        "soporte": round(soporte, 2),
        "resistencia": round(resistencia, 2),
        "rsi": rsi,
        "tendencia": tendencia,
        "gan_pct": gan_pct,
        "notas": notas,
        "precio_actual": round(last, 2),
    })
    return out


def resample_ohlc(df_daily: pd.DataFrame, freq: str) -> pd.DataFrame:
    """
    Reagrupa el OHLC diario a semanal ('1S') o mensual ('1M') y recalcula indicadores.
    Para '1D' devuelve el diario tal cual.
    """
    if df_daily.empty or freq == "1D":
        return df_daily
    rule = {"1S": "W-FRI", "1M": "MS"}.get(freq)
    if rule is None:
        return df_daily
    g = (df_daily.set_index("Fecha")[["Open", "High", "Low", "Close"]]
         .resample(rule)
         .agg({"Open": "first", "High": "max", "Low": "min", "Close": "last"})
         .dropna())
    if g.empty:
        return df_daily
    g = _add_indicators(g).reset_index()
    g["Fecha"] = pd.to_datetime(g["Fecha"])
    return g
