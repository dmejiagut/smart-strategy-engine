"""Registro e inicio de sesión con Supabase Auth (email + contraseña).

Por qué existe: el login de Google que ya había (auth_utils.login_google) usa el
flujo de ESCRITORIO — abre un navegador en la máquina donde corre la app. Sirve
para el uso local de una persona, pero con usuarios reales en la nube intentaría
abrir un navegador en el servidor. Esto es autenticación de verdad.

Se habla directo con la API de Supabase por HTTP (sin el SDK) para no sumar
dependencias pesadas: son dos endpoints.

La contraseña NUNCA se guarda ni se registra: viaja por HTTPS a Supabase, que la
almacena cifrada. Aquí solo se conserva el id del usuario.
"""
from __future__ import annotations

import os

import requests

_TIMEOUT = 15


def _cfg(clave: str) -> str:
    """Lee de st.secrets y, si no, de las variables de entorno."""
    try:
        import streamlit as st
        v = st.secrets.get(clave, "")
        if v:
            return str(v)
    except Exception:
        pass
    return os.environ.get(clave, "")


def url_base() -> str:
    return _cfg("SUPABASE_URL").rstrip("/")


def _anon_key() -> str:
    return _cfg("SUPABASE_ANON_KEY")


def disponible() -> bool:
    """True si hay credenciales para autenticar. Si no, la app sigue en modo
    local de un solo usuario (útil para desarrollar sin nube)."""
    return bool(url_base() and _anon_key())


def _headers() -> dict:
    k = _anon_key()
    return {"apikey": k, "Authorization": f"Bearer {k}",
            "Content-Type": "application/json"}


def _traducir_error(texto: str, codigo: int) -> str:
    """Mensajes de Supabase (en inglés y técnicos) a algo entendible."""
    t = (texto or "").lower()
    if "invalid login" in t or codigo == 400 and "credential" in t:
        return "Correo o contraseña incorrectos."
    if "already registered" in t or "already been registered" in t:
        return "Ese correo ya tiene una cuenta. Intenta iniciar sesión."
    if "password should be at least" in t or "weak" in t:
        return "La contraseña es muy corta: usa al menos 6 caracteres."
    if "unable to validate email" in t or "invalid email" in t:
        return "Ese correo no parece válido."
    if "email not confirmed" in t:
        return "Necesitas confirmar tu correo. Revisa tu bandeja de entrada."
    if "email rate limit" in t or "email_send_rate" in t:
        return ("Se alcanzó el límite de correos de confirmación por ahora "
                "(Supabase limita el plan gratis). Espera ~1 hora o desactiva "
                "'Confirm email' en Supabase para pruebas.")
    if "rate limit" in t or codigo == 429:
        return "Demasiados intentos. Espera un momento y vuelve a probar."
    if "signups not allowed" in t or "signup is disabled" in t:
        return "El registro está deshabilitado en Supabase. Actívalo en Authentication."
    return "No se pudo completar. Intenta de nuevo en un momento."


def _post(ruta: str, datos: dict) -> dict:
    try:
        r = requests.post(f"{url_base()}{ruta}", json=datos,
                          headers=_headers(), timeout=_TIMEOUT)
    except requests.RequestException:
        return {"ok": False, "msg": "No hay conexión con el servidor. Revisa tu internet."}
    if r.status_code >= 400:
        try:
            cuerpo = r.json()
            detalle = cuerpo.get("msg") or cuerpo.get("error_description") or cuerpo.get("message", "")
        except Exception:
            detalle = r.text
        return {"ok": False, "msg": _traducir_error(detalle, r.status_code)}
    return {"ok": True, "datos": r.json()}


def registrar(email: str, password: str) -> dict:
    """Crea la cuenta. Devuelve {ok, user_id, email, necesita_confirmar} o {ok:False, msg}."""
    r = _post("/auth/v1/signup", {"email": email.strip(), "password": password})
    if not r["ok"]:
        return r
    d = r["datos"]
    usuario = d.get("user") or d
    return {
        "ok": True,
        "user_id": usuario.get("id", ""),
        "email": usuario.get("email", email),
        # Si Supabase pide confirmar el correo, no manda sesión de inmediato.
        "necesita_confirmar": not d.get("access_token"),
    }


def entrar(email: str, password: str) -> dict:
    """Inicia sesión. Devuelve {ok, user_id, email} o {ok:False, msg}."""
    r = _post("/auth/v1/token?grant_type=password",
              {"email": email.strip(), "password": password})
    if not r["ok"]:
        return r
    d = r["datos"]
    usuario = d.get("user", {})
    uid = usuario.get("id", "")
    if not uid:
        return {"ok": False, "msg": "No se pudo iniciar sesión. Intenta de nuevo."}
    return {"ok": True, "user_id": uid, "email": usuario.get("email", email)}


def recuperar_password(email: str) -> dict:
    """Envía el correo para restablecer la contraseña."""
    r = _post("/auth/v1/recover", {"email": email.strip()})
    if not r["ok"]:
        return r
    return {"ok": True}
