"""Arabic visual-order correction for PDF text extraction only.

Never used by the frontend renderer — display uses PDF.js or Unicode bidi.
"""
from __future__ import annotations

import re
import unicodedata

_PRESENTATION = re.compile(r"[\uFB50-\uFDFF\uFE70-\uFEFF]")
_ARABIC = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]")
_LATIN = re.compile(r"[A-Za-z]")
_RTL_STRONG = re.compile(
    r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\u0660-\u0669\u06F0-\u06F9"
    r"\u0640\u061F\u060C\u061B\u064B-\u065F\u0670]*"
)


def contains_presentation_forms(text: str) -> bool:
    return bool(_PRESENTATION.search(text))


def deshape_visual_arabic(text: str, *, had_presentation: bool | None = None) -> str:
    """NFKC decompose presentation forms; reverse contiguous RTL runs if visual source."""
    if not text:
        return text
    if had_presentation is None:
        had_presentation = contains_presentation_forms(text)
    normalized = unicodedata.normalize("NFKC", text)
    if not had_presentation:
        return normalized

    def _reverse_rtl_run(m: re.Match[str]) -> str:
        return m.group(0)[::-1]

    return _RTL_STRONG.sub(_reverse_rtl_run, normalized)


def deshape_word(word: str) -> str:
    """De-shape a single extracted word when it contains presentation forms."""
    if not word:
        return word
    if not contains_presentation_forms(word):
        return unicodedata.normalize("NFKC", word)
    return deshape_visual_arabic(word, had_presentation=True)


def detect_direction(text: str) -> str:
    """Return rtl | ltr | mixed based on strong character counts."""
    if not text or not text.strip():
        return "ltr"
    ar = len(_ARABIC.findall(text))
    lat = len(_LATIN.findall(text))
    if ar == 0 and lat == 0:
        return "ltr"
    if ar > 0 and lat == 0:
        return "rtl"
    if lat > 0 and ar == 0:
        return "ltr"
    total = ar + lat
    if ar / total >= 0.65:
        return "rtl"
    if lat / total >= 0.65:
        return "ltr"
    return "mixed"
