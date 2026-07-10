"""
Exportación de 'Mis Resultados' a Excel y PDF.
Excel: hoja Resumen + una hoja por estrategia con el detalle de sus compras.
PDF: resumen general + sección por estrategia con su detalle.
"""
import io
import json
from pathlib import Path
from datetime import date

import pandas as pd

from utils.resumen_utils import resumen_global, _precio_mxn
from utils.ticker_search import get_precio_actual, get_tipo_cambio_actual
from utils import nav
from utils.db_utils import (
    load_strategies, load_purchases,
    load_div_strategies, load_div_purchases,
    load_obj_strategies, load_obj_purchases, load_obj_sales,
    load_fibra_strategies, load_fibra_purchases,
    load_copy_strategies, load_copy_purchases,
)


def _mxn(v):
    try:
        return f"${v:,.2f}"
    except Exception:
        return "—"


# ── Construir detalle por estrategia ─────────────────────────────────────────
def _compras_ticker(estrategias, load_p, modulo, nombre_key="ticker"):
    items = []
    for e in estrategias:
        compras = load_p(e["id"])
        if not compras:
            continue
        rows = []
        inv = 0.0
        tit = 0
        for c in compras:
            com = c.get("comision") or 0.0
            total = c["titulos"] * c["precio"] + com
            inv += total
            tit += c["titulos"]
            rows.append({"Fecha": str(c["fecha"])[:10], "Títulos": c["titulos"],
                         "Precio MXN": round(c["precio"], 2), "Comisión+IVA": round(com, 2),
                         "Total MXN": round(total, 2)})
        pm = _precio_mxn(e["ticker"])
        valor = tit * pm if pm else inv
        nombre = e.get(nombre_key) or e.get("nombre") or e["ticker"]
        items.append({"modulo": modulo, "nombre": nombre, "ticker": e["ticker"],
                      "invertido": inv, "valor": valor,
                      "rend": (valor / inv - 1) * 100 if inv else 0.0,
                      "df": pd.DataFrame(rows)})
    return items


def _compras_objetivos():
    items = []
    for e in load_obj_strategies():
        compras = load_obj_purchases(e["id"])
        if not compras:
            continue
        ventas = {v["compra_id"]: v for v in load_obj_sales(e["id"])}
        pm = _precio_mxn(e["ticker"])
        rows = []
        inv = 0.0
        val = 0.0
        for c in compras:
            com = c.get("comision") or 0.0
            total = c["titulos"] * c["precio"] + com
            inv += total
            v = ventas.get(c["id"])
            estado = "Vendido" if v else "Abierto"
            if v:
                val += v["titulos"] * v["precio"] - (v.get("comision") or 0)
            else:
                val += c["titulos"] * pm if pm else total
            rows.append({"Fecha": str(c["fecha"])[:10], "Estado": estado, "Títulos": c["titulos"],
                         "Precio compra MXN": round(c["precio"], 2), "Comisión+IVA": round(com, 2),
                         "Total MXN": round(total, 2),
                         "Precio venta MXN": round(v["precio"], 2) if v else None})
        items.append({"modulo": "Por Objetivos", "nombre": e.get("nombre") or e["ticker"],
                      "ticker": e["ticker"], "invertido": inv, "valor": val,
                      "rend": (val / inv - 1) * 100 if inv else 0.0,
                      "df": pd.DataFrame(rows)})
    return items


def _compras_copy():
    items = []
    fx = get_tipo_cambio_actual()
    for e in load_copy_strategies():
        compras = load_copy_purchases(e["id"])
        rows = []
        inv = 0.0
        val = 0.0
        for cp in compras:
            tc = cp.get("tipo_cambio") or fx
            com = cp.get("comision") or 0.0
            # Comisión+IVA de la compra repartida entre sus acciones (proporcional al costo)
            base = sum(d["titulos"] * d["precio_usd"] for d in cp["detalle"]) or 1.0
            for d in cp["detalle"]:
                costo_usd = d["titulos"] * d["precio_usd"]
                com_fila = com * (costo_usd / base)
                inv_mxn = costo_usd * tc + com_fila
                inv += inv_mxn
                q = get_precio_actual(d["ticker"])
                px = q["precio"] if q and q.get("precio") else d["precio_usd"]
                val += d["titulos"] * px * fx
                rows.append({"Fecha": str(cp["fecha"])[:10], "Acción": d["ticker"],
                             "Títulos": d["titulos"], "Precio compra USD": round(d["precio_usd"], 2),
                             "TC": round(tc, 4), "Comisión+IVA": round(com_fila, 2),
                             "Inversión MXN": round(inv_mxn, 2)})
        if inv <= 0:
            continue
        items.append({"modulo": "Copy Trading", "nombre": e.get("nombre") or e["investor_id"],
                      "ticker": "", "invertido": inv, "valor": val,
                      "rend": (val / inv - 1) * 100 if inv else 0.0,
                      "df": pd.DataFrame(rows)})
    return items


