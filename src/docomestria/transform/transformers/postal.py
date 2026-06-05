"""Spanish postal codes and provinces."""

from __future__ import annotations

import re
from typing import Any

from ..models import TransformContext

_CP_RE = re.compile(r"^\d{5}$")

# Map of postal-code prefix → province name (subset for v0.3.0).
_PROV_BY_PREFIX: dict[str, str] = {
    "01": "Álava",
    "02": "Albacete",
    "03": "Alicante",
    "04": "Almería",
    "05": "Ávila",
    "06": "Badajoz",
    "07": "Illes Balears",
    "08": "Barcelona",
    "09": "Burgos",
    "10": "Cáceres",
    "11": "Cádiz",
    "12": "Castellón",
    "13": "Ciudad Real",
    "14": "Córdoba",
    "15": "A Coruña",
    "16": "Cuenca",
    "17": "Girona",
    "18": "Granada",
    "19": "Guadalajara",
    "20": "Gipuzkoa",
    "21": "Huelva",
    "22": "Huesca",
    "23": "Jaén",
    "24": "León",
    "25": "Lleida",
    "26": "La Rioja",
    "27": "Lugo",
    "28": "Madrid",
    "29": "Málaga",
    "30": "Murcia",
    "31": "Navarra",
    "32": "Ourense",
    "33": "Asturias",
    "34": "Palencia",
    "35": "Las Palmas",
    "36": "Pontevedra",
    "37": "Salamanca",
    "38": "Santa Cruz de Tenerife",
    "39": "Cantabria",
    "40": "Segovia",
    "41": "Sevilla",
    "42": "Soria",
    "43": "Tarragona",
    "44": "Teruel",
    "45": "Toledo",
    "46": "Valencia",
    "47": "Valladolid",
    "48": "Bizkaia",
    "49": "Zamora",
    "50": "Zaragoza",
    "51": "Ceuta",
    "52": "Melilla",
}

_PROVINCES = set(_PROV_BY_PREFIX.values())


def postal_code_es(
    raw: str, *, context: TransformContext | None = None
) -> tuple[Any, float, tuple[str, ...]]:
    """Validate a 5-digit Spanish postal code."""
    text = (raw or "").strip()
    if not text:
        return None, 0.0, ("empty",)
    if not _CP_RE.match(text):
        return None, 0.0, ("postal_code_invalid",)
    prefix = text[:2]
    if prefix not in _PROV_BY_PREFIX:
        return text, 0.5, ("postal_code_prefix_unknown",)
    return text, 1.0, ()


postal_code_es.name = "postal_code_es"  # type: ignore[attr-defined]


def province_es(
    raw: str, *, context: TransformContext | None = None
) -> tuple[Any, float, tuple[str, ...]]:
    """Validate / normalise a Spanish province name (best-effort)."""
    text = (raw or "").strip()
    if not text:
        return None, 0.0, ("empty",)
    norm = text.title()
    if norm in _PROVINCES:
        return norm, 1.0, ()
    for p in _PROVINCES:
        if p.lower() == text.lower():
            return p, 1.0, ()
    return text, 0.5, ("province_unknown",)


province_es.name = "province_es"  # type: ignore[attr-defined]
