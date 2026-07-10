"""
Genera la tarjeta de LOGROS para compartir (imagen PNG estilo VestPlan).
El usuario la descarga y la comparte por WhatsApp/redes — marketing orgánico.

Diseño consciente:
- NO muestra cuánto dinero tiene el usuario (ni patrimonio ni montos). Solo
  celebra su DISCIPLINA y sus LOGROS: racha, constancia, rendimiento %, metas
  cumplidas y su estrategia más larga. Así puede presumir su progreso sin
  exponer su capital.
- Estilo emocional tipo Duolingo, pero con tipografía y color (las fuentes de
  PIL no traen emojis a color, así que la fuerza visual va en números grandes,
  píldoras y jerarquía, no en emojis).
"""
import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

_W, _H = 1080, 1080
_TOP = (45, 27, 143)      # #2D1B8F
_BOTTOM = (36, 18, 106)   # #24126A
GREEN = (94, 222, 173)
RED = (255, 138, 138)
WHITE = (255, 255, 255)
LILAC = (198, 191, 255)
GREY = (255, 255, 255, 150)
CARD_BG = (255, 255, 255, 20)
CARD_BR = (255, 255, 255, 40)

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


def _centrado(draw, y, texto, font, fill, tracking=0):
    if tracking:
        _centrado_tracking(draw, y, texto, font, fill, tracking)
        return
    w = draw.textlength(texto, font=font)
    draw.text(((_W - w) / 2, y), texto, font=font, fill=fill)


def _centrado_tracking(draw, y, texto, font, fill, tracking):
    """Texto centrado con espaciado entre letras (para títulos tipo etiqueta)."""
    anchos = [draw.textlength(ch, font=font) for ch in texto]
    total = sum(anchos) + tracking * (len(texto) - 1)
    x = (_W - total) / 2
    for ch, w in zip(texto, anchos):
        draw.text((x, y), ch, font=font, fill=fill)
        x += w + tracking


def _pill(draw, cx, y, texto, font, fill_texto, bg, pad_x=34, h=78):
    """Píldora centrada en cx. Devuelve el alto usado."""
    w = draw.textlength(texto, font=font)
    x0 = cx - w / 2 - pad_x
    x1 = cx + w / 2 + pad_x
    draw.rounded_rectangle([x0, y, x1, y + h], radius=h / 2, fill=bg)
    # centrar verticalmente el texto en la píldora
    asc, desc = font.getmetrics()
    ty = y + (h - (asc + desc)) / 2
    draw.text((cx - w / 2, ty), texto, font=font, fill=fill_texto)
    return h


def _logo(img, y):
    """Pega el icono de VestPlan centrado arriba, con el wordmark al lado."""
    d = ImageDraw.Draw(img, "RGBA")
    f_marca = _font(70)
    w_vest = d.textlength("Vest", font=f_marca)
    w_plan = d.textlength("Plan", font=f_marca)
    icon_sz = 116
    gap = 22
    total = icon_sz + gap + w_vest + w_plan
    x = int((_W - total) / 2)
    try:
        icon = Image.open(_ICON_PATH).convert("RGBA").resize((icon_sz, icon_sz), Image.LANCZOS)
        img.paste(icon, (x, int(y)), icon)
    except Exception:
        pass
    tx = x + icon_sz + gap
    # alinear el texto verticalmente al centro del icono
    asc, desc = f_marca.getmetrics()
    ty = y + (icon_sz - (asc + desc)) / 2
    d.text((tx, ty), "Vest", font=f_marca, fill=WHITE)
    d.text((tx + w_vest, ty), "Plan", font=f_marca, fill=LILAC)


