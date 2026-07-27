from __future__ import annotations

import io
import math
import re
import unicodedata
import xml.etree.ElementTree as ET
from dataclasses import dataclass, asdict
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Iterable, Optional

import pdfplumber
from dateutil import parser as dateparser
from rapidfuzz import fuzz

MONEY_Q = Decimal("0.01")
COMMON_VAT_RATES = [Decimal("0"), Decimal("4"), Decimal("5"), Decimal("10"), Decimal("21")]
COMMON_RET_RATES = [Decimal("1"), Decimal("2"), Decimal("7"), Decimal("15"), Decimal("19")]

SPANISH_MONTHS = {
    "ene": 1, "enero": 1,
    "feb": 2, "febrero": 2,
    "mar": 3, "marzo": 3,
    "abr": 4, "abril": 4,
    "may": 5, "mayo": 5,
    "jun": 6, "junio": 6,
    "jul": 7, "julio": 7,
    "ago": 8, "agosto": 8,
    "sep": 9, "sept": 9, "septiembre": 9, "setiembre": 9,
    "oct": 10, "octubre": 10,
    "nov": 11, "noviembre": 11,
    "dic": 12, "diciembre": 12,
}

SELLER_WORDS = (
    "emisor", "proveedor", "vendedor", "seller", "supplier", "expedido por",
    "prestador", "datos fiscales", "datos del emisor", "from",
)
BUYER_WORDS = (
    "cliente", "receptor", "destinatario", "comprador", "buyer", "customer",
    "bill to", "facturar a", "datos del cliente",
)
SECTION_WORDS = (
    "concepto", "descripcion", "descripción", "detalle", "unidades", "cantidad",
    "base imponible", "subtotal", "total", "forma de pago", "vencimiento",
)
ADDRESS_WORDS = (
    "calle", "c/", "cl.", "avenida", "avda", "av.", "plaza", "paseo", "camino",
    "carretera", "ronda", "poligono", "polígono", "urbanizacion", "urbanización",
    "road", "street", "avenue", "rue", "via",
)
LEGAL_SUFFIX_RE = re.compile(
    r"\b(?:S\.?\s*L\.?\s*U?\.?|S\.?\s*A\.?\s*U?\.?|S\.?\s*L\.?\s*P\.?|"
    r"S\.?\s*C\.?|S\.?\s*C\.?\s*P\.?|COOP\.?|LTD\.?|LIMITED|LLC|GMBH|BV|SARL)\b",
    re.IGNORECASE,
)

# NIF, NIE y CIF espanoles. Se permiten prefijos ES y separadores de OCR.
SPANISH_ID_RE = re.compile(
    r"(?<![A-Z0-9])(?:ES[\s\-]?)?(?:"
    r"[ABCDEFGHJKLMNPQRSUVW][\s\-]?\d{7}[\s\-]?[0-9A-J]"
    r"|[XYZ][\s\-]?\d{7}[\s\-]?[A-Z]"
    r"|\d{8}[\s\-]?[A-Z]"
    r")(?![A-Z0-9])",
    re.IGNORECASE,
)

DATE_TOKEN_RE = re.compile(
    r"\b(?:\d{1,2}[./-]\d{1,2}[./-]\d{2,4}|"
    r"\d{1,2}[\s./-]+(?:ene(?:ro)?|feb(?:rero)?|mar(?:zo)?|abr(?:il)?|may(?:o)?|"
    r"jun(?:io)?|jul(?:io)?|ago(?:sto)?|sep(?:t(?:iembre)?)?|set(?:iembre)?|"
    r"oct(?:ubre)?|nov(?:iembre)?|dic(?:iembre)?)[.\s/-]+\d{2,4})\b",
    re.IGNORECASE,
)

# Se priorizan importes con decimales para no confundir porcentajes, fechas, unidades o IBAN.
MONEY_RE = re.compile(
    r"(?<![A-Z0-9])(?:[-−–]\s*)?(?:"
    r"\d{1,3}(?:[.\s]\d{3})+(?:,\d{2,4})"
    r"|\d{1,3}(?:,\d{3})+(?:\.\d{2,4})"
    r"|\d+(?:[.,]\d{2,4})"
    r")(?:\s*(?:€|EUR))?(?![A-Z0-9])",
    re.IGNORECASE,
)
INTEGER_EUR_RE = re.compile(r"(?<![A-Z0-9])(?:[-−–]\s*)?\d+\s*(?:€|EUR)(?![A-Z0-9])", re.IGNORECASE)
PERCENT_RE = re.compile(r"(?<!\d)(\d{1,2}(?:[.,]\d{1,2})?)\s*%")

CONCEPTO_KW = {
    "Seguros": ["seguro", "prima", "cobertura", "axa", "mapfre", "allianz", "zurich"],
    "Aplicaciones / Software": ["software", "saas", "licencia", "suscripcion", "suscripción", "adobe", "microsoft", "hosting", "dominio", "cloud"],
    "Materiales": ["material", "papeleria", "papelería", "toner", "cartucho", "consumible", "papel", "tinta"],
    "Servicios profesionales": ["honorarios", "consultoria", "consultoría", "servicios profesionales", "cesion de clientes", "cesión de clientes", "comision", "comisión"],
    "Transporte": ["taxi", "uber", "cabify", "renfe", "avion", "avión", "vuelo", "transporte", "gasolina", "peaje", "parking"],
    "Alojamiento": ["hotel", "hostal", "airbnb", "alojamiento"],
    "Publicidad / Marketing": ["publicidad", "marketing", "anuncio", "ads", "diseño", "impresion", "impresión"],
    "Telecomunicaciones": ["telefono", "teléfono", "movil", "móvil", "internet", "fibra", "movistar", "vodafone", "orange", "digi"],
    "Suministros": ["electricidad", "agua", "gas", "energia", "energía", "iberdrola", "endesa", "naturgy"],
    "Formacion": ["formacion", "formación", "curso", "masterclass", "training", "seminario"],
    "Gestoria / Asesoria": ["gestoria", "gestoría", "asesoria", "asesoría", "notaria", "notaría", "abogado", "contabilidad"],
    "Arrendamiento": ["alquiler", "arrendamiento", "renta", "local", "oficina", "coworking"],
    "Equipos / Hardware": ["ordenador", "portatil", "portátil", "monitor", "teclado", "impresora", "disco", "tablet", "hardware"],
}

