"""Pantalla de bienvenida: login con Google o modo invitado + perfil financiero.

Actúa como "compuerta": mientras el usuario no haya entrado, la app muestra
esta pantalla en lugar del dashboard. Una vez completado el perfil, no se
vuelve a preguntar (y se puede editar luego desde "Mi perfil financiero").
"""
from pathlib import Path

import streamlit as st
from utils import db_utils, auth_utils, auth_supabase

# Logo oficial (arte del usuario). Si no existe, se usa el SVG de respaldo.
_LOGO_PATH = Path(__file__).resolve().parent.parent / "assets" / "vestplan_logo.png"

RIESGOS = ["Conservador", "Moderado", "Agresivo"]
_RIESGO_DESC = {
    "Conservador": "Prefiero seguridad aunque gane menos.",
    "Moderado": "Busco un equilibrio entre riesgo y ganancia.",
    "Agresivo": "Acepto más riesgo por más crecimiento.",
}
OBJETIVOS = ["Crecimiento de patrimonio", "Ingresos pasivos", "Retiro",
             "Ahorro de corto plazo", "Especulación / trading"]
# Casas de bolsa (brokers) más comunes en México + opciones abiertas.
CASAS_BOLSA = ["GBM", "Kuspit", "Actinver", "Bursanet (Banorte)", "Vector",
               "Finamex", "Hey Banco (Banregio)", "Invex", "Scotiabank",
               "Flink", "Interactive Brokers", "Otra", "Aún no tengo"]

_GOOGLE_LOGO = (
    "data:image/svg+xml;base64,"
    "PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCA0OCA0OCI+"
    "PHBhdGggZmlsbD0iI0VBNDMzNSIgZD0iTTI0IDkuNWMzLjU0IDAgNi43MSAxLjIyIDkuMjEgMy42bDYu"
    "ODUtNi44NUMzNS45IDIuMzggMzAuNDcgMCAyNCAwIDE0LjYyIDAgNi41MSA1LjM4IDIuNTYgMTMuMjJs"
    "Ny45OCA2LjE5QzEyLjQzIDEzLjcyIDE3Ljc0IDkuNSAyNCA5LjV6Ii8+PHBhdGggZmlsbD0iIzQyODVG"
    "NCIgZD0iTTQ2Ljk4IDI0LjU1YzAtMS41Ny0uMTUtMy4wOS0uMzgtNC41NUgyNHY5LjAyaDEyLjk0Yy0u"
    "NTggMi45Ni0yLjI2IDUuNDgtNC43OCA3LjE4bDcuNzMgNmM0LjUxLTQuMTggNy4wOS0xMC4zNiA3LjA5"
    "LTE3LjY1eiIvPjxwYXRoIGZpbGw9IiNGQkJDMDUiIGQ9Ik0xMC41MyAyOC41OWMtLjQ4LTEuNDUtLjc2"
    "LTIuOTktLjc2LTQuNTlzLjI3LTMuMTQuNzYtNC41OWwtNy45OC02LjE5Qy45MiAxNi40NiAwIDIwLjEy"
    "IDAgMjRjMCAzLjg4LjkyIDcuNTQgMi41NiAxMC43OGw3Ljk3LTYuMTl6Ii8+PHBhdGggZmlsbD0iIzM0"
    "QTg1MyIgZD0iTTI0IDQ4YzYuNDggMCAxMS45My0yLjEzIDE1Ljg5LTUuODFsLTcuNzMtNmMtMi4xNSAx"
    "LjQ1LTQuOTIgMi4zLTguMTYgMi4zLTYuMjYgMC0xMS41Ny00LjIyLTEzLjQ3LTkuOTFsLTcuOTggNi4x"
    "OUM2LjUxIDQyLjYyIDE0LjYyIDQ4IDI0IDQ4eiIvPjwvc3ZnPg=="
)


def _idx(opciones, valor):
    try:
        return opciones.index(valor)
    except (ValueError, TypeError):
        return 0


