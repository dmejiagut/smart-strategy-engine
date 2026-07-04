from datetime import date, datetime, timedelta
import streamlit as st

# Comparte token y permisos con el login (identidad + calendario en un solo token)
from utils.auth_utils import TOKEN_PATH, CREDS_PATH, SCOPES

def _get_service():
    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
    except ImportError:
        st.error("Ejecuta: pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client")
        return None
    creds = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    if not creds or not creds.valid:
        # Intentar refrescar el token guardado
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                # El token caducó o fue revocado (común si la app está en modo
                # "Testing": Google los invalida cada 7 días). Borramos el token
                # viejo y volvemos a pedir login en vez de crashear.
                creds = None
                try:
                    TOKEN_PATH.unlink()
                except FileNotFoundError:
                    pass
        # Si seguimos sin credenciales válidas, abrir el flujo de login de Google
        if not creds or not creds.valid:
            if not CREDS_PATH.exists():
                st.error("No se encontró credentials.json. Descárgalo de Google Cloud Console.")
                return None
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDS_PATH), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_PATH.write_text(creds.to_json())
    return build("calendar", "v3", credentials=creds)

def _hora_str_to_int(hora_str: str) -> tuple[int, int]:
    parts = hora_str.strip().split()
    hm = parts[0].split(":")
    h, m = int(hm[0]), int(hm[1])
    if parts[1].upper() == "PM" and h != 12:
        h += 12
    if parts[1].upper() == "AM" and h == 12:
        h = 0
    return h, m

def create_calendar_events(ticker, titulos, fechas, hora="9:00 AM", dias_antes=1) -> bool:
    service = _get_service()
    if not service:
        return False
    h, m = _hora_str_to_int(hora)
    created = 0
    errors = 0
    progress_bar = st.progress(0, text="Creando eventos en Google Calendar...")
    for i, f_compra in enumerate(fechas):
        f_rec = f_compra - timedelta(days=dias_antes)
        start_dt = datetime(f_rec.year, f_rec.month, f_rec.day, h, m)
        end_dt = datetime(f_rec.year, f_rec.month, f_rec.day, h, m + 30)
        evento = {
            "summary": f"📈 Compra DCA — {ticker} · {titulos} título{'s' if titulos > 1 else ''}",
            "description": f"Estrategia DCA — Smart Strategy Engine\n\nEmisora: {ticker}\nTítulos: {titulos}\nFecha de compra: {f_compra.strftime('%d/%m/%Y')}",
            "start": {"dateTime": start_dt.isoformat(), "timeZone": "America/Mexico_City"},
            "end": {"dateTime": end_dt.isoformat(), "timeZone": "America/Mexico_City"},
            "reminders": {"useDefault": False, "overrides": [
                {"method": "popup", "minutes": 10},
                {"method": "email", "minutes": 60},
            ]},
            "colorId": "9",
        }
        try:
            service.events().insert(calendarId="primary", body=evento).execute()
            created += 1
        except Exception:
            errors += 1
        progress_bar.progress((i + 1) / len(fechas), text=f"Creando eventos... {i+1}/{len(fechas)}")
    progress_bar.empty()
    if errors == 0:
        st.success(f"✅ {created} eventos creados en Google Calendar.")
        return True
    else:
        st.warning(f"⚠️ {created} creados, {errors} fallaron.")
        return False
