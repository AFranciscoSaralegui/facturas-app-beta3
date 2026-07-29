from __future__ import annotations

import streamlit as st


pages = {
    "eNTify Invoices": [
        st.Page(
            "pages/0_eNTify_Invoices.py",
            title="Inicio",
            icon="🏠",
            default=True,
        ),
        st.Page(
            "pages/2_Facturas_recibidas.py",
            title="Facturas recibidas",
            icon="📥",
        ),
        st.Page(
            "pages/3_Facturas_emitidas.py",
            title="Facturas emitidas",
            icon="📤",
        ),
    ],
    "Administración": [
        st.Page(
            "pages/4_Autonomos.py",
            title="Autónomos",
            icon="👤",
        ),
        st.Page(
            "pages/5_Configuracion.py",
            title="Configuración",
            icon="⚙️",
        ),
    ],
}

navigation = st.navigation(pages, position="sidebar")
navigation.run()
