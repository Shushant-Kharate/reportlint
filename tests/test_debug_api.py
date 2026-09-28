from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

FIXTURE = "tests/fixtures/mini_project_1a_format.docx"
RULESET = "tests/fixtures/mini_project_1a_ruleset.json"


def test_health():
    r = client.get("/debug/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_extract_ruleset_route_returns_valid_ruleset_json():
    with open(FIXTURE, "rb") as f:
        r = client.post(
            "/debug/extract-ruleset",
            files={"file": ("mini_project_1a_format.docx", f,
                             "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        )
    assert r.status_code == 200
    body = r.json()
    assert "typography_rules" in body
    assert "structure_rules" in body
    assert any(rule["id"] == "BODY_SIZE" for rule in body["typography_rules"])


def test_check_route_runs_full_pipeline():
    with open(FIXTURE, "rb") as report_f, open(RULESET, "rb") as ruleset_f:
        r = client.post(
            "/debug/check",
            files={
                "report": ("mini_project_1a_format.docx", report_f,
                           "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
                "ruleset": ("ruleset.json", ruleset_f, "application/json"),
            },
        )
    assert r.status_code == 200
    body = r.json()
    assert "overall_score" in body
    assert "violations" in body
    assert 0 <= body["overall_score"] <= 100


def test_check_route_rejects_non_docx():
    r = client.post(
        "/debug/check",
        files={
            "report": ("notes.txt", b"hello", "text/plain"),
            "ruleset": ("ruleset.json", b"{}", "application/json"),
        },
    )
    assert r.status_code == 400
