from __future__ import annotations

import streamlit as st

from modules.branding import apply_theme
from modules.invoice_workspace import render_invoice_workspace

st.set_page_config(page_title="Recibidas · eNTify Invoices", page_icon="📥", layout="wide")
apply_theme()
render_invoice_workspace("recibidas")
