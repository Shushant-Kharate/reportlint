from app.ooxml.docx_loader import DocxPackage
from app.ooxml.structure_extractor import build_document_model
from app.rules.rule_extractor import extract_ruleset, infer_body_typography

FIXTURE = "tests/fixtures/mini_project_1a_format.docx"


def _doc():
    pkg = DocxPackage.load(FIXTURE)
    return build_document_model(pkg, FIXTURE)


def test_body_typography_inference_confidence():
    doc = _doc()
    inferred = infer_body_typography(doc)
    # Font is documented-unresolvable on this template; size/spacing are not.
    assert inferred["font"]["value"] is None
    assert inferred["size"]["confidence"] > 0.6
    assert inferred["line_spacing"]["confidence"] > 0.6


def test_ruleset_extraction_produces_page_and_typography_rules():
    doc = _doc()
    rs = extract_ruleset(doc, FIXTURE)
    rule_ids = {r.id for r in rs.typography_rules}
    assert "BODY_SIZE" in rule_ids
    assert "BODY_LINE_SPACING" in rule_ids
    page_ids = {r.id for r in rs.page_rules}
    assert "PAGE_SIZE" in page_ids
    assert "PAGE_MARGINS" in page_ids


def test_cover_page_labels_are_not_required_sections():
    rs = extract_ruleset(_doc(), FIXTURE)
    names = {r.canonical_name for r in rs.structure_rules}
    assert "by" not in names
    assert "guided by" not in names
    assert "declaration" in names