def aplicar_usuario_de_sesion():
    """Le dice a la capa de datos de quién son los datos de ESTA sesión.

    Hay que llamarla al inicio de CADA ejecución del script: db_utils guarda al
    usuario en una variable del proceso, que es compartida por todas las sesiones.
    Sin esto, dos personas conectadas a la vez se pisarían los datos.
    """
    uid = st.session_state.get("usuario_id")
    db_utils.set_usuario(uid if uid else "local")


def necesita_bienvenida() -> bool:
    """True si hay que mostrar la pantalla de bienvenida antes del dashboard."""
    if st.session_state.get("_entro"):
        return False
    # Si el usuario cerró sesión, forzamos la bienvenida aunque haya perfil guardado.
    if st.session_state.get("_force_bienv"):
        return True
    # Con cuentas reales SIEMPRE hay que iniciar sesión: sin ella no sabemos de
    # quién son los datos, y entrar directo mostraría los de alguien más.
    if auth_supabase.disponible():
        return True
    # Modo local (sin nube): si ya hizo onboarding antes, entra directo.
    perfil = db_utils.get_perfil()
    if perfil.get("nombre"):
        st.session_state["_entro"] = True
        st.session_state["usuario_nombre"] = perfil.get("nombre")
        st.session_state["usuario_riesgo"] = perfil.get("perfil_riesgo")
        return False
    return True


def cerrar_sesion():
    """Vuelve a la pantalla de bienvenida (cierra la sesión actual)."""
    for k in ("_entro", "_login_google", "usuario_email", "usuario_id",
              "usuario_nombre", "usuario_riesgo"):
        st.session_state.pop(k, None)
    db_utils.set_usuario("local")
    st.session_state["_force_bienv"] = True
    st.session_state["_fase_bienv"] = "login"
    st.rerun()


def _entrar_al_dashboard(nombre: str, riesgo: str):
    st.session_state["usuario_nombre"] = nombre
    st.session_state["usuario_riesgo"] = riesgo
    st.session_state["_entro"] = True
    st.session_state.pop("_force_bienv", None)
    st.rerun()


# Logo VestPlan: una "V" trazada que sube y remata en flecha (degradado azul→morado).
# En una sola línea a propósito: si tiene saltos/indentación, Markdown lo trata como
# bloque de código y muestra el HTML de alrededor como texto crudo.
_LOGO_SVG = (
    '<svg width="78" height="78" viewBox="0 0 120 120" fill="none" xmlns="http://www.w3.org/2000/svg">'
    '<defs><linearGradient id="vpg" x1="15" y1="100" x2="108" y2="18" gradientUnits="userSpaceOnUse">'
    '<stop stop-color="#2563EB"/><stop offset="1" stop-color="#7C3AED"/></linearGradient></defs>'
    '<path d="M22 32 L56 92 L100 22" stroke="url(#vpg)" stroke-width="17" stroke-linecap="round" stroke-linejoin="round"/>'
    '<path d="M100 22 L78 25 M100 22 L97 45" stroke="url(#vpg)" stroke-width="15" stroke-linecap="round" stroke-linejoin="round"/>'
    '</svg>'
)


