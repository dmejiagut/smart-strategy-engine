"""
Genera la tarjeta de LOGROS para compartir (imagen PNG estilo VestPlan).
El usuario la descarga y la comparte por WhatsApp/redes — marketing orgánico.

Diseño (basado en el bosquejo del dueño): tema CLARO, logo arriba, rendimiento
como héroe con una mini-gráfica de tendencia, fila de 3 estadísticas con iconos
en círculos, estrategia más constante y píldora morada con la meta anual.

Reglas:
- NO muestra cuánto dinero tiene el usuario (ni patrimonio ni montos). Solo
  celebra su DISCIPLINA: rendimiento %, racha, estrategias, logros y metas.
- PIL no renderiza emojis a color: los iconos (flecha, diana, estrella) se
  dibujan en vector con primitivas, así se ven igual en Windows y en la nube.
"""
import io
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

_W, _H = 1080, 1080

# Paleta clara (mockup)
BG_TOP = (250, 250, 253)
BG_BOTTOM = (240, 239, 250)
NAVY = (30, 27, 75)          # texto principal
PURPLE = (108, 99, 255)      # #6C63FF marca
INDIGO = (79, 70, 200)       # héroe
GREY = (138, 143, 163)       # etiquetas
LIGHT_LINE = (222, 223, 236)
DISC_BG = (236, 234, 252)    # fondo de los círculos de iconos
GREEN = (22, 163, 74)
RED = (200, 55, 55)

_ICON_PATH = Path(__file__).parent.parent / "assets" / "vestplan_icon.png"

# Rutas de fuentes según el sistema (Windows local / Linux en Streamlit Cloud).
_FONTS_BOLD = ["seguisb.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf",
               "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
_FONTS_REG = ["segoeui.ttf", "arial.ttf", "DejaVuSans.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]


def _font(size, bold=True):
    for name in (_FONTS_BOLD if bold else _FONTS_REG):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _centrado(d, y, texto, font, fill, cx=_W / 2, tracking=0):
    if tracking:
        anchos = [d.textlength(ch, font=font) for ch in texto]
        total = sum(anchos) + tracking * (len(texto) - 1)
        x = cx - total / 2
        for ch, w in zip(texto, anchos):
            d.text((x, y), ch, font=font, fill=fill)
            x += w + tracking
        return total
    w = d.textlength(texto, font=font)
    d.text((cx - w / 2, y), texto, font=font, fill=fill)
    return w


def _ajustar_fuente(d, texto, max_w, size, bold=True, min_size=22):
    """Devuelve la fuente más grande (<= size) con la que el texto cabe en max_w."""
    while size > min_size and d.textlength(texto, font=_font(size, bold)) > max_w:
        size -= 2
    return _font(size, bold)


# ── Iconos vectoriales (PIL no trae emojis) ──────────────────────────────────
def _icono_tendencia(d, cx, cy):
    pts = [(cx - 17, cy + 10), (cx - 5, cy - 2), (cx + 3, cy + 5), (cx + 15, cy - 10)]
    d.line(pts, fill=PURPLE, width=5, joint="curve")
    # punta de flecha
    d.polygon([(cx + 18, cy - 13), (cx + 6, cy - 12), (cx + 16, cy - 2)], fill=PURPLE)


def _icono_diana(d, cx, cy):
    d.ellipse([cx - 16, cy - 16, cx + 16, cy + 16], outline=PURPLE, width=4)
    d.ellipse([cx - 7, cy - 7, cx + 7, cy + 7], outline=PURPLE, width=3)
    d.ellipse([cx - 2, cy - 2, cx + 2, cy + 2], fill=PURPLE)


def _icono_estrella(d, cx, cy):
    pts = []
    for i in range(10):
        r = 18 if i % 2 == 0 else 7.5
        a = -math.pi / 2 + i * math.pi / 5
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    d.polygon(pts, fill=PURPLE)


def _sparkline(img, x0, y0, x1, y1):
    """Mini-gráfica de tendencia al alza (curva + relleno + flecha), como el mockup."""
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    rel = [(0.0, 0.10), (0.14, 0.30), (0.28, 0.24), (0.44, 0.48),
           (0.58, 0.40), (0.74, 0.66), (0.88, 0.86), (1.0, 1.0)]
    pts = [(x0 + rx * (x1 - x0), y1 - ry * (y1 - y0)) for rx, ry in rel]
    # relleno suave bajo la curva
    od.polygon(pts + [(x1, y1), (x0, y1)], fill=PURPLE + (36,))
    od.line(pts, fill=PURPLE + (255,), width=6, joint="curve")
    # flecha al final (dirección del último tramo)
    (ax, ay), (bx, by) = pts[-2], pts[-1]
    ang = math.atan2(by - ay, bx - ax)
    L = 16
    p1 = (bx + L * math.cos(ang), by + L * math.sin(ang))
    p2 = (bx + 10 * math.cos(ang + 2.5), by + 10 * math.sin(ang + 2.5))
    p3 = (bx + 10 * math.cos(ang - 2.5), by + 10 * math.sin(ang - 2.5))
    od.polygon([p1, p2, p3], fill=PURPLE + (255,))
    img.alpha_composite(overlay)


def _pill_gradiente(img, x0, y0, x1, y1, texto, font):
    """Píldora con degradado morado (como el mockup) y texto blanco centrado."""
    w, h = int(x1 - x0), int(y1 - y0)
    grad = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grad)
    c1, c2 = (123, 108, 245), (90, 79, 209)   # #7B6CF5 → #5A4FD1
    for x in range(w):
        t = x / max(w - 1, 1)
        col = tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))
        gd.line([(x, 0), (x, h)], fill=col + (255,))
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, w - 1, h - 1], radius=h // 2, fill=255)
    img.paste(grad, (int(x0), int(y0)), mask)
    d = ImageDraw.Draw(img)
    tw = d.textlength(texto, font=font)
    asc, desc = font.getmetrics()
    d.text(((x0 + x1) / 2 - tw / 2, (y0 + y1) / 2 - (asc + desc) / 2),
           texto, font=font, fill=(255, 255, 255))


