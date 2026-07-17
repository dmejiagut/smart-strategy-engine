import sqlite3
from datetime import datetime, date
from pathlib import Path

from utils.db_conn import get_conn as _conn_nueva, motor

DB_DIR = Path(__file__).parent.parent / "db"
DB_FILES = {"real": "sse.db", "demo": "sse_demo.db"}
PRECIOS_DB = DB_DIR / "precios.db"  # caché de precios de mercado (público, no es dato del usuario)
_MODO = "real"          # 'real' o 'demo'
_USUARIO = "local"      # quién está usando la app (hasta que exista el login)

# Tablas "raíz": las que tienen dueño. Sus hijas (compras_*, detalle_copy…) se
# protegen a través de su estrategia, porque sus ids SIEMPRE salen de una lectura
# ya filtrada por usuario.
TABLAS_CON_DUENO = [
    "estrategias_dca", "estrategias_dividendos", "estrategias_objetivos",
    "estrategias_fibras", "estrategias_copy", "ventas_cerradas",
]
# Aparte van 'perfiles', 'patrimonio' y 'logros_usuario': ahí el usuario forma
# parte de la llave primaria, así que se crean ya listas (ver init_db).


def set_modo(modo: str):
    """Cambia entre los datos reales y los de demostración (sintéticos)."""
    global _MODO
    _MODO = modo if modo in DB_FILES else "real"


def get_modo() -> str:
    return _MODO


def set_usuario(uid: str):
    """Define de quién son los datos (lo llamará el login)."""
    global _USUARIO
    _USUARIO = str(uid or "local")


def get_usuario() -> str:
    return _USUARIO


def usuario_efectivo() -> str:
    """El dueño de los datos que se leen/escriben AHORA.

    Une login + modo en un solo concepto: en demostración se usa un usuario
    aparte ("…::demo"), así los datos sintéticos son simplemente las filas de
    otro dueño. Esto funciona igual en SQLite y en Postgres (donde hay UNA sola
    base y ya no se pueden separar por archivo).
    """
    return f"{_USUARIO}::demo" if _MODO == "demo" else _USUARIO


# ── Caché de lecturas ────────────────────────────────────────────────────────
# Al pintar una pantalla la app pregunta lo MISMO muchas veces (medido: el perfil
# 6 veces, las estrategias 6-7 veces… ~74 consultas para Inicio). Contra un
# archivo SQLite eso costaba microsegundos; contra la nube son 161 ms cada una.
# Aquí se recuerda lo leído y se olvida TODO en cuanto algo se escribe, así nunca
# se sirve información vieja.
_CACHE: dict = {}


def _invalidar_cache():
    """Cualquier escritura tira el caché: la próxima lectura va a la base."""
    _CACHE.clear()


def _cache_lectura(fn):
    """Recuerda el resultado de una lectura mientras nadie escriba.
    La llave incluye al usuario: los datos de uno nunca se sirven a otro."""
    import functools

    @functools.wraps(fn)
    def envoltorio(*args, **kwargs):
        try:
            llave = (fn.__name__, usuario_efectivo(), args,
                     tuple(sorted(kwargs.items())))
            hash(llave)
        except TypeError:
            return fn(*args, **kwargs)      # argumentos raros: mejor no cachear
        if llave in _CACHE:
            return _CACHE[llave]
        valor = fn(*args, **kwargs)
        _CACHE[llave] = valor
        return valor

    envoltorio._sin_cache = fn
    return envoltorio


def _db_path() -> Path:
    return DB_DIR / DB_FILES["real"]


def _get_conn():
    # Postgres si hay DATABASE_URL configurada; si no, SQLite (una sola base:
    # real y demo ya se distinguen por usuario, no por archivo).
    return _conn_nueva("real")


