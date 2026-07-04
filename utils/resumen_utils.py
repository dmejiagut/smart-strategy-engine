"""
Agrega la inversión y el rendimiento de TODAS las estrategias de los 5 módulos,
todo convertido a pesos mexicanos (MXN).
"""
import streamlit as st

from utils.ticker_search import get_precio_actual, get_tipo_cambio_actual, get_precios_varios
from utils import nav
from utils.db_utils import (
    load_strategies, load_purchases,                       # DCA
    load_div_strategies, load_div_purchases,               # Dividendos
    load_obj_strategies, load_obj_purchases, load_obj_sales,  # Objetivos
    load_fibra_strategies, load_fibra_purchases,           # FIBRAs
    load_copy_strategies, load_copy_purchases,             # Copy Trading
    titulos_vendidos,                                      # ventas cerradas
)


def _precio_mxn(ticker: str):
    q = get_precio_actual(ticker)
    if not q or not q.get("precio"):
        return None
    p = q["precio"]
    mon = q.get("moneda", "USD")
    if ticker.upper().endswith(".MX") or mon == "MXN":
        return p
    return p * get_tipo_cambio_actual()


def _item(modulo, nombre, ticker, invertido, valor, destino):
    rend = (valor / invertido - 1) * 100 if invertido else 0.0
    return {"modulo": modulo, "nombre": nombre, "ticker": ticker,
            "invertido": invertido, "valor": valor, "rend_pct": rend, "destino": destino}


def _resumen_ticker(estrategias, load_p, modulo, destino, nombre_key="ticker"):
    items = []
    for e in estrategias:
        compras = load_p(e["id"])
        if not compras:
            continue
        inv = sum(c["titulos"] * c["precio"] + (c.get("comision") or 0) for c in compras)
        tit = sum(c["titulos"] for c in compras)
        # Descontar lo ya vendido (queda solo la posición actual)
        vendidos = titulos_vendidos(modulo, e["id"])
        tit_rem = tit - vendidos
        if tit_rem <= 0:
            continue  # posición cerrada por completo → vive en el historial realizado
        prom = inv / tit if tit else 0.0
        inv = prom * tit_rem  # costo de lo que aún conservas
        pm = _precio_mxn(e["ticker"])
        val = tit_rem * pm if pm else inv
        nombre = e.get(nombre_key) or e.get("nombre") or e["ticker"]
        items.append(_item(modulo, nombre, e["ticker"], inv, val, destino))
    return items


def _resumen_objetivos():
    items = []
    for e in load_obj_strategies():
        compras = load_obj_purchases(e["id"])
        if not compras:
            continue
        ventas = {v["compra_id"]: v for v in load_obj_sales(e["id"])}
        pm = _precio_mxn(e["ticker"])
        inv = 0.0
        val = 0.0
        for c in compras:
            inv += c["titulos"] * c["precio"] + (c.get("comision") or 0)
            v = ventas.get(c["id"])
            if v:  # lote vendido → valor realizado
                val += v["titulos"] * v["precio"] - (v.get("comision") or 0)
            else:  # lote abierto → valor de mercado
                val += c["titulos"] * pm if pm else c["titulos"] * c["precio"]
        nombre = e.get("nombre") or e["ticker"]
        items.append(_item("Por Objetivos", nombre, e["ticker"], inv, val, nav.OBJ))
    return items


def _resumen_copy():
    items = []
    fx = get_tipo_cambio_actual()
    for e in load_copy_strategies():
        compras = load_copy_purchases(e["id"])
        inv = 0.0
        val = 0.0
        for cp in compras:
            tc = cp.get("tipo_cambio") or fx
            for d in cp["detalle"]:
                inv += d["titulos"] * d["precio_usd"] * tc
                q = get_precio_actual(d["ticker"])
                px = q["precio"] if q and q.get("precio") else d["precio_usd"]
                val += d["titulos"] * px * fx
        if inv <= 0:
            continue
        nombre = e.get("nombre") or e["investor_id"]
        items.append(_item("Copy Trading", nombre, "", inv, val, nav.COPY))
    return items


def invalidar_resumen():
    """Recalcula solo el resumen (tras registrar compras/ventas o cambiar de modo),
    sin tirar la caché de precios de mercado — así la app sigue rápida."""
    resumen_global.clear()


def _prewarm_precios():
    """#3 · Junta los tickers de TODAS las estrategias y pide sus precios en un solo viaje."""
    tickers = []
    for e in load_strategies():
        tickers.append(e["ticker"])
    for e in load_div_strategies():
        tickers.append(e["ticker"])
    for e in load_obj_strategies():
        tickers.append(e["ticker"])
    for e in load_fibra_strategies():
        tickers.append(e["ticker"])
    for e in load_copy_strategies():
        for cp in load_copy_purchases(e["id"]):
            for d in cp.get("detalle", []):
                tickers.append(d["ticker"])
    if tickers:
        get_precios_varios(tickers)


@st.cache_data(ttl=300, show_spinner="Calculando tus resultados...")
def resumen_global() -> dict:
    _prewarm_precios()  # una sola petición para todos los precios (luego cada uno lee de la base)
    items = []
    items += _resumen_ticker(load_strategies(), load_purchases, "DCA", nav.DCA)
    items += _resumen_ticker(load_div_strategies(), load_div_purchases, "Dividendos", nav.DIV, "nombre")
    items += _resumen_objetivos()
    items += _resumen_ticker(load_fibra_strategies(), load_fibra_purchases, "FIBRAs", nav.FIB, "nombre")
    items += _resumen_copy()
    total_inv = sum(i["invertido"] for i in items)
    total_val = sum(i["valor"] for i in items)
    total_rend = (total_val / total_inv - 1) * 100 if total_inv else 0.0
    return {"items": items, "total_invertido": total_inv,
            "total_valor": total_val, "total_rend_pct": total_rend}