def _slogan(d, y, cx=_W / 2):
    """'Invierte con un plan. No con emociones.' con 'plan' y 'emociones' en morado."""
    f = _font(27, bold=False)
    fb = _font(27, bold=True)
    partes = [("Invierte con un ", GREY, f), ("plan", PURPLE, fb), (". No con ", GREY, f),
              ("emociones", PURPLE, fb), (".", GREY, f)]
    total = sum(d.textlength(t, font=ft) for t, _c, ft in partes)
    x = cx - total / 2
    for t, c, ft in partes:
        d.text((x, y), t, font=ft, fill=c)
        x += d.textlength(t, font=ft)


def generar_tarjeta_resultados(datos: dict) -> bytes:
    """Tarjeta cuadrada (1080x1080) de LOGROS, tema claro. Recibe un dict con:
    nombre, anio, rend_pct, n_estrategias, logros_ganados, logros_total,
    racha, mejor_label, mejor_meses, meta_pct, meta_cumplida. Devuelve PNG."""
    img = Image.new("RGBA", (_W, _H))
    d = ImageDraw.Draw(img)

    # Fondo claro con degradado sutil
    for y in range(_H):
        t = y / _H
        col = tuple(int(BG_TOP[i] + (BG_BOTTOM[i] - BG_TOP[i]) * t) for i in range(3))
        d.line([(0, y), (_W, y)], fill=col + (255,))

    # ── Logo: icono centrado + wordmark debajo (como el mockup) ──
    icon_sz = 128
    try:
        icon = Image.open(_ICON_PATH).convert("RGBA").resize((icon_sz, icon_sz), Image.LANCZOS)
        img.alpha_composite(icon, (int(_W / 2 - icon_sz / 2), 48))
    except Exception:
        pass
    f_marca = _font(60)
    w_vest = d.textlength("Vest", font=f_marca)
    w_plan = d.textlength("Plan", font=f_marca)
    x0 = _W / 2 - (w_vest + w_plan) / 2
    d.text((x0, 180), "Vest", font=f_marca, fill=NAVY)
    d.text((x0 + w_vest, 180), "Plan", font=f_marca, fill=PURPLE)

    # ── "MI PROGRESO 2026" con líneas a los lados ──
    anio = datos.get("anio", "")
    f_prog = _font(30)
    y_prog = 274
    wt = _centrado(d, y_prog, f"MI PROGRESO {anio}".strip(), f_prog, INDIGO, tracking=9)
    ly = y_prog + 20
    d.line([(_W / 2 - wt / 2 - 120, ly), (_W / 2 - wt / 2 - 30, ly)], fill=PURPLE + (110,), width=3)
    d.line([(_W / 2 + wt / 2 + 30, ly), (_W / 2 + wt / 2 + 120, ly)], fill=PURPLE + (110,), width=3)

    # ── Héroe adaptativo ──
    rend = datos.get("rend_pct")
    racha = int(datos.get("racha") or 0)
    mejor_meses = int(datos.get("mejor_meses") or 0)
    n_estr = int(datos.get("n_estrategias") or 0)
    hero_es_rend = rend is not None and rend >= 0

    if hero_es_rend:
        _centrado(d, 336, "RENDIMIENTO TOTAL", _font(26, bold=False), GREY, tracking=7)
        # número héroe a la izquierda + gráfica a la derecha (mockup)
        hero_txt = f"+{rend:.1f}%"
        f_hero = _ajustar_fuente(d, hero_txt, 620, 128)
        wh = d.textlength(hero_txt, font=f_hero)
        d.text((max(60, 410 - wh / 2), 374), hero_txt, font=f_hero, fill=INDIGO)
        _sparkline(img, 760, 384, 1020, 522)
        d = ImageDraw.Draw(img)  # re-crear tras alpha_composite
    else:
        # sin rendimiento positivo que presumir: el héroe es la disciplina
        if racha >= 2:
            tag, num = "RACHA", racha
        elif mejor_meses >= 1:
            tag, num = "CONSTANCIA", mejor_meses
        else:
            tag, num = "EN MARCHA", n_estr
        _centrado(d, 336, tag, _font(26, bold=False), GREY, tracking=7)
        _centrado(d, 366, str(num), _font(132), INDIGO)

    # ── Sub-línea con insignia circular (racha / meses) ──
    y_sub = 540
    if hero_es_rend and racha >= 2:
        sub_lbl, sub_num = "compras seguidas a tiempo", racha
    elif hero_es_rend and mejor_meses >= 1:
        sub_lbl, sub_num = "meses invirtiendo con tu plan", mejor_meses
    elif not hero_es_rend and racha >= 2:
        sub_lbl, sub_num = "compras seguidas a tiempo", None
    elif not hero_es_rend and mejor_meses >= 1:
        sub_lbl, sub_num = "meses invirtiendo con tu plan", None
    else:
        sub_lbl, sub_num = ("estrategias activas" if not hero_es_rend else ""), None
    if sub_lbl:
        _centrado(d, y_sub, sub_lbl, _font(29, bold=False), GREY)
    if sub_num is not None:
        cy = y_sub + 74
        d.ellipse([_W / 2 - 30, cy - 30, _W / 2 + 30, cy + 30], fill=INDIGO)
        f_b = _font(32)
        wb = d.textlength(str(sub_num), font=f_b)
        asc, desc = f_b.getmetrics()
        d.text((_W / 2 - wb / 2, cy - (asc + desc) / 2), str(sub_num),
               font=f_b, fill=(255, 255, 255))

    # ── Fila de 3 estadísticas con iconos en círculos ──
    rend_txt = f"{rend:+.1f}%" if rend is not None else "—"
    rend_col = GREEN if (rend or 0) >= 0 else RED
    lg_g = int(datos.get("logros_ganados") or 0)
    lg_t = int(datos.get("logros_total") or 8)
    stats = [("RENDIMIENTO", rend_txt, rend_col, _icono_tendencia),
             ("ESTRATEGIAS", str(n_estr), NAVY, _icono_diana),
             ("LOGROS", f"{lg_g}/{lg_t}", NAVY, _icono_estrella)]
    cw = _W / 3
    y_disc, y_lbl, y_val = 692, 750, 786
    for i, (lbl, val, col, icono) in enumerate(stats):
        cx = cw * i + cw / 2
        d.ellipse([cx - 40, y_disc - 40, cx + 40, y_disc + 40], fill=DISC_BG)
        icono(d, cx, y_disc)
        _centrado(d, y_lbl, lbl, _font(22, bold=False), GREY, cx=cx, tracking=4)
        _centrado(d, y_val, val, _font(42), col, cx=cx)
        if i < 2:
            d.line([(cw * (i + 1), y_disc - 36), (cw * (i + 1), y_val + 40)],
                   fill=LIGHT_LINE, width=2)

    # ── Parte baja (cursor: estrategia más constante → píldora de meta) ──
    y = 862
    mejor_label = datos.get("mejor_label")
    if mejor_label and mejor_meses >= 1:
        _centrado(d, y, "MI ESTRATEGIA MÁS CONSTANTE", _font(22, bold=False), GREY, tracking=5)
        meses_txt = f"{mejor_meses} MES" if mejor_meses == 1 else f"{mejor_meses} MESES"
        txt = f"{mejor_label} · {meses_txt}".upper()
        f_v = _ajustar_fuente(d, txt, 960, 42)
        _centrado(d, y + 30, txt, f_v, NAVY)
        y += 96
    else:
        y += 10

    if datos.get("meta_cumplida"):
        _pill_gradiente(img, 190, y, _W - 190, y + 60, "META ANUAL CUMPLIDA", _font(29))
        d = ImageDraw.Draw(img)
    elif datos.get("meta_pct") is not None:
        _pill_gradiente(img, 165, y, _W - 165, y + 60,
                        f"VAS AL {datos['meta_pct']:.0f}% DE TU META ANUAL", _font(28))
        d = ImageDraw.Draw(img)

    # ── Eslogan al pie (con 'plan' y 'emociones' en morado, como el mockup) ──
    _slogan(d, 1036)

    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="PNG", optimize=True)
    return buf.getvalue()
