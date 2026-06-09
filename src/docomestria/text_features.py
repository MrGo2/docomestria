"""Text feature helpers shared by atoms extraction and the training table.

Single source of truth: extract_atoms.py imports from here so the atoms files
and the training table compute identical content flags.
"""
import re

_NUM_TOKEN = re.compile(r"\b\d[\d.,/\-]*\b")
_CURRENCY = re.compile(r"[€$£¥]|euros?")
_DATE = re.compile(r"\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b")
_PERCENT = re.compile(r"\d[\d.,]*\s*%")
_IBAN = re.compile(r"\b[A-Z]{2}\d{2}[\d ]{15,}\b")
_NIF = re.compile(r"\b\d{8}[A-Z]\b|\b[A-Z]\d{8}\b")


def case_class(text: str) -> str:
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return "none"
    up = sum(1 for c in letters if c.isupper())
    lo = sum(1 for c in letters if c.islower())
    if up / len(letters) >= 0.80:
        return "UPPER"
    if lo / len(letters) >= 0.80:
        return "lower"
    words = [w for w in text.split() if any(ch.isalpha() for ch in w)]
    if words:
        starts_upper = sum(
            1 for w in words
            if next((c for c in w if c.isalpha()), "").isupper()
        )
        if starts_upper / len(words) >= 0.70:
            return "Title"
    return "mixed"


def content_flags(text: str) -> dict:
    return {
        "digit_ratio": sum(c.isdigit() for c in text) / max(1, len(text)),
        "has_currency": bool(_CURRENCY.search(text)),
        "has_date": bool(_DATE.search(text)),
        "has_percent": bool(_PERCENT.search(text)),
        "has_iban": bool(_IBAN.search(text)),
        "has_nif": bool(_NIF.search(text)),
        "starts_paren": text.startswith("("),
        "ends_colon": text.rstrip().endswith(":"),
        "n_numeric_tokens": len(_NUM_TOKEN.findall(text)),
        "len_chars": len(text),
    }
