from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd
import streamlit as st

from excel_exporter import build_excel, safe_number
from extractor_v2 import extract_invoice
from modules.autonomos import slugify
from modules.branding import active_profile_card, hero
from modules.session_manager import sidebar_autonomo_selector, workspace_token

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


def _state_keys(profile: dict[str, Any], mode: str) -> dict[str, str]:
    token = workspace_token(profile, mode)
    return {
        "df": f"entify_df_{token}",
        "details": f"entify_tax_details_{token}",
        "debug": f"entify_debug_{token}",
        "uploader": f"entify_uploader_{token}",
        "editor": f"entify_editor_{token}",
    }


def _clear_workspace(keys: dict[str, str]) -> None:
    for key in keys.values():
        st.session_state.pop(key, None)


def _editor_columns(counterparty_label: str) -> dict[str, Any]:
    return {
        "archivo": st.column_config.TextColumn("Archivo", disabled=True, width="medium"),
        "tipo_documento": st.column_config.SelectboxColumn("Tipo", options=DOC_OPTIONS, width="small"),
        "fecha_factura": st.column_config.TextColumn("Fecha", width="small"),
        "numero_factura": st.column_config.TextColumn("N.º factura", width="small"),
        "proveedor": st.column_config.TextColumn(counterparty_label, width="large"),
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
        "confianza_proveedor": st.column_config.ProgressColumn("Conf. contraparte", min_value=0, max_value=100, format="%d%%", width="small"),
        "confianza_importes": st.column_config.ProgressColumn("Conf. importes", min_value=0, max_value=100, format="%d%%", width="small"),
        "fuente_lectura": st.column_config.TextColumn("Lectura", disabled=True, width="small"),
        "error": st.column_config.TextColumn("Observaciones", disabled=True, width="large"),
    }


def render_invoice_workspace(mode: str) -> None:
    is_received = mode == "recibidas"
    title = "Facturas recibidas" if is_received else "Facturas emitidas"
    subtitle = (
        "El autónomo activo se interpreta como cliente/receptor; la app busca al proveedor."
        if is_received
        else "El autónomo activo se interpreta como emisor; la app busca al cliente."
    )
    profile = sidebar_autonomo_selector()
    hero(f"eNTify Invoices · {title}", subtitle)
    active_profile_card(profile or {})
    if not profile:
        st.stop()

    keys = _state_keys(profile, mode)
    ocr_label = st.sidebar.selectbox(
        "OCR",
        ["Automático", "No usar", "Forzar siempre"],
        index=0,
        key=f"ocr_{workspace_token(profile, mode)}",
        help="Automático usa OCR cuando el texto nativo o los importes son insuficientes.",
    )
    ocr_mode = {"Automático": "auto", "No usar": "nunca", "Forzar siempre": "siempre"}[ocr_label]
    st.sidebar.caption("Los PDF se procesan en memoria y no se incorporan al registro de autónomos.")

    uploaded_files = st.file_uploader(
        f"Subí las {title.lower()} de {profile.get('nombre', '')}",
        type=["pdf", "xml"],
        accept_multiple_files=True,
        key=keys["uploader"],
        help="Podés seleccionar varias facturas a la vez.",
    )

    col_process, col_clear = st.columns([3, 1])
    process_clicked = col_process.button(
        "Procesar facturas",
        type="primary",
        use_container_width=True,
        disabled=not uploaded_files,
        key=f"process_{workspace_token(profile, mode)}",
    )
    if col_clear.button(
        "Limpiar lote",
        use_container_width=True,
        key=f"clear_{workspace_token(profile, mode)}",
    ):
        _clear_workspace(keys)
        st.rerun()

    if process_clicked and uploaded_files:
        rows: list[dict[str, Any]] = []
        details: list[dict[str, Any]] = []
        debug_results: list[dict[str, Any]] = []
        progress = st.progress(0, text="Preparando lectura...")
        for index, uploaded in enumerate(uploaded_files):
            progress.progress((index + 1) / len(uploaded_files), text=f"Analizando {uploaded.name}...")
            result = extract_invoice(
                file_bytes=uploaded.getvalue(),
                filename=uploaded.name,
                mode=mode,
                own_nif=profile.get("nif", ""),
                own_name=profile.get("nombre", ""),
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
        st.session_state[keys["df"]] = pd.DataFrame(rows, columns=INTERNAL_COLUMNS)
        st.session_state[keys["details"]] = details
        st.session_state[keys["debug"]] = debug_results
        st.success(f"Se procesaron {len(rows)} factura(s) para {profile.get('nombre', '')}.")

    if keys["df"] not in st.session_state:
        st.info("Subí una o más facturas y presioná “Procesar facturas”.")
        return

    df = st.session_state[keys["df"]]
    metric_cols = st.columns(4)
    metric_cols[0].metric("Facturas", len(df))
    metric_cols[1].metric("Base imponible", f"{df['base_imponible'].apply(safe_number).sum():,.2f} €")
    metric_cols[2].metric("IVA", f"{df['iva'].apply(safe_number).sum():,.2f} €")
    metric_cols[3].metric("Total", f"{df['total'].apply(safe_number).sum():,.2f} €")

    st.subheader("Revisión de datos")
    edited = st.data_editor(
        df,
        column_config=_editor_columns("Proveedor" if is_received else "Cliente"),
        hide_index=True,
        use_container_width=True,
        num_rows="dynamic",
        key=keys["editor"],
    )
    st.session_state[keys["df"]] = edited

    low_party = edited[edited["confianza_proveedor"].fillna(0) < 70]
    low_amount = edited[edited["confianza_importes"].fillna(0) < 70]
    if len(low_party) or len(low_amount):
        st.warning(
            f"Revisión recomendada: {len(low_party)} fila(s) con baja confianza de contraparte "
            f"y {len(low_amount)} con baja confianza de importes."
        )

    st.subheader("Exportar Excel")
    export_mode = "Recibidas (Gastos)" if is_received else "Emitidas (Ingresos)"
    excel_bytes = build_excel(edited, st.session_state.get(keys["details"], []), export_mode)
    file_slug = slugify(profile.get("nombre", "autonomo"))
    st.download_button(
        "Descargar Excel",
        data=excel_bytes,
        file_name=f"{file_slug}_{mode}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
        use_container_width=True,
        key=f"download_{workspace_token(profile, mode)}",
    )

    with st.expander("Diagnóstico de lectura"):
        st.caption("Permite entender por qué se eligió una contraparte y ajustar casos futuros.")
        for debug in st.session_state.get(keys["debug"], []):
            st.markdown(f"#### {debug['archivo']}")
            candidates = debug.get("candidatos", [])
            if candidates:
                st.dataframe(pd.DataFrame(candidates), hide_index=True, use_container_width=True)
            else:
                st.info("No se encontraron bloques fiscales estructurados.")
            st.text_area(
                "Texto detectado",
                debug.get("texto", ""),
                height=180,
                key=f"debug_{workspace_token(profile, mode)}_{debug['archivo']}",
            )