def _css():
    st.markdown("""
    <style>
    section[data-testid="stSidebar"] { display: none !important; }
    /* Fondo moderno: glow morado sutil arriba + degradado lavanda muy claro */
    [data-testid="stAppViewContainer"] {
        background:
            radial-gradient(900px 460px at 50% -90px, rgba(124,58,237,.16), transparent 60%),
            linear-gradient(180deg, #FBFAFF 0%, #F3F1FF 100%) !important;
    }
    .main .block-container {
        max-width: 430px !important; padding-top: 2.4rem !important; background: transparent !important;
    }
    /* Botón PRIMARIO 'Crear mi cuenta': gradiente morado, elevado */
    .st-key-btn_crear button {
        background: linear-gradient(135deg, #7C3AED 0%, #4F46E5 100%) !important;
        color: #fff !important; border: none !important; font-weight: 700 !important;
        border-radius: 16px !important; padding: 15px !important; font-size: 15px !important;
        box-shadow: 0 12px 26px rgba(99,63,231,.34) !important;
        transition: transform .05s ease, filter .15s ease !important;
    }
    .st-key-btn_crear button:hover { filter: brightness(1.06) !important; }
    .st-key-btn_crear button:active { transform: translateY(1px) !important; }
    /* Botón Google: blanco, elevado, con el logo */
    .st-key-btn_google_login button {
        background: #fff !important; border: 1px solid #EAE7F5 !important;
        color: #1a1a2e !important; font-weight: 600 !important;
        border-radius: 16px !important; padding: 14px !important; font-size: 15px !important;
        box-shadow: 0 3px 12px rgba(16,24,40,.06) !important;
    }
    .st-key-btn_google_login button::before {
        content: ""; display: inline-block;
        width: 18px; height: 18px; margin-right: 10px; vertical-align: -4px;
        background: url('""" + _GOOGLE_LOGO + """') no-repeat center / contain;
    }
    /* Divisor 'o' entre las dos opciones */
    .bienv-or { display: flex; align-items: center; gap: 12px; margin: 16px 2px; }
    .bienv-or::before, .bienv-or::after { content: ""; flex: 1; height: 1px; background: #E4E0F0; }
    .bienv-or span { font-size: 12px; color: #A9A2C4; }
    </style>
    """, unsafe_allow_html=True)


def render_bienvenida():
    _css()
    fase = st.session_state.get("_fase_bienv", "login")
    if fase == "login":
        _fase_login()
    else:
        _fase_datos()


def _iniciar_sesion_usuario(user_id: str, email: str):
    """Deja al usuario 'dentro': desde aquí, la app solo verá SUS datos."""
    st.session_state["usuario_id"] = user_id
    st.session_state["usuario_email"] = email
    db_utils.set_usuario(user_id)
    perfil = db_utils.get_perfil()
    if perfil.get("nombre"):
        _entrar_al_dashboard(perfil.get("nombre"), perfil.get("perfil_riesgo"))
    else:
        st.session_state["_fase_bienv"] = "datos"   # cuenta nueva: pedir perfil
        st.rerun()


def _formulario_cuenta():
    """Entrar o registrarse con correo y contraseña (Supabase Auth)."""
    entrar_tab, crear_tab = st.tabs(["Iniciar sesión", "Crear mi cuenta"])

    with entrar_tab:
        with st.form("form_entrar"):
            email = st.text_input("Correo", key="li_email", placeholder="tu@correo.com")
            pwd = st.text_input("Contraseña", type="password", key="li_pwd")
            ok = st.form_submit_button("Entrar", type="primary", use_container_width=True)
        if ok:
            if not email or not pwd:
                st.warning("Escribe tu correo y tu contraseña.")
            else:
                with st.spinner("Entrando…"):
                    r = auth_supabase.entrar(email, pwd)
                if r["ok"]:
                    _iniciar_sesion_usuario(r["user_id"], r["email"])
                else:
                    st.error(r["msg"])
        if st.button("Olvidé mi contraseña", key="li_olvide"):
            correo = st.session_state.get("li_email", "").strip()
            if not correo:
                st.warning("Escribe tu correo arriba y vuelve a pulsar.")
            else:
                auth_supabase.recuperar_password(correo)
                # Respuesta igual exista o no la cuenta: así no se revela quién está registrado.
                st.info(f"Si {correo} tiene cuenta, te llegará un correo para restablecerla.")

    with crear_tab:
        with st.form("form_crear"):
            email_n = st.text_input("Correo", key="su_email", placeholder="tu@correo.com")
            pwd_n = st.text_input("Contraseña", type="password", key="su_pwd",
                                  help="Mínimo 6 caracteres.")
            pwd_n2 = st.text_input("Repite tu contraseña", type="password", key="su_pwd2")
            ok_n = st.form_submit_button("Crear cuenta", type="primary", use_container_width=True)
        if ok_n:
            if not email_n or not pwd_n:
                st.warning("Escribe tu correo y una contraseña.")
            elif pwd_n != pwd_n2:
                st.warning("Las contraseñas no coinciden.")
            elif len(pwd_n) < 6:
                st.warning("Usa al menos 6 caracteres.")
            else:
                with st.spinner("Creando tu cuenta…"):
                    r = auth_supabase.registrar(email_n, pwd_n)
                if not r["ok"]:
                    st.error(r["msg"])
                elif r["necesita_confirmar"]:
                    st.success("✅ Cuenta creada. Revisa tu correo para confirmarla "
                               "y luego inicia sesión.")
                else:
                    _iniciar_sesion_usuario(r["user_id"], r["email"])


