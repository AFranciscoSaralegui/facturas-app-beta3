from __future__ import annotations

import streamlit as st

from modules.branding import active_profile_card, apply_theme, hero
from modules.session_manager import get_active_profile, sidebar_autonomo_selector

st.set_page_config(page_title="eNTify Invoices", page_icon="🧾", layout="wide")
apply_theme()
profile = sidebar_autonomo_selector()
hero(
    "eNTify Invoices",
    "Procesamiento interno de facturas para autónomos: seleccionar, extraer, revisar y exportar.",
)
active_profile_card(profile or {})

if not profile:
    st.page_link("pages/4_Autonomos.py", label="Crear el primer autónomo", icon="👤")
    st.stop()

st.markdown("### Flujo de trabajo")
col1, col2 = st.columns(2)
with col1:
    st.markdown(
        """
        <div class="entify-card">
          <h3>📥 Facturas recibidas</h3>
          <p>El autónomo activo se excluye como cliente y la aplicación identifica al proveedor.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.page_link("pages/2_Facturas_recibidas.py", label="Abrir facturas recibidas", icon="📥")
with col2:
    st.markdown(
        """
        <div class="entify-card">
          <h3>📤 Facturas emitidas</h3>
          <p>El autónomo activo se interpreta como emisor y la aplicación identifica al cliente.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.page_link("pages/3_Facturas_emitidas.py", label="Abrir facturas emitidas", icon="📤")

st.markdown("### Administración")
col3, col4 = st.columns(2)
with col3:
    st.page_link("pages/4_Autonomos.py", label="Gestionar autónomos", icon="👤")
with col4:
    st.page_link("pages/5_Configuracion.py", label="Configuración del autónomo", icon="⚙️")

st.info(
    "Esta BETA 4.0 agrega el flujo multi-autónomo sin sustituir la aplicación anterior. "
    "Los PDF se usan durante el procesamiento y no se guardan como archivo histórico."
)
