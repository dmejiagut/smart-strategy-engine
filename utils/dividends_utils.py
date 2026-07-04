"""
Utilidades para datos de dividendos vía yfinance.
Series históricas estilo Macrotrends: precio, dividendo TTM y yield TTM.
"""
import pandas as pd
import yfinance as yf
import streamlit as st
from datetime import date

# Acciones del SIC recomendadas por altos dividendos (aristócratas / alto yield)
RECOMENDADAS_SIC = [
    {"ticker": "JNJ",  "nombre": "Johnson & Johnson", "giro": "Salud",       "yield_aprox": "3.0%"},
    {"ticker": "KO",   "nombre": "Coca-Cola",         "giro": "Consumo",     "yield_aprox": "2.8%"},
    {"ticker": "PEP",  "nombre": "PepsiCo",           "giro": "Consumo",     "yield_aprox": "3.1%"},
    {"ticker": "PG",   "nombre": "Procter & Gamble",  "giro": "Consumo",     "yield_aprox": "2.5%"},
    {"ticker": "MCD",  "nombre": "McDonald's",        "giro": "Consumo",     "yield_aprox": "2.4%"},
    {"ticker": "ABBV", "nombre": "AbbVie",            "giro": "Salud",       "yield_aprox": "3.5%"},
    {"ticker": "O",    "nombre": "Realty Income",     "giro": "Inmobiliario","yield_aprox": "5.5%"},
    {"ticker": "CVX",  "nombre": "Chevron",           "giro": "Energía",     "yield_aprox": "4.0%"},
    {"ticker": "XOM",  "nombre": "Exxon Mobil",       "giro": "Energía",     "yield_aprox": "3.5%"},
    {"ticker": "MO",   "nombre": "Altria Group",      "giro": "Consumo",     "yield_aprox": "7%+"},
]


@st.cache_data(ttl=3600, show_spinner="Cargando la gráfica de dividendos…")
def get_dividend_series(ticker: str) -> pd.DataFrame:
    """
    Serie mensual con: precio de cierre, dividendo TTM (suma 12m) y yield TTM (%).
    Devuelve DataFrame vacío si el ticker no paga dividendos o no hay datos.
    """
    try:
        t = yf.Ticker(ticker)
        divs = t.dividends
        precios = t.history(period="max")["Close"]
        if divs is None or len(divs) == 0 or precios is None or len(precios) == 0:
            return pd.DataFrame()
        # Normalizar a tz-naive
        divs = divs.copy()
        divs.index = pd.to_datetime(divs.index).tz_localize(None)
        precios = precios.copy()
        precios.index = pd.to_datetime(precios.index).tz_localize(None)

        # Muestreo mensual desde el primer dividendo
        inicio = max(divs.index.min(), precios.index.min())
        fin = precios.index.max()
        fechas = pd.date_range(start=inicio, end=fin, freq="MS")
        rows = []
        for f in fechas:
            ventana = divs[(divs.index > f - pd.Timedelta(days=365)) & (divs.index <= f)]
            ttm_div = float(ventana.sum())
            px_hist = precios[precios.index <= f]
            if len(px_hist) == 0:
                continue
            precio = float(px_hist.iloc[-1])
            ttm_yield = (ttm_div / precio * 100) if precio > 0 else 0.0
            rows.append({"Fecha": f, "Precio": round(precio, 2),
                         "Dividendo TTM": round(ttm_div, 4),
                         "Yield TTM": round(ttm_yield, 3)})
        return pd.DataFrame(rows)
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=3600, show_spinner="Cargando dividendos…")
def get_dividend_summary(ticker: str) -> dict:
    """Resumen actual de dividendos: último pago, dividendo TTM, yield, frecuencia."""
    out = {"ultimo_pago": None, "ultima_fecha": None, "ttm": None,
           "yield_pct": None, "precio": None, "n_pagos_ttm": 0, "frecuencia": "—",
           "ex_date": None, "next_pay_date": None}
    try:
        t = yf.Ticker(ticker)
        divs = t.dividends
        if divs is None or len(divs) == 0:
            return out
        divs = divs.copy()
        divs.index = pd.to_datetime(divs.index).tz_localize(None)
        precio = None
        try:
            precio = float(t.fast_info.last_price)
        except Exception:
            hist = t.history(period="5d")["Close"].dropna()
            if len(hist):
                precio = float(hist.iloc[-1])
        out["ultimo_pago"] = float(divs.iloc[-1])
        out["ultima_fecha"] = divs.index[-1].date()
        ventana = divs[divs.index > divs.index[-1] - pd.Timedelta(days=365)]
        out["ttm"] = float(ventana.sum())
        out["n_pagos_ttm"] = int(len(ventana))
        out["precio"] = precio
        if precio and precio > 0:
            out["yield_pct"] = out["ttm"] / precio * 100
        freq_map = {1: "Anual", 2: "Semestral", 4: "Trimestral", 12: "Mensual"}
        out["frecuencia"] = freq_map.get(out["n_pagos_ttm"], f"{out['n_pagos_ttm']}/año")
        # Fechas futuras: ex-date y próximo pago
        try:
            from datetime import datetime, timezone
            info = t.info
            def _ts_to_date(v):
                if isinstance(v, (int, float)) and v and v > 1e8:
                    return datetime.fromtimestamp(v, timezone.utc).date()
                if isinstance(v, date):
                    return v
                return None
            out["ex_date"] = _ts_to_date(info.get("exDividendDate"))
            out["next_pay_date"] = _ts_to_date(info.get("dividendDate"))
            # Validar contra calendario si está disponible
            cal = t.calendar or {}
            if not out["ex_date"] and cal.get("Ex-Dividend Date"):
                out["ex_date"] = cal["Ex-Dividend Date"]
            if not out["next_pay_date"] and cal.get("Dividend Date"):
                out["next_pay_date"] = cal["Dividend Date"]
        except Exception:
            pass
        return out
    except Exception:
        return out


