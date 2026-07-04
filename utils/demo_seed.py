"""
Genera datos sintéticos en la base de DEMOSTRACIÓN (sse_demo.db) para proteger
la información real del usuario. Llena perfil + estrategias + compras en los 5 módulos.
Debe llamarse con el modo 'demo' activo (db_utils.set_modo('demo')).
"""
from datetime import date, timedelta

from utils import db_utils as db

_TABLAS = [
    "compras_dca", "estrategias_dca",
    "compras_dividendos", "estrategias_dividendos",
    "ventas_objetivos", "compras_objetivos", "estrategias_objetivos",
    "compras_fibras", "estrategias_fibras",
    "detalle_copy", "compras_copy", "estrategias_copy",
    "perfil",
]


def _wipe():
    conn = db._get_conn()
    for t in _TABLAS:
        try:
            conn.execute(f"DELETE FROM {t}")
        except Exception:
            pass
    conn.commit()
    conn.close()


def generar_datos_demo():
    """Reinicia la BD demo y la llena con una cartera sintética coherente."""
    assert db.get_modo() == "demo", "generar_datos_demo solo corre en modo demo"
    db.init_db()
    _wipe()
    hoy = date.today()
    TC = 17.20

    # Perfil ficticio
    db.save_perfil({
        "nombre": "Ana Demo", "edad": 35, "ingreso_mensual": 40000.0,
        "objetivo": "Crecimiento de patrimonio", "perfil_riesgo": "Moderado",
        "horizonte_anios": 15,
    })

    # 1) DCA — AAPL mensual
    fechas = [hoy - timedelta(days=30 * i) for i in range(6, 0, -1)]
    db.save_strategy({"ticker": "AAPL", "frecuencia": "Mensual", "titulos": 2,
                      "fecha_inicio": fechas[0], "fecha_fin": hoy, "fechas": fechas,
                      "tipo_cambio": TC, "comision_pct": 0.25})
    dca_id = db.load_strategies()[0]["id"]
    for f in fechas[:4]:
        db.save_purchase(dca_id, f, 2, 4750.0, TC, 23.75)

    # 2) Dividendos — Coca-Cola
    div_id = db.save_div_strategy("KO", "Coca-Cola", "Consumo")
    db.save_div_purchase(div_id, hoy - timedelta(days=120), 6, 1410.0, TC, 16.34)
    db.save_div_purchase(div_id, hoy - timedelta(days=30), 4, 1425.0, TC, 11.01)

    # 3) Por Objetivos — Microsoft (con una venta parcial realizada)
    obj_id = db.save_obj_strategy("MSFT", "Microsoft", 400.0, 480.0, TC)
    db.save_obj_purchase(obj_id, hoy - timedelta(days=80), 2, 6900.0, TC, 34.5)
    compra_obj = db.load_obj_purchases(obj_id)[0]
    db.save_obj_sale(compra_obj["id"], obj_id, hoy - timedelta(days=10), 1, 8050.0, TC, 40.25)

    # 4) FIBRAs — Fibra Uno (solo MXN)
    fib_id = db.save_fibra_strategy("FUNO11.MX", "Fibra Uno", "Diversificado")
    db.save_fibra_purchase(fib_id, hoy - timedelta(days=60), 150, 28.5, 17.81)
    db.save_fibra_purchase(fib_id, hoy - timedelta(days=15), 100, 29.2, 12.17)

    # 5) Copy Trading — cartera de Warren Buffett
    copy_id = db.save_copy_strategy("buffett", "Warren Buffett", "Berkshire Hathaway")
    db.save_copy_purchase(copy_id, hoy - timedelta(days=40), 30000.0, TC, [
        {"ticker": "AAPL", "titulos": 3, "precio_usd": 268.0},
        {"ticker": "AXP", "titulos": 2, "precio_usd": 320.0},
        {"ticker": "BAC", "titulos": 8, "precio_usd": 49.5},
        {"ticker": "KO", "titulos": 5, "precio_usd": 81.0},
    ])
    return True