def _migrar_dueno(conn):
    """Agrega user_id a las tablas con dueño y adopta los datos que ya existían.

    Las filas creadas antes del multiusuario no tienen dueño: se le asignan al
    usuario 'local' para que nadie pierda su información al actualizar.
    """
    for t in TABLAS_CON_DUENO:
        try:
            conn.execute(f"ALTER TABLE {t} ADD COLUMN user_id TEXT")
        except Exception:
            pass  # la columna ya existe
        try:
            conn.execute(f"UPDATE {t} SET user_id = 'local' WHERE user_id IS NULL")
        except Exception:
            pass
        try:
            conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{t}_user ON {t} (user_id)")
        except Exception:
            pass

_ESQUEMA_LISTO = False


def init_db(forzar: bool = False):
    """Crea/actualiza el esquema. Corre UNA sola vez por proceso.

    Ojo con el guardia: init_db() se invoca al inicio de casi todas las funciones
    (37 lugares) y crea/altera ~31 tablas. Contra un archivo SQLite eso era
    instantáneo, pero contra Postgres por internet significaba 31 viajes de red
    —con locks exclusivos— en CADA lectura: la app se arrastraba y llegaba a
    bloquearse. Con esto, el esquema se asegura una vez y ya.
    """
    global _ESQUEMA_LISTO
    if _ESQUEMA_LISTO and not forzar:
        return
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
    # Niveles de entrada escalonada: varios precios de compra (cada uno con sus
    # títulos) para UNA misma meta de salida. Si una estrategia no tiene niveles,
    # es de las viejas: su única entrada vive en estrategias_objetivos.precio_entrada.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS niveles_objetivos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            estrategia_id INTEGER NOT NULL,
            precio REAL NOT NULL,
            titulos INTEGER NOT NULL,
            orden INTEGER DEFAULT 0
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
    # La tabla vieja 'perfil' nació con CHECK (id = 1): una sola fila, un solo
    # usuario. Para multiusuario se usa 'perfiles', donde la llave ES el usuario.
    # (La vieja se conserva un tiempo y sus datos se adoptan en _migrar_perfiles.)
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
    conn.execute("""
        CREATE TABLE IF NOT EXISTS perfiles (
            user_id TEXT PRIMARY KEY,
            nombre TEXT,
            edad INTEGER,
            ingreso_mensual REAL,
            objetivo TEXT,
            perfil_riesgo TEXT,
            horizonte_anios INTEGER,
            comision_pct REAL DEFAULT 0.25,
            meta_anual REAL DEFAULT 20,
            meta_monto REAL DEFAULT 0,
            casa_bolsa TEXT,
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
    # Las dos tablas de arriba nacieron para UN usuario: su llave primaria era
    # solo la fecha / la clave, así que dos personas no podrían tener el mismo
    # día ni el mismo logro. Estas las reemplazan, con el usuario en la llave.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS patrimonio (
            user_id TEXT NOT NULL,
            fecha TEXT NOT NULL,             -- un snapshot por día y por usuario
            invertido REAL NOT NULL,
            valor REAL NOT NULL,
            creado_en TEXT DEFAULT (datetime('now')),
            PRIMARY KEY (user_id, fecha)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS logros_usuario (
            user_id TEXT NOT NULL,
            clave TEXT NOT NULL,
            fecha TEXT DEFAULT (datetime('now')),
            PRIMARY KEY (user_id, clave)
        )
    """)
    _migrar_dueno(conn)
    _adoptar_datos_viejos(conn)
    conn.commit()
    conn.close()
    _ESQUEMA_LISTO = True


