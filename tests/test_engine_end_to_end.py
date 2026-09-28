import json
from app.ooxml.docx_loader import DocxPackage
from app.ooxml.structure_extractor import build_document_model
from app.models.rule_model import RuleSet
from app.compliance.engine import ComplianceEngine
from tests.helpers import build_report_fixture

RULESET_PATH = "tests/fixtures/mini_project_1a_ruleset.json"


def _load_ruleset():
    with open(RULESET_PATH) as f:
        return RuleSet.model_validate(json.load(f))


def _analyze(path):
    pkg = DocxPackage.load(path)
    doc = build_document_model(pkg, path)
    return ComplianceEngine(_load_ruleset()).run(doc)


def test_correct_report_scores_high_with_zero_errors(tmp_path):
    path = str(tmp_path / "correct.docx")
    build_report_fixture(path)
    result = _analyze(path)
    errors = [v for v in result.violations if v.severity.value == "ERROR"]
    assert errors == [], f"unexpected errors: {errors}"
    assert result.overall_score >= 90


def test_wrong_font_detected(tmp_path):
    path = str(tmp_path / "wrong_font.docx")
    build_report_fixture(path, wrong_font=True)
    result = _analyze(path)
    font_violations = [v for v in result.violations if v.rule_id == "BODY_FONT"]
    assert len(font_violations) == 1
    assert font_violations[0].affected_count == 5  # one per section's body paragraph


def test_wrong_spacing_detected(tmp_path):
    path = str(tmp_path / "wrong_spacing.docx")
    build_report_fixture(path, wrong_spacing=True)
    result = _analyze(path)
    spacing_violations = [v for v in result.violations if v.rule_id == "BODY_LINE_SPACING"]
    assert len(spacing_violations) == 1


def test_missing_required_section_detected(tmp_path):
    path = str(tmp_path / "missing_section.docx")
    build_report_fixture(path, drop_heading="INDEX")
    result = _analyze(path)
    struct_violations = [v for v in result.violations if v.rule_id == "REQUIRED_SECTION_index"]
    assert len(struct_violations) == 1
    # No false positives on the sections that ARE present
    other_missing = [v for v in result.violations
                      if v.rule_id.startswith("REQUIRED_SECTION_") and v.rule_id != "REQUIRED_SECTION_index"]
    assert other_missing == []


def test_renamed_heading_matched_via_alias(tmp_path):
    path = str(tmp_path / "renamed.docx")
    build_report_fixture(path, rename_heading="ACKNOWLEDGEMENTS")
    result = _analyze(path)
    missing = [v for v in result.violations if v.rule_id == "REQUIRED_SECTION_acknowledgement"
               and v.actual is None]
    assert missing == []  # matched via alias, not reported as missing
