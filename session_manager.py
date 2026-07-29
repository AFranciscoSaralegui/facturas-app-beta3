from __future__ import annotations

import streamlit as st

CSS = """
<style>
:root{
  --entify-bg:#f7f5f2;
  --entify-surface:#ffffff;
  --entify-line:#e7e1da;
  --entify-ink:#211d1a;
  --entify-muted:#716a64;
  --entify-green:#276749;
  --entify-green-2:#2d7456;
  --entify-soft:#e7f3ec;
  --entify-warn:#fff6dc;
}
[data-testid="stAppViewContainer"]{background:var(--entify-bg)}
[data-testid="stSidebar"]{background:var(--entify-surface);border-right:1px solid var(--entify-line)}
.block-container{padding-top:1.7rem;max-width:1600px}
.entify-hero{background:linear-gradient(120deg,#204f3c,#2d7456);padding:1.45rem 1.65rem;border-radius:18px;color:#fff;margin-bottom:1.15rem;box-shadow:0 8px 30px rgba(32,79,60,.12)}
.entify-hero h1{font-size:2rem;margin:0 0 .25rem}.entify-hero p{margin:0;color:#dcece4}
.entify-card{background:var(--entify-surface);border:1px solid var(--entify-line);border-radius:14px;padding:1.1rem 1.2rem;margin-bottom:1rem;box-shadow:0 2px 10px rgba(40,30,20,.035)}
.entify-chip{display:inline-block;background:var(--entify-soft);color:#205d40;border:1px solid #b9ddc7;border-radius:999px;padding:.28rem .65rem;font-size:.82rem;font-weight:600;margin-right:.35rem}
.entify-warn{background:var(--entify-warn);border:1px solid #e9cc74;padding:.75rem 1rem;border-radius:10px;color:#72520a}
.entify-ok{background:var(--entify-soft);border:1px solid #a7d8bb;padding:.75rem 1rem;border-radius:10px;color:#205d40}
.entify-muted{color:var(--entify-muted);font-size:.88rem}
[data-testid="stMetric"]{background:var(--entify-surface);border:1px solid var(--entify-line);border-radius:12px;padding:.8rem 1rem}
</style>
"""


def apply_theme() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def hero(title: str, subtitle: str) -> None:
    st.markdown(
        f'<div class="entify-hero"><h1>{title}</h1><p>{subtitle}</p></div>',
        unsafe_allow_html=True,
    )


def active_profile_card(profile: dict) -> None:
    if not profile:
        st.markdown(
            '<div class="entify-warn"><strong>No hay un autónomo activo.</strong> '
            'Seleccioná o creá uno para comenzar.</div>',
            unsafe_allow_html=True,
        )
        return
    name = profile.get("nombre", "")
    nif = profile.get("nif", "")
    currency = profile.get("moneda", "EUR")
    st.markdown(
        f"""
        <div class="entify-card">
          <div class="entify-muted">Autónomo activo</div>
          <div style="font-size:1.2rem;font-weight:700;margin:.1rem 0 .4rem">{name}</div>
          <span class="entify-chip">NIF/CIF: {nif or 'Sin completar'}</span>
          <span class="entify-chip">Moneda: {currency}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