def _adoptar_datos_viejos(conn):
    """Pasa los datos de las tablas de un solo usuario a las nuevas, como del
    usuario 'local'. Así quien ya usaba la app no pierde nada al actualizar.
    Solo copia lo que aún no exista (es seguro correrlo muchas veces)."""
    try:
        conn.execute("""
            INSERT INTO perfiles (user_id, nombre, edad, ingreso_mensual, objetivo,
                                  perfil_riesgo, horizonte_anios)
            SELECT 'local', nombre, edad, ingreso_mensual, objetivo,
                   perfil_riesgo, horizonte_anios
            FROM perfil WHERE id = 1
              AND NOT EXISTS (SELECT 1 FROM perfiles WHERE user_id = 'local')
        """)
    except Exception:
        pass
    # Las columnas extra del perfil viejo (se agregaron con ALTER, pueden no estar)
    for col in ("comision_pct", "meta_anual", "meta_monto", "casa_bolsa"):
        try:
            conn.execute(f"""
                UPDATE perfiles SET {col} = (SELECT {col} FROM perfil WHERE id = 1)
                WHERE user_id = 'local'
                  AND (SELECT {col} FROM perfil WHERE id = 1) IS NOT NULL
            """)
        except Exception:
            pass
    try:
        conn.execute("""
            INSERT INTO patrimonio (user_id, fecha, invertido, valor)
            SELECT 'local', fecha, invertido, valor FROM historial_patrimonio
            WHERE fecha NOT IN (SELECT fecha FROM patrimonio WHERE user_id = 'local')
        """)
    except Exception:
        pass
    try:
        conn.execute("""
            INSERT INTO logros_usuario (user_id, clave, fecha)
            SELECT 'local', clave, fecha FROM logros
            WHERE clave NOT IN (SELECT clave FROM logros_usuario WHERE user_id = 'local')
        """)
    except Exception:
        pass

# ── Perfil del usuario ─────────────────────────────────────────────────────────

@_cache_lectura
def get_perfil() -> dict:
    init_db()
    conn = _get_conn()
    row = conn.execute("SELECT * FROM perfiles WHERE user_id = ?",
                       (usuario_efectivo(),)).fetchone()
    conn.close()
    return dict(row) if row else {}


def _set_campo_perfil(campo: str, valor):
    """Guarda UN campo del perfil del usuario actual (crea su fila si no existe)."""
    _invalidar_cache()
    init_db()
    conn = _get_conn()
    conn.execute(
        f"INSERT INTO perfiles (user_id, {campo}) VALUES (?, ?) "
        f"ON CONFLICT(user_id) DO UPDATE SET {campo} = ?",
        (usuario_efectivo(), valor, valor))
    conn.commit()
    conn.close()


def set_comision_pct(pct: float):
    """Guarda el % de comisión de la casa de bolsa en el perfil (aplica de aquí en adelante)."""
    _invalidar_cache()
    _set_campo_perfil("comision_pct", float(pct))


def set_meta_anual(pct: float):
    """Guarda la meta anual de rendimiento (%) del usuario."""
    _invalidar_cache()
    _set_campo_perfil("meta_anual", float(pct))


def set_casa_bolsa(nombre: str):
    """Guarda la casa de bolsa (broker) que usa el usuario."""
    _invalidar_cache()
    _set_campo_perfil("casa_bolsa", nombre)


def set_meta_monto(monto: float):
    """Guarda la meta anual de inversión (monto en MXN que el usuario busca invertir en el año)."""
    _invalidar_cache()
    _set_campo_perfil("meta_monto", float(monto))


@_cache_lectura
def load_logros() -> dict:
    """{clave: fecha} de los logros ya desbloqueados por el usuario actual."""
    init_db()
    conn = _get_conn()
    rows = conn.execute("SELECT clave, fecha FROM logros_usuario WHERE user_id = ?",
                        (usuario_efectivo(),)).fetchall()
    conn.close()
    return {r["clave"]: r["fecha"] for r in rows}


def guardar_logro(clave: str):
    """Marca un logro como desbloqueado (idempotente: no duplica ni actualiza)."""
    _invalidar_cache()
    init_db()
    conn = _get_conn()
    conn.execute(
        "INSERT INTO logros_usuario (user_id, clave) VALUES (?, ?) "
        "ON CONFLICT(user_id, clave) DO NOTHING", (usuario_efectivo(), clave))
    conn.commit()
    conn.close()


# ── Histórico diario del patrimonio ────────────────────────────────────────────

def guardar_snapshot_patrimonio(invertido: float, valor: float):
    """Guarda (o actualiza) el valor del portafolio de HOY. Una fila por día y
    por usuario, así que llamarla muchas veces al día no genera basura ni pesa."""
    _invalidar_cache()
    init_db()
    conn = _get_conn()
    hoy = date.today().isoformat()
    conn.execute(
        "INSERT INTO patrimonio (user_id, fecha, invertido, valor) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(user_id, fecha) DO UPDATE SET invertido = excluded.invertido, "
        "valor = excluded.valor", (usuario_efectivo(), hoy, float(invertido), float(valor)))
    conn.commit()
    conn.close()


