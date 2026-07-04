"""Utilidades de seguridad.

esc(): escapa texto que se interpola en HTML (unsafe_allow_html / components.html)
para prevenir XSS. Úsala SIEMPRE que el texto venga del usuario (nombre, perfil)
o de fuentes externas (nombres de empresas de Yahoo, archivos importados).
"""
import html


def esc(valor) -> str:
    """Convierte a str y escapa <, >, &, comillas. Seguro para meter en HTML."""
    if valor is None:
        return ""
    return html.escape(str(valor), quote=True)
