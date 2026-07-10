import sqlite3
from datetime import datetime, date
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
    # Meta anual de rendimiento (%) que el usuario quiere alcanzar (heredado)
    try:
        conn.execute("ALTER TABLE perfil ADD COLUMN meta_anual REAL DEFAULT 20")
    except Exception:
        pass  # columna ya existe
    # Meta anual de AHORRO/INVERSIÓN (monto en MXN que busca invertir en el año)
    try:
        conn.execute("ALTER TABLE perfil ADD COLUMN meta_monto REAL DEFAULT 0")
    except Exception:
        pass  # columna ya existe
    # Casa de bolsa (broker) con la que invierte el usuario
    try:
        conn.execute("ALTER TABLE perfil ADD COLUMN casa_bolsa TEXT")
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
    # Trimestre 13F vigente cuando el usuario copió la cartera (su "línea base").
    # Solo se avisan movimientos del experto de reportes POSTERIORES a esta base;
    # una estrategia recién creada no debe mostrar cambios pasados a su fecha.
    try:
        conn.execute("ALTER TABLE estrategias_copy ADD COLUMN reporte_base TEXT")
    except Exception:
        pass  # columna ya existe
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
    # Comisión + IVA de cada compra copy (misma regla que los demás módulos)
    try:
        conn.execute("ALTER TABLE compras_copy ADD COLUMN comision REAL DEFAULT 0.0")
    except Exception:
        pass  # columna ya existe
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
    # ── Histórico diario del patrimonio (para la gráfica de evolución) ──
    conn.execute("""
        CREATE TABLE IF NOT EXISTS historial_patrimonio (
            fecha TEXT PRIMARY KEY,          -- un snapshot por día (YYYY-MM-DD)
            invertido REAL NOT NULL,
            valor REAL NOT NULL,
            creado_en TEXT DEFAULT (datetime('now'))
        )
    """)
    # ── Logros desbloqueados (gamificación: una vez ganado, no se pierde) ──
    conn.execute("""
        CREATE TABLE IF NOT EXISTS logros (
            clave TEXT PRIMARY KEY,
            fecha TEXT DEFAULT (datetime('now'))
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


def set_meta_anual(pct: float):
    """Guarda la meta anual de rendimiento (%) del usuario."""
    init_db()
    conn = _get_conn()
    conn.execute(
        "INSERT INTO perfil (id, meta_anual) VALUES (1, ?) "
        "ON CONFLICT(id) DO UPDATE SET meta_anual = ?", (float(pct), float(pct)))
    conn.commit()
    conn.close()


def load_logros() -> dict:
    """{clave: fecha} de los logros ya desbloqueados."""
    init_db()
    conn = _get_conn()
    rows = conn.execute("SELECT clave, fecha FROM logros").fetchall()
    conn.close()
    return {r["clave"]: r["fecha"] for r in rows}


def guardar_logro(clave: str):
    """Marca un logro como desbloqueado (idempotente: no duplica ni actualiza)."""
    init_db()
    conn = _get_conn()
    conn.execute("INSERT OR IGNORE INTO logros (clave) VALUES (?)", (clave,))
    conn.commit()
    conn.close()


def set_casa_bolsa(nombre: str):
    """Guarda la casa de bolsa (broker) que usa el usuario."""
    init_db()
    conn = _get_conn()
    conn.execute(
        "INSERT INTO perfil (id, casa_bolsa) VALUES (1, ?) "
        "ON CONFLICT(id) DO UPDATE SET casa_bolsa = ?", (nombre, nombre))
    conn.commit()
    conn.close()


def set_meta_monto(monto: float):
    """Guarda la meta anual de inversión (monto en MXN que el usuario busca invertir en el año)."""
    init_db()
    conn = _get_conn()
    conn.execute(
        "INSERT INTO perfil (id, meta_monto) VALUES (1, ?) "
        "ON CONFLICT(id) DO UPDATE SET meta_monto = ?", (float(monto), float(monto)))
    conn.commit()
    conn.close()


# ── Histórico diario del patrimonio ────────────────────────────────────────────

def guardar_snapshot_patrimonio(invertido: float, valor: float):
    """Guarda (o actualiza) el valor del portafolio de HOY. Una fila por día,
    así que llamarla muchas veces al día no genera basura ni pesa."""
    init_db()
    conn = _get_conn()
    hoy = date.today().isoformat()
    conn.execute(
        "INSERT INTO historial_patrimonio (fecha, invertido, valor) VALUES (?, ?, ?) "
        "ON CONFLICT(fecha) DO UPDATE SET invertido = excluded.invertido, "
        "valor = excluded.valor", (hoy, float(invertido), float(valor)))
    conn.commit()
    conn.close()


def leer_historial_patrimonio() -> list[dict]:
    """Devuelve el histórico diario ordenado por fecha (ascendente)."""
    init_db()
    conn = _get_conn()
    rows = conn.execute(
        "SELECT fecha, invertido, valor FROM historial_patrimonio ORDER BY fecha ASC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


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

def save_copy_strategy(investor_id: str, nombre: str = "", fondo: str = "",
                       reporte_base: str = "") -> int:
    init_db()
    if not reporte_base:
        from utils.copytrading_utils import TRIMESTRE_ACTUAL
        reporte_base = TRIMESTRE_ACTUAL
    conn = _get_conn()
    existing = conn.execute(
        "SELECT id FROM estrategias_copy WHERE investor_id = ?", (investor_id,)
    ).fetchone()
    if existing:
        conn.close()
        return int(existing["id"])
    from utils.pipeline import pipeline_guardado, registrar_guardado
    chequeo = pipeline_guardado("Copy Trading", {"investor_id": investor_id, "nombre": nombre})
    if not chequeo["ok"]:
        conn.close()
        raise ValueError("La estrategia no pasó las validaciones: " + "; ".join(chequeo["errores"]))
    cur = conn.execute(
        "INSERT INTO estrategias_copy (investor_id, nombre, fondo, reporte_base) VALUES (?, ?, ?, ?)",
        (investor_id, nombre, fondo, reporte_base),
    )
    new_id = cur.lastrowid
    conn.commit()
    conn.close()
    registrar_guardado("Copy Trading", chequeo["version"], new_id)
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
                       detalle: list[dict], comision: float = 0.0) -> int:
    """detalle: lista de {ticker, titulos, precio_usd}. comision: MXN (com.+IVA)."""
    init_db()
    conn = _get_conn()
    cur = conn.execute(
        "INSERT INTO compras_copy (estrategia_id, fecha, monto_mxn, tipo_cambio, comision) "
        "VALUES (?, ?, ?, ?, ?)",
        (estrategia_id, str(fecha), float(monto_mxn), float(tipo_cambio), float(comision)),
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


def delete_copy_detalle(detalle_id: int):
    """Borra UNA compra individual (un renglón de detalle) de una cartera copiada.
    Si su canasta queda vacía, también la elimina."""
    conn = _get_conn()
    row = conn.execute("SELECT compra_id FROM detalle_copy WHERE id = ?", (detalle_id,)).fetchone()
    conn.execute("DELETE FROM detalle_copy WHERE id = ?", (detalle_id,))
    if row:
        quedan = conn.execute(
            "SELECT COUNT(*) AS n FROM detalle_copy WHERE compra_id = ?", (row["compra_id"],)
        ).fetchone()
        if quedan and quedan["n"] == 0:
            conn.execute("DELETE FROM compras_copy WHERE id = ?", (row["compra_id"],))
    conn.commit()
    conn.close()


def titulos_vendidos_copy(estrategia_id: int, ticker: str) -> int:
    """Acciones ya vendidas de UN ticker dentro de una cartera copiada."""
    init_db()
    conn = _get_conn()
    row = conn.execute(
        "SELECT COALESCE(SUM(titulos),0) AS s FROM ventas_cerradas "
        "WHERE modulo='Copy Trading' AND estrategia_id=? AND ticker=?",
        (estrategia_id, ticker)).fetchone()
    conn.close()
    return int(row["s"] or 0)


def posiciones_copy(estrategia_id: int) -> list[dict]:
    """Posición AGREGADA por ticker de una cartera copiada: cuántas acciones
    tienes hoy (compradas − vendidas) y su costo promedio (en MXN y USD)."""
    acc = {}  # ticker -> {comprados, cost_mxn, cost_usd}
    for cp in load_copy_purchases(estrategia_id):
        tc = cp.get("tipo_cambio") or 1.0
        com = cp.get("comision") or 0.0
        # La comisión+IVA de la compra se reparte entre sus acciones en proporción
        # a su costo (así el costo promedio ya la incluye, como en los demás módulos).
        base = sum(d["titulos"] * d["precio_usd"] for d in cp["detalle"]) or 1.0
        for d in cp["detalle"]:
            a = acc.setdefault(d["ticker"], {"comprados": 0, "cost_mxn": 0.0, "cost_usd": 0.0})
            costo_usd = d["titulos"] * d["precio_usd"]
            a["comprados"] += int(d["titulos"])
            a["cost_mxn"] += costo_usd * tc + com * (costo_usd / base)
            a["cost_usd"] += costo_usd
    out = []
    for tk, a in acc.items():
        vendidos = titulos_vendidos_copy(estrategia_id, tk)
        held = a["comprados"] - vendidos
        n = a["comprados"] or 1
        out.append({"ticker": tk, "comprados": a["comprados"], "vendidos": vendidos,
                    "titulos": held, "avg_cost_mxn": a["cost_mxn"] / n,
                    "avg_cost_usd": a["cost_usd"] / n})
    out.sort(key=lambda p: p["ticker"])
    return out


def registrar_venta_copy(estrategia_id: int, ticker: str, fecha, titulos: int,
                         precio_usd: float, tipo_cambio: float,
                         comision_mxn: float = 0.0) -> dict:
    """Vende N acciones de un ticker de la cartera copiada y registra la
    ganancia/pérdida realizada en ventas_cerradas (→ Rendimiento realizado)."""
    pos = {p["ticker"]: p for p in posiciones_copy(estrategia_id)}
    p = pos.get(ticker)
    if not p or p["titulos"] <= 0:
        return {"ok": False, "msg": "No tienes esa posición disponible."}
    titulos = int(titulos)
    if titulos <= 0:
        return {"ok": False, "msg": "La cantidad debe ser mayor a 0."}
    if titulos > p["titulos"]:
        return {"ok": False, "msg": f"Solo tienes {p['titulos']} acción(es) de {ticker}."}
    precio_mxn = float(precio_usd) * float(tipo_cambio)
    ingreso = titulos * precio_mxn - float(comision_mxn)
    costo_base = p["avg_cost_mxn"] * titulos
    ganancia = ingreso - costo_base
    init_db()
    conn = _get_conn()
    conn.execute("""
        INSERT INTO ventas_cerradas
            (modulo, estrategia_id, ticker, fecha, titulos, precio, tipo_cambio,
             comision, costo_base, ingreso, ganancia)
        VALUES ('Copy Trading', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (estrategia_id, ticker, str(fecha), titulos, precio_mxn, float(tipo_cambio),
          float(comision_mxn), costo_base, ingreso, ganancia))
    conn.commit()
    conn.close()
    return {"ok": True, "ganancia": ganancia, "costo_base": costo_base, "ingreso": ingreso}

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
    from utils.pipeline import pipeline_guardado, registrar_guardado
    chequeo = pipeline_guardado("FIBRAs", {"ticker": ticker, "nombre": nombre})
    if not chequeo["ok"]:
        conn.close()
        raise ValueError("La estrategia no pasó las validaciones: " + "; ".join(chequeo["errores"]))
    cur = conn.execute(
        "INSERT INTO estrategias_fibras (ticker, nombre, sector) VALUES (?, ?, ?)",
        (ticker, nombre, sector),
    )
    new_id = cur.lastrowid
    conn.commit()
    conn.close()
    registrar_guardado("FIBRAs", chequeo["version"], new_id)
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
    from utils.pipeline import pipeline_guardado, registrar_guardado
    chequeo = pipeline_guardado("Por Objetivos", {
        "ticker": ticker, "precio_entrada": precio_entrada, "precio_salida": precio_salida})
    if not chequeo["ok"]:
        raise ValueError("La estrategia no pasó las validaciones: " + "; ".join(chequeo["errores"]))
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
    registrar_guardado("Por Objetivos", chequeo["version"], new_id)
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
    from utils.pipeline import pipeline_guardado, registrar_guardado
    chequeo = pipeline_guardado("Dividendos", {"ticker": ticker, "nombre": nombre})
    if not chequeo["ok"]:
        conn.close()
        raise ValueError("La estrategia no pasó las validaciones: " + "; ".join(chequeo["errores"]))
    cur = conn.execute(
        "INSERT INTO estrategias_dividendos (ticker, nombre, giro) VALUES (?, ?, ?)",
        (ticker, nombre, giro),
    )
    new_id = cur.lastrowid
    conn.commit()
    conn.close()
    registrar_guardado("Dividendos", chequeo["version"], new_id)
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
    # Pipeline de validación (pasos 1-4) antes de escribir; bloquea si hay errores.
    from utils.pipeline import pipeline_guardado, registrar_guardado
    chequeo = pipeline_guardado("DCA", data)
    if not chequeo["ok"]:
        raise ValueError("La estrategia no pasó las validaciones: " + "; ".join(chequeo["errores"]))
    fechas = data.get("fechas", [])
    conn = _get_conn()
    cal_on = 1 if data.get("cal_activado") else 0
    cur = conn.execute("""
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
    new_id = cur.lastrowid
    conn.commit()
    conn.close()
    registrar_guardado("DCA", chequeo["version"], new_id)   # paso 5 (auditoría)


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
