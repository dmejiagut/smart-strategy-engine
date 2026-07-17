"""Pruebas de humo: renderiza TODAS las vistas de VestPlan y falla si alguna
truena. Es la red de seguridad para refactors grandes (ej. la migración a
multiusuario, que toca todas las consultas).

Uso:
    python tests/smoke.py            # modo demo (rápido y determinista)
    python tests/smoke.py --real     # también contra la base real

No necesita pytest: es un script para poder correrlo igual en local y en CI.
"""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

try:
    sys.stdout.reconfigure(encoding="utf-8")   # emojis en consola de Windows
except Exception:
    pass

from streamlit.testing.v1 import AppTest        # noqa: E402
from utils import nav                           # noqa: E402

APP = str(RAIZ / "app.py")
TIMEOUT = 240

# Todas las vistas navegables de la app
VISTAS = [
    ("Inicio", nav.INICIO),
    ("Estrategias (hub)", nav.ESTRATEGIAS),
    ("DCA", nav.DCA),
    ("Dividendos", nav.DIV),
    ("Por Objetivos", nav.OBJ),
    ("FIBRAs", nav.FIB),
    ("Copy Trading", nav.COPY),
    ("Mis Resultados", nav.RESULTADOS),
    ("Perfil", nav.PERFIL),
    ("Aprende", nav.APRENDE),
    ("Importar", nav.IMPORTAR),
]

# Estados concretos que ya nos han roto la app antes (regresiones conocidas)
CASOS_EXTRA = [
    ("DCA · wizard paso 1", {"nav": nav.DCA, "dca_view": "➕  Nueva estrategia", "dca_step": 1}),
    ("Dividendos · wizard paso 1", {"nav": nav.DIV, "div_view": "➕  Nueva estrategia", "div_step": 1}),
    ("FIBRAs · wizard paso 1", {"nav": nav.FIB, "fibra_view": "➕  Nueva estrategia", "fibra_step": 1}),
    ("Objetivos · wizard paso 1", {"nav": nav.OBJ, "obj_view": "➕  Nueva estrategia", "obj_step": 1}),
    # Escalera de entrada: pasos 2 y 3 con niveles ya definidos
    ("Objetivos · escalera paso 2", {
        "nav": nav.OBJ, "obj_view": "➕  Nueva estrategia", "obj_step": 2,
        "obj_data": {"ticker": "AAPL", "nombre": "Apple", "precio": 200.0, "moneda": "USD",
                     "p_sal": 180.0,
                     "niveles": [{"precio": 120.0, "titulos": 1},
                                 {"precio": 110.0, "titulos": 2}]}}),
    ("Objetivos · escalera paso 3", {
        "nav": nav.OBJ, "obj_view": "➕  Nueva estrategia", "obj_step": 3,
        "obj_data": {"ticker": "AAPL", "nombre": "Apple", "precio": 200.0, "moneda": "USD",
                     "p_sal": 180.0,
                     "niveles": [{"precio": 120.0, "titulos": 1},
                                 {"precio": 110.0, "titulos": 2}]}}),
    ("Resultados · Cargar Excel", {"nav": nav.RESULTADOS, "res_view": "📥 Cargar Excel"}),
    ("Resultados · Rendimiento realizado",
     {"nav": nav.RESULTADOS, "res_view": "🏁 Rendimiento realizado"}),
]


def _correr(nombre: str, estado: dict, modo: str) -> bool:
    """Renderiza una vista. True si no lanzó excepción."""
    at = AppTest.from_file(APP, default_timeout=TIMEOUT)
    at.session_state["_entro"] = True          # saltar la bienvenida
    at.session_state["_modo_actual"] = modo
    for k, v in estado.items():
        at.session_state[k] = v
    try:
        at.run()
    except Exception as exc:                   # el runner mismo falló
        print(f"  ✗ {nombre} — el runner falló: {exc!r}")
        return False
    if at.exception:
        print(f"  ✗ {nombre}")
        for e in at.exception:
            print(f"      {e.value!r}")
        return False
    print(f"  ✓ {nombre}")
    return True


def main() -> int:
    modos = ["demo"]
    if "--real" in sys.argv:
        modos.append("real")

    # El modo demo necesita datos: los generamos para probar con la app llena.
    from utils import db_utils
    from utils.demo_seed import generar_datos_demo
    db_utils.set_modo("demo")
    generar_datos_demo()
    db_utils.set_modo("real")

    fallos = []
    for modo in modos:
        print(f"\n=== Modo {modo.upper()} ===")
        for nombre, destino in VISTAS:
            if not _correr(nombre, {"nav": destino}, modo):
                fallos.append(f"{modo}/{nombre}")
        for nombre, estado in CASOS_EXTRA:
            if not _correr(nombre, estado, modo):
                fallos.append(f"{modo}/{nombre}")

    total = len(modos) * (len(VISTAS) + len(CASOS_EXTRA))
    print(f"\n{'─' * 52}")
    if fallos:
        print(f"❌ {len(fallos)} de {total} fallaron:")
        for f in fallos:
            print(f"   · {f}")
        return 1
    print(f"✅ Las {total} vistas renderizaron sin errores.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
