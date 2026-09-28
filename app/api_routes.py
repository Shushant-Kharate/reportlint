import json
from datetime import datetime, timezone

from fastapi import APIRouter, UploadFile, File, HTTPException, Body

from app.rules.rule_extractor import extract_ruleset
from app.models.rule_model import RuleSet
from app.models.template_model import Template, TemplateStatus
from app.compliance.engine import ComplianceEngine
from app import storage
from app.uploads import parse_upload
from starlette.concurrency import run_in_threadpool

router = APIRouter(prefix="/api")

@router.post("/templates")
async def upload_template(file: UploadFile = File(...), name: str | None = None):
    """Teacher uploads a format .docx. Extracts a proposed RuleSet and saves
    it as a DRAFT template — never auto-published (Section 5.5 / 17)."""
    doc = await parse_upload(file)
    ruleset = await run_in_threadpool(extract_ruleset, doc, doc.source_filename)

    template = Template(
        name=(name or "").strip()[:120] or doc.source_filename.rsplit(".", 1)[0],
        source_filename=doc.source_filename,
        status=TemplateStatus.DRAFT,
        ruleset=ruleset,
    )
    storage.save_template(template)
    return json.loads(template.model_dump_json())


@router.get("/templates")
def list_templates():
    return [json.loads(s.model_dump_json()) for s in storage.list_templates()]


@router.get("/templates/{template_id}")
def get_template(template_id: str):
    t = storage.get_template(template_id)
    if t is None:
        raise HTTPException(404, "Template not found")
    return json.loads(t.model_dump_json())


@router.put("/templates/{template_id}/rules")
def update_rules(template_id: str, ruleset: dict = Body(...)):
    """Teacher review step: replace the proposed RuleSet with a corrected
    one. This is the JSON-editing 'teacher review' contract described in
    Section 5.5 of the engine spec, now exposed as a real endpoint instead
    of hand-editing a fixture file."""
    t = storage.get_template(template_id)
    if t is None:
        raise HTTPException(404, "Template not found")
    try:
        t.ruleset = RuleSet.model_validate(ruleset)
    except Exception as e:
        raise HTTPException(400, f"Invalid ruleset: {e}")
    t.status = TemplateStatus.DRAFT
    t.updated_at = datetime.now(timezone.utc).isoformat()
    storage.save_template(t)
    return json.loads(t.model_dump_json())


@router.post("/templates/{template_id}/publish")
def publish_template(template_id: str):
    t = storage.get_template(template_id)
    if t is None:
        raise HTTPException(404, "Template not found")
    t.status = TemplateStatus.PUBLISHED
    t.updated_at = datetime.now(timezone.utc).isoformat()
    storage.save_template(t)
    return json.loads(t.model_dump_json())


@router.delete("/templates/{template_id}")
def delete_template(template_id: str):
    if not storage.delete_template(template_id):
        raise HTTPException(404, "Template not found")
    return {"deleted": True}


@router.post("/templates/{template_id}/check")
async def check_report(template_id: str, report: UploadFile = File(...)):
    """Student uploads a report .docx; checked against the given template's
    current RuleSet (DRAFT templates are allowed too, so a teacher can test
    the rules before publishing — but the UI should visually distinguish
    this)."""
    t = storage.get_template(template_id)
    if t is None:
        raise HTTPException(404, "Template not found")

    doc = await parse_upload(report)
    result = await run_in_threadpool(ComplianceEngine(t.ruleset).run, doc)
    response = json.loads(result.model_dump_json())
    response["template_id"] = template_id
    response["template_name"] = t.name
    response["template_status"] = t.status.value
    response["report_filename"] = report.filename
    return response
