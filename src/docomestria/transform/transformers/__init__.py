"""All transformers, re-exported under one namespace.

Usage:
    from docomestria.transform import transformers as tr
    Field(tr.date_es), Field(tr.amount_eur), Field(tr.nif_es), ...
"""

from __future__ import annotations

from .amounts import (
    Money,
    amount_auto,
    amount_currency,
    amount_eu,
    amount_eur,
    amount_us,
    amount_usd,
)
from .bank import bic, iban
from .base import compose, enum, regex
from .contact import email, phone_es, phone_international, url
from .dates import date_es, date_es_long, date_es_short, date_iso, datetime_iso
from .forms import checkbox_binary, checkbox_choice, multi_checkbox
from .identity import cif_es, nie_es, nif_es
from .numeric import decimal, integer, percentage
from .postal import postal_code_es, province_es

__all__ = [
    "Money",
    "amount_auto",
    "amount_currency",
    "amount_eu",
    "amount_eur",
    "amount_us",
    "amount_usd",
    "bic",
    "checkbox_binary",
    "checkbox_choice",
    "cif_es",
    "compose",
    "date_es",
    "date_es_long",
    "date_es_short",
    "date_iso",
    "datetime_iso",
    "decimal",
    "email",
    "enum",
    "iban",
    "integer",
    "multi_checkbox",
    "nie_es",
    "nif_es",
    "percentage",
    "phone_es",
    "phone_international",
    "postal_code_es",
    "province_es",
    "regex",
    "url",
]
