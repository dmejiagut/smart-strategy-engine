"""Comparativa honesta contra referencias: ¿cómo te iría si ESE MISMO dinero,
en ESAS MISMAS fechas, lo hubieras metido a CETES o al S&P 500?

Metodología (transparente):
- Se toman TODAS tus compras registradas (fecha y monto en MXN, con comisión,
  porque ese es el dinero que realmente salió de tu bolsillo).
- S&P 500: cada monto "compra" SPY al cierre de ese día, al tipo de cambio de
  ese día; se valúa hoy con el precio y FX de hoy (datos reales de mercado).
- CETES: cada monto crece a la tasa anual indicada con interés compuesto
  diario (aproximación de reinvertir CETES de 28 días). La tasa es editable
  para que el usuario ponga la vigente — la app no la inventa.
"""
from datetime import date

import pandas as pd
import streamlit as st
import yfinance as yf


def flujos_de_compras() -> list:
    """(fecha_iso, monto_mxn con comisión) de TODAS las compras registradas."""
    from utils.db_utils import (
        load_strategies, load_purchases,
        load_div_strategies, load_div_purchases,
        load_obj_strategies, load_obj_purchases,
        load_fibra_strategies, load_fibra_purchases,
        load_copy_strategies, load_copy_purchases,
    )
    flujos = []

    def _scan(estrategias, load_p):
        for e in estrategias:
            for c in load_p(e["id"]):
                monto = c["titulos"] * c["precio"] + (c.get("comision") or 0.0)
                flujos.append((str(c["fecha"])[:10], float(monto)))

    _scan(load_strategies(), load_purchases)
    _scan(load_div_strategies(), load_div_purchases)
    _scan(load_obj_strategies(), load_obj_purchases)
    _scan(load_fibra_strategies(), load_fibra_purchases)
    for e in load_copy_strategies():
        for cp in load_copy_purchases(e["id"]):
            tc = cp.get("tipo_cambio") or 1.0
            com = cp.get("comision") or 0.0
            base = sum(d["titulos"] * d["precio_usd"] for d in cp["detalle"])
            flujos.append((str(cp["fecha"])[:10], base * tc + com))
    flujos.sort()
    return flujos


@st.cache_data(ttl=1800, show_spinner=False)
def _serie(ticker: str):
    """Cierres diarios (5 años) de un ticker; None si no hay datos."""
    try:
        h = yf.Ticker(ticker).history(period="5y")["Close"].dropna()
        if h.empty:
            return None
        h.index = h.index.tz_localize(None)
        return h
    except Exception:
        return None


def _px_asof(serie: pd.Series, fecha_iso: str) -> float:
    """Primer cierre EN o DESPUÉS de la fecha (si es fin de semana, el lunes)."""
    s = serie[serie.index >= pd.Timestamp(fecha_iso)]
    return float(s.iloc[0]) if not s.empty else float(serie.iloc[-1])


@st.cache_data(ttl=1800, show_spinner=False)
def simular_spy(flujos: tuple):
    """Valor HOY en MXN si cada flujo hubiera comprado SPY (S&P 500) ese día,
    al tipo de cambio de ese día. None si el mercado no devuelve datos."""
    spy = _serie("SPY")
    fx = _serie("MXN=X")
    if spy is None or fx is None or not flujos:
        return None
    unidades = 0.0
    for f, monto in flujos:
        px = _px_asof(spy, f)
        tc = _px_asof(fx, f)
        if px <= 0 or tc <= 0:
            return None
        unidades += monto / (px * tc)
    return unidades * float(spy.iloc[-1]) * float(fx.iloc[-1])


def simular_cetes(flujos, tasa_anual_pct: float) -> float:
    """Valor HOY si cada flujo se hubiera invertido en CETES a esa tasa anual
    (interés compuesto diario ≈ reinvertir CETES de 28 días)."""
    hoy = date.today()
    r = tasa_anual_pct / 100.0
    total = 0.0
    for f, monto in flujos:
        try:
            y, m, d = (int(x) for x in f.split("-"))
            dias = max((hoy - date(y, m, d)).days, 0)
        except Exception:
            dias = 0
        total += monto * (1 + r / 365) ** dias
    return total
