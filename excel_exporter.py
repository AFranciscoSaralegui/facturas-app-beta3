from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd
import streamlit as st

from excel_exporter import build_excel, safe_number
from extractor_v2 import extract_invoice

st.set_page_config(page_title="FacturasAI BETA 3.1", page_icon="🧾", layout="wide")

st.markdown(
    """
<style>
:root{--bg:#f7f5f2;--surface:#fff;--line:#e7e1da;--ink:#211d1a;--muted:#716a64;--green:#276749;--soft:#e7f3ec;--warn:#fff6dc}
[data-testid="stAppViewContainer"]{background:var(--bg)}
[data-testid="stSidebar"]{background:var(--surface);border-right:1px solid var(--line)}
.block-container{padding-top:2rem;max-width:1600px}
.hero{background:linear-gradient(120deg,#204f3c,#2d7456);padding:1.5rem 1.7rem;border-radius:18px;color:#fff;margin-bottom:1.2rem}
.hero h1{font-size:2rem;margin:0 0 .25rem}.hero p{margin:0;color:#dcece4}
.card{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:1.15rem 1.25rem;margin-bottom:1rem;box-shadow:0 2px 10px rgba(40,30,20,.035)}
.small{color:var(--muted);font-size:.86rem}.ok{background:var(--soft);border:1px solid #a7d8bb;padding:.75rem 1rem;border-radius:10px;color:#205d40}.warn{background:var(--warn);border:1px solid #e9cc74;padding:.75rem 1rem;border-radius:10px;color:#72520a}
[data-testid="stMetric"]{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:.8rem 1rem}
</style>
""",
    unsafe_allow_html=True,
)

INTERNAL_COLUMNS = [
    "archivo", "tipo_documento", "fecha_factura", "numero_factura", "proveedor", "nif",
    "concepto", "direccion", "codigo_postal", "pais", "base_imponible", "tipo_iva", "iva",
    "tipo_retencion", "retencion", "total", "modelo_303", "porcentaje_deduccion",
    "importe_deducible_irpf", "cuenta", "tipo_gasto", "validacion",
    "confianza_proveedor", "confianza_importes", "fuente_lectura", "error",
]

EXPENSE_OPTIONS = [
    "Seguros", "Aplicaciones / Software", "Materiales", "Servicios profesionales", "Transporte",
    "Alojamiento", "Publicidad / Marketing", "Telecomunicaciones", "Suministros", "Formacion",
    "Gestoria / Asesoria", "Cuota seguridad social", "Arrendamiento", "Equipos / Hardware", "Otros gastos",
]
DOC_OPTIONS = ["Factura", "Factura simplificada", "Ticket", "Recibo", "Débito", "Nota de cargo", "Otro"]


def reset_results() -> None:
    for key in ("invoice_df", "tax_details", "debug_results", "processed_mode"):
        st.session_state.pop(key, None)


with st.sidebar:
    st.title("🧾 FacturasAI")
    st.caption("BETA 3.1 · Facturación española")
    st.divider()
    mode = st.selectbox("Tipo de procesamiento", ["Recibidas (Gastos)", "Emitidas (Ingresos)"], index=0)
    st.markdown("**Identidad del titular**")
    st.caption("Sirve para excluir al cliente o emisor propio y detectar correctamente la contraparte.")
    own_name = st.text_input("Tu nombre o razón social", placeholder="Ej.: ADAM AIZENBERG TIRZA")
    own_nif = st.text_input("Tu NIF/CIF", placeholder="Ej.: 12345678Z").upper().strip()
    ocr_label = st.selectbox(
        "OCR",
        ["Automático", "No usar", "Forzar siempre"],
        help="Automático usa OCR solo cuando el texto nativo o los importes son insuficientes.",
    )
    ocr_mode = {"Automático": "auto", "No usar": "nunca", "Forzar siempre": "siempre"}[ocr_label]
    st.divider()
    st.caption("La app no guarda archivos de forma permanente. En Streamlit Cloud se procesan en memoria.")

st.markdown(
    """
<div class="hero"><h1>Gestor de facturas · BETA 3.1</h1>
<p>Extracción atenta de proveedor/cliente, NIF, dirección, base imponible, IVA, retención y total.</p></div>
""",
    unsafe_allow_html=True,
)

if not own_nif:
    st.markdown('<div class="warn"><strong>Recomendación:</strong> ingresá el NIF/CIF del titular. Es la forma más segura de impedir que la app confunda al cliente con el proveedor.</div>', unsafe_allow_html=True)

st.markdown('<div class="card">', unsafe_allow_html=True)
uploaded_files = st.file_uploader(
    "Subí facturas PDF o XML Facturae",
    type=["pdf", "xml"],
    accept_multiple_files=True,
    help="Podés seleccionar varias facturas a la vez.",
)
st.markdown('</div>', unsafe_allow_html=True)

