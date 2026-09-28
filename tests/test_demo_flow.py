"""Exercise the files a new user is told to upload in the README."""

from pathlib import Path

from tests.test_stage2_api import client


DEMO = Path(__file__).resolve().parents[1] / "demo"


def test_demo_documents_show_a_clean_and_a_failing_report(client):
    with (DEMO / "format_template.docx").open("rb") as file:
        response = client.post(
            "/api/templates", files={"file": ("format_template.docx", file)}
        )
    assert response.status_code == 200
    template = response.json()
    assert template["status"] == "DRAFT"
    assert {rule["canonical_name"] for rule in template["ruleset"]["structure_rules"]} == {
        "introduction", "methods", "results", "conclusion"
    }

    published = client.post(f"/api/templates/{template['id']}/publish")
    assert published.status_code == 200
    assert published.json()["status"] == "PUBLISHED"

    with (DEMO / "correct_report.docx").open("rb") as file:
        correct_response = client.post(
            f"/api/templates/{template['id']}/check",
            files={"report": ("correct_report.docx", file)},
        )
    assert correct_response.status_code == 200
    correct = correct_response.json()
    assert correct["overall_score"] == 100
    assert correct["total_errors"] == 0
    assert correct["violations"] == []

    with (DEMO / "formatting_errors_report.docx").open("rb") as file:
        wrong_response = client.post(
            f"/api/templates/{template['id']}/check",
            files={"report": ("formatting_errors_report.docx", file)},
        )
    assert wrong_response.status_code == 200
    wrong = wrong_response.json()
    assert wrong["overall_score"] < correct["overall_score"]
    assert wrong["total_errors"] > 0
    found = {issue["rule_id"] for issue in wrong["violations"]}
    assert {"BODY_FONT", "BODY_SIZE", "BODY_LINE_SPACING", "PAGE_MARGINS",
            "REQUIRED_SECTION_methods"} <= found