def leer_historial_patrimonio() -> list[dict]:
    """Histórico diario del usuario actual, ordenado por fecha (ascendente)."""
    init_db()
    conn = _get_conn()
    rows = conn.execute(
        "SELECT fecha, invertido, valor FROM patrimonio WHERE user_id = ? "
        "ORDER BY fecha ASC", (usuario_efectivo(),)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_perfil(data: dict):
    """Guarda los datos personales del usuario actual.
    Placeholders posicionales (?) a propósito: los de nombre (:campo) solo
    existen en SQLite y romperían en Postgres."""
    _invalidar_cache()
    init_db()
    conn = _get_conn()
    vals = (data.get("nombre"), data.get("edad"), data.get("ingreso_mensual"),
            data.get("objetivo"), data.get("perfil_riesgo"), data.get("horizonte_anios"))
    conn.execute("""
        INSERT INTO perfiles (user_id, nombre, edad, ingreso_mensual, objetivo,
                              perfil_riesgo, horizonte_anios, actualizado)
        VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
        ON CONFLICT(user_id) DO UPDATE SET
            nombre = ?, edad = ?, ingreso_mensual = ?, objetivo = ?,
            perfil_riesgo = ?, horizonte_anios = ?, actualizado = datetime('now')
    """, (usuario_efectivo(),) + vals + vals)
    conn.commit()
    conn.close()

# ── Estrategias de Copy Trading ────────────────────────────────────────────────

def save_copy_strategy(investor_id: str, nombre: str = "", fondo: str = "",
                       reporte_base: str = "") -> int:
    _invalidar_cache()
    init_db()
    if not reporte_base:
        from utils.copytrading_utils import TRIMESTRE_ACTUAL
        reporte_base = TRIMESTRE_ACTUAL
    conn = _get_conn()
    existing = conn.execute(
        "SELECT id FROM estrategias_copy WHERE investor_id = ? AND user_id = ?",
        (investor_id, usuario_efectivo())
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
        "INSERT INTO estrategias_copy (investor_id, nombre, fondo, reporte_base, user_id) "
        "VALUES (?, ?, ?, ?, ?)",
        (investor_id, nombre, fondo, reporte_base, usuario_efectivo()),
    )
    new_id = cur.lastrowid
    conn.commit()
    conn.close()
    registrar_guardado("Copy Trading", chequeo["version"], new_id)
    return int(new_id)

@_cache_lectura
def load_copy_strategies() -> list[dict]:
    init_db()
    conn = _get_conn()
    rows = conn.execute("SELECT * FROM estrategias_copy WHERE user_id = ? "
                        "ORDER BY creado_en DESC", (usuario_efectivo(),)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def delete_copy_strategy(strategy_id: int):
    _invalidar_cache()
    conn = _get_conn()
    compras = conn.execute("SELECT id FROM compras_copy WHERE estrategia_id = ?", (strategy_id,)).fetchall()
    for c in compras:
        conn.execute("DELETE FROM detalle_copy WHERE compra_id = ?", (c["id"],))
    conn.execute("DELETE FROM compras_copy WHERE estrategia_id = ?", (strategy_id,))
    conn.execute("DELETE FROM estrategias_copy WHERE id = ? AND user_id = ?",
                 (strategy_id, usuario_efectivo()))
    conn.commit()
    conn.close()

def save_copy_purchase(estrategia_id: int, fecha, monto_mxn: float, tipo_cambio: float,
                       detalle: list[dict], comision: float = 0.0) -> int:
    """detalle: lista de {ticker, titulos, precio_usd}. comision: MXN (com.+IVA)."""
    _invalidar_cache()
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

@_cache_lectura
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
    _invalidar_cache()
    conn = _get_conn()
    conn.execute("DELETE FROM detalle_copy WHERE compra_id = ?", (compra_id,))
    conn.execute("DELETE FROM compras_copy WHERE id = ?", (compra_id,))
    conn.commit()
    conn.close()


def delete_copy_detalle(detalle_id: int):
    """Borra UNA compra individual (un renglón de detalle) de una cartera copiada.
    Si su canasta queda vacía, también la elimina."""
    _invalidar_cache()
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


@_cache_lectura
def titulos_vendidos_copy(estrategia_id: int, ticker: str) -> int:
    """Acciones ya vendidas de UN ticker dentro de una cartera copiada."""
    init_db()
    conn = _get_conn()
    row = conn.execute(
        "SELECT COALESCE(SUM(titulos),0) AS s FROM ventas_cerradas "
        "WHERE modulo='Copy Trading' AND estrategia_id=? AND ticker=? AND user_id=?",
        (estrategia_id, ticker, usuario_efectivo())).fetchone()
    conn.close()
    return int(row["s"] or 0)


@_cache_lectura
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
    _invalidar_cache()
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
             comision, costo_base, ingreso, ganancia, user_id)
        VALUES ('Copy Trading', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (estrategia_id, ticker, str(fecha), titulos, precio_mxn, float(tipo_cambio),
          float(comision_mxn), costo_base, ingreso, ganancia, usuario_efectivo()))
    conn.commit()
    conn.close()
    return {"ok": True, "ganancia": ganancia, "costo_base": costo_base, "ingreso": ingreso}

# ── Estrategias de FIBRAs ──────────────────────────────────────────────────────

def save_fibra_strategy(ticker: str, nombre: str = "", sector: str = "") -> int:
    _invalidar_cache()
    init_db()
    conn = _get_conn()
    existing = conn.execute(
        "SELECT id FROM estrategias_fibras WHERE ticker = ? AND user_id = ?",
        (ticker, usuario_efectivo())
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
        "INSERT INTO estrategias_fibras (ticker, nombre, sector, user_id) VALUES (?, ?, ?, ?)",
        (ticker, nombre, sector, usuario_efectivo()),
    )
    new_id = cur.lastrowid
    conn.commit()
    conn.close()
    registrar_guardado("FIBRAs", chequeo["version"], new_id)
    return int(new_id)

@_cache_lectura
def load_fibra_strategies() -> list[dict]:
    init_db()
    conn = _get_conn()
    rows = conn.execute("SELECT * FROM estrategias_fibras WHERE user_id = ? "
                        "ORDER BY creado_en DESC", (usuario_efectivo(),)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def delete_fibra_strategy(strategy_id: int):
    _invalidar_cache()
    conn = _get_conn()
    conn.execute("DELETE FROM estrategias_fibras WHERE id = ? AND user_id = ?",
                 (strategy_id, usuario_efectivo()))
    conn.execute("DELETE FROM compras_fibras WHERE estrategia_id = ?", (strategy_id,))
    conn.commit()
    conn.close()

def save_fibra_purchase(estrategia_id: int, fecha, titulos: int, precio: float, comision: float = 0.0):
    _invalidar_cache()
    init_db()
    conn = _get_conn()
    conn.execute(
        "INSERT INTO compras_fibras (estrategia_id, fecha, titulos, precio, comision) VALUES (?, ?, ?, ?, ?)",
        (estrategia_id, str(fecha), int(titulos), float(precio), float(comision)),
    )
    conn.commit()
    conn.close()

@_cache_lectura
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
    _invalidar_cache()
    conn = _get_conn()
    conn.execute("DELETE FROM compras_fibras WHERE id = ?", (purchase_id,))
    conn.commit()
    conn.close()

# ── Estrategias por objetivos ──────────────────────────────────────────────────

def save_obj_strategy(ticker: str, nombre: str, precio_entrada: float,
                      precio_salida: float, tipo_cambio: float = 1.0,
                      niveles: list[dict] | None = None) -> int:
    """niveles: entrada escalonada [{precio, titulos}, ...] para la misma meta de
    salida. precio_entrada queda como la entrada principal (el primer nivel)."""
    _invalidar_cache()
    init_db()
    from utils.pipeline import pipeline_guardado, registrar_guardado
    chequeo = pipeline_guardado("Por Objetivos", {
        "ticker": ticker, "precio_entrada": precio_entrada, "precio_salida": precio_salida})
    if not chequeo["ok"]:
        raise ValueError("La estrategia no pasó las validaciones: " + "; ".join(chequeo["errores"]))
    conn = _get_conn()
    cur = conn.execute(
        """INSERT INTO estrategias_objetivos
           (ticker, nombre, precio_entrada, precio_salida, tipo_cambio, user_id)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (ticker, nombre, float(precio_entrada), float(precio_salida), float(tipo_cambio),
         usuario_efectivo()),
    )
    new_id = cur.lastrowid
    for i, n in enumerate(niveles or []):
        if float(n.get("precio") or 0) <= 0 or int(n.get("titulos") or 0) <= 0:
            continue
        conn.execute(
            "INSERT INTO niveles_objetivos (estrategia_id, precio, titulos, orden) "
            "VALUES (?, ?, ?, ?)",
            (new_id, float(n["precio"]), int(n["titulos"]), i),
        )
    conn.commit()
    conn.close()
    registrar_guardado("Por Objetivos", chequeo["version"], new_id)
    return int(new_id)


@_cache_lectura
def load_obj_niveles(estrategia_id: int) -> list[dict]:
    """Niveles de entrada escalonada de una estrategia. Lista vacía si es una
    estrategia vieja (de una sola entrada, sin cantidad planeada)."""
    init_db()
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM niveles_objetivos WHERE estrategia_id = ? ORDER BY orden, id",
        (estrategia_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

@_cache_lectura
def load_obj_strategies() -> list[dict]:
    init_db()
    conn = _get_conn()
    rows = conn.execute("SELECT * FROM estrategias_objetivos WHERE user_id = ? "
                        "ORDER BY creado_en DESC", (usuario_efectivo(),)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def delete_obj_strategy(strategy_id: int):
    _invalidar_cache()
    conn = _get_conn()
    conn.execute("DELETE FROM estrategias_objetivos WHERE id = ? AND user_id = ?",
                 (strategy_id, usuario_efectivo()))
    conn.execute("DELETE FROM niveles_objetivos WHERE estrategia_id = ?", (strategy_id,))
    conn.execute("DELETE FROM compras_objetivos WHERE estrategia_id = ?", (strategy_id,))
    conn.execute("DELETE FROM ventas_objetivos WHERE estrategia_id = ?", (strategy_id,))
    conn.commit()
    conn.close()

def save_obj_purchase(estrategia_id: int, fecha, titulos: int, precio: float,
                      tipo_cambio: float = 1.0, comision: float = 0.0):
    _invalidar_cache()
    init_db()
    conn = _get_conn()
    conn.execute(
        "INSERT INTO compras_objetivos (estrategia_id, fecha, titulos, precio, tipo_cambio, comision) VALUES (?, ?, ?, ?, ?, ?)",
        (estrategia_id, str(fecha), int(titulos), float(precio), float(tipo_cambio), float(comision)),
    )
    conn.commit()
    conn.close()

@_cache_lectura
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
    _invalidar_cache()
    conn = _get_conn()
    conn.execute("DELETE FROM compras_objetivos WHERE id = ?", (purchase_id,))
    conn.execute("DELETE FROM ventas_objetivos WHERE compra_id = ?", (purchase_id,))
    conn.commit()
    conn.close()

def save_obj_sale(compra_id: int, estrategia_id: int, fecha, titulos: int, precio: float,
                  tipo_cambio: float = 1.0, comision: float = 0.0):
    _invalidar_cache()
    init_db()
    conn = _get_conn()
    conn.execute(
        "INSERT INTO ventas_objetivos (compra_id, estrategia_id, fecha, titulos, precio, tipo_cambio, comision) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (compra_id, estrategia_id, str(fecha), int(titulos), float(precio), float(tipo_cambio), float(comision)),
    )
    conn.commit()
    conn.close()

@_cache_lectura
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
    _invalidar_cache()
    conn = _get_conn()
    conn.execute("DELETE FROM ventas_objetivos WHERE id = ?", (sale_id,))
    conn.commit()
    conn.close()

# ── Estrategias de dividendos ──────────────────────────────────────────────────

def save_div_strategy(ticker: str, nombre: str = "", giro: str = "") -> int:
    _invalidar_cache()
    init_db()
    conn = _get_conn()
    # Evitar duplicados del mismo ticker
    existing = conn.execute(
        "SELECT id FROM estrategias_dividendos WHERE ticker = ? AND user_id = ?",
        (ticker, usuario_efectivo())
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
        "INSERT INTO estrategias_dividendos (ticker, nombre, giro, user_id) VALUES (?, ?, ?, ?)",
        (ticker, nombre, giro, usuario_efectivo()),
    )
    new_id = cur.lastrowid
    conn.commit()
    conn.close()
    registrar_guardado("Dividendos", chequeo["version"], new_id)
    return int(new_id)

@_cache_lectura
def load_div_strategies() -> list[dict]:
    init_db()
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM estrategias_dividendos WHERE user_id = ? ORDER BY creado_en DESC",
        (usuario_efectivo(),)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def delete_div_strategy(strategy_id: int):
    _invalidar_cache()
    conn = _get_conn()
    conn.execute("DELETE FROM estrategias_dividendos WHERE id = ? AND user_id = ?",
                 (strategy_id, usuario_efectivo()))
    conn.execute("DELETE FROM compras_dividendos WHERE estrategia_id = ?", (strategy_id,))
    conn.commit()
    conn.close()

def save_div_purchase(estrategia_id: int, fecha, titulos: int, precio: float,
                      tipo_cambio: float = 1.0, comision: float = 0.0):
    _invalidar_cache()
    init_db()
    conn = _get_conn()
    conn.execute(
        "INSERT INTO compras_dividendos (estrategia_id, fecha, titulos, precio, tipo_cambio, comision) VALUES (?, ?, ?, ?, ?, ?)",
        (estrategia_id, str(fecha), int(titulos), float(precio), float(tipo_cambio), float(comision)),
    )
    conn.commit()
    conn.close()

@_cache_lectura
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
    _invalidar_cache()
    conn = _get_conn()
    conn.execute("DELETE FROM compras_dividendos WHERE id = ?", (purchase_id,))
    conn.commit()
    conn.close()

def save_purchase(estrategia_id: int, fecha, titulos: int, precio: float,
                  tipo_cambio: float = 1.0, comision: float = 0.0):
    _invalidar_cache()
    init_db()
    conn = _get_conn()
    conn.execute(
        "INSERT INTO compras_dca (estrategia_id, fecha, titulos, precio, tipo_cambio, comision) VALUES (?, ?, ?, ?, ?, ?)",
        (estrategia_id, str(fecha), int(titulos), float(precio), float(tipo_cambio), float(comision)),
    )
    conn.commit()
    conn.close()

@_cache_lectura
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
    _invalidar_cache()
    conn = _get_conn()
    conn.execute("DELETE FROM compras_dca WHERE id = ?", (purchase_id,))
    conn.commit()
    conn.close()

def save_strategy(data: dict):
    _invalidar_cache()
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
             tipo_cambio, comision_pct, cal_activado, cal_hora, cal_anticip, cal_creado,
             user_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data.get("ticker"), data.get("frecuencia"), data.get("titulos"),
        str(data.get("fecha_inicio")), str(data.get("fecha_fin")), len(fechas),
        data.get("tipo_cambio"), data.get("comision_pct"),
        cal_on, data.get("cal_hora"), data.get("cal_anticip"),
        cal_on,  # si se activó al crear, los eventos ya se crearon
        usuario_efectivo(),
    ))
    new_id = cur.lastrowid
    conn.commit()
    conn.close()
    registrar_guardado("DCA", chequeo["version"], new_id)   # paso 5 (auditoría)


def set_cal_creado(strategy_id: int, valor: int = 1):
    """Marca (o desmarca) que los recordatorios de Calendar ya se crearon."""
    _invalidar_cache()
    conn = _get_conn()
    conn.execute("UPDATE estrategias_dca SET cal_creado = ? WHERE id = ?",
                 (int(valor), strategy_id))
    conn.commit()
    conn.close()

@_cache_lectura
def load_strategies() -> list[dict]:
    init_db()
    conn = _get_conn()
    rows = conn.execute("SELECT * FROM estrategias_dca WHERE user_id = ? "
                        "ORDER BY creado_en DESC", (usuario_efectivo(),)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def delete_strategy(strategy_id: int):
    _invalidar_cache()
    conn = _get_conn()
    conn.execute("DELETE FROM compras_dca WHERE estrategia_id = ?", (strategy_id,))
    conn.execute("DELETE FROM estrategias_dca WHERE id = ? AND user_id = ?",
                 (strategy_id, usuario_efectivo()))
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


@_cache_lectura
def titulos_vendidos(modulo: str, estrategia_id: int) -> int:
    init_db()
    conn = _get_conn()
    row = conn.execute(
        "SELECT COALESCE(SUM(titulos),0) AS s FROM ventas_cerradas "
        "WHERE modulo=? AND estrategia_id=? AND user_id=?",
        (modulo, estrategia_id, usuario_efectivo())).fetchone()
    conn.close()
    return int(row["s"] or 0)


@_cache_lectura
def titulos_disponibles(modulo: str, estrategia_id: int) -> int:
    comprados = sum(int(c["titulos"]) for c in _compras_de(modulo, estrategia_id))
    return comprados - titulos_vendidos(modulo, estrategia_id)


def registrar_venta(modulo: str, estrategia_id: int, ticker: str, fecha,
                    titulos: int, precio: float, comision: float = 0.0,
                    tipo_cambio: float = 1.0) -> dict:
    """Registra una venta: calcula costo promedio, ganancia realizada y la guarda.

    Todos los importes en MXN (el precio de compra ya se guarda en pesos).
    """
    _invalidar_cache()
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
             comision, costo_base, ingreso, ganancia, user_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (modulo, estrategia_id, ticker, str(fecha), titulos, float(precio),
          float(tipo_cambio), float(comision), costo_base, ingreso, ganancia,
          usuario_efectivo()))
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
    _invalidar_cache()
    ingreso = titulos * float(precio) - float(comision)
    ganancia = ingreso - float(costo_base)
    init_db()
    conn = _get_conn()
    conn.execute("""
        INSERT INTO ventas_cerradas
            (modulo, estrategia_id, ticker, fecha, titulos, precio, tipo_cambio,
             comision, costo_base, ingreso, ganancia, user_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (modulo, estrategia_id, ticker, str(fecha), int(titulos), float(precio),
          float(tipo_cambio), float(comision), float(costo_base), ingreso, ganancia,
          usuario_efectivo()))
    conn.commit()
    conn.close()


@_cache_lectura
def load_ventas_cerradas(modulo: str, estrategia_id: int) -> list[dict]:
    init_db()
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM ventas_cerradas WHERE modulo=? AND estrategia_id=? AND user_id=? "
        "ORDER BY fecha DESC, id DESC",
        (modulo, estrategia_id, usuario_efectivo())).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_venta_cerrada(venta_id: int):
    _invalidar_cache()
    conn = _get_conn()
    conn.execute("DELETE FROM ventas_cerradas WHERE id = ? AND user_id = ?",
                 (venta_id, usuario_efectivo()))
    conn.commit()
    conn.close()


@_cache_lectura
def load_historial_realizado() -> list[dict]:
    """Todas las ventas cerradas (con ganancia realizada), de todos los módulos."""
    init_db()
    conn = _get_conn()
    filas = []
    for r in conn.execute("SELECT * FROM ventas_cerradas WHERE user_id = ? "
                          "ORDER BY fecha DESC, id DESC", (usuario_efectivo(),)).fetchall():
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
    _invalidar_cache()
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