FACTURAE_NS = [
    "http://www.facturae.gob.es/formato/Versiones/Facturaev3_2_2.xsd",
    "http://www.facturae.gob.es/formato/Versiones/Facturaev3_2_1.xsd",
    "http://www.facturae.gob.es/formato/Versiones/Facturaev3_2.xsd",
    "",
]


def strip_accents(value: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", value or "") if not unicodedata.combining(c))


def norm_text(value: str) -> str:
    value = strip_accents(value or "").lower()
    value = value.replace("º", "o").replace("ª", "a")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def clean_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").replace("\xa0", " ")).strip()


def normalize_tax_id(value: str) -> str:
    value = re.sub(r"[^A-Z0-9]", "", strip_accents(value or "").upper())
    if value.startswith("ES") and len(value) > 9:
        value = value[2:]
    return value


def q2(value: Decimal) -> Decimal:
    return value.quantize(MONEY_Q, rounding=ROUND_HALF_UP)


def parse_decimal(value: Any) -> Optional[Decimal]:
    if value is None:
        return None
    raw = str(value).strip().upper().replace("EUR", "").replace("€", "")
    raw = raw.replace("−", "-").replace("–", "-").replace(" ", "")
    if not raw:
        return None
    negative = raw.startswith("-") or (raw.startswith("(") and raw.endswith(")"))
    raw = raw.strip("-()")
    if "," in raw and "." in raw:
        if raw.rfind(",") > raw.rfind("."):
            raw = raw.replace(".", "").replace(",", ".")
        else:
            raw = raw.replace(",", "")
    elif "," in raw:
        raw = raw.replace(".", "").replace(",", ".")
    raw = re.sub(r"[^0-9.]", "", raw)
    if not raw:
        return None
    try:
        result = Decimal(raw)
        if negative:
            result = -result
        return q2(result)
    except InvalidOperation:
        return None


def decimal_to_float(value: Optional[Decimal]) -> Optional[float]:
    return float(value) if value is not None else None


def money_tokens(line: str) -> list[Decimal]:
    text = line or ""
    found: list[tuple[int, int, Decimal]] = []
    occupied: list[tuple[int, int]] = []

    # Primero se capturan importes decimales completos. Esto evita que
    # "222,73 €" produzca también el falso importe entero "73 €".
    for match in MONEY_RE.finditer(text):
        tail = text[match.end():match.end() + 3]
        if "%" in tail:
            continue
        amount = parse_decimal(match.group(0))
        if amount is not None:
            found.append((match.start(), match.end(), amount))
            occupied.append((match.start(), match.end()))

    # Los importes enteros con símbolo monetario solo se aceptan si no se
    # solapan con un importe decimal ya detectado.
    for match in INTEGER_EUR_RE.finditer(text):
        if any(not (match.end() <= start or match.start() >= end) for start, end in occupied):
            continue
        amount = parse_decimal(match.group(0))
        if amount is not None:
            found.append((match.start(), match.end(), amount))

    found.sort(key=lambda item: item[0])
    return [amount for _, _, amount in found]


def percent_tokens(line: str) -> list[Decimal]:
    out: list[Decimal] = []
    for match in PERCENT_RE.finditer(line or ""):
        value = parse_decimal(match.group(1))
        if value is not None:
            out.append(value)
    return out


def parse_spanish_date(value: str) -> str:
    if not value:
        return ""
    raw = clean_spaces(value).strip(" ,;:")
    normalized = norm_text(raw).replace(".", " ")
    # Fecha con mes escrito: 01-abr.-26, 1 abril 2026, etc.
    match = re.search(
        r"\b(\d{1,2})[\s/-]+([a-z]+)[\s/-]+(\d{2,4})\b",
        normalized,
        re.IGNORECASE,
    )
    if match:
        day = int(match.group(1))
        month_key = match.group(2).lower()
        month = SPANISH_MONTHS.get(month_key)
        if month is None:
            for key, number in SPANISH_MONTHS.items():
                if month_key.startswith(key) or key.startswith(month_key):
                    month = number
                    break
        if month:
            year = int(match.group(3))
            if year < 100:
                year += 2000 if year < 70 else 1900
            try:
                return datetime(year, month, day).strftime("%d/%m/%Y")
            except ValueError:
                return ""
    try:
        parsed = dateparser.parse(raw, dayfirst=True, fuzzy=False)
        return parsed.strftime("%d/%m/%Y") if parsed else ""
    except Exception:
        return ""


@dataclass
class Line:
    page: int
    top: float
    bottom: float
    x0: float
    x1: float
    text: str
    words: list[dict[str, Any]]

    @property
    def center_x(self) -> float:
        return (self.x0 + self.x1) / 2


@dataclass
class PartyCandidate:
    name: str
    tax_id: str
    address: str
    postal_code: str
    country: str
    page: int
    x: float
    top: float
    score: float = 0.0
    reasons: str = ""


@dataclass
class InvoiceResult:
    archivo: str = ""
    tipo_documento: str = "Factura"
    fecha_factura: str = ""
    numero_factura: str = ""
    proveedor: str = ""
    nif: str = ""
    concepto: str = ""
    direccion: str = ""
    codigo_postal: str = ""
    pais: str = "España"
    base_imponible: Optional[float] = None
    tipo_iva: str = ""
    iva: Optional[float] = None
    tipo_retencion: str = ""
    retencion: Optional[float] = None
    total: Optional[float] = None
    modelo_303: str = ""
    porcentaje_deduccion: str = ""
    importe_deducible_irpf: Optional[float] = None
    cuenta: str = ""
    tipo_gasto: str = "Otros gastos"
    validacion: str = ""
    confianza_proveedor: int = 0
    confianza_importes: int = 0
    fuente_lectura: str = "PDF"
    error: str = ""
    detalle_iva: list[dict[str, Any]] | None = None
    candidatos_partes: list[dict[str, Any]] | None = None
    texto_detectado: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_lines(words: list[dict[str, Any]], tolerance: float = 3.2) -> list[Line]:
    if not words:
        return []
    prepared = []
    for word in words:
        text = clean_spaces(str(word.get("text", "")))
        if not text:
            continue
        prepared.append({
            **word,
            "text": text,
            "page": int(word.get("page", 0)),
            "top": float(word.get("top", 0.0)),
            "bottom": float(word.get("bottom", word.get("top", 0.0) + 8.0)),
            "x0": float(word.get("x0", 0.0)),
            "x1": float(word.get("x1", word.get("x0", 0.0) + 1.0)),
        })
    prepared.sort(key=lambda w: (w["page"], w["top"], w["x0"]))
    groups: list[list[dict[str, Any]]] = []
    for word in prepared:
        placed = False
        for group in reversed(groups[-8:]):
            if group[0]["page"] != word["page"]:
                continue
            avg_top = sum(w["top"] for w in group) / len(group)
            if abs(avg_top - word["top"]) <= tolerance:
                group.append(word)
                placed = True
                break
        if not placed:
            groups.append([word])
    lines: list[Line] = []
    for group in groups:
        group.sort(key=lambda w: w["x0"])
        lines.append(Line(
            page=group[0]["page"],
            top=min(w["top"] for w in group),
            bottom=max(w["bottom"] for w in group),
            x0=min(w["x0"] for w in group),
            x1=max(w["x1"] for w in group),
            text=clean_spaces(" ".join(w["text"] for w in group)),
            words=group,
        ))
    return sorted(lines, key=lambda line: (line.page, line.top, line.x0))


def lines_to_text(lines: Iterable[Line]) -> str:
    return "\n".join(line.text for line in lines)


def split_lines_by_columns(lines: list[Line], gap_threshold: float = 75.0) -> list[Line]:
    """Divide una línea visual cuando existen columnas claramente separadas.

    pdfplumber puede devolver en una sola línea el proveedor de la izquierda y
    el cliente de la derecha. Esta función conserva las líneas contables
    originales para importes, pero crea fragmentos por columna para las partes.
    """
    output: list[Line] = []
    for line in lines:
        if len(line.words) <= 1:
            output.append(line)
            continue
        groups: list[list[dict[str, Any]]] = [[line.words[0]]]
        for word in line.words[1:]:
            previous = groups[-1][-1]
            gap = float(word["x0"]) - float(previous["x1"])
            if gap >= gap_threshold:
                groups.append([word])
            else:
                groups[-1].append(word)
        for group in groups:
            output.append(Line(
                page=line.page,
                top=min(float(w["top"]) for w in group),
                bottom=max(float(w["bottom"]) for w in group),
                x0=min(float(w["x0"]) for w in group),
                x1=max(float(w["x1"]) for w in group),
                text=clean_spaces(" ".join(str(w["text"]) for w in group)),
                words=group,
            ))
    return sorted(output, key=lambda item: (item.page, item.top, item.x0))


def extract_native_pdf(file_bytes: bytes) -> tuple[str, list[dict[str, Any]], list[Line], list[float]]:
    words: list[dict[str, Any]] = []
    texts: list[str] = []
    widths: list[float] = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page_index, page in enumerate(pdf.pages):
            widths.append(float(page.width))
            page_text = page.extract_text(x_tolerance=2, y_tolerance=3) or ""
            texts.append(page_text)
            for word in page.extract_words(use_text_flow=False, keep_blank_chars=False):
                words.append({**word, "page": page_index})
    lines = build_lines(words)
    text = "\n".join(texts).strip() or lines_to_text(lines)
    return text, words, lines, widths


def extract_ocr_pdf(file_bytes: bytes, dpi: int = 260) -> tuple[str, list[dict[str, Any]], list[Line], list[float]]:
    try:
        import fitz
        import pytesseract
        from PIL import Image
        from pytesseract import Output
    except ImportError as exc:
        raise RuntimeError("Faltan dependencias OCR (PyMuPDF, Pillow o pytesseract).") from exc

    doc = fitz.open(stream=file_bytes, filetype="pdf")
    words: list[dict[str, Any]] = []
    page_texts: list[str] = []
    widths: list[float] = []
    for page_index, page in enumerate(doc):
        pix = page.get_pixmap(dpi=dpi, alpha=False)
        image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        widths.append(float(page.rect.width))
        data = pytesseract.image_to_data(image, lang="spa+eng", output_type=Output.DICT, config="--psm 6")
        sx = float(page.rect.width) / float(pix.width)
        sy = float(page.rect.height) / float(pix.height)
        collected: list[str] = []
        for idx, raw_text in enumerate(data.get("text", [])):
            text = clean_spaces(raw_text)
            try:
                confidence = float(data.get("conf", ["-1"])[idx])
            except (TypeError, ValueError):
                confidence = -1
            if not text or confidence < 25:
                continue
            left = float(data["left"][idx])
            top = float(data["top"][idx])
            width = float(data["width"][idx])
            height = float(data["height"][idx])
            words.append({
                "text": text,
                "x0": left * sx,
                "x1": (left + width) * sx,
                "top": top * sy,
                "bottom": (top + height) * sy,
                "page": page_index,
                "confidence": confidence,
            })
            collected.append(text)
        page_texts.append(" ".join(collected))
    lines = build_lines(words, tolerance=4.2)
    text = lines_to_text(lines) or "\n".join(page_texts)
    return text, words, lines, widths


def detect_document_type(text: str) -> str:
    normalized = norm_text(text)
    if "factura simplificada" in normalized:
        return "Factura simplificada"
    if "ticket" in normalized:
        return "Ticket"
    if "nota de cargo" in normalized:
        return "Nota de cargo"
    if "recibo" in normalized and "factura" not in normalized:
        return "Recibo"
    return "Factura"


def extract_invoice_date(lines: list[Line], text: str) -> str:
    # Las fechas rotuladas como vencimiento se descartan expresamente.
    for line in lines:
        normalized = norm_text(line.text)
        if "fecha" in normalized and "vencimiento" not in normalized and "caduc" not in normalized:
            token = DATE_TOKEN_RE.search(line.text)
            if token:
                parsed = parse_spanish_date(token.group(0))
                if parsed:
                    return parsed
    for raw_line in text.splitlines():
        normalized = norm_text(raw_line)
        if "fecha" in normalized and "vencimiento" not in normalized:
            token = DATE_TOKEN_RE.search(raw_line)
            if token:
                parsed = parse_spanish_date(token.group(0))
                if parsed:
                    return parsed
    for token in DATE_TOKEN_RE.finditer(text):
        parsed = parse_spanish_date(token.group(0))
        if parsed:
            return parsed
    return ""


def extract_invoice_number(lines: list[Line], text: str) -> str:
    patterns = [
        re.compile(r"(?:n[º°o]?\s*(?:de\s*)?factura|numero\s*(?:de\s*)?factura|factura\s*n[º°o]?)\s*[:#.-]*\s*([A-Z0-9][A-Z0-9./_-]{2,})", re.IGNORECASE),
        re.compile(r"(?:invoice\s*(?:number|no\.?|#))\s*[:#.-]*\s*([A-Z0-9][A-Z0-9./_-]{2,})", re.IGNORECASE),
    ]
    for line in lines:
        for pattern in patterns:
            match = pattern.search(line.text)
            if match:
                candidate = match.group(1).strip(" .:-")
                if not DATE_TOKEN_RE.fullmatch(candidate):
                    return candidate
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            return match.group(1).strip(" .:-")
    # Fallback conservador: serie con ano y secuencia.
    fallback = re.search(r"\b[A-Z]{1,5}[-/]?\d{2,4}[-/]\d{2,8}\b", text, re.IGNORECASE)
    return fallback.group(0) if fallback else ""


def _candidate_id_words(words: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen: set[tuple[int, str, int, int]] = set()
    for word in words:
        cleaned = normalize_tax_id(word.get("text", ""))
        if SPANISH_ID_RE.fullmatch(cleaned):
            key = (int(word.get("page", 0)), cleaned, round(float(word.get("x0", 0))), round(float(word.get("top", 0))))
            if key not in seen:
                seen.add(key)
                candidates.append({**word, "tax_id": cleaned})
    # OCR puede separar una letra y los digitos. Se reconstruyen IDs desde lineas.
    for line in build_lines(words):
        for match in SPANISH_ID_RE.finditer(line.text):
            cleaned = normalize_tax_id(match.group(0))
            if not cleaned:
                continue
            matching_words = [w for w in line.words if normalize_tax_id(w.get("text", "")) and normalize_tax_id(w.get("text", "")) in cleaned]
            if matching_words:
                x0 = min(float(w["x0"]) for w in matching_words)
                x1 = max(float(w["x1"]) for w in matching_words)
            else:
                x0, x1 = line.x0, line.x1
            key = (line.page, cleaned, round(x0), round(line.top))
            if key not in seen:
                seen.add(key)
                candidates.append({
                    "text": match.group(0), "tax_id": cleaned, "page": line.page,
                    "x0": x0, "x1": x1, "top": line.top, "bottom": line.bottom,
                })
    return candidates


def _line_in_region(line: Line, left: float, right: float) -> bool:
    overlap = max(0.0, min(line.x1, right) - max(line.x0, left))
    width = max(1.0, line.x1 - line.x0)
    return overlap / width >= 0.55 or left <= line.center_x <= right


def _looks_like_name(line: str) -> bool:
    text = clean_spaces(line)
    normalized = norm_text(text)
    if not text or len(text) < 3 or len(text) > 100:
        return False
    if any(word in normalized for word in SECTION_WORDS + SELLER_WORDS + BUYER_WORDS):
        return False
    if DATE_TOKEN_RE.search(text) or MONEY_RE.search(text) or PERCENT_RE.search(text):
        return False
    if SPANISH_ID_RE.search(text):
        return False
    if re.search(r"\b(?:iban|swift|bic|factura|fecha|telefono|tel\.|email|www\.)\b", normalized):
        return False
    if any(normalized.startswith(word) for word in ADDRESS_WORDS):
        return False
    letters = sum(ch.isalpha() for ch in text)
    return letters >= max(3, len(text) // 3)


def _looks_like_address(line: str) -> bool:
    normalized = norm_text(line)
    return bool(
        any(word in normalized for word in ADDRESS_WORDS)
        or re.search(r"\b\d{5}\b", line)
        or re.search(r"\b(?:madrid|barcelona|valencia|sevilla|bilbao|zaragoza|malaga|málaga|spain|espana|españa)\b", normalized)
    )


def detect_party_candidates(
    words: list[dict[str, Any]],
    lines: list[Line],
    page_widths: list[float],
    own_nif: str = "",
    own_name: str = "",
    mode: str = "recibidas",
) -> list[PartyCandidate]:
    ids = _candidate_id_words(words)
    party_lines = split_lines_by_columns(lines)
    own_nif_n = normalize_tax_id(own_nif)
    own_name_n = norm_text(own_name)
    parties: list[PartyCandidate] = []

    for item in ids:
        page = int(item.get("page", 0))
        x = (float(item.get("x0", 0)) + float(item.get("x1", 0))) / 2
        top = float(item.get("top", 0))
        width = page_widths[page] if page < len(page_widths) else 595.0
        same_band = [other for other in ids if int(other.get("page", 0)) == page and abs(float(other.get("top", 0)) - top) <= 45 and other is not item]
        left_neighbors = [other for other in same_band if (float(other.get("x0", 0)) + float(other.get("x1", 0))) / 2 < x]
        right_neighbors = [other for other in same_band if (float(other.get("x0", 0)) + float(other.get("x1", 0))) / 2 > x]
        left = 0.0
        right = width
        if left_neighbors:
            nearest = max((float(o.get("x0", 0)) + float(o.get("x1", 0))) / 2 for o in left_neighbors)
            left = (nearest + x) / 2
        elif same_band:
            left = max(0.0, x - width * 0.32)
        if right_neighbors:
            nearest = min((float(o.get("x0", 0)) + float(o.get("x1", 0))) / 2 for o in right_neighbors)
            right = (nearest + x) / 2
        elif same_band:
            right = min(width, x + width * 0.32)

        nearby = [
            line for line in party_lines
            if line.page == page and top - 90 <= line.top <= top + 90 and _line_in_region(line, left, right)
        ]
        above = sorted([line for line in nearby if line.bottom <= top + 2 and line.top >= top - 52], key=lambda line: line.top, reverse=True)
        below = sorted([line for line in nearby if line.top >= top - 1 and line.top <= top + 62], key=lambda line: line.top)

        name = ""
        for line in above:
            if _looks_like_name(line.text):
                name = line.text
                break
        if not name:
            for line in nearby:
                normalized = norm_text(line.text)
                if any(label in normalized for label in SELLER_WORDS + BUYER_WORDS):
                    # Capturar texto posterior a la etiqueta.
                    parts = re.split(r"[:\-]", line.text, maxsplit=1)
                    if len(parts) == 2 and _looks_like_name(parts[1]):
                        name = clean_spaces(parts[1])
                        break

        address_parts: list[str] = []
        postal_code = ""
        country = "España"
        for line in below:
            if line.top <= top + 3 or SPANISH_ID_RE.search(line.text):
                continue
            normalized = norm_text(line.text)
            if any(section in normalized for section in SECTION_WORDS):
                break
            if _looks_like_address(line.text):
                address_parts.append(line.text)
                cp_match = re.search(r"\b(\d{5})\b", line.text)
                if cp_match:
                    postal_code = cp_match.group(1)
                if re.search(r"\b(?:france|francia|germany|alemania|portugal|italy|italia|ireland|irlanda|united kingdom|uk)\b", normalized):
                    country = line.text
        address = clean_spaces(", ".join(dict.fromkeys(address_parts)))

        context = norm_text(" ".join(line.text for line in nearby))
        score = 50.0
        reasons: list[str] = []
        tax_id = normalize_tax_id(item.get("tax_id", item.get("text", "")))

        is_own = bool(own_nif_n and tax_id == own_nif_n)
        name_similarity = fuzz.token_set_ratio(own_name_n, norm_text(name)) if own_name_n and name else 0
        if is_own:
            score -= 120
            reasons.append("coincide con tu NIF/CIF")
        if name_similarity >= 85:
            score -= 90
            reasons.append("coincide con tu nombre")

        seller_hits = sum(1 for keyword in SELLER_WORDS if keyword in context)
        buyer_hits = sum(1 for keyword in BUYER_WORDS if keyword in context)
        if mode.lower().startswith("recib"):
            score += seller_hits * 24
            score -= buyer_hits * 24
        else:
            score -= seller_hits * 24
            score += buyer_hits * 24
        if seller_hits:
            reasons.append("bloque de emisor/proveedor")
        if buyer_hits:
            reasons.append("bloque de cliente/receptor")
        if LEGAL_SUFFIX_RE.search(name):
            score += 12
            reasons.append("razón social")
        if name:
            score += 8
        if address:
            score += 5
        if postal_code:
            score += 3
        if x < width * 0.52:
            score += 7 if mode.lower().startswith("recib") else 1
            reasons.append("bloque izquierdo")
        if top < 350:
            score += 4
        parties.append(PartyCandidate(
            name=clean_spaces(name), tax_id=tax_id, address=address,
            postal_code=postal_code, country=country, page=page, x=x, top=top,
            score=score, reasons=", ".join(dict.fromkeys(reasons)),
        ))

    # Eliminar duplicados del mismo NIF conservando el bloque mejor puntuado.
    best_by_id: dict[str, PartyCandidate] = {}
    for party in parties:
        current = best_by_id.get(party.tax_id)
        if current is None or party.score > current.score:
            best_by_id[party.tax_id] = party
    return sorted(best_by_id.values(), key=lambda party: party.score, reverse=True)


def fallback_party(text: str, own_nif: str = "", own_name: str = "") -> PartyCandidate | None:
    own_nif_n = normalize_tax_id(own_nif)
    lines = [clean_spaces(line) for line in text.splitlines() if clean_spaces(line)]
    for index, line in enumerate(lines):
        for match in SPANISH_ID_RE.finditer(line):
            tax_id = normalize_tax_id(match.group(0))
            if own_nif_n and tax_id == own_nif_n:
                continue
            name = ""
            for previous in reversed(lines[max(0, index - 3):index]):
                if _looks_like_name(previous) and fuzz.token_set_ratio(norm_text(previous), norm_text(own_name)) < 85:
                    name = previous
                    break
            address_parts = [candidate for candidate in lines[index + 1:index + 4] if _looks_like_address(candidate)]
            address = clean_spaces(", ".join(address_parts))
            cp = ""
            cp_match = re.search(r"\b(\d{5})\b", address)
            if cp_match:
                cp = cp_match.group(1)
            return PartyCandidate(name=name, tax_id=tax_id, address=address, postal_code=cp, country="España", page=0, x=0, top=0, score=45)
    return None


def _find_labeled_amount(lines: list[Line], include: tuple[str, ...], exclude: tuple[str, ...] = ()) -> tuple[Optional[Decimal], bool]:
    candidates: list[tuple[int, Decimal]] = []
    for line in lines:
        normalized = norm_text(line.text)
        if not any(label in normalized for label in include):
            continue
        if any(label in normalized for label in exclude):
            continue
        amounts = money_tokens(line.text)
        if amounts:
            priority = 10
            if normalized.startswith(include[0]):
                priority += 3
            candidates.append((priority, amounts[-1]))
    if not candidates:
        return None, False
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1], True


def _snap_rate(rate: Decimal, common: list[Decimal], tolerance: Decimal = Decimal("0.45")) -> Decimal:
    nearest = min(common, key=lambda candidate: abs(candidate - rate))
    return nearest if abs(nearest - rate) <= tolerance else q2(rate)


def extract_amounts(lines: list[Line]) -> dict[str, Any]:
    base, base_labeled = _find_labeled_amount(lines, ("base imponible", "base sujeta", "subtotal"), ("total base",))
    total, total_labeled = _find_labeled_amount(lines, ("total a pagar", "importe total", "total factura", "total"), ("subtotal", "total base", "total iva"))
    retention, retention_labeled = _find_labeled_amount(lines, ("retencion", "retención", "irpf"), ("tipo", "%"))

    vat_details: list[dict[str, Any]] = []
    vat_quotas: list[Decimal] = []
    vat_rates: list[Decimal] = []
    iva_labeled = False
    for line in lines:
        normalized = norm_text(line.text)
        if not re.search(r"\b(?:i\.?v\.?a\.?|vat|impuesto)\b", normalized):
            continue
        if "incluido" in normalized and not money_tokens(line.text):
            continue
        rates = percent_tokens(line.text)
        amounts = money_tokens(line.text)
        if not rates and not amounts:
            continue
        rate = rates[0] if rates else None
        quota = amounts[-1] if amounts else None
        detail_base = amounts[-2] if len(amounts) >= 2 else None
        if quota is not None:
            vat_quotas.append(quota)
            iva_labeled = True
        if rate is not None:
            vat_rates.append(rate)
        vat_details.append({
            "tipo_iva": f"{rate.normalize()}%" if rate is not None else "",
            "base": decimal_to_float(detail_base),
            "cuota": decimal_to_float(quota),
            "texto": line.text,
        })

    # Evitar duplicados exactos, comunes cuando texto nativo y tablas repiten una linea.
    unique_details: list[dict[str, Any]] = []
    seen_details = set()
    for detail in vat_details:
        key = (detail["tipo_iva"], detail["base"], detail["cuota"], norm_text(detail["texto"]))
        if key not in seen_details:
            seen_details.add(key)
            unique_details.append(detail)
    vat_details = unique_details

    iva = None
    if vat_quotas:
        # En una factura resumen suele existir una sola linea IVA. Si hay varias, se suman cuotas distintas.
        distinct_quotas: list[Decimal] = []
        for quota in vat_quotas:
            if quota not in distinct_quotas:
                distinct_quotas.append(quota)
        iva = q2(sum(distinct_quotas, Decimal("0")))

    # Si el total no fue encontrado por etiqueta, no se usa el mayor numero del documento:
    # eso evita confundir IBAN, telefonos o importes de lineas con el total.
    if base is not None and iva is None and total is not None:
        candidate = q2(total - base + (retention or Decimal("0")))
        if candidate >= 0:
            iva = candidate
    if base is None and total is not None and iva is not None:
        candidate = q2(total - iva + (retention or Decimal("0")))
        if candidate >= 0:
            base = candidate

    # Derivar o validar tipos fiscales.
    if not vat_rates and base not in (None, Decimal("0")) and iva is not None:
        derived = q2(iva * Decimal("100") / base)
        vat_rates = [_snap_rate(derived, COMMON_VAT_RATES)]
    rate_strings = []
    for rate in vat_rates:
        snapped = _snap_rate(rate, COMMON_VAT_RATES)
        label = f"{snapped.normalize()}%"
        if label not in rate_strings:
            rate_strings.append(label)

    ret_rates: list[Decimal] = []
    for line in lines:
        normalized = norm_text(line.text)
        if "retencion" in normalized or "irpf" in normalized:
            ret_rates.extend(percent_tokens(line.text))
    if not ret_rates and base not in (None, Decimal("0")) and retention is not None:
        ret_rates = [_snap_rate(q2(retention * Decimal("100") / base), COMMON_RET_RATES)]
    ret_strings = []
    for rate in ret_rates:
        label = f"{_snap_rate(rate, COMMON_RET_RATES).normalize()}%"
        if label not in ret_strings:
            ret_strings.append(label)

    validation = ""
    equation_ok = False
    if base is not None and total is not None:
        calculated = q2(base + (iva or Decimal("0")) - (retention or Decimal("0")))
        difference = abs(calculated - total)
        equation_ok = difference <= Decimal("0.05")
        validation = "OK" if equation_ok else f"Revisar (diferencia {difference} EUR)"

    confidence = 0
    confidence += 24 if base_labeled and base is not None else 8 if base is not None else 0
    confidence += 24 if total_labeled and total is not None else 5 if total is not None else 0
    confidence += 18 if iva_labeled and iva is not None else 8 if iva is not None else 0
    confidence += 8 if rate_strings else 0
    confidence += 22 if equation_ok else 0
    confidence += 4 if retention_labeled else 0
    confidence = min(100, confidence)

    # Completar la base del unico detalle IVA cuando esta aparece en otra linea.
    if len(vat_details) == 1 and vat_details[0]["base"] is None and base is not None:
        vat_details[0]["base"] = float(base)

    return {
        "base": base,
        "iva": iva,
        "tipo_iva": "; ".join(rate_strings),
        "retencion": retention,
        "tipo_retencion": "; ".join(ret_strings),
        "total": total,
        "validacion": validation,
        "confianza": confidence,
        "detalle_iva": vat_details,
    }


def guess_expense_type(text: str) -> str:
    normalized = norm_text(text)
    for category, keywords in CONCEPTO_KW.items():
        if any(norm_text(keyword) in normalized for keyword in keywords):
            return category
    return "Otros gastos"


def extract_concept_text(lines: list[Line]) -> str:
    for index, line in enumerate(lines):
        normalized = norm_text(line.text)
        if normalized in {"concepto", "descripcion", "descripción", "detalle"} or normalized.startswith("concepto:") or normalized.startswith("concepto "):
            same_or_next = line.text.split(":", 1)[1].strip() if ":" in line.text else ""
            if same_or_next and not re.search(r"\b(?:ud|cantidad|base|precio)\b", norm_text(same_or_next)):
                return same_or_next[:180]
            for next_line in lines[index + 1:index + 5]:
                next_norm = norm_text(next_line.text)
                if next_norm and not any(section in next_norm for section in ("base imponible", "total", "iva")):
                    return next_line.text[:180]
    return ""


def _provider_confidence(score: float, candidate_count: int) -> int:
    if score < 0:
        return 0
    confidence = 45 + int(min(45, max(0, score - 50)))
    if candidate_count == 1:
        confidence += 5
    return min(100, confidence)


def parse_pdf_invoice(
    file_bytes: bytes,
    filename: str,
    mode: str = "recibidas",
    own_nif: str = "",
    own_name: str = "",
    ocr_mode: str = "auto",
) -> InvoiceResult:
    result = InvoiceResult(archivo=filename)
    try:
        native_text, native_words, native_lines, widths = extract_native_pdf(file_bytes)
    except Exception as exc:
        native_text, native_words, native_lines, widths = "", [], [], []
        native_error = str(exc)
    else:
        native_error = ""

    def parse_source(text: str, words: list[dict[str, Any]], lines: list[Line], page_widths: list[float], source: str) -> InvoiceResult:
        parsed = InvoiceResult(archivo=filename, fuente_lectura=source)
        parsed.tipo_documento = detect_document_type(text)
        parsed.fecha_factura = extract_invoice_date(lines, text)
        parsed.numero_factura = extract_invoice_number(lines, text)
        parties = detect_party_candidates(words, lines, page_widths, own_nif=own_nif, own_name=own_name, mode=mode)
        chosen = parties[0] if parties else fallback_party(text, own_nif=own_nif, own_name=own_name)
        if chosen:
            parsed.proveedor = chosen.name
            parsed.nif = chosen.tax_id
            parsed.direccion = chosen.address
            parsed.codigo_postal = chosen.postal_code
            parsed.pais = chosen.country or "España"
            parsed.confianza_proveedor = _provider_confidence(chosen.score, len(parties))
        parsed.candidatos_partes = [asdict(party) for party in parties]
        amounts = extract_amounts(lines)
        parsed.base_imponible = decimal_to_float(amounts["base"])
        parsed.tipo_iva = amounts["tipo_iva"]
        parsed.iva = decimal_to_float(amounts["iva"])
        parsed.tipo_retencion = amounts["tipo_retencion"]
        parsed.retencion = decimal_to_float(amounts["retencion"])
        parsed.total = decimal_to_float(amounts["total"])
        parsed.validacion = amounts["validacion"]
        parsed.confianza_importes = amounts["confianza"]
        parsed.detalle_iva = amounts["detalle_iva"]
        concept_text = extract_concept_text(lines)
        parsed.concepto = concept_text
        parsed.tipo_gasto = guess_expense_type(f"{parsed.proveedor}\n{concept_text}\n{text}")
        parsed.modelo_303 = "Sí" if parsed.iva not in (None, 0) else ""
        parsed.texto_detectado = text[:15000]
        return parsed

    native = parse_source(native_text, native_words, native_lines, widths, "PDF") if native_text or native_lines else InvoiceResult(archivo=filename)
    should_ocr = ocr_mode == "siempre" or (
        ocr_mode == "auto" and (
            len(native_text.strip()) < 80
            or len(native_words) < 15
            or native.confianza_importes < 55
            or native.total is None
            or not native.nif
        )
    )

    if should_ocr:
        try:
            ocr_text, ocr_words, ocr_lines, ocr_widths = extract_ocr_pdf(file_bytes)
            ocr = parse_source(ocr_text, ocr_words, ocr_lines, ocr_widths, "OCR")
            native_quality = native.confianza_importes + native.confianza_proveedor + (10 if native.numero_factura else 0) + (10 if native.fecha_factura else 0)
            ocr_quality = ocr.confianza_importes + ocr.confianza_proveedor + (10 if ocr.numero_factura else 0) + (10 if ocr.fecha_factura else 0)
            result = ocr if ocr_quality > native_quality + 5 else native
            # Combinar campos ausentes sin mezclar bloques de partes.
            other = native if result is ocr else ocr
            for field in ("fecha_factura", "numero_factura", "concepto", "tipo_gasto"):
                if not getattr(result, field) and getattr(other, field):
                    setattr(result, field, getattr(other, field))
            for field in ("base_imponible", "iva", "retencion", "total"):
                if getattr(result, field) is None and getattr(other, field) is not None:
                    setattr(result, field, getattr(other, field))
            if not result.tipo_iva:
                result.tipo_iva = other.tipo_iva
            if not result.tipo_retencion:
                result.tipo_retencion = other.tipo_retencion
        except Exception as exc:
            result = native
            if not result.error:
                result.error = f"OCR no disponible: {exc}"
    else:
        result = native

    if not result.texto_detectado and native_text:
        result.texto_detectado = native_text[:15000]
    if not result.proveedor or not result.nif:
        warning = "No se pudo identificar con suficiente seguridad el proveedor y su NIF/CIF."
        result.error = f"{result.error} {warning}".strip()
    if result.total is None:
        warning = "No se pudo localizar el total de la factura."
        result.error = f"{result.error} {warning}".strip()
    if native_error and not result.error:
        result.error = native_error
    return result


def xml_find(root: ET.Element, *paths: str) -> str:
    for namespace in FACTURAE_NS:
        prefix = "{" + namespace + "}" if namespace else ""
        for path in paths:
            namespaced = "/".join(prefix + part for part in path.split("/"))
            element = root.find(".//" + namespaced)
            if element is not None and element.text:
                return clean_spaces(element.text)
    return ""


def parse_xml_invoice(file_bytes: bytes, filename: str) -> InvoiceResult:
    result = InvoiceResult(archivo=filename, fuente_lectura="Facturae XML")
    try:
        root = ET.fromstring(file_bytes)
    except ET.ParseError as exc:
        result.error = f"XML inválido: {exc}"
        return result
    result.fecha_factura = parse_spanish_date(xml_find(root, "IssueDate"))
    series = xml_find(root, "InvoiceSeriesCode")
    number = xml_find(root, "InvoiceNumber")
    result.numero_factura = f"{series}-{number}" if series and number else number or series
    result.proveedor = xml_find(root, "SellerParty/LegalEntity/CorporateName", "SellerParty/Individual/Name")
    result.nif = normalize_tax_id(xml_find(root, "SellerParty/TaxIdentification/TaxIdentificationNumber"))
    address = xml_find(root, "SellerParty/LegalEntity/AddressInSpain/Address")
    postcode = xml_find(root, "SellerParty/LegalEntity/AddressInSpain/PostCode")
    town = xml_find(root, "SellerParty/LegalEntity/AddressInSpain/Town")
    result.direccion = clean_spaces(", ".join(part for part in (address, postcode, town) if part))
    result.codigo_postal = postcode
    result.base_imponible = decimal_to_float(parse_decimal(xml_find(root, "InvoiceTotals/TotalTaxableBase", "TaxableBaseAmount")))
    rate = parse_decimal(xml_find(root, "Tax/TaxRate"))
    result.tipo_iva = f"{rate.normalize()}%" if rate is not None else ""
    result.iva = decimal_to_float(parse_decimal(xml_find(root, "Tax/TaxAmount/TotalAmount", "TaxAmount")))
    ret_rate = parse_decimal(xml_find(root, "WithholdingTax/WithholdingTaxRate"))
    result.tipo_retencion = f"{ret_rate.normalize()}%" if ret_rate is not None else ""
    result.retencion = decimal_to_float(parse_decimal(xml_find(root, "WithholdingTax/WithholdingTaxAmount/TotalAmount")))
    result.total = decimal_to_float(parse_decimal(xml_find(root, "InvoiceTotals/TotalInvoiceAmount", "InvoiceTotals/TotalGrossAmount")))
    result.concepto = xml_find(root, "Items/InvoiceLine/ItemDescription")
    result.tipo_gasto = guess_expense_type(f"{result.proveedor} {result.concepto}")
    result.modelo_303 = "Sí" if result.iva not in (None, 0) else ""
    if result.base_imponible is not None and result.total is not None:
        calculated = Decimal(str(result.base_imponible)) + Decimal(str(result.iva or 0)) - Decimal(str(result.retencion or 0))
        result.validacion = "OK" if abs(calculated - Decimal(str(result.total))) <= Decimal("0.05") else "Revisar"
    result.confianza_proveedor = 98 if result.proveedor and result.nif else 70
    result.confianza_importes = 98 if result.total is not None and result.base_imponible is not None else 70
    return result


def extract_invoice(
    file_bytes: bytes,
    filename: str,
    mode: str = "recibidas",
    own_nif: str = "",
    own_name: str = "",
    ocr_mode: str = "auto",
) -> dict[str, Any]:
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if extension == "xml":
        return parse_xml_invoice(file_bytes, filename).to_dict()
    if extension == "pdf":
        return parse_pdf_invoice(
            file_bytes=file_bytes,
            filename=filename,
            mode=mode,
            own_nif=own_nif,
            own_name=own_name,
            ocr_mode=ocr_mode,
        ).to_dict()
    result = InvoiceResult(archivo=filename, error="Formato no soportado. Usa PDF o XML Facturae.")
    return result.to_dict()