def estrategias_detalle():
    items = []
    items += _compras_ticker(load_strategies(), load_purchases, "DCA")
    items += _compras_ticker(load_div_strategies(), load_div_purchases, "Dividendos", "nombre")
    items += _compras_objetivos()
    items += _compras_ticker(load_fibra_strategies(), load_fibra_purchases, "FIBRAs", "nombre")
    items += _compras_copy()
    return items


EXPORT_DIR = Path(__file__).parent.parent / "exports"


def cartera_payload(perfil: dict | None = None) -> dict:
    """Estructura de la cartera (perfil + totales + estrategias) para análisis."""
    res = resumen_global()
    return {
        "generado": date.today().isoformat(),
        "perfil": {
            "nombre": (perfil or {}).get("nombre"),
            "edad": (perfil or {}).get("edad"),
            "ingreso_mensual": (perfil or {}).get("ingreso_mensual"),
            "objetivo": (perfil or {}).get("objetivo"),
            "perfil_riesgo": (perfil or {}).get("perfil_riesgo"),
            "horizonte_anios": (perfil or {}).get("horizonte_anios"),
        },
        "totales": {
            "invertido_mxn": round(res["total_invertido"], 2),
            "valor_mxn": round(res["total_valor"], 2),
            "rendimiento_pct": round(res["total_rend_pct"], 2),
        },
        "estrategias": [
            {"modulo": it["modulo"], "nombre": it["nombre"], "ticker": it.get("ticker", ""),
             "invertido_mxn": round(it["invertido"], 2), "valor_mxn": round(it["valor"], 2),
             "rendimiento_pct": round(it["rend_pct"], 2)}
            for it in res["items"]
        ],
    }


def exportar_json(perfil: dict | None = None, payload: dict | None = None) -> bytes:
    """
    Exporta la cartera a JSON para que el skill 'Revisor de Cartera' la analice.
    Lo guarda en exports/cartera_export.json y devuelve los bytes para descarga.
    Acepta un payload ya construido para no calcularlo dos veces.
    """
    if payload is None:
        payload = cartera_payload(perfil)
    data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    try:
        EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        (EXPORT_DIR / "cartera_export.json").write_bytes(data)
    except Exception:
        pass
    return data


def _resumen_df(res, perfil=None):
    filas = [{"Módulo": it["modulo"], "Estrategia": it["nombre"],
              "Invertido MXN": round(it["invertido"], 2), "Valor actual MXN": round(it["valor"], 2),
              "Rendimiento %": round(it["rend_pct"], 2)} for it in res["items"]]
    filas.append({"Módulo": "TOTAL", "Estrategia": "",
                  "Invertido MXN": round(res["total_invertido"], 2),
                  "Valor actual MXN": round(res["total_valor"], 2),
                  "Rendimiento %": round(res["total_rend_pct"], 2)})
    return pd.DataFrame(filas)


# ── Excel ────────────────────────────────────────────────────────────────────
def export_excel(perfil: dict | None = None) -> bytes:
    res = resumen_global()
    detalle = estrategias_detalle()
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xl:
        _resumen_df(res).to_excel(xl, sheet_name="Resumen", index=False)
        usados = {"Resumen"}
        for it in detalle:
            base = f"{it['modulo'][:4]}-{it['nombre']}"
            name = "".join(ch for ch in base if ch not in "[]:*?/\\")[:31] or "Estrategia"
            n = name
            i = 2
            while n in usados:
                n = f"{name[:28]}_{i}"
                i += 1
            usados.add(n)
            it["df"].to_excel(xl, sheet_name=n, index=False)
    return buf.getvalue()


