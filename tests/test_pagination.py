import pytest
import shutil
pytestmark = pytest.mark.skipif(shutil.which("soffice") is None, reason="Optional LibreOffice renderer is not installed")

from app.ooxml.docx_loader import DocxPackage
from app.ooxml.structure_extractor import build_document_model
from app.pagination.libreoffice_render import (
    render_docx_to_pdf, extract_page_texts, match_paragraphs_to_pages)

FIXTURE = "tests/fixtures/mini_project_1a_format.docx"


def _matches():
    pkg = DocxPackage.load(FIXTURE)
    doc = build_document_model(pkg, FIXTURE)
    pdf_path = render_docx_to_pdf(FIXTURE)
    page_texts = extract_page_texts(pdf_path)
    return doc, match_paragraphs_to_pages(doc, page_texts)


def test_renders_expected_page_count():
    pdf_path = render_docx_to_pdf(FIXTURE)
    page_texts = extract_page_texts(pdf_path)
    assert len(page_texts) == 11  # verified manually against LibreOffice output


def test_distinctive_multiword_body_text_matches_correctly():
    """Spot-checked against the real rendered PDF: long, distinctive body
    sentences match their true page with high confidence."""
    doc, matches = _matches()
    by_index = {m.paragraph_index: m for m in matches}

    # Paragraph 95 is deep in the ABSTRACT body text, manually confirmed on
    # page 4 of the rendered PDF.
    m = by_index[95]
    assert m.page_number == 4
    assert m.confidence >= 95


def test_monotonic_matching_resolves_repeated_names_correctly():
    """Documented fix: text containing a student's name+roll-number repeats
    on the title page (idx 13, page 1) and again in the declaration
    signature block (idx 82, page 3). Without monotonic (forward-only)
    search, the second occurrence would false-match page 1 again since the
    text is a near-exact repeat. Verified manually against the rendered PDF
    that idx 82 is actually on page 3."""
    doc, matches = _matches()
    by_index = {m.paragraph_index: m for m in matches}
    assert by_index[13].page_number == 1   # title page occurrence
    assert by_index[82].page_number == 3   # declaration-signature occurrence


def test_known_limitation_short_generic_headings_unreliable():
    """Documented finding: very short, generic all-caps single-word headings
    (e.g. 'INDEX') are excluded from matching entirely (below the 15-char
    normalized-snippet threshold) rather than risk a spuriously confident
    wrong match — this was an empirically observed failure mode, not a
    theoretical concern (see libreoffice_render.py docstring)."""
    doc, matches = _matches()
    by_index = {m.paragraph_index: m for m in matches}
    index_heading = next(p for p in doc.paragraphs if p.text.strip() == "INDEX")
    assert by_index[index_heading.index].page_number is None
