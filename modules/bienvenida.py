"""Pantalla de bienvenida: login con Google o modo invitado + perfil financiero.

Actúa como "compuerta": mientras el usuario no haya entrado, la app muestra
esta pantalla en lugar del dashboard. Una vez completado el perfil, no se
vuelve a preguntar (y se puede editar luego desde "Mi perfil financiero").
"""
import streamlit as st
from utils import db_utils, auth_utils

RIESGOS = ["Conservador", "Moderado", "Agresivo"]
_RIESGO_DESC = {
    "Conservador": "Prefiero seguridad aunque gane menos.",
    "Moderado": "Busco un equilibrio entre riesgo y ganancia.",
    "Agresivo": "Acepto más riesgo por más crecimiento.",
}
OBJETIVOS = ["Crecimiento de patrimonio", "Ingresos pasivos", "Retiro",
             "Ahorro de corto plazo", "Especulación / trading"]

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


def necesita_bienvenida() -> bool:
    """True si hay que mostrar la pantalla de bienvenida antes del dashboard."""
    if st.session_state.get("_entro"):
        return False
    # Si el usuario cerró sesión, forzamos la bienvenida aunque haya perfil guardado.
    if st.session_state.get("_force_bienv"):
        return True
    # Si ya hizo onboarding antes (nombre guardado), entra directo.
    perfil = db_utils.get_perfil()
    if perfil.get("nombre"):
        st.session_state["_entro"] = True
        st.session_state["usuario_nombre"] = perfil.get("nombre")
        st.session_state["usuario_riesgo"] = perfil.get("perfil_riesgo")
        return False
    return True


def cerrar_sesion():
    """Vuelve a la pantalla de bienvenida (cierra la sesión actual)."""
    for k in ("_entro", "_login_google", "usuario_email"):
        st.session_state.pop(k, None)
    st.session_state["_force_bienv"] = True
    st.session_state["_fase_bienv"] = "login"
    st.rerun()


def _entrar_al_dashboard(nombre: str, riesgo: str):
    st.session_state["usuario_nombre"] = nombre
    st.session_state["usuario_riesgo"] = riesgo
    st.session_state["_entro"] = True
    st.session_state.pop("_force_bienv", None)
    st.rerun()


def _css():
    st.markdown("""
    <style>
    section[data-testid="stSidebar"] { display: none !important; }
    .main .block-container { max-width: 460px !important; padding-top: 2.5rem; }
    .bienv-logo {
        width: 64px; height: 64px; border-radius: 18px; margin: 0 auto 16px;
        background: #EEEDFE; color: #534AB7;
        display: flex; align-items: center; justify-content: center; font-size: 30px;
    }
    .bienv-title { text-align: center; font-size: 20px; font-weight: 600; margin: 0; }
    .bienv-sub { text-align: center; font-size: 14px; color: #7B8494; margin: 8px 0 28px; }
    .st-key-btn_google_login button::before {
        content: ""; display: inline-block;
        width: 18px; height: 18px; margin-right: 10px; vertical-align: -4px;
        background: url('""" + _GOOGLE_LOGO + """') no-repeat center / contain;
    }
    </style>
    """, unsafe_allow_html=True)


def render_bienvenida():
    _css()
    fase = st.session_state.get("_fase_bienv", "login")
    if fase == "login":
        _fase_login()
    else:
        _fase_datos()


def _fase_login():
    st.markdown('<div class="bienv-logo">📈</div>', unsafe_allow_html=True)
    st.markdown('<p class="bienv-title">Smart Strategy Engine</p>', unsafe_allow_html=True)
    st.markdown('<p class="bienv-sub">Invierte con estrategias claras, '
                'aunque no sepas nada de finanzas.</p>', unsafe_allow_html=True)

    if st.button("Continuar con Google", key="btn_google_login", use_container_width=True):
        with st.spinner("Abriendo Google en tu navegador..."):
            info = auth_utils.login_google()
        if info is not None:
            st.session_state["usuario_email"] = info.get("email", "")
            st.session_state["_login_google"] = True
            perfil = db_utils.get_perfil()
            if perfil.get("nombre"):
                # Ya tiene perfil → directo al dashboard, sin volver a preguntar.
                _entrar_al_dashboard(perfil.get("nombre"), perfil.get("perfil_riesgo"))
            else:
                # Usuario nuevo → completar perfil (nombre precargado de Google).
                st.session_state["usuario_nombre"] = info.get("nombre", "")
                st.session_state["_fase_bienv"] = "datos"
                st.rerun()

    if st.button("Entrar sin iniciar sesión", use_container_width=True):
        st.session_state["_fase_bienv"] = "datos"
        st.rerun()

    st.caption("Con Google también conectas tu calendario para recordatorios.")


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

    c1, c2 = st.columns(2)
    edad = c1.number_input("Edad", min_value=18, max_value=100,
                           value=int(perfil.get("edad") or 30), step=1)
    horizonte = c2.number_input("Horizonte (años)", min_value=1, max_value=50,
                                value=int(perfil.get("horizonte_anios") or 10), step=1)

    ingreso = st.number_input("Ingreso mensual (MXN)", min_value=0.0,
                              value=float(perfil.get("ingreso_mensual") or 0),
                              step=1000.0, format="%.2f")

    objetivo = st.selectbox("¿Cuál es tu objetivo principal?", OBJETIVOS,
                            index=_idx(OBJETIVOS, perfil.get("objetivo")))

    riesgo = st.radio("¿Cuál es tu perfil de riesgo?", RIESGOS,
                      captions=[_RIESGO_DESC[r] for r in RIESGOS],
                      index=_idx(RIESGOS, perfil.get("perfil_riesgo")))

    comision = st.number_input(
        "Comisión de tu casa de bolsa (%)", min_value=0.0, max_value=2.0,
        value=float(perfil.get("comision_pct") if perfil.get("comision_pct") is not None else 0.25),
        step=0.05, format="%.2f",
        help="El % que te cobra tu broker (ej. GBM ≈ 0.25%) por cada compra o venta. "
             "La app la calcula sola en cada operación; podrás cambiarla luego desde tu perfil.")

    if st.button("Empezar", type="primary", use_container_width=True,
                 disabled=not nombre.strip()):
        db_utils.save_perfil({
            "nombre": nombre.strip(), "edad": int(edad),
            "ingreso_mensual": float(ingreso), "objetivo": objetivo,
            "perfil_riesgo": riesgo, "horizonte_anios": int(horizonte),
        })
        db_utils.set_comision_pct(comision)
        _entrar_al_dashboard(nombre.strip(), riesgo)

    if st.button("← Volver", use_container_width=True):
        st.session_state["_fase_bienv"] = "login"
        st.rerun()
