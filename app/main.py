import json
import os
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from app.rules.rule_extractor import extract_ruleset
from app.models.rule_model import RuleSet
from app.compliance.engine import ComplianceEngine
from app.api_routes import router as api_router
from app.analysis.api import router as analysis_router
from app.review.api import router as review_router
from app.checking.api import router as checking_router
from app.uploads import parse_upload, read_limited
from starlette.concurrency import run_in_threadpool

app = FastAPI(title="ReportLint Engine")
_origins = [origin.strip() for origin in os.environ.get("REPORTLINT_CORS_ORIGINS", "").split(",") if origin.strip()]
if _origins:
    app.add_middleware(CORSMiddleware, allow_origins=_origins,
                       allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
                       allow_headers=["Content-Type", "Accept"])
app.include_router(api_router)
app.include_router(analysis_router)
app.include_router(review_router)
app.include_router(checking_router)

_STATIC_DIR = Path(os.environ.get("REPORTLINT_WEB_DIR", Path(__file__).parent.parent / "frontend" / "build" / "web"))

@app.get("/app/complex.html", include_in_schema=False)
def old_frontend_link():
    from fastapi.responses import RedirectResponse
    return RedirectResponse("/app/")

if (_STATIC_DIR / "index.html").is_file():
    app.mount("/app", StaticFiles(directory=str(_STATIC_DIR), html=True), name="flutter")
else:
    @app.get("/app/", include_in_schema=False)
    def frontend_not_built():
        raise HTTPException(503, "Flutter frontend is not built. Run flutter pub get and flutter build web --base-href /app/ in frontend/, then restart the server. The API remains available at /docs.")

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
