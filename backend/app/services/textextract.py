"""Stage 1 — text extraction.

PDF: pdfplumber first; if text is empty OR Arabic comes out as presentation-form
glyphs (reversed/garbled shaping), fall back to PyMuPDF (fitz).
DOCX: python-docx (paragraphs + tables), split into pseudo-pages (~2500 chars)
so page markers / source viewer still work.
Files with no text layer are rejected with code 'scanned_pdf_not_supported'.
"""
import io
import re


class TextExtractError(Exception):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


# U+FB50–U+FDFF / U+FE70–U+FEFF: Arabic presentation forms — a sign the PDF
# extractor returned shaped glyphs (usually also reversed) instead of logical text.
_PRESENTATION = re.compile(r"[ﭐ-﷿ﹰ-﻿]")


def _looks_garbled(text: str) -> bool:
    return len(_PRESENTATION.findall(text)) > 20


def _pdf_pdfplumber(data: bytes) -> list[dict]:
    import pdfplumber

    pages = []
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            pages.append({"page": i, "text": page.extract_text() or ""})
    return pages


def _pdf_fitz(data: bytes) -> list[dict]:
    import fitz  # PyMuPDF

    pages = []
    with fitz.open(stream=data, filetype="pdf") as doc:
        for i, page in enumerate(doc, start=1):
            pages.append({"page": i, "text": page.get_text() or ""})
    return pages


def _docx(data: bytes) -> list[dict]:
    from docx import Document

    doc = Document(io.BytesIO(data))
    blocks: list[str] = []
    for para in doc.paragraphs:
        if para.text.strip():
            blocks.append(para.text)
    for table in doc.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells if c.text.strip()]
            if cells:
                blocks.append(" | ".join(cells))

    # DOCX has no real pages — build pseudo-pages of ~2500 chars at paragraph boundaries.
    pages, current, size = [], [], 0
    for b in blocks:
        current.append(b)
        size += len(b) + 1
        if size >= 2500:
            pages.append({"page": len(pages) + 1, "text": "\n".join(current)})
            current, size = [], 0
    if current:
        pages.append({"page": len(pages) + 1, "text": "\n".join(current)})
    return pages


def extract_pages(data: bytes, filename: str) -> list[dict]:
    """Return [{page:int, text:str}]. Raises TextExtractError with codes:
    'scanned_pdf_not_supported' | 'unsupported_type' | 'corrupted'."""
    name = filename.lower()
    try:
        if name.endswith(".pdf"):
            pages = _pdf_pdfplumber(data)
            joined = "".join(p["text"] for p in pages)
            if not joined.strip() or _looks_garbled(joined):
                pages = _pdf_fitz(data)
                joined = "".join(p["text"] for p in pages)
            if not joined.strip():
                raise TextExtractError("scanned_pdf_not_supported")
            return pages
        if name.endswith(".docx"):
            pages = _docx(data)
            if not any(p["text"].strip() for p in pages):
                raise TextExtractError("scanned_pdf_not_supported")
            return pages
    except TextExtractError:
        raise
    except Exception:
        raise TextExtractError("corrupted")
    raise TextExtractError("unsupported_type")


def build_raw_text(pages: list[dict]) -> tuple[str, dict[int, int]]:
    """Concatenate pages with [[PAGE n]] markers.

    Returns (raw_text, page_char_starts) where page_char_starts[n] is the
    char offset in raw_text where page n's marker begins — used to map global
    quote offsets back to a page for the source viewer.
    """
    parts: list[str] = []
    starts: dict[int, int] = {}
    offset = 0
    for p in pages:
        marker = f"\n[[PAGE {p['page']}]]\n"
        starts[p["page"]] = offset
        parts.append(marker + p["text"])
        offset += len(marker) + len(p["text"])
    return "".join(parts), starts
