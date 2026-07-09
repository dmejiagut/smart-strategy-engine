"""
Pipeline de validación y auditoría de estrategias VestPlan.

Al CREAR o MODIFICAR una estrategia (lo disparan los save_* de db_utils):
  1. Validar campos requeridos.
  2. Revisar coherencia lógica.
  3. Calcular métricas de riesgo (volatilidad anualizada, máximo drawdown).
  4. Validar disponibilidad y calidad de datos de mercado.
  5. Guardar la estrategia (la escribe db_utils; aquí queda el registro).

PERIÓDICAMENTE — 1 vez al día, al abrir la app (Streamlit no tiene procesos
en segundo plano, así que "periódico" = oportunista con candado diario):
  6. Revisar condiciones de entrada y salida.
  7. Actualizar estadísticas históricas.
  8. Detectar posibles optimizaciones.

Idempotencia: cada paso corre UNA sola vez por VERSIÓN de la estrategia
(hash md5 de sus campos definitorios). Los pasos periódicos corren una vez
por versión POR DÍA. Un paso que terminó en 'error' sí puede reintentarse
(p. ej. si falló la red); uno que terminó 'ok' o 'advertencia' no se repite.
Cada resultado queda en la tabla pipeline_logs para auditoría.
"""
import hashlib
import json
from datetime import date

PASOS = {1: "1. Campos requeridos", 2: "2. Coherencia lógica",
         3: "3. Métricas de riesgo", 4: "4. Calidad de datos",
         5: "5. Guardar estrategia", 6: "6. Condiciones entrada/salida",
         7: "7. Estadísticas históricas", 8: "8. Optimizaciones"}

# Campos que DEFINEN cada estrategia (la versión cambia solo si cambian éstos)
_CAMPOS_VERSION = {
    "DCA": ("ticker", "frecuencia", "titulos", "fecha_inicio", "fecha_fin"),
    "Dividendos": ("ticker", "nombre"),
    "Por Objetivos": ("ticker", "precio_entrada", "precio_salida"),
    "FIBRAs": ("ticker", "nombre"),
    "Copy Trading": ("investor_id", "nombre"),
}


def _conn():
    from utils import db_utils
    c = db_utils._get_conn()
    c.execute("""
        CREATE TABLE IF NOT EXISTS pipeline_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            modulo TEXT NOT NULL,
            version TEXT NOT NULL,
            paso INTEGER NOT NULL,
            resultado TEXT NOT NULL,   -- ok | advertencia | error | omitido
            detalle TEXT,
            estrategia_id INTEGER,
            periodo TEXT DEFAULT '',   -- '' pasos 1-5; 'YYYY-MM-DD' pasos 6-8
            creado_en TEXT DEFAULT (datetime('now'))
        )
    """)
    return c


def version_de(modulo: str, datos: dict) -> str:
    """Versión = hash corto de los campos definitorios (mismo dato → misma versión)."""
    campos = _CAMPOS_VERSION.get(modulo, tuple(sorted(datos)))
    base = json.dumps({k: str(datos.get(k)) for k in campos}, sort_keys=True)
    return hashlib.md5(base.encode()).hexdigest()[:10]


def _hecho(modulo: str, version: str, paso: int, periodo: str = "") -> bool:
    """True si el paso ya corrió para esta versión (y periodo) SIN terminar en error."""
    c = _conn()
    row = c.execute(
        "SELECT 1 FROM pipeline_logs WHERE modulo=? AND version=? AND paso=? "
        "AND periodo=? AND resultado != 'error' LIMIT 1",
        (modulo, version, paso, periodo)).fetchone()
    c.close()
    return row is not None