def generar_tarjeta_resultados(datos: dict) -> bytes:
    """Tarjeta cuadrada (1080x1080) de LOGROS. Recibe un dict con:
        nombre, anio, rend_pct, n_estrategias, logros_ganados, logros_total,
        racha, mejor_label, mejor_meses, meta_pct, meta_cumplida.
    Todos opcionales salvo lo mínimo. Devuelve PNG en bytes.
    """
    img = Image.new("RGB", (_W, _H))
    d = ImageDraw.Draw(img, "RGBA")

    # Fondo: degradado vertical morado (identidad VestPlan)
    for y in range(_H):
        t = y / _H
        r = int(_TOP[0] + (_BOTTOM[0] - _TOP[0]) * t)
        g = int(_TOP[1] + (_BOTTOM[1] - _TOP[1]) * t)
        b = int(_TOP[2] + (_BOTTOM[2] - _TOP[2]) * t)
        d.line([(0, y), (_W, y)], fill=(r, g, b))

    # ── Logo (icono + wordmark) ──
    _logo(img, 92)
    d = ImageDraw.Draw(img, "RGBA")

    anio = datos.get("anio", "")
    _centrado(d, 244, f"MI PROGRESO {anio}".strip(), _font(29, bold=False), GREY, tracking=8)

    # ── Héroe: el número que más motiva (racha / meses / estrategias) ──
    racha = int(datos.get("racha") or 0)
    mejor_meses = int(datos.get("mejor_meses") or 0)
    n_estr = int(datos.get("n_estrategias") or 0)
    if racha >= 2:
        hero_tag, hero_num, hero_lbl = "RACHA", racha, "compras seguidas a tiempo"
    elif mejor_meses >= 1:
        hero_tag, hero_num = "CONSTANCIA", mejor_meses
        hero_lbl = "meses invirtiendo con tu plan"
    else:
        hero_tag, hero_num, hero_lbl = "EN MARCHA", n_estr, "estrategias activas"

    _pill(d, _W / 2, 298, hero_tag, _font(25), _TOP, LILAC, pad_x=26, h=54)
    _centrado(d, 356, str(hero_num), _font(162), WHITE)
    _centrado(d, 566, hero_lbl, _font(34, bold=False), GREY)

    # ── Fila de 3 estadísticas (sin montos: %, número, logros) ──
    rend = datos.get("rend_pct")
    rend_txt = f"{rend:+.1f}%" if rend is not None else "—"
    rend_col = GREEN if (rend or 0) >= 0 else RED
    lg_g = int(datos.get("logros_ganados") or 0)
    lg_t = int(datos.get("logros_total") or 8)
    stats = [(rend_txt, "rendimiento", rend_col),
             (str(n_estr), "estrategias", WHITE),
             (f"{lg_g}/{lg_t}", "logros", WHITE)]
    cw = _W / 3
    y_val, y_lbl = 656, 748
    for i, (val, lbl, col) in enumerate(stats):
        cx = cw * i + cw / 2
        wv = d.textlength(val, font=_font(64))
        d.text((cx - wv / 2, y_val), val, font=_font(64), fill=col)
        wl = d.textlength(lbl, font=_font(27, bold=False))
        d.text((cx - wl / 2, y_lbl), lbl, font=_font(27, bold=False), fill=GREY)
        if i < 2:
            d.line([(cw * (i + 1), y_val + 6), (cw * (i + 1), y_lbl + 32)],
                   fill=(255, 255, 255, 40), width=2)

    # ── Estrategia más larga (constancia) ──
    y = 812
    mejor_label = datos.get("mejor_label")
    if mejor_label and mejor_meses >= 1:
        _centrado(d, y, "MI ESTRATEGIA MÁS CONSTANTE", _font(23, bold=False), GREY, tracking=6)
        meses_txt = f"{mejor_meses} mes" if mejor_meses == 1 else f"{mejor_meses} meses"
        _centrado(d, y + 32, f"{mejor_label} · {meses_txt}", _font(38), WHITE)
        y += 100

    # ── Meta anual (solo %, nunca el monto) ──
    if datos.get("meta_cumplida"):
        _pill(d, _W / 2, y, "META ANUAL CUMPLIDA", _font(28), _TOP, GREEN, pad_x=32, h=64)
    elif datos.get("meta_pct") is not None:
        _pill(d, _W / 2, y, f"VAS AL {datos['meta_pct']:.0f}% DE TU META ANUAL",
              _font(26), WHITE, CARD_BG, pad_x=32, h=64)

    # ── Eslogan + autor ──
    d.line([(250, 994), (_W - 250, 994)], fill=(255, 255, 255, 46), width=2)
    _centrado(d, 1012, "Invierte con un plan. No con emociones.", _font(29, bold=False), LILAC)
    nombre = datos.get("nombre")
    if nombre:
        _centrado(d, 1050, f"— {nombre}", _font(25, bold=False), GREY)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
