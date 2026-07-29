from __future__ import annotations

import streamlit as st

from modules.autonomos import normalize_profile, save_autonomos
from modules.branding import active_profile_card, apply_theme, hero
from modules.session_manager import get_active_profile, get_autonomos, set_autonomos, sidebar_autonomo_selector

st.set_page_config(page_title="Configuración · eNTify Invoices", page_icon="⚙️", layout="wide")
apply_theme()
profile = sidebar_autonomo_selector()
hero("Configuración del autónomo", "Definí las reglas que se aplicarán al perfil activo.")
active_profile_card(profile or {})
if not profile:
    st.stop()

with st.form("profile_settings"):
    c1, c2 = st.columns(2)
    direccion = c1.text_input("Dirección", value=profile.get("direccion", ""))
    codigo_postal = c2.text_input("Código postal", value=profile.get("codigo_postal", ""))
    c3, c4, c5 = st.columns(3)
    ciudad = c3.text_input("Ciudad", value=profile.get("ciudad", ""))
    pais = c4.text_input("País", value=profile.get("pais", "España"))
    epigrafe = c5.text_input("Epígrafe", value=profile.get("epigrafe", ""))
    c6, c7 = st.columns(2)
    monedas = ["EUR", "USD", "GBP"]
    moneda_actual = profile.get("moneda", "EUR")
    moneda = c6.selectbox("Moneda habitual", monedas, index=monedas.index(moneda_actual) if moneda_actual in monedas else 0)
    plantillas = ["estandar", "internacional"]
    plantilla_actual = profile.get("plantilla", "estandar")
    plantilla = c7.selectbox("Plantilla de Excel", plantillas, index=plantillas.index(plantilla_actual) if plantilla_actual in plantillas else 0)
    internacional = st.checkbox("Emite o recibe facturas internacionales", value=profile.get("facturacion_internacional", False))
    clientes_usa = st.checkbox("Trabaja con clientes de Estados Unidos", value=profile.get("clientes_usa", False))
    notas = st.text_area("Notas y reglas particulares", value=profile.get("notas", ""), height=120)
    submitted = st.form_submit_button("Guardar configuración", type="primary")

if submitted:
    updated_profile = normalize_profile({
        **profile,
        "direccion": direccion,
        "codigo_postal": codigo_postal,
        "ciudad": ciudad,
        "pais": pais,
        "epigrafe": epigrafe,
        "moneda": moneda,
        "plantilla": plantilla,
        "facturacion_internacional": internacional,
        "clientes_usa": clientes_usa,
        "notas": notas,
    })
    updated_items = [updated_profile if item.get("id") == profile.get("id") else item for item in get_autonomos()]
    set_autonomos(updated_items)
    if save_autonomos(updated_items):
        st.success("Configuración guardada.")
    else:
        st.warning("Configuración guardada solo en esta sesión.")

st.info(
    "Las columnas especiales para facturas emitidas en USD y tipos de cambio se incorporarán "
    "en una versión posterior, perfil por perfil, sin alterar la plantilla estándar."
)