# ── PDF ──────────────────────────────────────────────────────────────────────
def export_pdf(perfil: dict | None = None) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import cm
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle)

    res = resumen_global()
    detalle = estrategias_detalle()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, topMargin=1.5 * cm, bottomMargin=1.5 * cm,
                            leftMargin=1.5 * cm, rightMargin=1.5 * cm)
    styles = getSampleStyleSheet()
    PURPLE = colors.HexColor("#6C63FF")
    h = ParagraphStyle("h", parent=styles["Title"], textColor=PURPLE, fontSize=18)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], textColor=colors.HexColor("#1a1a2e"), fontSize=13)
    small = ParagraphStyle("small", parent=styles["Normal"], fontSize=9, textColor=colors.HexColor("#6B7280"))
    el = []

    el.append(Paragraph("Smart Strategy Engine — Mis Resultados", h))
    el.append(Paragraph(f"Generado el {date.today().strftime('%d/%m/%Y')}", small))
    if perfil and perfil.get("nombre"):
        el.append(Paragraph(f"Inversionista: {perfil['nombre']} · Perfil: {perfil.get('perfil_riesgo','—')} · "
                            f"Objetivo: {perfil.get('objetivo','—')}", small))
    el.append(Spacer(1, 0.4 * cm))

    # Totales
    gan = res["total_valor"] - res["total_invertido"]
    tot = [["Capital invertido", "Valor actual", "Rendimiento total"],
           [_mxn(res["total_invertido"]), _mxn(res["total_valor"]),
            f"{_mxn(gan)}  ({res['total_rend_pct']:+.2f}%)"]]
    t = Table(tot, colWidths=[5.6 * cm, 5.6 * cm, 5.6 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PURPLE),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 10), ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"), ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E6EE")),
        ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    el.append(t)
    el.append(Spacer(1, 0.5 * cm))

    # Resumen por estrategia
    el.append(Paragraph("Resumen por estrategia", h2))
    data = [["Módulo", "Estrategia", "Invertido", "Valor actual", "Rend. %"]]
    for it in res["items"]:
        data.append([it["modulo"], it["nombre"], _mxn(it["invertido"]),
                     _mxn(it["valor"]), f"{it['rend_pct']:+.2f}%"])
    rt = Table(data, colWidths=[3 * cm, 5 * cm, 3 * cm, 3 * cm, 2.4 * cm])
    rt.setStyle(_estilo_tabla(PURPLE))
    el.append(rt)
    el.append(Spacer(1, 0.6 * cm))

    # Detalle de cada estrategia
    el.append(Paragraph("Detalle de inversiones por estrategia", h2))
    for it in detalle:
        el.append(Spacer(1, 0.25 * cm))
        tk = f" ({it['ticker']})" if it["ticker"] else ""
        el.append(Paragraph(f"<b>{it['modulo']} — {it['nombre']}{tk}</b>", styles["Normal"]))
        el.append(Paragraph(f"Invertido: {_mxn(it['invertido'])} · Valor actual: {_mxn(it['valor'])} · "
                            f"Rendimiento: {it['rend']:+.2f}%", small))
        df = it["df"]
        if not df.empty:
            cols = list(df.columns)
            data = [cols] + df.astype(object).where(df.notna(), "—").values.tolist()
            tabla = Table(data, repeatRows=1)
            tabla.setStyle(_estilo_tabla(colors.HexColor("#9DA5B8"), header_fontsize=8, body_fontsize=8))
            el.append(tabla)
        el.append(Spacer(1, 0.2 * cm))

    el.append(Spacer(1, 0.4 * cm))
    el.append(Paragraph("Valores actuales con precios de mercado en vivo (convertidos a MXN). "
                        "Los rendimientos pasados no garantizan resultados futuros.", small))
    doc.build(el)
    return buf.getvalue()


def _estilo_tabla(header_color, header_fontsize=9, body_fontsize=9):
    from reportlab.lib import colors
    from reportlab.platypus import TableStyle
    return TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), header_color),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), header_fontsize),
        ("FONTSIZE", (0, 1), (-1, -1), body_fontsize),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#E2E6EE")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8F9FC")]),
        ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ])
