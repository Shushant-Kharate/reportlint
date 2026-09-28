import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

FIXTURE = "tests/fixtures/mini_project_1a_format.docx"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("REPORTLINT_STORAGE_DIR", str(tmp_path / "storage"))
    # storage module reads the env var at import time via a module-level
    # constant, so force a fresh import bound to this test's tmp dir.
    import importlib
    import app.storage as storage_module
    importlib.reload(storage_module)
    import app.api_routes as api_routes_module
    importlib.reload(api_routes_module)
    import app.main as main_module
    importlib.reload(main_module)
    return TestClient(main_module.app)


def test_root_redirects_to_app(client):
    r = client.get("/", follow_redirects=False)
    assert r.status_code in (307, 308)
    assert r.headers["location"] == "/app/"


def test_static_frontend_served(client):
    r = client.get("/app/")
    assert r.status_code == 200
    assert "ReportLint" in r.text


def test_template_upload_creates_draft(client):
    with open(FIXTURE, "rb") as f:
        r = client.post("/api/templates", files={"file": ("mini_project_1a_format.docx", f)})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "DRAFT"
    assert body["ruleset"]["typography_rules"]


def test_template_list_and_get(client):
    with open(FIXTURE, "rb") as f:
        created = client.post("/api/templates", files={"file": ("x.docx", f)}).json()

    listed = client.get("/api/templates").json()
    assert any(t["id"] == created["id"] for t in listed)

    fetched = client.get(f"/api/templates/{created['id']}").json()
    assert fetched["id"] == created["id"]


def test_template_rule_edit_and_publish(client):
    with open(FIXTURE, "rb") as f:
        created = client.post("/api/templates", files={"file": ("x.docx", f)}).json()

    rs = created["ruleset"]
    rs["typography_rules"][0]["severity"] = "WARNING"
    rs["typography_rules"][0]["expected_value"] = {"font": "Times New Roman"}
    rs["typography_rules"][0]["teacher_confirmed"] = True
    updated = client.put(f"/api/templates/{created['id']}/rules", json=rs).json()
    assert updated["ruleset"]["typography_rules"][0]["severity"] == "WARNING"

    published = client.post(f"/api/templates/{created['id']}/publish").json()
    assert published["status"] == "PUBLISHED"


def test_check_report_against_template(client):
    with open(FIXTURE, "rb") as f:
        created = client.post("/api/templates", files={"file": ("x.docx", f)}).json()
    client.post(f"/api/templates/{created['id']}/publish")

    with open(FIXTURE, "rb") as f:
        result = client.post(
            f"/api/templates/{created['id']}/check",
            files={"report": ("report.docx", f)},
        ).json()
    assert "overall_score" in result
    assert result["template_id"] == created["id"]


def test_check_report_missing_template_404(client):
    with open(FIXTURE, "rb") as f:
        r = client.post("/api/templates/does-not-exist/check", files={"report": ("x.docx", f)})
    assert r.status_code == 404


def test_delete_template(client):
    with open(FIXTURE, "rb") as f:
        created = client.post("/api/templates", files={"file": ("x.docx", f)}).json()
    r = client.delete(f"/api/templates/{created['id']}")
    assert r.status_code == 200
    assert client.get(f"/api/templates/{created['id']}").status_code == 404