if uploaded_files:
    col_process, col_reset = st.columns([3, 1])
    with col_process:
        process_clicked = st.button("Procesar facturas", type="primary", use_container_width=True)
    with col_reset:
        st.button("Limpiar resultados", on_click=reset_results, use_container_width=True)

    if process_clicked:
        rows: list[dict[str, Any]] = []
        details: list[dict[str, Any]] = []
        debug_results: list[dict[str, Any]] = []
        progress = st.progress(0, text="Preparando lectura...")
        for index, uploaded in enumerate(uploaded_files):
            progress.progress((index + 1) / len(uploaded_files), text=f"Analizando {uploaded.name}...")
            data = uploaded.getvalue()
            result = extract_invoice(
                file_bytes=data,
                filename=uploaded.name,
                mode="recibidas" if mode.startswith("Recibidas") else "emitidas",
                own_nif=own_nif,
                own_name=own_name,
                ocr_mode=ocr_mode,
            )
            tax_details = result.pop("detalle_iva", []) or []
            candidates = result.pop("candidatos_partes", []) or []
            detected_text = result.pop("texto_detectado", "")
            for detail in tax_details:
                details.append({"archivo": uploaded.name, **detail})
            debug_results.append({"archivo": uploaded.name, "candidatos": candidates, "texto": detected_text})
            rows.append({column: result.get(column) for column in INTERNAL_COLUMNS})
        progress.empty()
        st.session_state["invoice_df"] = pd.DataFrame(rows, columns=INTERNAL_COLUMNS)
        st.session_state["tax_details"] = details
        st.session_state["debug_results"] = debug_results
        st.session_state["processed_mode"] = mode
        st.markdown(f'<div class="ok">Se procesaron {len(rows)} factura(s). Revisá especialmente las columnas de confianza antes de exportar.</div>', unsafe_allow_html=True)

if "invoice_df" in st.session_state:
    df = st.session_state["invoice_df"]
    metric_cols = st.columns(4)
    metric_cols[0].metric("Facturas", len(df))
    metric_cols[1].metric("Base imponible", f"{df['base_imponible'].apply(safe_number).sum():,.2f} €")
    metric_cols[2].metric("IVA", f"{df['iva'].apply(safe_number).sum():,.2f} €")
    metric_cols[3].metric("Total", f"{df['total'].apply(safe_number).sum():,.2f} €")

    st.subheader("Datos extraídos")
    editor_columns = {
        "archivo": st.column_config.TextColumn("Archivo", disabled=True, width="medium"),
        "tipo_documento": st.column_config.SelectboxColumn("Tipo", options=DOC_OPTIONS, width="small"),
        "fecha_factura": st.column_config.TextColumn("Fecha", width="small"),
        "numero_factura": st.column_config.TextColumn("N.º factura", width="small"),
        "proveedor": st.column_config.TextColumn("Proveedor / Cliente", width="large"),
        "nif": st.column_config.TextColumn("NIF/CIF", width="small"),
        "concepto": st.column_config.TextColumn("Concepto detectado", width="large"),
        "direccion": st.column_config.TextColumn("Dirección", width="large"),
        "codigo_postal": st.column_config.TextColumn("Código postal", width="small"),
        "pais": st.column_config.TextColumn("País", width="small"),
        "base_imponible": st.column_config.NumberColumn("Base imponible", format="%.2f €", width="small"),
        "tipo_iva": st.column_config.TextColumn("Tipo IVA", width="small"),
        "iva": st.column_config.NumberColumn("IVA", format="%.2f €", width="small"),
        "tipo_retencion": st.column_config.TextColumn("Tipo retención", width="small"),
        "retencion": st.column_config.NumberColumn("Retención", format="%.2f €", width="small"),
        "total": st.column_config.NumberColumn("Total", format="%.2f €", width="small"),
        "modelo_303": st.column_config.SelectboxColumn("Modelo 303", options=["", "Sí", "No", "sí", "no"], width="small"),
        "porcentaje_deduccion": st.column_config.TextColumn("% deducción", width="small"),
        "importe_deducible_irpf": st.column_config.NumberColumn("Deducible IRPF", format="%.2f €", width="small"),
        "cuenta": st.column_config.TextColumn("Cuenta", width="small"),
        "tipo_gasto": st.column_config.SelectboxColumn("Tipo de gasto", options=EXPENSE_OPTIONS, width="medium"),
        "validacion": st.column_config.TextColumn("Validación", disabled=True, width="medium"),
        "confianza_proveedor": st.column_config.ProgressColumn("Conf. proveedor", min_value=0, max_value=100, format="%d%%", width="small"),
        "confianza_importes": st.column_config.ProgressColumn("Conf. importes", min_value=0, max_value=100, format="%d%%", width="small"),
        "fuente_lectura": st.column_config.TextColumn("Lectura", disabled=True, width="small"),
        "error": st.column_config.TextColumn("Observaciones", disabled=True, width="large"),
    }
    edited = st.data_editor(
        df,
        column_config=editor_columns,
        hide_index=True,
        use_container_width=True,
        num_rows="dynamic",
        key="invoice_editor",
    )
    st.session_state["invoice_df"] = edited

    low_party = edited[edited["confianza_proveedor"].fillna(0) < 70]
    low_amount = edited[edited["confianza_importes"].fillna(0) < 70]
    if len(low_party) or len(low_amount):
        st.warning(f"Revisión recomendada: {len(low_party)} fila(s) con baja confianza de proveedor y {len(low_amount)} con baja confianza de importes.")

    st.subheader("Exportar")
    processed_mode = st.session_state.get("processed_mode", mode)
    excel_bytes = build_excel(edited, st.session_state.get("tax_details", []), processed_mode)
    st.download_button(
        "Descargar Excel",
        data=excel_bytes,
        file_name=f"facturas_beta3_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
        use_container_width=True,
    )

    with st.expander("Diagnóstico de lectura"):
        st.caption("Esta sección permite entender por qué se eligió un proveedor y corregir casos nuevos.")
        for debug in st.session_state.get("debug_results", []):
            st.markdown(f"#### {debug['archivo']}")
            candidates = debug.get("candidatos", [])
            if candidates:
                st.dataframe(pd.DataFrame(candidates), hide_index=True, use_container_width=True)
            else:
                st.info("No se encontraron bloques fiscales estructurados.")
            st.text_area("Texto detectado", debug.get("texto", ""), height=180, key=f"debug_{debug['archivo']}")
else:
    st.info("Subí una o más facturas y presioná “Procesar facturas”.")
