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

    Traduce la sentencia y, en los INSERT, agrega RETURNING id para poder
    ofrecer `lastrowid` (que en Postgres no existe)."""

    def __init__(self, conn):
        self._conn = conn

    def execute(self, sql: str, params=()):
        sql_pg = traducir(sql)
        es_insert = sql_pg.lstrip().upper().startswith("INSERT")
        devuelve_id = es_insert and "RETURNING" not in sql_pg.upper()
        if devuelve_id:
            sql_pg = sql_pg.rstrip().rstrip(";") + " RETURNING id"
        cur = self._conn.cursor()
        try:
            cur.execute(sql_pg, tuple(params))
        except Exception:
            if devuelve_id:
                # La tabla no tiene columna id (ej. perfil con id fijo): reintenta sin RETURNING.
                self._conn.rollback()
                cur = self._conn.cursor()
                cur.execute(traducir(sql), tuple(params))
            else:
                raise
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
        self._conn.close()


def get_conn(modo: str = "real"):
    """Conexión lista para usar. Postgres si hay credenciales; si no, SQLite.

    Las filas se leen como diccionarios en ambos motores, así que `fila["campo"]`
    funciona igual (es como ya lo usa toda la app).
    """
    url = postgres_url()
    if url:
        import psycopg
        from psycopg.rows import dict_row
        return _ConnCompat(psycopg.connect(url, row_factory=dict_row))
    p = DB_DIR / DB_FILES.get(modo, DB_FILES["real"])
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(p))
    conn.row_factory = sqlite3.Row
    return conn
