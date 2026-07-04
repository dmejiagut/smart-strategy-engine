"""Generación e importación de la plantilla Excel de compras/ventas.

Diseño:
- Hoja 'Movimientos' (donde se llena): la Estrategia y la Operación se eligen de
  listas desplegables, no se escriben a mano. La lista de estrategias muestra el
  detalle que distingue a cada una (frecuencia, fechas, entrada/salida) para que
  dos estrategias del mismo ticker no se confundan, y lleva un id oculto.
- Hoja 'Historial' (solo lectura): todo lo ya cargado.
Copy Trading queda fuera (su estructura es una canasta, no filas simples).
"""
import io
import re
from datetime import date, datetime

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from utils import db_utils
from utils.comisiones import comision_desde_perfil

COLS = ["Estrategia", "Operación", "Fecha", "Títulos", "Precio", "Tipo de cambio"]
_CODE = {"DCA": "DCA", "Dividendos": "DIV", "Por Objetivos": "OBJ", "FIBRAs": "FIB"}
_CODE_MOD = {"DCA": "DCA", "DIV": "Dividendos", "OBJ": "Por Objetivos", "FIB": "FIBRAs"}
_HEAD_FILL = PatternFill("solid", fgColor="6C63FF")
_HEAD_FONT = Font(color="FFFFFF", bold=True, size=11)
_TITLE_FONT = Font(bold=True, size=13, color="1A1A2E")


def _modulos():
    return [
        ("DCA", db_utils.load_strategies(), db_utils.load_purchases, None),
        ("Dividendos", db_utils.load_div_strategies(), db_utils.load_div_purchases, None),
        ("Por Objetivos", db_utils.load_obj_strategies(), db_utils.load_obj_purchases,
         db_utils.load_obj_sales),
        ("FIBRAs", db_utils.load_fibra_strategies(), db_utils.load_fibra_purchases, None),
    ]


def _label_estrategia(modulo, e) -> str:
    """Etiqueta legible y ÚNICA para el desplegable (con id oculto al final)."""
    tk = e.get("ticker", "")
    code = _CODE[modulo]
    if modulo == "DCA":
        det = f"{e.get('frecuencia', '')} · inicio {str(e.get('fecha_inicio', ''))[:10]}"
        base = f"DCA · {tk} · {det}"
    elif modulo == "Por Objetivos":
        base = f"Por Objetivos · {tk} · entrada {e.get('precio_entrada')} / salida {e.get('precio_salida')}"
    elif modulo == "Dividendos":
        base = f"Dividendos · {tk}"
    else:
        base = f"FIBRAs · {tk}"
    return f"{base}  —  id {code}-{e['id']}"


