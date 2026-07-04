import sqlite3
from datetime import datetime
from pathlib import Path

DB_DIR = Path(__file__).parent.parent / "db"
DB_FILES = {"real": "sse.db", "demo": "sse_demo.db"}
PRECIOS_DB = DB_DIR / "precios.db"  # caché de precios de mercado (público, no es dato del usuario)
_MODO = "real"  # 'real' o 'demo'


def set_modo(modo: str):
    """Cambia entre la base real y la de demostración (datos sintéticos)."""
    global _MODO
    _MODO = modo if modo in DB_FILES else "real"


def get_modo() -> str:
    return _MODO


def _db_path() -> Path:
    return DB_DIR / DB_FILES[_MODO]


def _get_conn():
    p = _db_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(p))
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = _get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS estrategias_dca (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            frecuencia TEXT NOT NULL,
            titulos INTEGER NOT NULL,
            fecha_inicio TEXT NOT NULL,
            fecha_fin TEXT NOT NULL,
            n_fechas INTEGER NOT NULL,
            tipo_cambio REAL,
            comision_pct REAL,
            cal_activado INTEGER DEFAULT 0,
            cal_hora TEXT,
            cal_anticip INTEGER DEFAULT 1,
            creado_en TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS compras_dca (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            estrategia_id INTEGER NOT NULL,
            fecha TEXT NOT NULL,
            titulos INTEGER NOT NULL,
            precio REAL NOT NULL,
            tipo_cambio REAL DEFAULT 1.0,
            comision REAL DEFAULT 0.0,
            creado_en TEXT DEFAULT (datetime('now'))
        )
    """)
    for alter in (
        "ALTER TABLE compras_dca ADD COLUMN tipo_cambio REAL DEFAULT 1.0",
        "ALTER TABLE compras_dca ADD COLUMN comision REAL DEFAULT 0.0",
    ):
        try:
            conn.execute(alter)
        except Exception:
            pass  # columna ya existe
    # Marca de "recordatorios ya creados en Google Calendar" (migración única)
    try:
        conn.execute("ALTER TABLE estrategias_dca ADD COLUMN cal_creado INTEGER DEFAULT 0")
        conn.execute("UPDATE estrategias_dca SET cal_creado = 1 WHERE cal_activado = 1")
    except Exception:
        pass  # columna ya existe
    # % de comisión de la casa de bolsa (se guarda en el perfil)
    try:
        conn.execute("ALTER TABLE perfil ADD COLUMN comision_pct REAL DEFAULT 0.25")
    except Exception:
        pass  # columna ya existe
    # ── Dividendos ──
    conn.execute("""
        CREATE TABLE IF NOT EXISTS estrategias_dividendos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            nombre TEXT,
            giro TEXT,
            creado_en TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS compras_dividendos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            estrategia_id INTEGER NOT NULL,
            fecha TEXT NOT NULL,
            titulos INTEGER NOT NULL,
            precio REAL NOT NULL,
            tipo_cambio REAL DEFAULT 1.0,
            comision REAL DEFAULT 0.0,
            creado_en TEXT DEFAULT (datetime('now'))
        )
    """)
    # ── Por Objetivos (análisis técnico) ──
    conn.execute("""
        CREATE TABLE IF NOT EXISTS estrategias_objetivos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            nombre TEXT,
            precio_entrada REAL NOT NULL,
            precio_salida REAL NOT NULL,
            tipo_cambio REAL DEFAULT 1.0,
            creado_en TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS compras_objetivos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            estrategia_id INTEGER NOT NULL,
            fecha TEXT NOT NULL,
            titulos INTEGER NOT NULL,
            precio REAL NOT NULL,
            tipo_cambio REAL DEFAULT 1.0,
            comision REAL DEFAULT 0.0,
            creado_en TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ventas_objetivos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            compra_id INTEGER NOT NULL,
            estrategia_id INTEGER NOT NULL,
            fecha TEXT NOT NULL,
            titulos INTEGER NOT NULL,
            precio REAL NOT NULL,
            tipo_cambio REAL DEFAULT 1.0,
            comision REAL DEFAULT 0.0,
            creado_en TEXT DEFAULT (datetime('now'))
        )
    """)
    # ── FIBRAs (solo MXN) ──
    conn.execute("""
        CREATE TABLE IF NOT EXISTS estrategias_fibras (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            nombre TEXT,
            sector TEXT,
            creado_en TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS compras_fibras (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            estrategia_id INTEGER NOT NULL,
            fecha TEXT NOT NULL,
            titulos INTEGER NOT NULL,
            precio REAL NOT NULL,
            comision REAL DEFAULT 0.0,
            creado_en TEXT DEFAULT (datetime('now'))
        )
    """)
    # ── Copy Trading ──
    conn.execute("""
        CREATE TABLE IF NOT EXISTS estrategias_copy (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            investor_id TEXT NOT NULL,
            nombre TEXT,
            fondo TEXT,
            creado_en TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS compras_copy (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            estrategia_id INTEGER NOT NULL,
            fecha TEXT NOT NULL,
            monto_mxn REAL NOT NULL,
            tipo_cambio REAL NOT NULL,
            creado_en TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS detalle_copy (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            compra_id INTEGER NOT NULL,
            ticker TEXT NOT NULL,
            titulos INTEGER NOT NULL,
            precio_usd REAL NOT NULL
        )
    """)
    # ── Perfil del usuario ──
    conn.execute("""
        CREATE TABLE IF NOT EXISTS perfil (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            nombre TEXT,
            edad INTEGER,
            ingreso_mensual REAL,
            objetivo TEXT,
            perfil_riesgo TEXT,
            horizonte_anios INTEGER,
            actualizado TEXT DEFAULT (datetime('now'))
        )
    """)
    # ── Ventas cerradas (historial de rendimiento realizado, multi-módulo) ──
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ventas_cerradas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            modulo TEXT NOT NULL,
            estrategia_id INTEGER NOT NULL,
            ticker TEXT,
            fecha TEXT NOT NULL,
            titulos INTEGER NOT NULL,
            precio REAL NOT NULL,
            tipo_cambio REAL DEFAULT 1.0,
            comision REAL DEFAULT 0.0,
            costo_base REAL DEFAULT 0.0,
            ingreso REAL DEFAULT 0.0,
            ganancia REAL DEFAULT 0.0,
            creado_en TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.commit()
    conn.close()

# ── Perfil del usuario ─────────────────────────────────────────────────────────

def get_perfil() -> dict:
    init_db()
    conn = _get_conn()
    row = conn.execute("SELECT * FROM perfil WHERE id = 1").fetchone()
    conn.close()
    return dict(row) if row else {}

def set_comision_pct(pct: float):
    """Guarda el % de comisión de la casa de bolsa en el perfil (aplica de aquí en adelante)."""
    init_db()
    conn = _get_conn()
    conn.execute(
        "INSERT INTO perfil (id, comision_pct) VALUES (1, ?) "
        "ON CONFLICT(id) DO UPDATE SET comision_pct = ?", (float(pct), float(pct)))
    conn.commit()
    conn.close()


def save_perfil(data: dict):
    init_db()
    conn = _get_conn()
    conn.execute("""
        INSERT INTO perfil (id, nombre, edad, ingreso_mensual, objetivo, perfil_riesgo, horizonte_anios, actualizado)
        VALUES (1, :nombre, :edad, :ingreso_mensual, :objetivo, :perfil_riesgo, :horizonte_anios, datetime('now'))
        ON CONFLICT(id) DO UPDATE SET
            nombre=:nombre, edad=:edad, ingreso_mensual=:ingreso_mensual,
            objetivo=:objetivo, perfil_riesgo=:perfil_riesgo,
            horizonte_anios=:horizonte_anios, actualizado=datetime('now')
    """, {
        "nombre": data.get("nombre"), "edad": data.get("edad"),
        "ingreso_mensual": data.get("ingreso_mensual"), "objetivo": data.get("objetivo"),
        "perfil_riesgo": data.get("perfil_riesgo"), "horizonte_anios": data.get("horizonte_anios"),
    })
    conn.commit()
    conn.close()

# ── Estrategias de Copy Trading ────────────────────────────────────────────────

def save_copy_strategy(investor_id: str, nombre: str = "", fondo: str = "") -> int:
    init_db()
    conn = _get_conn()
    existing = conn.execute(
        "SELECT id FROM estrategias_copy WHERE investor_id = ?", (investor_id,)
    ).fetchone()
    if existing:
        conn.close()
        return int(existing["id"])
    cur = conn.execute(
        "INSERT INTO estrategias_copy (investor_id, nombre, fondo) VALUES (?, ?, ?)",
        (investor_id, nombre, fondo),
    )
    new_id = cur.lastrowid
    conn.commit()
    conn.close()
    return int(new_id)

def load_copy_strategies() -> list[dict]:
    init_db()
    conn = _get_conn()
    rows = conn.execute("SELECT * FROM estrategias_copy ORDER BY creado_en DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def delete_copy_strategy(strategy_id: int):
    conn = _get_conn()
    compras = conn.execute("SELECT id FROM compras_copy WHERE estrategia_id = ?", (strategy_id,)).fetchall()
    for c in compras:
        conn.execute("DELETE FROM detalle_copy WHERE compra_id = ?", (c["id"],))
    conn.execute("DELETE FROM compras_copy WHERE estrategia_id = ?", (strategy_id,))
    conn.execute("DELETE FROM estrategias_copy WHERE id = ?", (strategy_id,))
    conn.commit()
    conn.close()

def save_copy_purchase(estrategia_id: int, fecha, monto_mxn: float, tipo_cambio: float,
                       detalle: list[dict]) -> int:
    """detalle: lista de {ticker, titulos, precio_usd}."""
    init_db()
    conn = _get_conn()
    cur = conn.execute(
        "INSERT INTO compras_copy (estrategia_id, fecha, monto_mxn, tipo_cambio) VALUES (?, ?, ?, ?)",
        (estrategia_id, str(fecha), float(monto_mxn), float(tipo_cambio)),
    )
    compra_id = cur.lastrowid
    for d in detalle:
        if d["titulos"] <= 0:
            continue
        conn.execute(
            "INSERT INTO detalle_copy (compra_id, ticker, titulos, precio_usd) VALUES (?, ?, ?, ?)",
            (compra_id, d["ticker"], int(d["titulos"]), float(d["precio_usd"])),
        )
    conn.commit()
    conn.close()
    return int(compra_id)

def load_copy_purchases(estrategia_id: int) -> list[dict]:
    init_db()
    conn = _get_conn()
    compras = conn.execute(
        "SELECT * FROM compras_copy WHERE estrategia_id = ? ORDER BY fecha DESC",
        (estrategia_id,),
    ).fetchall()
    result = []
    for c in compras:
        det = conn.execute(
            "SELECT * FROM detalle_copy WHERE compra_id = ?", (c["id"],)
        ).fetchall()
        d = dict(c)
        d["detalle"] = [dict(x) for x in det]
        result.append(d)
    conn.close()
    return result

def delete_copy_purchase(compra_id: int):
    conn = _get_conn()
    conn.execute("DELETE FROM detalle_copy WHERE compra_id = ?", (compra_id,))
    conn.execute("DELETE FROM compras_copy WHERE id = ?", (compra_id,))
    conn.commit()
    conn.close()

# ── Estrategias de FIBRAs ──────────────────────────────────────────────────────

def save_fibra_strategy(ticker: str, nombre: str = "", sector: str = "") -> int:
    init_db()
    conn = _get_conn()
    existing = conn.execute(
        "SELECT id FROM estrategias_fibras WHERE ticker = ?", (ticker,)
    ).fetchone()
    if existing:
        conn.close()
        return int(existing["id"])
    cur = conn.execute(
        "INSERT INTO estrategias_fibras (ticker, nombre, sector) VALUES (?, ?, ?)",
        (ticker, nombre, sector),
    )
    new_id = cur.lastrowid
    conn.commit()
    conn.close()
    return int(new_id)

def load_fibra_strategies() -> list[dict]:
    init_db()
    conn = _get_conn()
    rows = conn.execute("SELECT * FROM estrategias_fibras ORDER BY creado_en DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def delete_fibra_strategy(strategy_id: int):
    conn = _get_conn()
    conn.execute("DELETE FROM estrategias_fibras WHERE id = ?", (strategy_id,))
    conn.execute("DELETE FROM compras_fibras WHERE estrategia_id = ?", (strategy_id,))
    conn.commit()
    conn.close()

def save_fibra_purchase(estrategia_id: int, fecha, titulos: int, precio: float, comision: float = 0.0):
    init_db()
    conn = _get_conn()
    conn.execute(
        "INSERT INTO compras_fibras (estrategia_id, fecha, titulos, precio, comision) VALUES (?, ?, ?, ?, ?)",
        (estrategia_id, str(fecha), int(titulos), float(precio), float(comision)),
    )
    conn.commit()
    conn.close()

def load_fibra_purchases(estrategia_id: int) -> list[dict]:
    init_db()
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM compras_fibras WHERE estrategia_id = ? ORDER BY fecha ASC",
        (estrategia_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def delete_fibra_purchase(purchase_id: int):
    conn = _get_conn()
    conn.execute("DELETE FROM compras_fibras WHERE id = ?", (purchase_id,))
    conn.commit()
    conn.close()

# ── Estrategias por objetivos ──────────────────────────────────────────────────

def save_obj_strategy(ticker: str, nombre: str, precio_entrada: float,
                      precio_salida: float, tipo_cambio: float = 1.0) -> int:
    init_db()
    conn = _get_conn()
    cur = conn.execute(
        """INSERT INTO estrategias_objetivos
           (ticker, nombre, precio_entrada, precio_salida, tipo_cambio)
           VALUES (?, ?, ?, ?, ?)""",
        (ticker, nombre, float(precio_entrada), float(precio_salida), float(tipo_cambio)),
    )
    new_id = cur.lastrowid
    conn.commit()
    conn.close()
    return int(new_id)

def load_obj_strategies() -> list[dict]:
    init_db()
    conn = _get_conn()
    rows = conn.execute("SELECT * FROM estrategias_objetivos ORDER BY creado_en DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def delete_obj_strategy(strategy_id: int):
    conn = _get_conn()
    conn.execute("DELETE FROM estrategias_objetivos WHERE id = ?", (strategy_id,))
    conn.execute("DELETE FROM compras_objetivos WHERE estrategia_id = ?", (strategy_id,))
    conn.execute("DELETE FROM ventas_objetivos WHERE estrategia_id = ?", (strategy_id,))
    conn.commit()
    conn.close()

def save_obj_purchase(estrategia_id: int, fecha, titulos: int, precio: float,
                      tipo_cambio: float = 1.0, comision: float = 0.0):
    init_db()
    conn = _get_conn()
    conn.execute(
        "INSERT INTO compras_objetivos (estrategia_id, fecha, titulos, precio, tipo_cambio, comision) VALUES (?, ?, ?, ?, ?, ?)",
        (estrategia_id, str(fecha), int(titulos), float(precio), float(tipo_cambio), float(comision)),
    )
    conn.commit()
    conn.close()

def load_obj_purchases(estrategia_id: int) -> list[dict]:
    init_db()
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM compras_objetivos WHERE estrategia_id = ? ORDER BY fecha ASC",
        (estrategia_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def delete_obj_purchase(purchase_id: int):
    conn = _get_conn()
    conn.execute("DELETE FROM compras_objetivos WHERE id = ?", (purchase_id,))
    conn.execute("DELETE FROM ventas_objetivos WHERE compra_id = ?", (purchase_id,))
    conn.commit()
    conn.close()

def save_obj_sale(compra_id: int, estrategia_id: int, fecha, titulos: int, precio: float,
                  tipo_cambio: float = 1.0, comision: float = 0.0):
    init_db()
    conn = _get_conn()
    conn.execute(
        "INSERT INTO ventas_objetivos (compra_id, estrategia_id, fecha, titulos, precio, tipo_cambio, comision) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (compra_id, estrategia_id, str(fecha), int(titulos), float(precio), float(tipo_cambio), float(comision)),
    )
    conn.commit()
    conn.close()

def load_obj_sales(estrategia_id: int) -> list[dict]:
    init_db()
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM ventas_objetivos WHERE estrategia_id = ? ORDER BY fecha ASC",
        (estrategia_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def delete_obj_sale(sale_id: int):
    conn = _get_conn()
    conn.execute("DELETE FROM ventas_objetivos WHERE id = ?", (sale_id,))
    conn.commit()
    conn.close()

# ── Estrategias de dividendos ──────────────────────────────────────────────────

def save_div_strategy(ticker: str, nombre: str = "", giro: str = "") -> int:
    init_db()
    conn = _get_conn()
    # Evitar duplicados del mismo ticker
    existing = conn.execute(
        "SELECT id FROM estrategias_dividendos WHERE ticker = ?", (ticker,)
    ).fetchone()
    if existing:
        conn.close()
        return int(existing["id"])
    cur = conn.execute(
        "INSERT INTO estrategias_dividendos (ticker, nombre, giro) VALUES (?, ?, ?)",
        (ticker, nombre, giro),
    )
    new_id = cur.lastrowid
    conn.commit()
    conn.close()
    return int(new_id)

def load_div_strategies() -> list[dict]:
    init_db()
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM estrategias_dividendos ORDER BY creado_en DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def delete_div_strategy(strategy_id: int):
    conn = _get_conn()
    conn.execute("DELETE FROM estrategias_dividendos WHERE id = ?", (strategy_id,))
    conn.execute("DELETE FROM compras_dividendos WHERE estrategia_id = ?", (strategy_id,))
    conn.commit()
    conn.close()

def save_div_purchase(estrategia_id: int, fecha, titulos: int, precio: float,
                      tipo_cambio: float = 1.0, comision: float = 0.0):
    init_db()
    conn = _get_conn()
    conn.execute(
        "INSERT INTO compras_dividendos (estrategia_id, fecha, titulos, precio, tipo_cambio, comision) VALUES (?, ?, ?, ?, ?, ?)",
        (estrategia_id, str(fecha), int(titulos), float(precio), float(tipo_cambio), float(comision)),
    )
    conn.commit()
    conn.close()

def load_div_purchases(estrategia_id: int) -> list[dict]:
    init_db()
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM compras_dividendos WHERE estrategia_id = ? ORDER BY fecha ASC",
        (estrategia_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def delete_div_purchase(purchase_id: int):
    conn = _get_conn()
    conn.execute("DELETE FROM compras_dividendos WHERE id = ?", (purchase_id,))
    conn.commit()
    conn.close()

def save_purchase(estrategia_id: int, fecha, titulos: int, precio: float,
                  tipo_cambio: float = 1.0, comision: float = 0.0):
    init_db()
    conn = _get_conn()
    conn.execute(
        "INSERT INTO compras_dca (estrategia_id, fecha, titulos, precio, tipo_cambio, comision) VALUES (?, ?, ?, ?, ?, ?)",
        (estrategia_id, str(fecha), int(titulos), float(precio), float(tipo_cambio), float(comision)),
    )
    conn.commit()
    conn.close()

def load_purchases(estrategia_id: int) -> list[dict]:
    init_db()
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM compras_dca WHERE estrategia_id = ? ORDER BY fecha DESC",
        (estrategia_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def delete_purchase(purchase_id: int):
    conn = _get_conn()
    conn.execute("DELETE FROM compras_dca WHERE id = ?", (purchase_id,))
    conn.commit()
    conn.close()

def save_strategy(data: dict):
    init_db()
    fechas = data.get("fechas", [])
    conn = _get_conn()
    cal_on = 1 if data.get("cal_activado") else 0
    conn.execute("""
        INSERT INTO estrategias_dca
            (ticker, frecuencia, titulos, fecha_inicio, fecha_fin, n_fechas,
             tipo_cambio, comision_pct, cal_activado, cal_hora, cal_anticip, cal_creado)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data.get("ticker"), data.get("frecuencia"), data.get("titulos"),
        str(data.get("fecha_inicio")), str(data.get("fecha_fin")), len(fechas),
        data.get("tipo_cambio"), data.get("comision_pct"),
        cal_on, data.get("cal_hora"), data.get("cal_anticip"),
        cal_on,  # si se activó al crear, los eventos ya se crearon
    ))
    conn.commit()
    conn.close()


def set_cal_creado(strategy_id: int, valor: int = 1):
    """Marca (o desmarca) que los recordatorios de Calendar ya se crearon."""
    conn = _get_conn()
    conn.execute("UPDATE estrategias_dca SET cal_creado = ? WHERE id = ?",
                 (int(valor), strategy_id))
    conn.commit()
    conn.close()

def load_strategies() -> list[dict]:
    init_db()
    conn = _get_conn()
    rows = conn.execute("SELECT * FROM estrategias_dca ORDER BY creado_en DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def delete_strategy(strategy_id: int):
    conn = _get_conn()
    conn.execute("DELETE FROM compras_dca WHERE estrategia_id = ?", (strategy_id,))
    conn.execute("DELETE FROM estrategias_dca WHERE id = ?", (strategy_id,))
    # OJO: NO borramos ventas_cerradas — el historial de rendimiento es permanente,
    # para poder revisarlo aunque la estrategia ya no exista.
    conn.commit()
    conn.close()


# ── Ventas cerradas / rendimiento realizado (DCA, Dividendos, FIBRAs) ─────────
def _compras_de(modulo: str, estrategia_id: int) -> list:
    loaders = {"DCA": load_purchases, "Dividendos": load_div_purchases,
               "FIBRAs": load_fibra_purchases}
    f = loaders.get(modulo)
    return f(estrategia_id) if f else []


def titulos_vendidos(modulo: str, estrategia_id: int) -> int:
    init_db()
    conn = _get_conn()
    row = conn.execute(
        "SELECT COALESCE(SUM(titulos),0) AS s FROM ventas_cerradas WHERE modulo=? AND estrategia_id=?",
        (modulo, estrategia_id)).fetchone()
    conn.close()
    return int(row["s"] or 0)


def titulos_disponibles(modulo: str, estrategia_id: int) -> int:
    comprados = sum(int(c["titulos"]) for c in _compras_de(modulo, estrategia_id))
    return comprados - titulos_vendidos(modulo, estrategia_id)


def registrar_venta(modulo: str, estrategia_id: int, ticker: str, fecha,
                    titulos: int, precio: float, comision: float = 0.0,
                    tipo_cambio: float = 1.0) -> dict:
    """Registra una venta: calcula costo promedio, ganancia realizada y la guarda.

    Todos los importes en MXN (el precio de compra ya se guarda en pesos).
    """
    compras = _compras_de(modulo, estrategia_id)
    comprados = sum(int(c["titulos"]) for c in compras)
    if comprados <= 0:
        return {"ok": False, "msg": "No hay compras registradas en esta estrategia."}
    costo_total = sum(c["titulos"] * c["precio"] + (c.get("comision") or 0.0) for c in compras)
    promedio = costo_total / comprados
    titulos = int(titulos)
    disponibles = comprados - titulos_vendidos(modulo, estrategia_id)
    if titulos <= 0:
        return {"ok": False, "msg": "La cantidad debe ser mayor a 0."}
    if titulos > disponibles:
        return {"ok": False, "msg": f"Solo tienes {disponibles} título(s) disponibles para vender."}
    costo_base = promedio * titulos
    ingreso = titulos * float(precio) - float(comision)
    ganancia = ingreso - costo_base
    init_db()
    conn = _get_conn()
    conn.execute("""
        INSERT INTO ventas_cerradas
            (modulo, estrategia_id, ticker, fecha, titulos, precio, tipo_cambio,
             comision, costo_base, ingreso, ganancia)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (modulo, estrategia_id, ticker, str(fecha), titulos, float(precio),
          float(tipo_cambio), float(comision), costo_base, ingreso, ganancia))
    conn.commit()
    conn.close()
    return {"ok": True, "ganancia": ganancia, "costo_base": costo_base, "ingreso": ingreso}


def log_venta_cerrada(modulo: str, estrategia_id: int, ticker: str, fecha,
                      titulos: int, precio: float, comision: float,
                      costo_base: float, tipo_cambio: float = 1.0):
    """Registra una venta ya calculada en el historial permanente (sin validar stock).

    Lo usa 'Por Objetivos', que maneja sus ventas por lote pero quiere que el
    rendimiento quede guardado aunque luego borre la estrategia.
    """
    ingreso = titulos * float(precio) - float(comision)
    ganancia = ingreso - float(costo_base)
    init_db()
    conn = _get_conn()
    conn.execute("""
        INSERT INTO ventas_cerradas
            (modulo, estrategia_id, ticker, fecha, titulos, precio, tipo_cambio,
             comision, costo_base, ingreso, ganancia)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (modulo, estrategia_id, ticker, str(fecha), int(titulos), float(precio),
          float(tipo_cambio), float(comision), float(costo_base), ingreso, ganancia))
    conn.commit()
    conn.close()


def load_ventas_cerradas(modulo: str, estrategia_id: int) -> list[dict]:
    init_db()
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM ventas_cerradas WHERE modulo=? AND estrategia_id=? ORDER BY fecha DESC, id DESC",
        (modulo, estrategia_id)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_venta_cerrada(venta_id: int):
    conn = _get_conn()
    conn.execute("DELETE FROM ventas_cerradas WHERE id = ?", (venta_id,))
    conn.commit()
    conn.close()


def load_historial_realizado() -> list[dict]:
    """Todas las ventas cerradas (con ganancia realizada), de todos los módulos."""
    init_db()
    conn = _get_conn()
    filas = []
    for r in conn.execute("SELECT * FROM ventas_cerradas ORDER BY fecha DESC, id DESC").fetchall():
        d = dict(r)
        filas.append({"modulo": d["modulo"], "ticker": d["ticker"], "fecha": d["fecha"],
                      "titulos": d["titulos"], "precio": d["precio"],
                      "costo_base": d["costo_base"], "ingreso": d["ingreso"],
                      "ganancia": d["ganancia"]})
    conn.close()
    filas.sort(key=lambda x: str(x["fecha"]), reverse=True)
    return filas


# ── Caché de precios de mercado (#4: guardar último precio conocido) ──────────
def _precios_conn():
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(PRECIOS_DB))
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS precios_cache (
            ticker TEXT PRIMARY KEY,
            nombre TEXT, precio REAL, moneda TEXT, mercado TEXT,
            cambio_pct REAL, actualizado TEXT
        )
    """)
    return conn


def guardar_precio(d: dict):
    """Guarda el último precio conocido de un ticker (compartido entre real y demo)."""
    try:
        conn = _precios_conn()
        conn.execute("""
            INSERT INTO precios_cache (ticker, nombre, precio, moneda, mercado, cambio_pct, actualizado)
            VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(ticker) DO UPDATE SET
                nombre=excluded.nombre, precio=excluded.precio, moneda=excluded.moneda,
                mercado=excluded.mercado, cambio_pct=excluded.cambio_pct, actualizado=datetime('now')
        """, (d.get("ticker"), d.get("nombre"), d.get("precio"), d.get("moneda"),
              d.get("mercado"), d.get("cambio_pct")))
        conn.commit()
        conn.close()
    except Exception:
        pass  # el caché es un extra; nunca debe romper la app


def leer_precio(ticker: str) -> dict | None:
    try:
        conn = _precios_conn()
        row = conn.execute("SELECT * FROM precios_cache WHERE ticker = ?", (ticker,)).fetchone()
        conn.close()
        return dict(row) if row else None
    except Exception:
        return None


def edad_precio_segundos(actualizado) -> float:
    """Antigüedad en segundos del precio guardado (para saber si sigue fresco)."""
    try:
        t = datetime.strptime(str(actualizado)[:19], "%Y-%m-%d %H:%M:%S")
        return (datetime.utcnow() - t).total_seconds()
    except Exception:
        return 1e9
