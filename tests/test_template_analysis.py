"""Contract and behavioral tests using fictional inputs, not private documents."""
from hashlib import sha256
from io import BytesIO
import json

from docx import Document
from docx.shared import Pt
from fastapi.testclient import TestClient
from pydantic import ValidationError
import pytest

from app.analysis.service import analyze_bytes
from app.main import app
from app.models.template_analysis import SizeValue, TemplateAnalysis
from app.ooxml.docx_loader import InvalidDocxError
from scripts.inspect_template import main as inspect_main


def encoded(document):
    stream = BytesIO()
    document.save(stream)
    return stream.getvalue()


def complex_format():
    d = Document()
    d.styles["Normal"].font.name = "Times New Roman"
    d.styles["Normal"].font.size = Pt(11.5)
    for label, headings in (("Topic", ["Introduction\nBackground\nScope", "System Design", "References"]),
                            ("Flow of the Synopsis", ["Abstract", "Proposed System/ Problem Statement"])):
        table = d.add_table(rows=1, cols=3)
        for cell, text in zip(table.rows[0].cells, ["Sr. No.", label, "Page No."]):
            cell.text = text
        for n, title in enumerate(headings, 1):
            row = table.add_row()
            row.cells[0].text = str(n)
            row.cells[1].text = title
    d.add_paragraph("Guidelines for project report format")
    d.add_paragraph("The size of the paper shall be standard A4; height 297 mm, width 210 mm.")
    d.add_paragraph("2.2 Type Setting, Text Processing and Printing:")
    d.add_paragraph("The standard font shall be Times New Roman of 12 pts with 1.5 line spacing.")
    d.add_paragraph("Top Margin : 15 mm")
    d.add_paragraph("Bottom Margin : 22 mm")
    d.add_paragraph("Left Margin : 30 mm")
    d.add_paragraph("Right Margin : 20 mm")
    d.add_paragraph("When header is not used the top margin shall be 30 mm.")
    d.add_paragraph("Vertical space between paragraphs shall be about 2.5 line spacing.")
    d.add_paragraph("2.3.1 Chapter:")
    d.add_paragraph("Chapter number and title shall be printed at 18 pt in bold.")
    d.add_paragraph("All lettering shall be embossed in gold.")
    d.add_paragraph("Name of student: Synthetic Private Student")
    return d


def explicit(analysis, kind):
    return [c for c in analysis.candidates if c.origin == "EXPLICIT_PROSE" and c.value.kind == kind]


def test_written_requirements_are_distinct_from_observed_appearance():
    result = analyze_bytes(encoded(complex_format()))
    assert explicit(result, "font_size")[0].value.expected_pt == 12
    observed = [c.value.expected_pt for c in result.candidates if c.value.kind == "font_size" and c.origin == "OBSERVED_APPEARANCE"]
    assert observed == [11.5]
    page = explicit(result, "page_size")[0].value
    assert page.width_pt == pytest.approx(210 * 72 / 25.4)
    assert page.height_pt == pytest.approx(297 * 72 / 25.4)
    assert explicit(result, "font_family")[0].value.font == "Times New Roman"
    conflicts = {tuple(sorted(c.candidate_ids)) for c in result.conflicts}
    size_ids = [c.candidate_id for c in result.candidates if c.value.kind == "font_size"]
    assert tuple(sorted(size_ids)) in conflicts
    assert result.publication_ready is False
    assert {c.review_status for c in result.candidates} == {"PROPOSED"}


def test_paragraph_gap_and_chapter_font_are_not_body_rules():
    result = analyze_bytes(encoded(complex_format()))
    assert [c.value.multiplier for c in explicit(result, "line_spacing_multiple")] == [1.5]
    assert [c.value.expected_pt for c in explicit(result, "font_size")] == [12]
    lookup = {e.source_id: e.excerpt for e in result.evidence}
    pending = [lookup[item.evidence_id] for item in result.requirement_ledger if item.status == "UNCLASSIFIED"]
    assert any("Chapter number" in text for text in pending)
    assert any("Vertical space" in text for text in pending)


def test_conditional_top_margin_is_preserved_for_review():
    result = analyze_bytes(encoded(complex_format()))
    candidates = [c for c in explicit(result, "margin") if c.value.side == "top"]
    assert {c.condition for c in candidates} == {"ALWAYS", "HEADER_ABSENT"}
    conditional = next(c for c in candidates if c.condition == "HEADER_ABSENT")
    assert conditional.value.expected_pt == pytest.approx(30 * 72 / 25.4)
    assert any(c.kind == "CONDITIONAL_OVERRIDE" for c in result.conflicts)


def test_chapter_profiles_do_not_mix_or_promote_topics_to_requirements():
    result = analyze_bytes(encoded(complex_format()))
    profiles = {p.label: p for p in result.profiles}
    assert profiles["report"].chapters[0].title == "Introduction"
    assert profiles["report"].chapters[0].suggested_topics == ["Background", "Scope"]
    assert profiles["synopsis"].chapters[1].title == "Proposed System/ Problem Statement"
    assert all(c.required is None for p in result.profiles for c in p.chapters)


def test_evidence_links_are_valid_and_deterministic():
    data = encoded(complex_format())
    one, two = analyze_bytes(data), analyze_bytes(data)
    assert one.model_dump() == two.model_dump()
    assert one.source_sha256 == sha256(data).hexdigest()
    evidence = {e.source_id: e for e in one.evidence}
    for candidate in explicit(one, "font_size"):
        assert "12 pts" in evidence[candidate.evidence_ids[0]].excerpt
    assert any("/tbl[" in e.path for e in one.evidence)