# ── Generar plantilla ────────────────────────────────────────────────────────
def generar_plantilla() -> bytes:
    wb = openpyxl.Workbook()
    _hoja_instrucciones(wb.active)

    ws = wb.create_sheet("Movimientos")
    ws_lst = wb.create_sheet("Listas")

    # Lista de estrategias (para el desplegable)
    labels = [_label_estrategia(m, e) for m, ests, _lc, _lv in _modulos() for e in ests]
    ws_lst["A1"] = "Estrategias"
    for i, lab in enumerate(labels, start=2):
        ws_lst.cell(row=i, column=1, value=lab)
    ws_lst.sheet_state = "hidden"

    # Encabezados de Movimientos
    for c, h in enumerate(COLS, start=1):
        cell = ws.cell(row=1, column=c, value=h)
        cell.fill = _HEAD_FILL
        cell.font = _HEAD_FONT
        cell.alignment = Alignment(horizontal="center")
    for i, w in enumerate([50, 12, 13, 9, 11, 14], start=1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "A2"

    # Desplegables
    n = max(len(labels), 1)
    dv_est = DataValidation(type="list", formula1=f"Listas!$A$2:$A${n + 1}", allow_blank=True,
                            showErrorMessage=True)
    dv_est.error = "Elige una estrategia de la lista."
    dv_est.prompt = "Elige la estrategia de la lista desplegable"
    ws.add_data_validation(dv_est)
    dv_est.add("A2:A1000")

    dv_op = DataValidation(type="list", formula1='"Compra,Venta"', allow_blank=True,
                           showErrorMessage=True)
    dv_op.error = "Escribe Compra o Venta."
    ws.add_data_validation(dv_op)
    dv_op.add("B2:B1000")

    _hoja_historial(wb)

    bio = io.BytesIO()
    wb.save(bio)
    return bio.getvalue()


def _precio_usd(precio, tc):
    """Precio en dólares: solo aplica a empresas del SIC (compradas en USD, tc != 1)."""
    try:
        if precio is not None and tc and float(tc) != 1.0:
            return round(float(precio) / float(tc), 2)
    except Exception:
        pass
    return ""  # empresas en pesos (BMV/FIBRAs): no aplica


def _hoja_historial(wb):
    ws = wb.create_sheet("Historial")
    headers = ["Módulo", "Estrategia", "Operación", "Fecha", "Títulos",
               "Precio MXN", "Tipo de cambio", "Precio USD (SIC)", "Comisión"]
    for c, h in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=c, value=h)
        cell.fill = _HEAD_FILL
        cell.font = _HEAD_FONT
    for modulo, estrategias, load_c, load_v in _modulos():
        for e in estrategias:
            nombre = e.get("ticker", "")
            for c in load_c(e["id"]):
                tc = c.get("tipo_cambio", 1.0)
                ws.append([modulo, nombre, "Compra", c.get("fecha"), c.get("titulos"),
                           c.get("precio"), tc, _precio_usd(c.get("precio"), tc),
                           c.get("comision", 0.0)])
            if load_v:
                for v in load_v(e["id"]):
                    tc = v.get("tipo_cambio", 1.0)
                    ws.append([modulo, nombre, "Venta", v.get("fecha"), v.get("titulos"),
                               v.get("precio"), tc, _precio_usd(v.get("precio"), tc),
                               v.get("comision", 0.0)])
    for i, w in enumerate([14, 16, 11, 14, 10, 12, 14, 15, 12], start=1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "A2"


def _hoja_instrucciones(ws):
    ws.title = "Instrucciones"
    lineas = [
        ("Plantilla — Smart Strategy Engine", _TITLE_FONT),
        ("", None),
        ("Cómo llenarla:", Font(bold=True, size=11)),
        ("1. Ve a la pestaña 'Movimientos'.", None),
        ("2. En cada fila, elige la Estrategia y la Operación desde las listas", None),
        ("   desplegables (la flechita ▾). No las escribas a mano.", None),
        ("3. Llena los datos de cada fila:", None),
        ("     • Fecha: formato AÑO-MES-DÍA, por ejemplo 2026-01-15.", None),
        ("     • Títulos: cuántas acciones (número entero).", None),
        ("     • Precio: el precio por acción EN PESOS (MXN).", None),
        ("     • Tipo de cambio: solo si compraste en dólares (pesos por dólar). Si no, deja 1.", None),
        ("     La comisión NO se pide aquí: se calcula sola con el % de comisión de tu Perfil.", None),
        ("4. Guarda el archivo y súbelo en la app, en el botón 'Importar'.", None),
        ("", None),
        ("Notas:", Font(bold=True, size=11)),
        ("• La lista de Estrategia distingue las repetidas: si tienes dos DCA de MU,", None),
        ("  verás su frecuencia y fecha de inicio para saber cuál es cuál.", None),
        ("• Solo 'Por Objetivos' admite Venta. Copy Trading no se importa por aquí.", None),
        ("• La pestaña 'Historial' es solo informativa (lo que ya tienes cargado).", None),
    ]
    for i, (txt, font) in enumerate(lineas, start=1):
        ws.cell(row=i, column=1, value=txt)
        if font:
            ws.cell(row=i, column=1).font = font
    ws.column_dimensions["A"].width = 95


# ── Importar plantilla ───────────────────────────────────────────────────────
def _parse_fecha(v):
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    s = str(v).strip()[:10]
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"fecha inválida: {v}")


