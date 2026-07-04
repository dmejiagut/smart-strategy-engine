"""
Motor del Revisor de Cartera dentro de la app.
Calcula métricas (diversificación, concentración, riesgo vs perfil) y genera un
informe en HTML con el diagnóstico en prosa — sin necesidad de un LLM externo.
"""
from datetime import date

from utils.seguridad import esc

PURPLE = "#6C63FF"
GREEN = "#1D9E75"
RED = "#A32D2D"
GOLD = "#C77F00"

TODOS_MODULOS = ["DCA", "Dividendos", "Por Objetivos", "FIBRAs", "Copy Trading"]


def analizar(payload: dict) -> dict:
    estrategias = payload.get("estrategias", [])
    perfil = payload.get("perfil", {})
    totales = payload.get("totales", {})
    total_inv = totales.get("invertido_mxn", 0) or 0

    pesos = []
    for e in estrategias:
        w = (e["invertido_mxn"] / total_inv * 100) if total_inv else 0
        pesos.append({"nombre": e["nombre"], "modulo": e["modulo"], "peso_pct": round(w, 2),
                      "rendimiento_pct": e["rendimiento_pct"], "invertido_mxn": e["invertido_mxn"],
                      "valor_mxn": e["valor_mxn"]})
    hhi = round(sum((p["peso_pct"] / 100) ** 2 for p in pesos), 4)
    nivel = "alta" if hhi >= 0.25 else "media" if hhi >= 0.15 else "baja"
    mayor = max(pesos, key=lambda p: p["peso_pct"], default=None)

    por_modulo = {}
    for e in estrategias:
        d = por_modulo.setdefault(e["modulo"], {"invertido_mxn": 0.0, "valor_mxn": 0.0, "n": 0})
        d["invertido_mxn"] += e["invertido_mxn"]
        d["valor_mxn"] += e["valor_mxn"]
        d["n"] += 1
    for d in por_modulo.values():
        d["peso_pct"] = round(d["invertido_mxn"] / total_inv * 100, 2) if total_inv else 0
        d["rendimiento_pct"] = round((d["valor_mxn"] / d["invertido_mxn"] - 1) * 100, 2) if d["invertido_mxn"] else 0

    ordenadas = sorted(estrategias, key=lambda e: e["rendimiento_pct"], reverse=True)
    mejor = ordenadas[0] if ordenadas else None
    peor = ordenadas[-1] if ordenadas else None

    banderas = []
    riesgo = (perfil.get("perfil_riesgo") or "").lower()
    p_trading = por_modulo.get("Por Objetivos", {}).get("peso_pct", 0)
    p_copy = por_modulo.get("Copy Trading", {}).get("peso_pct", 0)
    p_fibras = por_modulo.get("FIBRAs", {}).get("peso_pct", 0)
    p_div = por_modulo.get("Dividendos", {}).get("peso_pct", 0)
    if riesgo == "conservador" and (p_trading + p_copy) > 40:
        banderas.append("Tu perfil es Conservador pero más del 40% está en estrategias de mayor riesgo (Trading + Copy Trading).")
    if riesgo == "agresivo" and (p_fibras + p_div) > 70:
        banderas.append("Tu perfil es Agresivo pero la cartera es muy defensiva (FIBRAs + Dividendos > 70%).")
    if mayor and mayor["peso_pct"] > 50:
        banderas.append(f"Dependes mucho de una sola estrategia: '{mayor['nombre']}' es el {mayor['peso_pct']:.0f}% de tu capital.")
    if len(por_modulo) <= 1 and estrategias:
        banderas.append("Toda tu inversión está en un solo tipo de estrategia. Diversificar entre módulos reduce el riesgo.")
    if nivel == "alta":
        banderas.append(f"Índice de concentración alto (HHI={hhi}). Tu cartera está poco diversificada.")

    return {"perfil": perfil, "totales": totales, "n_estrategias": len(estrategias),
            "modulos_usados": list(por_modulo.keys()), "faltantes": [m for m in TODOS_MODULOS if m not in por_modulo],
            "pesos": sorted(pesos, key=lambda p: p["peso_pct"], reverse=True), "hhi": hhi,
            "nivel_concentracion": nivel, "mayor": mayor, "por_modulo": por_modulo,
            "mejor": mejor, "peor": peor, "banderas": banderas}