def _log(modulo, version, paso, resultado, detalle="", eid=None, periodo=""):
    c = _conn()
    c.execute(
        "INSERT INTO pipeline_logs (modulo, version, paso, resultado, detalle, "
        "estrategia_id, periodo) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (modulo, version, int(paso), resultado, str(detalle)[:500], eid, periodo))
    c.commit()
    c.close()


def leer_logs(limite: int = 30) -> list[dict]:
    """Últimos registros del pipeline (para el visor de auditoría)."""
    c = _conn()
    rows = c.execute(
        "SELECT * FROM pipeline_logs ORDER BY id DESC LIMIT ?", (limite,)).fetchall()
    c.close()
    return [dict(r) for r in rows]


# ─── Pasos 1-4: validaciones al guardar ──────────────────────────────────────

def _validar_campos(modulo, d):
    requeridos = {
        "DCA": ["ticker", "frecuencia", "titulos", "fecha_inicio", "fecha_fin"],
        "Dividendos": ["ticker"],
        "Por Objetivos": ["ticker", "precio_entrada", "precio_salida"],
        "FIBRAs": ["ticker"],
        "Copy Trading": ["investor_id"],
    }.get(modulo, [])
    return [c for c in requeridos if d.get(c) in (None, "", 0)]


def _coherencia(modulo, d):
    """(errores, advertencias) de lógica del negocio."""
    err, adv = [], []
    if modulo == "DCA":
        if str(d.get("fecha_fin")) <= str(d.get("fecha_inicio")):
            err.append("la fecha final debe ser posterior a la inicial")
        try:
            t = int(d.get("titulos") or 0)
            if t < 1:
                err.append("los títulos por compra deben ser al menos 1")
            elif t > 10000:
                adv.append("títulos por compra inusualmente altos")
        except (TypeError, ValueError):
            err.append("títulos inválidos")
    elif modulo == "Por Objetivos":
        ent = float(d.get("precio_entrada") or 0)
        sal = float(d.get("precio_salida") or 0)
        if ent <= 0:
            err.append("el precio de entrada debe ser mayor a 0")
        if sal <= ent:
            err.append("el precio de salida debe ser mayor al de entrada")
        elif ent > 0 and (sal - ent) / ent > 1.0:
            adv.append(f"ganancia objetivo de {(sal-ent)/ent*100:.0f}% — meta muy ambiciosa")
    if modulo in ("Dividendos", "FIBRAs", "DCA"):
        tk = str(d.get("ticker") or "")
        if tk and (len(tk) > 12 or " " in tk):
            adv.append(f"ticker '{tk}' con formato inusual")
    return err, adv


def _metricas_riesgo(ticker):
    """Volatilidad anualizada, máximo drawdown y etiqueta de riesgo (10 años)."""
    from utils.technical_utils import get_ohlc
    df = get_ohlc(ticker)
    if df is None or df.empty or len(df) < 30:
        return None
    r = df["Close"].pct_change().dropna()
    vol = float(r.std() * (252 ** 0.5) * 100)
    dd = float(((df["Close"] / df["Close"].cummax()) - 1).min() * 100)
    etiqueta = "Bajo" if vol < 20 else ("Medio" if vol < 35 else "Alto")
    return {"volatilidad_anual_pct": round(vol, 1),
            "max_drawdown_pct": round(dd, 1), "riesgo": etiqueta,
            "observaciones": len(df)}


def _calidad_datos(ticker):
    """(errores, advertencias) sobre disponibilidad/calidad de datos de mercado."""
    from utils.ticker_search import get_precio_actual
    from utils.technical_utils import get_ohlc
    err, adv = [], []
    q = get_precio_actual(ticker)
    precio = q.get("precio") if q else None
    df = get_ohlc(ticker)
    sin_hist = df is None or df.empty
    if not precio and sin_hist:
        err.append(f"no hay datos de mercado para {ticker}")
    else:
        if not precio:
            adv.append("sin precio en vivo (se usará el último conocido)")
        if sin_hist:
            adv.append("sin histórico OHLC (no habrá métricas de riesgo)")
        elif len(df) < 200:
            adv.append(f"histórico corto ({len(df)} días) — métricas poco robustas")
    return err, adv


def pipeline_guardado(modulo: str, datos: dict) -> dict:
    """Corre los pasos 1-4 (una vez por versión). Devuelve ok/errores/advertencias."""
    v = version_de(modulo, datos)
    res = {"version": v, "ok": True, "errores": [], "advertencias": [], "metricas": None}
    ticker = datos.get("ticker")

    # 1. Campos requeridos
    if not _hecho(modulo, v, 1):
        faltan = _validar_campos(modulo, datos)
        _log(modulo, v, 1, "error" if faltan else "ok",
             f"faltan: {', '.join(faltan)}" if faltan else "todos los campos presentes")
        if faltan:
            res["ok"] = False
            res["errores"].append("faltan campos: " + ", ".join(faltan))
            return res

    # 2. Coherencia lógica
    if not _hecho(modulo, v, 2):
        err, adv = _coherencia(modulo, datos)
        _log(modulo, v, 2, "error" if err else ("advertencia" if adv else "ok"),
             "; ".join(err + adv) or "coherente")
        res["advertencias"] += adv
        if err:
            res["ok"] = False
            res["errores"] += err
            return res

    # 3. Métricas de riesgo (solo estrategias con ticker)
    if not _hecho(modulo, v, 3):
        if ticker:
            m = _metricas_riesgo(ticker)
            res["metricas"] = m
            _log(modulo, v, 3, "ok" if m else "advertencia",
                 json.dumps(m) if m else "sin histórico suficiente para métricas")
            if m is None:
                res["advertencias"].append("sin métricas de riesgo (histórico insuficiente)")
        else:
            _log(modulo, v, 3, "omitido", "estrategia sin ticker único (n/a)")

    # 4. Disponibilidad y calidad de datos
    if not _hecho(modulo, v, 4):
        if ticker:
            err, adv = _calidad_datos(ticker)
            _log(modulo, v, 4, "error" if err else ("advertencia" if adv else "ok"),
                 "; ".join(err + adv) or "datos disponibles y frescos")
            res["advertencias"] += adv
            if err:
                res["ok"] = False
                res["errores"] += err
        else:
            _log(modulo, v, 4, "omitido", "sin ticker único (n/a)")
    return res


def registrar_guardado(modulo: str, version: str, eid):
    """Paso 5: deja constancia de que la estrategia se guardó (una vez por id)."""
    c = _conn()
    ya = c.execute(
        "SELECT 1 FROM pipeline_logs WHERE modulo=? AND version=? AND paso=5 "
        "AND estrategia_id=? LIMIT 1", (modulo, version, eid)).fetchone()
    c.close()
    if not ya:
        _log(modulo, version, 5, "ok", f"estrategia guardada (id {eid})", eid=eid)


# ─── Pasos 6-8: revisión periódica (1 vez al día por versión) ────────────────

def pipeline_periodico():
    """Corre los pasos 6-8 para todas las estrategias. Candado: 1 vez al día."""
    from utils import db_utils as db
    hoy = date.today().isoformat()
    c = _conn()
    ya_hoy = c.execute(
        "SELECT 1 FROM pipeline_logs WHERE periodo=? LIMIT 1", (hoy,)).fetchone()
    c.close()
    if ya_hoy:
        return False   # ya corrió hoy

    from utils.ticker_search import get_precio_actual
    from utils.technical_utils import get_ohlc, sugerir_entrada_salida

    def _fila_datos(modulo, e):
        return {k: e.get(k) for k in _CAMPOS_VERSION[modulo]}

    # 6-8 para DCA
    for e in db.load_strategies():
        v = version_de("DCA", _fila_datos("DCA", e))
        if not _hecho("DCA", v, 6, hoy):
            try:
                from modules.dca import generar_fechas_dca, _parse_fecha, FRECUENCIAS
                plan = generar_fechas_dca(_parse_fecha(e["fecha_inicio"]),
                                          _parse_fecha(e["fecha_fin"]), e["frecuencia"])
                hechas = len(db.load_purchases(e["id"]))
                if hechas >= len(plan):
                    det = "plan completado"
                else:
                    delta = (plan[hechas] - date.today()).days
                    det = (f"compra vencida hace {-delta} día(s)" if delta < 0
                           else ("compra programada HOY" if delta == 0
                                 else f"próxima compra en {delta} día(s)"))
                _log("DCA", v, 6, "ok", det, eid=e["id"], periodo=hoy)
            except Exception as ex:
                _log("DCA", v, 6, "error", str(ex), eid=e["id"], periodo=hoy)
        _estadisticas_y_optimizacion("DCA", e, v, hoy, db, get_precio_actual, get_ohlc)

    # 6-8 para Por Objetivos
    for e in db.load_obj_strategies():
        v = version_de("Por Objetivos", _fila_datos("Por Objetivos", e))
        if not _hecho("Por Objetivos", v, 6, hoy):
            q = get_precio_actual(e["ticker"])
            px = q.get("precio") if q else None
            if not px:
                _log("Por Objetivos", v, 6, "advertencia", "sin precio en vivo",
                     eid=e["id"], periodo=hoy)
            else:
                ent, sal = float(e["precio_entrada"] or 0), float(e["precio_salida"] or 0)
                det = (f"tocó SALIDA (${px:,.2f} ≥ ${sal:,.2f})" if sal and px >= sal
                       else (f"tocó ENTRADA (${px:,.2f} ≤ ${ent:,.2f})" if ent and px <= ent
                             else f"en rango (${px:,.2f})"))
                _log("Por Objetivos", v, 6, "ok", det, eid=e["id"], periodo=hoy)
        # 8. Optimización: comparar objetivos con la sugerencia técnica del día
        if not _hecho("Por Objetivos", v, 8, hoy):
            try:
                sug = sugerir_entrada_salida(get_ohlc(e["ticker"]))
                if sug.get("ok"):
                    ent = float(e["precio_entrada"] or 0)
                    dif = abs(sug["entrada"] - ent) / ent * 100 if ent else 0
                    if dif > 10:
                        _log("Por Objetivos", v, 8, "advertencia",
                             f"posible optimización: entrada sugerida ${sug['entrada']:,.2f} "
                             f"vs tu ${ent:,.2f} ({dif:.0f}% de diferencia)",
                             eid=e["id"], periodo=hoy)
                    else:
                        _log("Por Objetivos", v, 8, "ok",
                             "objetivos alineados con el análisis técnico del día",
                             eid=e["id"], periodo=hoy)
                else:
                    _log("Por Objetivos", v, 8, "omitido", "sin datos para sugerencia",
                         eid=e["id"], periodo=hoy)
            except Exception as ex:
                _log("Por Objetivos", v, 8, "error", str(ex), eid=e["id"], periodo=hoy)
        _estadisticas_y_optimizacion("Por Objetivos", e, v, hoy, db,
                                     get_precio_actual, get_ohlc, solo_stats=True)

    # 6-8 para Dividendos y FIBRAs (condiciones n/a; estadísticas sí)
    for modulo, cargar in (("Dividendos", db.load_div_strategies),
                           ("FIBRAs", db.load_fibra_strategies)):
        for e in cargar():
            v = version_de(modulo, _fila_datos(modulo, e))
            if not _hecho(modulo, v, 6, hoy):
                _log(modulo, v, 6, "omitido", "sin condiciones de entrada/salida (n/a)",
                     eid=e["id"], periodo=hoy)
            _estadisticas_y_optimizacion(modulo, e, v, hoy, db,
                                         get_precio_actual, get_ohlc)
    return True


def _estadisticas_y_optimizacion(modulo, e, v, hoy, db, get_precio_actual,
                                 get_ohlc, solo_stats=False):
    """Paso 7 (todas con ticker) y paso 8 genérico (DCA: precio vs promedio)."""
    ticker = e.get("ticker")
    if not ticker:
        return
    if not _hecho(modulo, v, 7, hoy):
        m = _metricas_riesgo(ticker)
        q = get_precio_actual(ticker)
        px = q.get("precio") if q else None
        det = dict(m or {})
        if px:
            det["precio_actual"] = px
        _log(modulo, v, 7, "ok" if m else "advertencia",
             json.dumps(det) if det else "sin datos", eid=e["id"], periodo=hoy)
    if solo_stats or modulo != "DCA":
        return
    if not _hecho("DCA", v, 8, hoy):
        try:
            compras = db.load_purchases(e["id"])
            q = get_precio_actual(ticker)
            px = q.get("precio") if q else None
            if compras and px:
                tot_t = sum(c["titulos"] for c in compras)
                prom_mxn = (sum(c["titulos"] * c["precio"] for c in compras) / tot_t) if tot_t else 0
                tc = compras[-1].get("tipo_cambio") or 1.0
                prom_usd = prom_mxn / tc if tc else prom_mxn
                if prom_usd and px < prom_usd * 0.9:
                    _log("DCA", v, 8, "advertencia",
                         f"precio actual ${px:,.2f} está 10%+ debajo de tu promedio "
                         f"(≈${prom_usd:,.2f}) — ventana favorable para tu siguiente compra",
                         eid=e["id"], periodo=hoy)
                else:
                    _log("DCA", v, 8, "ok", "sin optimización relevante hoy",
                         eid=e["id"], periodo=hoy)
            else:
                _log("DCA", v, 8, "omitido", "sin compras o sin precio", eid=e["id"], periodo=hoy)
        except Exception as ex:
            _log("DCA", v, 8, "error", str(ex), eid=e["id"], periodo=hoy)
