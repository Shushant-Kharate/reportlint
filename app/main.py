import json
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.staticfiles import StaticFiles

from app.rules.rule_extractor import extract_ruleset
from app.models.rule_model import RuleSet
from app.compliance.engine import ComplianceEngine
from app.api_routes import router as api_router
from app.uploads import parse_upload, read_limited
from starlette.concurrency import run_in_threadpool

app = FastAPI(title="ReportLint Engine")
app.include_router(api_router)

_STATIC_DIR = Path(__file__).parent.parent / "static"
if _STATIC_DIR.exists():
    app.mount("/app", StaticFiles(directory=str(_STATIC_DIR), html=True), name="static")

@app.get("/")
def root():
    from fastapi.responses import RedirectResponse
    return RedirectResponse("/app/")


@app.get("/debug/health")
def health():
    return {"status": "ok"}


@app.post("/debug/extract-ruleset")
async def extract_ruleset_route(file: UploadFile = File(...)):
    doc = await parse_upload(file)
    ruleset = extract_ruleset(doc, file.filename)
    return json.loads(ruleset.model_dump_json())


@app.post("/debug/check")
async def check_route(report: UploadFile = File(...), ruleset: UploadFile = File(...)):
    doc = await parse_upload(report)
    ruleset_bytes = await read_limited(ruleset, 2 * 1024 * 1024)
    try:
        rs = RuleSet.model_validate(json.loads(ruleset_bytes))
    except Exception as e:
        raise HTTPException(400, f"Invalid ruleset JSON: {e}")

    result = await run_in_threadpool(ComplianceEngine(rs).run, doc)
    return json.loads(result.model_dump_json())