def _fase_login():
    # Logo oficial (imagen) o SVG de respaldo si el archivo no está.
    if _LOGO_PATH.exists():
        lc1, lc2, lc3 = st.columns([1, 2, 1])
        lc2.image(str(_LOGO_PATH), use_container_width=True)
    else:
        st.markdown(
            '<div style="text-align:center;margin:6px 0 0;">' + _LOGO_SVG +
            '<div style="font-size:32px;font-weight:800;letter-spacing:-.5px;margin-top:6px;">'
            '<span style="color:#1a1a2e;">Vest</span><span style="color:#6C63FF;">Plan</span></div></div>',
            unsafe_allow_html=True)

    # Titular + subtítulo (estilo VestPlan)
    st.markdown(
        '<div style="text-align:center;margin:14px 0 8px;">'
        '<div style="font-size:26px;font-weight:800;line-height:1.15;color:#1a1a2e;">Invierte con un plan.</div>'
        '<div style="font-size:26px;font-weight:800;line-height:1.15;color:#6C63FF;">No con emociones.</div></div>'
        '<div style="text-align:center;font-size:14px;color:#7B8494;margin:0 0 28px;">'
        'Estrategias claras. Decisiones inteligentes.<br>Patrimonio a largo plazo.</div>',
        unsafe_allow_html=True)

    # Cuenta real (correo + contraseña) cuando hay Supabase configurado.
    if auth_supabase.disponible():
        _formulario_cuenta()
        st.markdown('<div class="bienv-or"><span>o</span></div>', unsafe_allow_html=True)
    else:
        # Sin nube configurada: modo local de un solo usuario (para desarrollar).
        if st.button("Crear mi cuenta", key="btn_crear", use_container_width=True):
            st.session_state["_fase_bienv"] = "datos"
            st.rerun()
        st.markdown('<div class="bienv-or"><span>o</span></div>', unsafe_allow_html=True)

    # Google: solo en modo LOCAL. Con cuentas reales queda deshabilitado porque
    # su flujo actual (navegador de escritorio) no produce un usuario_id de
    # Supabase; sin ese id, la sesión caería en el usuario "local" y vería datos
    # que no son suyos. Integrarlo bien es "Google OAuth vía Supabase" (pendiente).
    if not auth_supabase.disponible():
        if st.button("Continuar con Google", key="btn_google_login", use_container_width=True):
            with st.spinner("Abriendo Google en tu navegador..."):
                info = auth_utils.login_google()
            if info is not None:
                st.session_state["usuario_email"] = info.get("email", "")
                st.session_state["_login_google"] = True
                perfil = db_utils.get_perfil()
                if perfil.get("nombre"):
                    _entrar_al_dashboard(perfil.get("nombre"), perfil.get("perfil_riesgo"))
                else:
                    st.session_state["usuario_nombre"] = info.get("nombre", "")
                    st.session_state["_fase_bienv"] = "datos"
                    st.rerun()

    st.markdown("""
    <div style="display:flex;align-items:center;justify-content:center;gap:7px;margin-top:26px;">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#6C63FF"
             stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
        <span style="font-size:12px;color:#7B8494;"><b>Tus datos están protegidos.</b></span>
    </div>
    <div style="text-align:center;font-size:11px;color:#A9A2C4;margin-top:4px;">
        Nunca compartimos tu información.</div>
    <div style="text-align:center;font-size:11px;color:#C3C9D6;margin-top:10px;">
        Con Google también conectas tu calendario para recordatorios.</div>
    """, unsafe_allow_html=True)


