"""Geometry-aware PDF extraction (synthetic PDFs only)."""
import io

import fitz
import pytest

from app.services.textextract import extract_pages_geometry


def _two_column_pdf() -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=400, height=200)
    page.insert_text((320, 50), "Arabic column line", fontsize=10)
    page.insert_text((40, 50), "English column line", fontsize=10)
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


def _arabic_table_pdf() -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=300, height=120)
    page.insert_text((50, 40), "Row1-A", fontsize=9)
    page.insert_text((150, 40), "Row1-B", fontsize=9)
    page.insert_text((50, 70), "Row2-A", fontsize=9)
    page.insert_text((150, 70), "Row2-B", fontsize=9)
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


def test_two_column_page_has_multiple_blocks():
    pages = extract_pages_geometry(_two_column_pdf(), "sample.pdf")
    assert len(pages) == 1
    blocks = pages[0]["blocks"]
    assert len(blocks) >= 2
    texts = [b["text"] for b in blocks]
    assert any("English" in t for t in texts)
    assert any("Arabic" in t for t in texts)


def test_table_not_single_corrupted_line():
    pages = extract_pages_geometry(_arabic_table_pdf(), "table.pdf")
    blocks = pages[0]["blocks"]
    assert len(blocks) >= 2
    joined = " ".join(b["text"] for b in blocks)
    assert "Row1-A" in joined and "Row2-B" in joined


def test_arabic_only_paragraph_direction():
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), "نص عربي للاختبار", fontsize=11)
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    pages = extract_pages_geometry(buf.getvalue(), "ar.pdf")
    assert pages[0]["blocks"]
    assert pages[0]["blocks"][0]["direction"] in ("rtl", "mixed", "ltr")
