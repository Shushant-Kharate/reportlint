from app.ooxml.docx_loader import DocxPackage
from app.ooxml.structure_extractor import build_document_model
from app.models.document_model import Confidence
from tests.helpers import build_style_resolution_fixture


def test_style_chain_resolution(tmp_path):
    path = str(tmp_path / "fixture.docx")
    build_style_resolution_fixture(path)

    pkg = DocxPackage.load(path)
    doc = build_document_model(pkg, path)

    p0, p1, p2 = doc.paragraphs[0], doc.paragraphs[1], doc.paragraphs[2]

    assert p0.runs[0].font_name == "Arial"
    assert p0.runs[0].font_size_pt == 11
    assert p0.runs[0].confidence == Confidence.EXPLICIT

    assert p1.runs[0].font_name == "Georgia"
    assert p1.runs[0].font_size_pt == 13
    assert p1.runs[0].confidence == Confidence.INHERITED

    # p2 relies on the chain beyond direct run formatting — must NOT be
    # EXPLICIT, and must not silently be None if the chain resolves.
    assert p2.runs[0].confidence == Confidence.UNKNOWN
    assert p2.runs[0].font_size_pt == 11  # known size remains independently checkable


def test_real_fixture_body_font_is_unresolvable_or_default():
    """Empirically documented finding: the real Mini Project template has no
    docDefaults rFonts and minimal explicit run-level fonts, so font_name
    resolves to None for most body text. This is a known limitation —
    asserted explicitly rather than papered over."""
    pkg = DocxPackage.load("tests/fixtures/mini_project_1a_format.docx")
    doc = build_document_model(pkg, "x")
    unresolved = sum(
        1 for p in doc.paragraphs for r in p.runs
        if r.text.strip() and r.font_name is None
    )
    total = sum(1 for p in doc.paragraphs for r in p.runs if r.text.strip())
    assert total > 0
    assert unresolved / total > 0.5  # majority unresolvable — documented limitation