def _recomendaciones(a: dict) -> list[str]:
    recs = []
    if a["mayor"] and a["mayor"]["peso_pct"] > 40:
        recs.append(f"Reduce gradualmente tu mayor posición ('{a['mayor']['nombre']}'): evita que una sola "
                    "estrategia supere el 30-40% de tu capital.")
    riesgo = (a["perfil"].get("perfil_riesgo") or "").lower()
    p_trading = a["por_modulo"].get("Por Objetivos", {}).get("peso_pct", 0)
    p_copy = a["por_modulo"].get("Copy Trading", {}).get("peso_pct", 0)
    if riesgo == "conservador" and (p_trading + p_copy) > 40:
        recs.append("Mueve parte de las estrategias de mayor riesgo (Trading/Copy) hacia FIBRAs o Dividendos, "
                    "más acordes a tu perfil conservador.")
    if riesgo == "agresivo" and a["por_modulo"].get("FIBRAs", {}).get("peso_pct", 0) + a["por_modulo"].get("Dividendos", {}).get("peso_pct", 0) > 70:
        recs.append("Si buscas crecimiento, sube algo de exposición a Trading por Objetivos o Copy Trading.")
    if a["faltantes"]:
        recs.append("Diversifica entrando a tipos de estrategia que aún no usas: " + ", ".join(a["faltantes"]) + ".")
    if a["peor"] and a["peor"]["rendimiento_pct"] < -10:
        recs.append(f"Revisa '{a['peor']['nombre']}' ({a['peor']['rendimiento_pct']:+.1f}%): define si mantienes la tesis o cortas la pérdida.")
    recs.append("Aporta de forma constante y gradual (DCA) a tus mejores estrategias para suavizar el costo de entrada.")
    return recs


def _fmt(v):
    return f"${v:,.2f}"


def generar_html(payload: dict) -> str:
    a = analizar(payload)
    perfil = a["perfil"]
    tot = a["totales"]
    rend = tot.get("rendimiento_pct", 0)
    col_rend = GREEN if rend >= 0 else RED
    nombre = esc(perfil.get("nombre") or "Inversionista")

    if not a["pesos"]:
        cuerpo = "<p>Aún no hay inversiones registradas. Registra compras en tus estrategias para obtener un diagnóstico.</p>"
        return _envolver(nombre, cuerpo)

    # Diversificación
    div_rows = "".join(
        f"<tr><td>{m}</td><td style='text-align:right'>{d['peso_pct']:.1f}%</td>"
        f"<td style='text-align:right'>{_fmt(d['invertido_mxn'])}</td>"
        f"<td style='text-align:right;color:{GREEN if d['rendimiento_pct']>=0 else RED}'>{d['rendimiento_pct']:+.2f}%</td></tr>"
        for m, d in a["por_modulo"].items())

    pesos_rows = "".join(
        f"<tr><td>{esc(p['nombre'])}</td><td>{esc(p['modulo'])}</td>"
        f"<td style='text-align:right'>{p['peso_pct']:.1f}%</td>"
        f"<td style='text-align:right;color:{GREEN if p['rendimiento_pct']>=0 else RED}'>{p['rendimiento_pct']:+.2f}%</td></tr>"
        for p in a["pesos"])

    banderas_html = ("".join(f"<li>{esc(b)}</li>" for b in a["banderas"])
                     if a["banderas"] else "<li>No se detectaron banderas de riesgo relevantes. ✅</li>")
    recs_html = "".join(f"<li>{esc(r)}</li>" for r in _recomendaciones(a))

    conc_txt = {"alta": "alta — tu cartera está concentrada en pocas posiciones",
                "media": "media — hay cierta concentración",
                "baja": "baja — tu cartera está bien repartida"}[a["nivel_concentracion"]]

    coherencia = _texto_coherencia(a)

    cuerpo = f"""
    <div class="kpis">
      <div class="kpi"><span>Capital invertido</span><b>{_fmt(tot.get('invertido_mxn',0))} MXN</b></div>
      <div class="kpi"><span>Valor actual</span><b>{_fmt(tot.get('valor_mxn',0))} MXN</b></div>
      <div class="kpi"><span>Rendimiento total</span><b style="color:{col_rend}">{rend:+.2f}%</b></div>
    </div>

    <h2>1. Resumen general</h2>
    <p>{nombre}, llevas <b>{_fmt(tot.get('invertido_mxn',0))} MXN</b> invertidos en
    {a['n_estrategias']} estrategia(s), con un valor actual de <b>{_fmt(tot.get('valor_mxn',0))} MXN</b>.
    Tu rendimiento total es de <b style="color:{col_rend}">{rend:+.2f}%</b>.</p>

    <h2>2. Diversificación</h2>
    <p>Tu capital se reparte así entre los tipos de estrategia:</p>
    <table><tr><th>Módulo</th><th>Peso</th><th>Invertido</th><th>Rend.</th></tr>{div_rows}</table>
    <p>Usas {len(a['modulos_usados'])} de 5 tipos de estrategia.{(' Te faltaría explorar: <b>' + ', '.join(a['faltantes']) + '</b>.') if a['faltantes'] else ' ¡Tienes presencia en todos los tipos!'}</p>

    <h2>3. Concentración y riesgo</h2>
    <p>Índice de concentración (HHI) = <b>{a['hhi']}</b> → concentración <b>{conc_txt}</b>.
    Tu mayor posición es <b>{esc(a['mayor']['nombre'])}</b> con el <b>{a['mayor']['peso_pct']:.1f}%</b> del capital.</p>
    <table><tr><th>Estrategia</th><th>Módulo</th><th>Peso</th><th>Rend.</th></tr>{pesos_rows}</table>

    <h2>4. Coherencia con tu perfil</h2>
    <p>{coherencia}</p>

    <h2>5. Ganadoras y perdedoras</h2>
    <p>🟢 Mejor: <b>{esc(a['mejor']['nombre'])}</b> ({a['mejor']['rendimiento_pct']:+.2f}%) ·
    🔴 Peor: <b>{esc(a['peor']['nombre'])}</b> ({a['peor']['rendimiento_pct']:+.2f}%).</p>

    <h2>⚠️ Banderas de atención</h2>
    <ul>{banderas_html}</ul>

    <h2>6. Recomendaciones</h2>
    <ol>{recs_html}</ol>

    <p class="disc">Este es un análisis informativo generado automáticamente, no asesoría financiera personalizada.</p>
    """
    return _envolver(nombre, cuerpo)


