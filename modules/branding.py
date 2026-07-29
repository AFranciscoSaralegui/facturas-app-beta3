from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
AUTONOMOS_PATH = DATA_DIR / "autonomos.json"

DEFAULT_PROFILE: dict[str, Any] = {
    "id": "",
    "nombre": "",
    "nif": "",
    "direccion": "",
    "codigo_postal": "",
    "ciudad": "",
    "pais": "España",
    "epigrafe": "",
    "moneda": "EUR",
    "plantilla": "estandar",
    "facturacion_internacional": False,
    "clientes_usa": False,
    "activo": True,
    "notas": "",
}


def slugify(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text or "autonomo"


def normalize_nif(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())


def normalize_profile(raw: dict[str, Any]) -> dict[str, Any]:
    profile = {**DEFAULT_PROFILE, **(raw or {})}
    profile["nombre"] = str(profile.get("nombre", "")).strip()
    profile["nif"] = normalize_nif(profile.get("nif", ""))
    profile["moneda"] = str(profile.get("moneda", "EUR") or "EUR").upper().strip()
    profile["pais"] = str(profile.get("pais", "España") or "España").strip()
    profile["activo"] = bool(profile.get("activo", True))
    profile["facturacion_internacional"] = bool(profile.get("facturacion_internacional", False))
    profile["clientes_usa"] = bool(profile.get("clientes_usa", False))
    profile["id"] = str(profile.get("id", "")).strip() or slugify(
        f"{profile['nombre']}-{profile['nif']}"
    )
    return profile


def load_autonomos() -> list[dict[str, Any]]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not AUTONOMOS_PATH.exists():
        return []
    try:
        payload = json.loads(AUTONOMOS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if isinstance(payload, dict):
        payload = payload.get("autonomos", [])
    if not isinstance(payload, list):
        return []
    result = [normalize_profile(item) for item in payload if isinstance(item, dict)]
    return sorted(result, key=lambda item: item.get("nombre", "").casefold())


def save_autonomos(items: list[dict[str, Any]]) -> bool:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    normalized = [normalize_profile(item) for item in items]
    try:
        AUTONOMOS_PATH.write_text(
            json.dumps(normalized, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return True
    except OSError:
        return False


def dump_autonomos(items: list[dict[str, Any]]) -> bytes:
    normalized = [normalize_profile(item) for item in items]
    return json.dumps(normalized, ensure_ascii=False, indent=2).encode("utf-8")


def merge_autonomos(current: list[dict[str, Any]], incoming: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {item["id"]: normalize_profile(item) for item in current}
    for raw in incoming:
        profile = normalize_profile(raw)
        by_id[profile["id"]] = profile
    return sorted(by_id.values(), key=lambda item: item.get("nombre", "").casefold())


def find_profile(items: list[dict[str, Any]], profile_id: str) -> dict[str, Any] | None:
    for item in items:
        if item.get("id") == profile_id:
            return item
    return None
