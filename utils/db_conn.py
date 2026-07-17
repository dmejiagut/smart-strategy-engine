"""Capa de conexión: la app habla SQL una sola vez y aquí decidimos si va a
SQLite (local, pruebas, CI) o a Postgres/Supabase (nube, multiusuario).

Por qué existe: SQLite y Postgres NO hablan igual, y sin esto habría que
mantener dos versiones de cada consulta:

    SQLite                      Postgres
    ------                      --------
    execute("... ?", (x,))      execute("... %s", (x,))
    cur.lastrowid               INSERT ... RETURNING id
    INTEGER PRIMARY KEY         SERIAL PRIMARY KEY
      AUTOINCREMENT
    datetime('now')             now()

La app sigue escribiendo SQL estilo SQLite (con `?`) y este módulo lo traduce.
Así la migración es un interruptor, no una reescritura.

Se usa Postgres solo si hay credenciales configuradas (st.secrets o variable de
entorno). Si no, cae a SQLite — por eso las pruebas corren sin internet.
"""
from __future__ import annotations

import os
import re
import sqlite3
from pathlib import Path

DB_DIR = Path(__file__).parent.parent / "db"
DB_FILES = {"real": "sse.db", "demo": "sse_demo.db"}


# ── ¿A dónde nos conectamos? ─────────────────────────────────────────────────
def postgres_url() -> str:
    """Cadena de conexión a Postgres, o "" si no está configurada.

    Se busca (en orden): st.secrets["DATABASE_URL"] y la variable de entorno
    DATABASE_URL. NUNCA se escribe la cadena en el código: trae la contraseña.
    """
    try:
        import streamlit as st
        url = st.secrets.get("DATABASE_URL", "")
        if url:
            return str(url)
    except Exception:
        pass  # sin streamlit o sin archivo de secretos
    return os.environ.get("DATABASE_URL", "")


def usando_postgres() -> bool:
    return bool(postgres_url())


def motor() -> str:
    """'postgres' o 'sqlite' — útil para mensajes y para las pruebas."""
    return "postgres" if usando_postgres() else "sqlite"


# ── Traducción de SQL (escribimos estilo SQLite, corre en ambos) ─────────────
_TRADUCCIONES = [
    (re.compile(r"\bINTEGER PRIMARY KEY AUTOINCREMENT\b", re.I), "SERIAL PRIMARY KEY"),
    (re.compile(r"\bdatetime\('now'\)", re.I), "now()"),
    (re.compile(r"\bINSERT OR REPLACE INTO\b", re.I), "INSERT INTO"),
]


def traducir(sql: str) -> str:
    """Convierte SQL estilo SQLite a Postgres. Idempotente y sin efectos si ya
    estamos en SQLite (ahí se devuelve tal cual)."""
    for patron, reemplazo in _TRADUCCIONES:
        sql = patron.sub(reemplazo, sql)
    # Los placeholders van al final: ? → %s (sin tocar los ? dentro de textos)
    return _reemplazar_placeholders(sql)


def _reemplazar_placeholders(sql: str) -> str:
    """? → %s, respetando lo que esté entre comillas simples."""
    fuera, dentro_comilla = [], False
    for ch in sql:
        if ch == "'":
            dentro_comilla = not dentro_comilla
        if ch == "?" and not dentro_comilla:
            fuera.append("%s")
        else:
            fuera.append(ch)
    return "".join(fuera)


# ── Envoltorios: hacen que psycopg se comporte como sqlite3 ──────────────────
class _CursorCompat:
    """Cursor de Postgres con la API que ya usa la app (lastrowid incluido)."""

    def __init__(self, cur):
        self._cur = cur
        self.lastrowid = None

    def fetchone(self):
        return self._cur.fetchone()

    def fetchall(self):
        return self._cur.fetchall()

    def __iter__(self):
        return iter(self._cur)

    @property
    def rowcount(self):
        return self._cur.rowcount