def _fase_datos():
    perfil = db_utils.get_perfil()
    st.markdown("### Cuéntanos de ti")
    st.caption("Para darte sugerencias a tu medida. Podrás cambiar estos datos "
               "cuando quieras desde **Mi perfil financiero**.")

    if st.session_state.get("_login_google") and st.session_state.get("usuario_nombre"):
        st.success(f"Conectado como {st.session_state['usuario_nombre']}")

    nombre = st.text_input(
        "¿Cómo te llamas?",
        value=st.session_state.get("usuario_nombre") or perfil.get("nombre", ""),
        placeholder="Tu nombre")

    objetivo = st.selectbox("¿Cuál es tu objetivo principal?", OBJETIVOS,
                            index=_idx(OBJETIVOS, perfil.get("objetivo")))

    meta_monto = st.number_input(
        "Meta de ahorro anual (MXN)", min_value=0.0,
        value=float(perfil.get("meta_monto") or 0), step=1000.0, format="%.0f",
        help="¿Cuánto quieres invertir/ahorrar a lo largo de este año? En tu pantalla de "
             "Inicio verás una barra que se llena con lo que ya llevas invertido. "
             "Puedes dejarlo en 0 y ponerlo después desde tu perfil.")

    riesgo = st.radio("¿Cuál es tu perfil de riesgo?", RIESGOS,
                      captions=[_RIESGO_DESC[r] for r in RIESGOS],
                      index=_idx(RIESGOS, perfil.get("perfil_riesgo")))

    casa = st.selectbox("¿Con qué casa de bolsa inviertes?", CASAS_BOLSA,
                        index=_idx(CASAS_BOLSA, perfil.get("casa_bolsa")),
                        help="Nos ayuda a personalizar tu experiencia. Si no ves la tuya, elige 'Otra'.")

    comision = st.number_input(
        "Comisión de tu casa de bolsa (%)", min_value=0.0, max_value=2.0,
        value=float(perfil.get("comision_pct") if perfil.get("comision_pct") is not None else 0.25),
        step=0.05, format="%.2f",
        help="El % que te cobra tu broker (ej. GBM ≈ 0.25%) por cada compra o venta. "
             "La app la calcula sola en cada operación; podrás cambiarla luego desde tu perfil.")

    # Validación: solo falta el nombre para empezar (registro corto = más gente
    # que lo termina). Edad, ingreso y horizonte se editan luego en Perfil.
    completo = bool(nombre.strip())

    if st.button("Empezar", type="primary", use_container_width=True, disabled=not completo):
        db_utils.save_perfil({
            "nombre": nombre.strip(),
            # Conservar lo que ya hubiera (no se piden en el alta corta).
            "edad": perfil.get("edad"),
            "ingreso_mensual": perfil.get("ingreso_mensual"),
            "horizonte_anios": perfil.get("horizonte_anios"),
            "objetivo": objetivo, "perfil_riesgo": riesgo,
        })
        db_utils.set_comision_pct(comision)
        db_utils.set_meta_monto(meta_monto)
        db_utils.set_casa_bolsa(casa)
        _entrar_al_dashboard(nombre.strip(), riesgo)
    if not completo:
        st.caption("✍️ Escribe tu nombre para empezar.")

    if st.button("← Volver", use_container_width=True):
        st.session_state["_fase_bienv"] = "login"
        st.rerun()
