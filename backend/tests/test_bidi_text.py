"""Arabic de-shaping and direction detection."""
import unicodedata

from app.services.bidi_text import contains_presentation_forms, deshape_visual_arabic, detect_direction, deshape_word


def test_english_unchanged():
    s = "Payment terms shall apply within 30 days."
    assert deshape_visual_arabic(s) == s
    assert detect_direction(s) == "ltr"


def test_arabic_logical_unchanged_without_presentation():
    s = "العقد"
    assert deshape_visual_arabic(s, had_presentation=False) == s
    assert detect_direction(s) == "rtl"


def test_visual_word_deshape():
    # pdfplumber-style visual token (reversed logical letters, no presentation forms after NFKC)
    visual = "لمعلا"
    logical = "العمل"
    assert deshape_visual_arabic(visual, had_presentation=True) == logical


def test_mixed_line_direction():
    s = "Article 5 — البند الخامس"
    assert detect_direction(s) == "mixed"


def test_presentation_form_word():
    pres = "\uFE91\uFEDF\uFEE4"
    out = deshape_word(pres)
    assert len(out) >= 1
    assert not contains_presentation_forms(out)
