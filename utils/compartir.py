"""
Genera la tarjeta de resultados para compartir (imagen PNG estilo VestPlan).
El usuario la descarga y la comparte por WhatsApp/redes — marketing orgánico.
Solo usa PIL (ya instalada); sin emojis porque las fuentes PIL no los traen.
"""
import io

from PIL import Image, ImageDraw, ImageFont

_W, _H = 1080, 1080
_TOP = (45, 27, 143)      # #2D1B8F
_BOTTOM = (36, 18, 106)   # #24126A
GREEN = (94, 222, 173)
RED = (255, 138, 138)
GREY = (255, 255, 255, 140)

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


def _centrado(draw, y, texto, font, fill):
    w = draw.textlength(texto, font=font)
    draw.text(((_W - w) / 2, y), texto, font=font, fill=fill)


def generar_tarjeta_resultados(nombre, valor, rend_pct, mejor_modulo=None,
                               mejor_pct=None) -> bytes:
    """Tarjeta cuadrada (1080x1080) con el resumen del portafolio. Devuelve PNG."""
    img = Image.new("RGB", (_W, _H))
    d = ImageDraw.Draw(img, "RGBA")

    # Fondo: degradado vertical morado (identidad VestPlan)
    for y in range(_H):
        t = y / _H
        r = int(_TOP[0] + (_BOTTOM[0] - _TOP[0]) * t)
        g = int(_TOP[1] + (_BOTTOM[1] - _TOP[1]) * t)
        b = int(_TOP[2] + (_BOTTOM[2] - _TOP[2]) * t)
        d.line([(0, y), (_W, y)], fill=(r, g, b))

    # Marca
    f_marca = _font(64)
    w_vest = d.textlength("Vest", font=f_marca)
    w_plan = d.textlength("Plan", font=f_marca)
    x0 = (_W - w_vest - w_plan) / 2
    d.text((x0, 110), "Vest", font=f_marca, fill=(255, 255, 255))
    d.text((x0 + w_vest, 110), "Plan", font=f_marca, fill=(178, 165, 255))

    _centrado(d, 300, "Mi portafolio", _font(38, bold=False), GREY)
    _centrado(d, 370, f"${valor:,.2f} MXN", _font(96), (255, 255, 255))

    # Píldora de rendimiento
    signo = GREEN if rend_pct >= 0 else RED
    txt_r = f"{rend_pct:+.2f}% total"
    f_pill = _font(44)
    w_r = d.textlength(txt_r, font=f_pill)
    px, py, pad = (_W - w_r) / 2, 530, 26
    d.rounded_rectangle([px - pad, py - 12, px + w_r + pad, py + 62],
                        radius=38, fill=(255, 255, 255, 26))
    d.text((px, py), txt_r, font=f_pill, fill=signo)

    if mejor_modulo and mejor_pct is not None:
        _centrado(d, 680, "Mi mejor estrategia", _font(32, bold=False), GREY)
        _centrado(d, 730, f"{mejor_modulo}  ({mejor_pct:+.1f}%)", _font(48), (255, 255, 255))

    # Eslogan + autor
    d.line([(240, 880), (_W - 240, 880)], fill=(255, 255, 255, 46), width=2)
    _centrado(d, 915, "Invierte con un plan. No con emociones.", _font(34, bold=False), (206, 199, 255))
    if nombre:
        _centrado(d, 975, f"— {nombre}", _font(28, bold=False), GREY)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
