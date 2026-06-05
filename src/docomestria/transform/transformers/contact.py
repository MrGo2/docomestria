"""Contact info: phone, email, url."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from ..models import TransformContext

try:  # pragma: no cover
    import phonenumbers as _phonenumbers  # type: ignore

    _HAS_PHONENUMBERS = True
except ImportError:  # pragma: no cover
    _phonenumbers = None  # type: ignore[assignment]
    _HAS_PHONENUMBERS = False


_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
_ES_PHONE_RE = re.compile(r"^(?:\+34|0034)?[6789]\d{8}$")


def _phone_clean(raw: str) -> str:
    return re.sub(r"[\s\-().]", "", (raw or ""))


def phone_es(
    raw: str, *, context: TransformContext | None = None
) -> tuple[Any, float, tuple[str, ...]]:
    """Validate a Spanish phone number. Returns E.164 string when possible."""
    cleaned = _phone_clean(raw)
    if not cleaned:
        return None, 0.0, ("empty",)
    if _HAS_PHONENUMBERS:
        try:
            parsed = _phonenumbers.parse(cleaned, "ES")  # type: ignore[union-attr]
            if not _phonenumbers.is_valid_number(parsed):  # type: ignore[union-attr]
                return cleaned, 0.5, ("phone_invalid",)
            return (
                _phonenumbers.format_number(  # type: ignore[union-attr]
                    parsed,
                    _phonenumbers.PhoneNumberFormat.E164,  # type: ignore[union-attr]
                ),
                1.0,
                (),
            )
        except Exception:
            return cleaned, 0.0, ("phone_unparseable",)
    if _ES_PHONE_RE.match(cleaned):
        nine = cleaned[-9:]
        return f"+34{nine}", 1.0, ()
    return cleaned, 0.0, ("phone_format_invalid",)


phone_es.name = "phone_es"  # type: ignore[attr-defined]


def phone_international(
    raw: str, *, context: TransformContext | None = None
) -> tuple[Any, float, tuple[str, ...]]:
    """Validate a phone number with an explicit country prefix."""
    cleaned = _phone_clean(raw)
    if not cleaned:
        return None, 0.0, ("empty",)
    if not cleaned.startswith("+"):
        return cleaned, 0.0, ("missing_country_code",)
    if _HAS_PHONENUMBERS:
        try:
            parsed = _phonenumbers.parse(cleaned, None)  # type: ignore[union-attr]
            if not _phonenumbers.is_valid_number(parsed):  # type: ignore[union-attr]
                return cleaned, 0.5, ("phone_invalid",)
            return (
                _phonenumbers.format_number(  # type: ignore[union-attr]
                    parsed,
                    _phonenumbers.PhoneNumberFormat.E164,  # type: ignore[union-attr]
                ),
                1.0,
                (),
            )
        except Exception:
            return cleaned, 0.0, ("phone_unparseable",)
    return cleaned, 0.7, ()


phone_international.name = "phone_international"  # type: ignore[attr-defined]


def email(
    raw: str, *, context: TransformContext | None = None
) -> tuple[Any, float, tuple[str, ...]]:
    """Validate an email address (lowercased)."""
    text = (raw or "").strip().lower()
    if not text:
        return None, 0.0, ("empty",)
    if _EMAIL_RE.match(text):
        return text, 1.0, ()
    return None, 0.0, ("email_format_invalid",)


email.name = "email"  # type: ignore[attr-defined]


def url(raw: str, *, context: TransformContext | None = None) -> tuple[Any, float, tuple[str, ...]]:
    """Validate a URL."""
    text = (raw or "").strip()
    if not text:
        return None, 0.0, ("empty",)
    candidate = text if "://" in text else f"https://{text}"
    try:
        parsed = urlparse(candidate)
    except ValueError:
        return None, 0.0, ("url_format_invalid",)
    if not parsed.scheme or not parsed.netloc:
        return None, 0.0, ("url_format_invalid",)
    return candidate, 1.0, ()


url.name = "url"  # type: ignore[attr-defined]
