from __future__ import annotations

import re
from typing import Any

import streamlit as st

from modules.autonomos import find_profile, load_autonomos

AUTONOMOS_KEY = "entify_autonomos"
ACTIVE_ID_KEY = "entify_active_autonomo_id"


def init_session() -> None:
    if AUTONOMOS_KEY not in st.session_state:
        st.session_state[AUTONOMOS_KEY] = load_autonomos()
    profiles = st.session_state[AUTONOMOS_KEY]
    if ACTIVE_ID_KEY not in st.session_state:
        active_profiles = [item for item in profiles if item.get("activo", True)]
        st.session_state[ACTIVE_ID_KEY] = active_profiles[0]["id"] if active_profiles else ""


def get_autonomos() -> list[dict[str, Any]]:
    init_session()
    return st.session_state[AUTONOMOS_KEY]


def set_autonomos(items: list[dict[str, Any]]) -> None:
    st.session_state[AUTONOMOS_KEY] = items
    active_id = st.session_state.get(ACTIVE_ID_KEY, "")
    if active_id and not find_profile(items, active_id):
        st.session_state[ACTIVE_ID_KEY] = items[0]["id"] if items else ""


def get_active_profile() -> dict[str, Any] | None:
    init_session()
    return find_profile(get_autonomos(), st.session_state.get(ACTIVE_ID_KEY, ""))


def set_active_profile(profile_id: str) -> None:
    st.session_state[ACTIVE_ID_KEY] = profile_id


def sidebar_autonomo_selector() -> dict[str, Any] | None:
    init_session()
    profiles = [item for item in get_autonomos() if item.get("activo", True)]
    st.sidebar.markdown("### eNTify Invoices")
    st.sidebar.caption("Gestión interna de facturas")
    if not profiles:
        st.sidebar.warning("Todavía no hay autónomos cargados.")
        st.sidebar.page_link("pages/4_Autonomos.py", label="Agregar autónomo", icon="👤")
        return None

    labels = {
        item["id"]: f"{item.get('nombre', '')} · {item.get('nif', '') or 'sin NIF'}"
        for item in profiles
    }
    ids = list(labels)
    current = st.session_state.get(ACTIVE_ID_KEY, "")
    index = ids.index(current) if current in ids else 0
    selected_id = st.sidebar.selectbox(
        "Autónomo activo",
        options=ids,
        index=index,
        format_func=lambda item_id: labels[item_id],
        key="entify_global_autonomo_selector",
    )
    set_active_profile(selected_id)
    profile = find_profile(profiles, selected_id)
    if profile:
        st.sidebar.caption(f"NIF/CIF: {profile.get('nif') or 'Sin completar'}")
    st.sidebar.divider()
    return profile


def workspace_token(profile: dict[str, Any], mode: str) -> str:
    raw = f"{profile.get('id', 'autonomo')}_{mode}"
    return re.sub(r"[^a-zA-Z0-9_]+", "_", raw)