def importar_excel(archivo) -> dict:
    wb = openpyxl.load_workbook(archivo, data_only=True)
    res = {"insertadas": 0, "errores": [], "por_estrategia": {}}
    if "Movimientos" not in wb.sheetnames:
        res["errores"].append("El archivo no tiene la hoja 'Movimientos'. Descarga la plantilla de nuevo.")
        return res
    ws = wb["Movimientos"]
    for r in range(2, ws.max_row + 1):
        est = ws.cell(r, 1).value
        op = ws.cell(r, 2).value
        fecha = ws.cell(r, 3).value
        tit = ws.cell(r, 4).value
        precio = ws.cell(r, 5).value
        tc = ws.cell(r, 6).value
        if not est and tit in (None, "") and precio in (None, ""):
            continue  # fila vacía
        m = re.search(r"id (DCA|DIV|OBJ|FIB)-(\d+)", str(est or ""))
        if not m:
            res["errores"].append(f"fila {r}: elige la Estrategia de la lista desplegable")
            continue
        modulo = _CODE_MOD[m.group(1)]
        sid = int(m.group(2))
        etiqueta = str(est).split("  —  ")[0]
        try:
            fecha_d = _parse_fecha(fecha)
            tit_i = int(float(tit))
            precio_f = float(precio)
            tc_f = float(tc) if tc not in (None, "") else 1.0
            # La comisión ya no se pide en el Excel: se calcula con el % del perfil.
            com_f = comision_desde_perfil(tit_i * precio_f)
            es_venta = bool(op) and str(op).strip().lower().startswith("v")
        except Exception:
            res["errores"].append(f"fila {r}: datos incompletos o inválidos")
            continue
        if tit_i <= 0 or precio_f <= 0:
            res["errores"].append(f"fila {r}: títulos y precio deben ser mayores a 0")
            continue
        ok = _insertar(modulo, sid, es_venta, fecha_d, tit_i, precio_f, tc_f, com_f, res, r)
        if ok:
            res["insertadas"] += 1
            res["por_estrategia"][etiqueta] = res["por_estrategia"].get(etiqueta, 0) + 1
    return res


def _insertar(modulo, sid, es_venta, fecha, tit, precio, tc, com, res, r) -> bool:
    if modulo == "DCA":
        if es_venta:
            res["errores"].append(f"fila {r}: DCA no admite ventas")
            return False
        db_utils.save_purchase(sid, fecha, tit, precio, tc, com)
        return True
    if modulo == "Dividendos":
        if es_venta:
            res["errores"].append(f"fila {r}: Dividendos no admite ventas")
            return False
        db_utils.save_div_purchase(sid, fecha, tit, precio, tc, com)
        return True
    if modulo == "FIBRAs":
        if es_venta:
            res["errores"].append(f"fila {r}: FIBRAs no admite ventas")
            return False
        db_utils.save_fibra_purchase(sid, fecha, tit, precio, com)
        return True
    if modulo == "Por Objetivos":
        if not es_venta:
            db_utils.save_obj_purchase(sid, fecha, tit, precio, tc, com)
            return True
        return _vender_objetivos_fifo(sid, fecha, tit, precio, tc, com, res, r)
    res["errores"].append(f"fila {r}: módulo desconocido")
    return False


def _vender_objetivos_fifo(sid, fecha, titulos, precio, tc, com, res, r) -> bool:
    compras = sorted(db_utils.load_obj_purchases(sid), key=lambda c: str(c["fecha"]))
    ventas = db_utils.load_obj_sales(sid)
    vendido = {}
    for v in ventas:
        vendido[v["compra_id"]] = vendido.get(v["compra_id"], 0) + v["titulos"]
    restante = titulos
    com_pendiente = com
    for c in compras:
        if restante <= 0:
            break
        disponible = c["titulos"] - vendido.get(c["id"], 0)
        if disponible <= 0:
            continue
        asignar = min(disponible, restante)
        db_utils.save_obj_sale(c["id"], sid, fecha, asignar, precio, tc, com_pendiente)
        com_pendiente = 0.0
        restante -= asignar
    if restante == titulos:
        res["errores"].append(f"fila {r}: no hay títulos disponibles para vender")
        return False
    if restante > 0:
        res["errores"].append(
            f"fila {r}: venta de {titulos} excede lo disponible ({titulos - restante} aplicados)")
    return True
