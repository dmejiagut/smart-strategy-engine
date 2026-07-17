"""Comprueba que la app puede hablar con la base de datos configurada.

Uso:
    python tests/probar_conexion.py

Si hay DATABASE_URL (en .streamlit/secrets.toml o en variable de entorno),
prueba Postgres/Supabase; si no, prueba SQLite. No imprime NUNCA la contraseña.
"""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from utils.db_conn import get_conn, motor, postgres_url   # noqa: E402


def _sin_secretos(url: str) -> str:
    """Muestra a qué host nos conectamos SIN revelar usuario ni contraseña."""
    try:
        cola = url.split("@", 1)[1]
        return f"…@{cola}"
    except Exception:
        return "(no se pudo leer el host)"


def main() -> int:
    m = motor()
    print(f"Motor detectado: {m.upper()}")
    if m == "sqlite":
        print("→ No hay DATABASE_URL configurada; se usará SQLite local.")
        print("  Para probar Supabase, crea .streamlit/secrets.toml con:")
        print('     DATABASE_URL = "postgresql://..."')
    else:
        print(f"→ Conectando a {_sin_secretos(postgres_url())}")

    try:
        conn = get_conn("real")
    except Exception as exc:
        print(f"\n❌ No se pudo conectar: {exc}")
        print("\nRevisa que la contraseña sea la correcta y que hayas usado el")
        print("'Connection string' de Supabase (modo Session/Transaction pooler).")
        return 1

    try:
        if m == "postgres":
            fila = conn.execute("SELECT version() AS v").fetchone()
            print(f"\n✅ Conectado. Postgres dice: {str(fila['v'])[:60]}…")
            # Escritura/lectura/borrado real, para probar permisos de verdad
            conn.execute("CREATE TABLE IF NOT EXISTS _prueba_vestplan "
                         "(id INTEGER PRIMARY KEY AUTOINCREMENT, nota TEXT)")
            cur = conn.execute("INSERT INTO _prueba_vestplan (nota) VALUES (?)", ("hola",))
            conn.commit()
            print(f"✅ Escritura OK (id generado: {cur.lastrowid})")
            n = conn.execute("SELECT COUNT(*) AS n FROM _prueba_vestplan").fetchone()["n"]
            print(f"✅ Lectura OK ({n} fila(s))")
            conn.execute("DROP TABLE _prueba_vestplan")
            conn.commit()
            print("✅ Limpieza OK — la tabla de prueba se borró")
        else:
            fila = conn.execute("SELECT sqlite_version() AS v").fetchone()
            print(f"\n✅ Conectado. SQLite {fila['v']}")
        conn.close()
    except Exception as exc:
        print(f"\n❌ Conectó, pero falló al operar: {exc}")
        return 1

    print("\n🎉 Todo listo.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