class _ConnCompat:
    """Conexión de Postgres que acepta el SQL estilo SQLite de la app.

    Hace dos traducciones importantes:

    1. En los INSERT agrega RETURNING id, para poder ofrecer `lastrowid`
       (que en Postgres no existe).
    2. Trabaja en modo autocommit (ver el pool). Esto resuelve dos cosas de un
       golpe: la app usa el patrón `try: ALTER TABLE ... except: pass` (para
       cuando la columna ya existe), que en SQLite es inofensivo pero en Postgres
       ABORTA la transacción y tumba todo lo que siga; y además evita los viajes
       de red extra de abrir/cerrar transacción en cada lectura.

    Compromiso conocido: sin transacción explícita, una operación de varias
    sentencias (ej. guardar una estrategia y sus niveles) no es atómica. Se
    aceptó a cambio de la velocidad; si más adelante hace falta, se envuelven
    esos casos puntuales en una transacción propia.
    """

    def __init__(self, conn, pool=None):
        self._conn = conn
        self._pool = pool      # si viene de un pool, al cerrar se devuelve ahí
        self._n = 0
        self._cerrada = False

    def execute(self, sql: str, params=()):
        sql_pg = traducir(sql)
        es_insert = sql_pg.lstrip().upper().startswith("INSERT")
        devuelve_id = es_insert and "RETURNING" not in sql_pg.upper()
        cur = self._conn.cursor()
        if devuelve_id:
            try:
                cur.execute(sql_pg.rstrip().rstrip(";") + " RETURNING id", tuple(params))
            except Exception:
                # La tabla no tiene columna id (ej. perfiles, cuya llave es el
                # usuario): se reintenta sin RETURNING. Con autocommit, el error
                # anterior no dejó la transacción envenenada.
                devuelve_id = False
                cur = self._conn.cursor()
                cur.execute(sql_pg, tuple(params))
        else:
            cur.execute(sql_pg, tuple(params))
        envoltorio = _CursorCompat(cur)
        if devuelve_id:
            try:
                fila = cur.fetchone()
                if fila:
                    envoltorio.lastrowid = fila["id"] if isinstance(fila, dict) else fila[0]
            except Exception:
                pass
        return envoltorio

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        """No cierra de verdad: devuelve la conexión al pool para reutilizarla."""
        if self._cerrada:
            return
        self._cerrada = True
        if self._pool is not None:
            self._pool.putconn(self._conn)   # el pool la limpia (rollback) solo
        else:
            self._conn.close()


# ── Pool de conexiones ───────────────────────────────────────────────────────
# La app abre y cierra una conexión por consulta. Con SQLite (un archivo local)
# eso es gratis; contra Postgres cada apertura es un saludo TLS por internet:
# medimos ~1.7 s POR CONSULTA, o sea 85-170 s para pintar una sola pantalla.
# El pool mantiene unas pocas conexiones vivas y las presta, así el costo se
# paga una vez y cada consulta vuelve a ser de milisegundos.
_POOL = None


def _pool():
    global _POOL
    if _POOL is None:
        from psycopg.rows import dict_row
        from psycopg_pool import ConnectionPool
        _POOL = ConnectionPool(
            postgres_url(), min_size=1, max_size=5,      # Supabase free: 60 máx
            # autocommit: cada sentencia se confirma sola. Evita el viaje extra
            # de cerrar transacción en cada lectura y hace que un ALTER que falla
            # (columna ya existente) no tumbe lo que sigue.
            kwargs={"row_factory": dict_row, "autocommit": True},
            timeout=30, open=True,
        )
    return _POOL


def cerrar_pool():
    """Cierra el pool (para pruebas o al apagar la app)."""
    global _POOL
    if _POOL is not None:
        _POOL.close()
        _POOL = None


def get_conn(modo: str = "real"):
    """Conexión lista para usar. Postgres si hay credenciales; si no, SQLite.

    Las filas se leen como diccionarios en ambos motores, así que `fila["campo"]`
    funciona igual (es como ya lo usa toda la app).
    """
    if usando_postgres():
        p = _pool()
        return _ConnCompat(p.getconn(), p)
    ruta = DB_DIR / DB_FILES.get(modo, DB_FILES["real"])
    ruta.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(ruta))
    conn.row_factory = sqlite3.Row
    return conn
