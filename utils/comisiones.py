IVA = 0.16
COMISION_DEFAULT = 0.25

def calcular_comision(monto: float, comision_pct: float = 0.25) -> float:
    comision = monto * (comision_pct / 100)
    iva = comision * IVA
    return round(comision + iva, 4)

def comision_pct_perfil() -> float:
    """% de comisión guardado en el perfil (default 0.25)."""
    from utils.db_utils import get_perfil
    try:
        pct = get_perfil().get("comision_pct")
        return float(pct) if pct is not None else COMISION_DEFAULT
    except Exception:
        return COMISION_DEFAULT

def comision_desde_perfil(monto: float) -> float:
    """Comisión + IVA calculada con el % de comisión del perfil del usuario."""
    pct = comision_pct_perfil()
    return calcular_comision(monto, pct) if pct > 0 else 0.0

def desglose_comision(monto: float, comision_pct: float = 0.25) -> dict:
    comision = monto * (comision_pct / 100)
    iva = comision * IVA
    return {
        "monto_base": round(monto, 2),
        "comision": round(comision, 4),
        "iva": round(iva, 4),
        "total": round(comision + iva, 4),
    }
