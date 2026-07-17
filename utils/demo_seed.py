"""
Genera datos sintéticos en la base de DEMOSTRACIÓN (sse_demo.db) para proteger
la información real del usuario. Llena perfil + estrategias + compras en los 5 módulos.
Debe llamarse con el modo 'demo' activo (db_utils.set_modo('demo')).
"""
from datetime import date, timedelta

from utils import db_utils as db

# Tablas hija → la estrategia de la que cuelgan (para borrarlas por su dueño)
_HIJAS = {
    "compras_dca": "estrategias_dca",
    "compras_dividendos": "estrategias_dividendos",
    "ventas_objetivos": "estrategias_objetivos",
    "compras_objetivos": "estrategias_objetivos",
    "niveles_objetivos": "estrategias_objetivos",
    "compras_fibras": "estrategias_fibras",
    "compras_copy": "estrategias_copy",
}
_RAICES = [
    "estrategias_dca", "estrategias_dividendos", "estrategias_objetivos",
    "estrategias_fibras", "estrategias_copy", "ventas_cerradas",
    "perfiles", "patrimonio", "logros_usuario",
]


def _wipe():
    """Borra SOLO los datos del usuario de demostración.

    OJO: antes borraba tablas completas, y eso funcionaba porque el demo vivía en
    otro archivo. Ahora demo y real conviven en la misma base (separados por
    dueño), así que un DELETE sin filtro borraría los datos REALES del usuario.
    """
    uid = db.usuario_efectivo()
    conn = db._get_conn()
    # 1) Lo más profundo primero: el detalle cuelga de la compra, no de la estrategia.
    try:
        conn.execute(
            "DELETE FROM detalle_copy WHERE compra_id IN ("
            "  SELECT id FROM compras_copy WHERE estrategia_id IN ("
            "    SELECT id FROM estrategias_copy WHERE user_id = ?))", (uid,))
    except Exception:
        pass
    # 2) Las hijas, a través de su estrategia.
    for hija, padre in _HIJAS.items():
        try:
            conn.execute(
                f"DELETE FROM {hija} WHERE estrategia_id IN "
                f"(SELECT id FROM {padre} WHERE user_id = ?)", (uid,))
        except Exception:
            pass
    # 3) Y al final las raíces.
    for t in _RAICES:
        try:
            conn.execute(f"DELETE FROM {t} WHERE user_id = ?", (uid,))
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

    # 5) Copy Trading — cartera de Warren Buffett.
    # Ana la copió el trimestre PASADO (Q4 2025); desde entonces salió un reporte
    # nuevo (Q1 2026), así que la demo muestra el aviso de "reajustar al nuevo reporte".
    from utils.copytrading_utils import TRIMESTRE_ANTERIOR
    from utils.comisiones import calcular_comision
    copy_id = db.save_copy_strategy("buffett", "Warren Buffett", "Berkshire Hathaway",
                                    reporte_base=TRIMESTRE_ANTERIOR)
    detalle_copy = [
        {"ticker": "AAPL", "titulos": 3, "precio_usd": 268.0},
        {"ticker": "AXP", "titulos": 2, "precio_usd": 320.0},
        {"ticker": "BAC", "titulos": 8, "precio_usd": 49.5},
        {"ticker": "KO", "titulos": 5, "precio_usd": 81.0},
    ]
    costo_copy = sum(d["titulos"] * d["precio_usd"] for d in detalle_copy) * TC
    db.save_copy_purchase(copy_id, hoy - timedelta(days=40), round(costo_copy, 2), TC,
                          detalle_copy, comision=calcular_comision(costo_copy, 0.25))

    # Meta de ahorro anual + casa de bolsa (para que el perfil se vea completo)
    db.set_meta_monto(120000.0)
    db.set_casa_bolsa("GBM")

    # Ventas realizadas → alimentan la pestaña "Rendimiento realizado"
    #   MSFT (Por Objetivos): la venta de arriba, también en el historial permanente.
    db.log_venta_cerrada("Por Objetivos", obj_id, "MSFT", hoy - timedelta(days=10),
                         1, 8050.0, 40.25, costo_base=6917.25, tipo_cambio=TC)
    #   AAPL (DCA): una venta parcial con ganancia.
    try:
        # Comisión 0.25% + IVA sobre el importe de la venta (regla de toda la app)
        db.registrar_venta("DCA", dca_id, "AAPL", hoy - timedelta(days=5),
                           1, 5150.0, comision=calcular_comision(5150.0, 0.25),
                           tipo_cambio=TC)
    except Exception:
        pass

    # Histórico diario del patrimonio → la gráfica de Inicio sale llena
    _seed_historial(hoy)
    return True


def _seed_historial(hoy):
    """Rellena ~120 días de valor de portafolio (ficticio, tendencia al alza y con
    ruido) para que la gráfica de Inicio y 'ganancia hoy' se vean funcionando."""
    import random
    try:
        from utils.resumen_utils import resumen_global, invalidar_resumen
        invalidar_resumen()
        res = resumen_global()
        inv_total = float(res.get("total_invertido") or 0.0)
        val_hoy = float(res.get("total_valor") or 0.0)
    except Exception:
        inv_total, val_hoy = 100000.0, 108000.0
    if val_hoy <= 0:
        val_hoy = (inv_total or 100000.0) * 1.08
    if inv_total <= 0:
        inv_total = val_hoy * 0.92

    rng = random.Random(7)
    n = 120
    start = inv_total * 0.90
    conn = db._get_conn()
    for i in range(n, 0, -1):                 # i = días atrás (120 … 1 = ayer)
        f = hoy - timedelta(days=i)
        frac = (n - i) / (n - 1)              # 0 (más viejo) … 1 (ayer)
        base = start + (val_hoy - start) * frac
        valor = base * (1 + rng.uniform(-0.015, 0.02))     # leve sesgo al alza
        invertido = inv_total * min(1.0, 0.35 + 0.65 * frac)
        conn.execute(
            "INSERT INTO historial_patrimonio (fecha, invertido, valor) VALUES (?, ?, ?) "
            "ON CONFLICT(fecha) DO UPDATE SET invertido=excluded.invertido, valor=excluded.valor",
            (f.isoformat(), float(invertido), float(valor)))
    conn.commit()
    conn.close()
