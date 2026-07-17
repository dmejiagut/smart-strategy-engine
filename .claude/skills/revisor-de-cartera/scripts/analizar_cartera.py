"""
Analiza la cartera exportada por Smart Strategy Engine y calcula métricas de
diversificación, concentración y riesgo. Imprime un JSON con los hallazgos para
que el skill 'revisor-de-cartera' redacte el diagnóstico.

Uso:
    python analizar_cartera.py [ruta_cartera_export.json]
Por defecto busca exports/cartera_export.json subiendo desde la carpeta del proyecto.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path


def _localizar_json(arg: str | None) -> Path | None:
    if arg:
        p = Path(arg).expanduser()
        return p if p.exists() else None
    # Buscar exports/cartera_export.json subiendo desde este script
    aqui = Path(__file__).resolve()
    for base in [Path.cwd(), *aqui.parents]:
        cand = base / "exports" / "cartera_export.json"
        if cand.exists():
            return cand
        cand2 = base / "cartera_export.json"
        if cand2.exists():
            return cand2
    return None


def analizar(data: dict) -> dict:
    estrategias = data.get("estrategias", [])
    perfil = data.get("perfil", {})
    totales = data.get("totales", {})
    total_inv = totales.get("invertido_mxn", 0) or 0

    # Pesos por estrategia y concentración (HHI)
    pesos = []
    for e in estrategias:
        w = (e["invertido_mxn"] / total_inv * 100) if total_inv else 0
        pesos.append({"nombre": e["nombre"], "modulo": e["modulo"],
                      "peso_pct": round(w, 2), "rendimiento_pct": e["rendimiento_pct"],
                      "invertido_mxn": e["invertido_mxn"], "valor_mxn": e["valor_mxn"]})
    hhi = round(sum((p["peso_pct"] / 100) ** 2 for p in pesos), 4)  # 0–1
    nivel_concentracion = ("alta" if hhi >= 0.25 else "media" if hhi >= 0.15 else "baja")
    mayor = max(pesos, key=lambda p: p["peso_pct"], default=None)

    # Desglose por módulo
    por_modulo = {}
    for e in estrategias:
        m = e["modulo"]
        d = por_modulo.setdefault(m, {"invertido_mxn": 0.0, "valor_mxn": 0.0, "n": 0})
        d["invertido_mxn"] += e["invertido_mxn"]
        d["valor_mxn"] += e["valor_mxn"]
        d["n"] += 1
    for m, d in por_modulo.items():
        d["invertido_mxn"] = round(d["invertido_mxn"], 2)
        d["valor_mxn"] = round(d["valor_mxn"], 2)
        d["peso_pct"] = round(d["invertido_mxn"] / total_inv * 100, 2) if total_inv else 0
        d["rendimiento_pct"] = round((d["valor_mxn"] / d["invertido_mxn"] - 1) * 100, 2) if d["invertido_mxn"] else 0

    # Ganadoras / perdedoras
    ordenadas = sorted(estrategias, key=lambda e: e["rendimiento_pct"], reverse=True)
    mejor = ordenadas[0] if ordenadas else None
    peor = ordenadas[-1] if ordenadas else None

    # Banderas de riesgo vs perfil
    banderas = []
    riesgo = (perfil.get("perfil_riesgo") or "").lower()
    peso_trading = por_modulo.get("Por Objetivos", {}).get("peso_pct", 0)
    peso_copy = por_modulo.get("Copy Trading", {}).get("peso_pct", 0)
    peso_fibras = por_modulo.get("FIBRAs", {}).get("peso_pct", 0)
    peso_div = por_modulo.get("Dividendos", {}).get("peso_pct", 0)

    if riesgo == "conservador" and (peso_trading + peso_copy) > 40:
        banderas.append("Tu perfil es Conservador pero más del 40% está en estrategias de mayor riesgo "
                        "(Trading por Objetivos + Copy Trading).")
    if riesgo == "agresivo" and (peso_fibras + peso_div) > 70:
        banderas.append("Tu perfil es Agresivo pero la cartera es muy defensiva (FIBRAs + Dividendos > 70%); "
                        "podrías buscar más crecimiento.")
    if mayor and mayor["peso_pct"] > 50:
        banderas.append(f"Dependes mucho de una sola estrategia: '{mayor['nombre']}' es el "
                        f"{mayor['peso_pct']:.0f}% de tu capital.")
    if len(por_modulo) <= 1 and len(estrategias) > 0:
        banderas.append("Toda tu inversión está en un solo tipo de estrategia. Diversificar entre módulos reduce riesgo.")
    if nivel_concentracion == "alta":
        banderas.append(f"Índice de concentración alto (HHI={hhi}). Tu cartera está poco diversificada.")

    return {
        "perfil": perfil,
        "totales": totales,
        "n_estrategias": len(estrategias),
        "modulos_usados": list(por_modulo.keys()),
        "pesos_estrategias": sorted(pesos, key=lambda p: p["peso_pct"], reverse=True),
        "hhi": hhi,
        "nivel_concentracion": nivel_concentracion,
        "mayor_posicion": mayor,
        "por_modulo": por_modulo,
        "mejor_estrategia": mejor,
        "peor_estrategia": peor,
        "banderas_riesgo": banderas,
    }


def main():
    # Forzar UTF-8 en la salida: en Windows la consola usa cp1252 y corrompe
    # los acentos del JSON (bug real detectado en auditoría).
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    ruta = _localizar_json(arg)
    if not ruta:
        print(json.dumps({"error": "No se encontró cartera_export.json. Genera el export desde "
                                    "el dashboard: Mis Resultados → 'Exportar datos para el Revisor de Cartera'."},
                         ensure_ascii=False))
        return
    data = json.loads(ruta.read_text(encoding="utf-8"))
    if not data.get("estrategias"):
        print(json.dumps({"error": "La cartera está vacía. Registra compras en tus estrategias primero.",
                          "perfil": data.get("perfil", {})}, ensure_ascii=False))
        return
    resultado = analizar(data)
    # Fecha de los datos (para avisar si el export está desactualizado)
    resultado["fecha_datos"] = data.get("generado")
    # JSON compacto: menos tokens que leer para el skill → análisis más rápido y barato
    print(json.dumps(resultado, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