def _texto_coherencia(a: dict) -> str:
    perfil = a["perfil"]
    riesgo = esc(perfil.get("perfil_riesgo") or "—")
    objetivo = esc(perfil.get("objetivo") or "—")
    horizonte = perfil.get("horizonte_anios") or "—"
    base = (f"Tu perfil es <b>{riesgo}</b>, con objetivo de <b>{objetivo}</b> y un horizonte de "
            f"<b>{horizonte} años</b>. ")
    riesgo_l = riesgo.lower()
    p_trading = a["por_modulo"].get("Por Objetivos", {}).get("peso_pct", 0)
    p_copy = a["por_modulo"].get("Copy Trading", {}).get("peso_pct", 0)
    p_def = a["por_modulo"].get("FIBRAs", {}).get("peso_pct", 0) + a["por_modulo"].get("Dividendos", {}).get("peso_pct", 0)
    if riesgo_l == "conservador" and (p_trading + p_copy) > 40:
        return base + ("Sin embargo, una parte importante está en estrategias de mayor riesgo, lo cual "
                       "no encaja del todo con un perfil conservador. Considera moverte hacia opciones más estables.")
    if riesgo_l == "agresivo" and p_def > 70:
        return base + ("Tu cartera es bastante defensiva para un perfil agresivo; podrías buscar más crecimiento.")
    return base + "En general, la composición de tu cartera es razonablemente coherente con tu perfil."


def _envolver(nombre: str, cuerpo: str) -> str:
    return f"""<!DOCTYPE html><html lang="es"><head><meta charset="utf-8">
<title>Revisor de Cartera — {nombre}</title>
<style>
  body{{font-family:'Segoe UI',Inter,sans-serif;color:#1a1a2e;background:#F4F6FA;margin:0;padding:24px;}}
  .wrap{{max-width:820px;margin:0 auto;background:#fff;border:1px solid #E8ECF4;border-radius:14px;padding:28px 34px;}}
  h1{{color:{PURPLE};font-size:22px;margin:0 0 2px;}}
  .sub{{color:#9DA5B8;font-size:13px;margin:0 0 18px;}}
  h2{{font-size:15px;color:#1a1a2e;border-top:1px solid #EEF0F5;padding-top:14px;margin-top:20px;}}
  p{{font-size:13.5px;line-height:1.6;color:#3a4257;}}
  table{{width:100%;border-collapse:collapse;margin:8px 0;font-size:12.5px;}}
  th{{text-align:left;color:#9DA5B8;font-weight:600;border-bottom:1px solid #E8ECF4;padding:6px;}}
  td{{padding:6px;border-bottom:1px solid #F2F4F8;}}
  ul,ol{{font-size:13.5px;line-height:1.7;color:#3a4257;}}
  .kpis{{display:flex;gap:12px;margin:6px 0 8px;}}
  .kpi{{flex:1;background:#F8F9FC;border:1px solid #E8ECF4;border-radius:10px;padding:12px 14px;}}
  .kpi span{{display:block;font-size:11px;color:#9DA5B8;text-transform:uppercase;letter-spacing:.04em;}}
  .kpi b{{font-size:18px;}}
  .disc{{font-size:11px;color:#9DA5B8;font-style:italic;margin-top:18px;}}
</style></head><body><div class="wrap">
<h1>📈 Revisor de Cartera</h1>
<p class="sub">Smart Strategy Engine · {nombre} · {date.today().strftime('%d/%m/%Y')}</p>
{cuerpo}
</div></body></html>"""