def test_ordinary_sample_does_not_become_explicit_rule():
    d = Document()
    d.add_paragraph("This example discusses a body font of 12 pt and the design of an A4 page.")
    result = analyze_bytes(encoded(d))
    assert not any(c.origin == "EXPLICIT_PROSE" for c in result.candidates)
    assert result.publication_ready is False


def test_guideline_fields_do_not_leak_into_sample_region():
    d = Document()
    d.add_paragraph("Formatting requirements")
    d.add_paragraph("Left Margin: 30 mm")
    d.add_paragraph("Sample report")
    d.add_paragraph("Right Margin: 99 mm")
    result = analyze_bytes(encoded(d))
    assert [c.value.side for c in explicit(result, "margin")] == ["left"]


def test_merged_index_table_is_not_guessed():
    d = complex_format()
    d.tables[0].cell(1, 1).merge(d.tables[0].cell(1, 2))
    result = analyze_bytes(encoded(d))
    assert [p.label for p in result.profiles] == ["synopsis"]
    assert any("Merged index table" in n for n in result.notices)


def test_manual_requirements_remain_visible():
    result = analyze_bytes(encoded(complex_format()))
    assert any(d.status == "MANUAL_REVIEW" for d in result.requirement_ledger)


@pytest.mark.parametrize("instruction", [
    "The standard font must not be Arial of 12 pt.",
    "The standard font shall be Times New Roman or Arial of 12 pt.",
    "The paper must not be A4.",
    "The paper shall be A4 or Letter.",
])
def test_unsupported_negation_and_alternatives_are_not_guessed(instruction):
    d = Document()
    d.add_paragraph(instruction)
    result = analyze_bytes(encoded(d))
    assert not any(c.origin == "EXPLICIT_PROSE" for c in result.candidates)
    assert result.requirement_ledger[0].status == "UNCLASSIFIED"


def test_explicit_dimensions_conflicting_with_paper_name_are_visible():
    d = Document()
    d.add_paragraph("The paper shall be A4; width 216 mm, height 297 mm.")
    result = analyze_bytes(encoded(d))
    assert len(explicit(result, "page_size")) == 2
    assert any(c.kind == "COMPETING_REQUIREMENTS" for c in result.conflicts)


def test_unrelated_alternatives_do_not_hide_explicit_property_sentences():
    d = Document()
    d.add_paragraph("Paper whiteness shall be 95% or above. The paper size shall be A4; height 297 mm, width 210 mm.")
    d.add_paragraph("Use a laser or inkjet printer. The standard font shall be Times New Roman of 12 pt with 1.5 line spacing.")
    result = analyze_bytes(encoded(d))
    assert len(explicit(result, "page_size")) == 1
    assert explicit(result, "font_size")[0].value.expected_pt == 12


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -1, 0, True, "12"])
def test_rule_payload_rejects_invalid_numbers(value):
    with pytest.raises(ValidationError):
        SizeValue(expected_pt=value)


def test_analysis_cannot_claim_publication_or_lose_evidence():
    value = analyze_bytes(encoded(complex_format())).model_dump()
    value["publication_ready"] = True
    with pytest.raises(ValidationError):
        TemplateAnalysis.model_validate(value)
    value["publication_ready"] = False
    value["evidence"] = []
    with pytest.raises(ValidationError):
        TemplateAnalysis.model_validate(value)


def test_cli_redacts_prose_and_verifies_source_hash(tmp_path, capsys):
    path = tmp_path / "private-file.docx"
    data = encoded(complex_format())
    path.write_bytes(data)
    inspect_main([str(path), "--expected-sha256", sha256(data).hexdigest()])
    stdout = capsys.readouterr().out
    value = json.loads(stdout)
    assert value["source_sha256"] == sha256(data).hexdigest()
    assert "Synthetic Private Student" not in stdout
    assert "private-file" not in stdout
    assert "The standard font shall" not in stdout
    assert "Introduction" not in stdout
    with pytest.raises(SystemExit) as error:
        inspect_main([str(path), "--expected-sha256", "0" * 64])
    assert error.value.code == 2


def test_api_is_read_only_and_capabilities_are_honest(monkeypatch):
    from app import storage
    def no_save(*args):
        pytest.fail("Preview must not publish or persist a template")
    monkeypatch.setattr(storage, "save_template", no_save)
    with TestClient(app) as client:
        response = client.post("/api/v2/template-analysis", files={"file": ("format.docx", encoded(complex_format()))})
        assert response.status_code == 200
        result = response.json()
        assert result["publication_ready"] is False
        assert result["conflicts"]
        capabilities = client.get("/api/v2/capabilities").json()
        assert capabilities["v2_publication"] is True
        assert capabilities["v2_report_checking"] is False


@pytest.mark.parametrize("filename,data,status", [("bad.pdf", b"bad", 415), ("empty.docx", b"", 422), ("bad.docx", b"bad", 422)])
def test_invalid_uploads_have_explicit_errors(filename, data, status):
    with TestClient(app) as client:
        response = client.post("/api/v2/template-analysis", files={"file": (filename, data)})
    assert response.status_code == status
    assert response.json()["detail"]["code"]


def test_analysis_resource_budget(monkeypatch):
    from app.analysis import service
    monkeypatch.setattr(service, "MAX_UPLOAD_BYTES", 10)
    with pytest.raises(InvalidDocxError):
        analyze_bytes(b"x" * 11)


def test_oversized_upload_keeps_v2_error_contract(monkeypatch):
    from app.analysis import api
    from fastapi import HTTPException
    async def oversized(file):
        raise HTTPException(413, "too large")
    monkeypatch.setattr(api, "read_limited", oversized)
    with TestClient(app) as client:
        response = client.post("/api/v2/template-analysis", files={"file": ("format.docx", b"x")})
    assert response.status_code == 413
    assert response.json()["detail"]["code"] == "INPUT_LIMIT_EXCEEDED"
