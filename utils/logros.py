"""
Logros de VestPlan (gamificación estilo Duolingo).
Premian la DISCIPLINA (aportar, ser constante), no la suerte del mercado.
Una vez desbloqueado, un logro no se pierde (queda guardado en la tabla logros).
"""
from datetime import date

from utils.db_utils import load_logros, guardar_logro, load_historial_realizado

# (clave, emoji, título, descripción)
LOGROS = [
    ("primera_compra", "🥇", "Primera compra", "Registraste tu primera inversión"),
    ("racha_3", "🔥", "Racha de 3", "3 compras DCA seguidas a tiempo"),
    ("constante_3m", "📅", "3 meses constante", "Aportaste 3 meses seguidos"),
    ("diversificado", "🌱", "Diversificado", "Inviertes en 3 o más estrategias"),
    ("meta_50", "🎯", "Mitad del camino", "Llevas 50% de tu meta anual"),
    ("meta_100", "🏆", "Meta cumplida", "Alcanzaste tu meta anual"),
    ("venta_ganadora", "💰", "Venta ganadora", "Tu primera venta con ganancia"),
    ("cien_mil", "🚀", "Club de los $100k", "Has aportado más de $100,000"),
]


def _meses_consecutivos(aportaciones: dict, n: int = 3) -> bool:
    """True si hay n meses seguidos con aportación (ej. mar, abr, may)."""
    ms = sorted({int(ym[:4]) * 12 + int(ym[5:7]) for ym, v in aportaciones.items() if v > 0})
    return any(ms[i + n - 1] - ms[i] == n - 1 for i in range(len(ms) - n + 1))


def evaluar_logros(res: dict, racha: int, perfil: dict):
    """Evalúa qué logros se cumplen HOY, persiste los nuevos y devuelve:
    (lista completa con estado, títulos de los recién desbloqueados)."""
    from utils.resumen_utils import aportaciones_por_mes, invertido_en_anio
    ap = aportaciones_por_mes()
    total_aportado = sum(ap.values())
    meta = float(perfil.get("meta_monto") or 0)
    inv_anio = invertido_en_anio(date.today().year) if meta > 0 else 0.0
    modulos = {i["modulo"] for i in res.get("items", [])}
    hay_venta_ganadora = any((v.get("ganancia") or 0) > 0 for v in load_historial_realizado())

    cumplidos = {
        "primera_compra": total_aportado > 0,
        "racha_3": racha >= 3,
        "constante_3m": _meses_consecutivos(ap, 3),
        "diversificado": len(modulos) >= 3,
        "meta_50": meta > 0 and inv_anio >= meta * 0.5,
        "meta_100": meta > 0 and inv_anio >= meta,
        "venta_ganadora": hay_venta_ganadora,
        "cien_mil": total_aportado >= 100_000,
    }

    ya = load_logros()
    nuevos = []
    badges = []
    for clave, emoji, titulo, desc in LOGROS:
        ganado = clave in ya or cumplidos.get(clave, False)
        if ganado and clave not in ya:
            guardar_logro(clave)          # se desbloquea AHORA (y queda para siempre)
            nuevos.append(f"{emoji} {titulo}")
        badges.append({"clave": clave, "emoji": emoji, "titulo": titulo,
                       "desc": desc, "ganado": ganado})
    return badges, nuevos
