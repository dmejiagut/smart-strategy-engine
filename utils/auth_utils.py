"""Login con Google (identidad + calendario) en un solo paso.

Pide el nombre/correo del usuario y de una vez el permiso de calendario,
para que iniciar sesión y conectar recordatorios sea la misma acción.
"""
from pathlib import Path
import streamlit as st

TOKEN_PATH = Path(__file__).parent.parent / ".token_gcal.json"
CREDS_PATH = Path(__file__).parent.parent / "credentials.json"

# Identidad (openid/email/profile) + calendario, todo junto.
SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/calendar.events",
]


def login_google() -> dict | None:
    """Abre el login de Google, guarda el token y devuelve {nombre, email}.

    Devuelve None si falta configuración o las librerías. En modo local
    (corriendo en la PC del usuario) abre una ventana del navegador para
    el consentimiento; el token queda en .token_gcal.json.
    """
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError:
        st.error("Faltan las librerías de Google. Revisa requirements.txt.")
        return None

    if not CREDS_PATH.exists():
        st.error("No se encontró credentials.json. Descárgalo de Google Cloud Console.")
        return None

    try:
        flow = InstalledAppFlow.from_client_secrets_file(str(CREDS_PATH), SCOPES)
        creds = flow.run_local_server(port=0)
        TOKEN_PATH.write_text(creds.to_json())
    except Exception as e:
        st.error(f"No se pudo completar el inicio de sesión con Google: {e}")
        return None

    # Obtener nombre y correo del perfil de Google
    try:
        info = build("oauth2", "v2", credentials=creds).userinfo().get().execute()
        return {"nombre": info.get("name", ""), "email": info.get("email", "")}
    except Exception:
        # El login sí funcionó (y el calendario quedó conectado), solo no
        # pudimos leer el nombre; se lo pediremos a mano.
        return {"nombre": "", "email": ""}
