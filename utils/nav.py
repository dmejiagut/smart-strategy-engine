"""Navegación central entre vistas del dashboard."""
import streamlit as st

INICIO = "🏠 Inicio"
DCA = "📊 DCA"
DIV = "💰 Dividendos"
OBJ = "🎯 Por Objetivos"
FIB = "🏢 FIBRAs"
COPY = "👥 Copy Trading"
RESULTADOS = "📈 Mis Resultados"
ESTRATEGIAS = "📊 Estrategias"
PERFIL = "👤 Perfil"
AGENDA = "📅 Agenda"
IMPORTAR = "📥 Importar"
CONVIENE = "🎯 ¿Qué me conviene?"

# Módulos de estrategia (sub-páginas a las que se llega desde el hub Estrategias)
MODULOS_ESTRATEGIA = [DCA, DIV, OBJ, FIB, COPY]

OPCIONES = [INICIO, DCA, DIV, OBJ, FIB, COPY, RESULTADOS]


def goto(target: str):
    """Cambia de vista."""
    st.session_state["nav"] = target
    st.rerun()