@st.cache_data(ttl=3600, show_spinner=False)
def analizar_salud_dividendo(ticker: str) -> dict:
    """
    Diagnostica la calidad y sostenibilidad del dividendo:
    crecimiento (CAGR), años consecutivos aumentando, historial y posible 'yield trap'.
    """
    from datetime import date as _date
    out = {"ok": False}
    try:
        t = yf.Ticker(ticker)
        divs = t.dividends
        if divs is None or len(divs) < 4:
            return out
        divs = divs.copy()
        divs.index = pd.to_datetime(divs.index).tz_localize(None)
        anual = divs.groupby(divs.index.year).sum()
        # excluir el año en curso (incompleto)
        if len(anual) > 1 and anual.index[-1] == _date.today().year:
            anual = anual.iloc[:-1]
        if len(anual) < 2:
            return out
        vals = [float(v) for v in anual.values]
        primero, ultimo, n = vals[0], vals[-1], len(vals) - 1
        cagr = ((ultimo / primero) ** (1 / n) - 1) * 100 if primero > 0 and n > 0 else None
        # años consecutivos aumentando (desde el más reciente hacia atrás)
        inc = 0
        for i in range(len(vals) - 1, 0, -1):
            if vals[i] > vals[i - 1]:
                inc += 1
            else:
                break
        anios_pagando = len(anual)
        # yield actual vs promedio histórico
        serie = get_dividend_series(ticker)
        y_now = y_avg = None
        if not serie.empty:
            y_now = float(serie["Yield TTM"].iloc[-1])
            y_avg = float(serie["Yield TTM"].mean())
        yield_trap = (y_now is not None and y_avg is not None and y_avg > 0 and y_now > y_avg * 1.5)

        score = 0
        motivos = []
        if cagr is not None:
            if cagr >= 7:
                score += 40; motivos.append(f"Dividendo creciendo fuerte ({cagr:+.1f}%/año).")
            elif cagr >= 2:
                score += 28; motivos.append(f"Dividendo creciendo moderado ({cagr:+.1f}%/año).")
            elif cagr >= 0:
                score += 15; motivos.append(f"Dividendo casi estable ({cagr:+.1f}%/año).")
            else:
                motivos.append(f"Dividendo decreciente ({cagr:+.1f}%/año) — señal de cautela.")
        if inc >= 5:
            score += 30; motivos.append(f"{inc} años consecutivos aumentando el pago (muy sólido).")
        elif inc >= 2:
            score += 18; motivos.append(f"{inc} años consecutivos aumentando.")
        else:
            score += 5; motivos.append("Sin una racha clara de aumentos recientes.")
        if anios_pagando >= 10:
            score += 20; motivos.append(f"{anios_pagando} años de historial de pagos.")
        elif anios_pagando >= 5:
            score += 12; motivos.append(f"{anios_pagando} años de historial de pagos.")
        if yield_trap:
            motivos.append(f"⚠️ Yield actual ({y_now:.1f}%) muy por encima de su promedio ({y_avg:.1f}%): "
                           "posible 'yield trap' por caída del precio, revisa con cuidado.")
        else:
            score += 10

        if score >= 70:
            ver, color = "Dividendo sólido", "verde"
        elif score >= 45:
            ver, color = "Dividendo aceptable", "amarillo"
        else:
            ver, color = "Dividendo de riesgo", "rojo"
        out.update(ok=True, cagr=cagr, anios_pagando=anios_pagando, anios_aumentando=inc,
                   yield_actual=y_now, yield_promedio=y_avg, yield_trap=yield_trap,
                   score=round(score), veredicto=ver, color=color, motivos=motivos)
        return out
    except Exception:
        return out


@st.cache_data(ttl=3600, show_spinner=False)
def get_dividends_since(ticker: str, desde: str) -> float:
    """Suma de dividendos por acción pagados después de la fecha 'desde' (YYYY-MM-DD)."""
    try:
        t = yf.Ticker(ticker)
        divs = t.dividends
        if divs is None or len(divs) == 0:
            return 0.0
        divs = divs.copy()
        divs.index = pd.to_datetime(divs.index).tz_localize(None)
        corte = pd.to_datetime(desde)
        return float(divs[divs.index >= corte].sum())
    except Exception:
        return 0.0
