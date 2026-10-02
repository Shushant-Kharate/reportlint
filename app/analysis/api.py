"""Experimental read-only v2 preview; no template publication or rule execution."""
from fastapi import APIRouter, File, HTTPException, UploadFile
from starlette.concurrency import run_in_threadpool

from app.analysis.service import analyze_bytes
from app.models.template_analysis import TemplateAnalysis
from app.ooxml.docx_loader import InvalidDocxError
from app.uploads import read_limited, MAX_UPLOAD_BYTES

router = APIRouter(prefix="/api/v2", tags=["Experimental template analysis"])


@router.get("/capabilities")
def capabilities():
    return {
        "schema_version": 2,
        "template_analysis": "EXPERIMENTAL_PREVIEW",
        "accepted_inputs": ["docx"],
        "guideline_languages": ["en"],
        "candidate_properties": ["font_family", "font_size", "line_spacing_multiple", "page_size", "margin"],
        "chapter_profiles": "TABLE_CANDIDATES_REQUIRING_REVIEW",
        "v2_publication": True,
        "v2_publication_scope": "REVIEWED_SPECIFICATION_SNAPSHOTS",
        "v2_report_checking": True,
        "v2_report_checking_scope": "EXPLICIT_PAGE_SETTINGS_BODY_TEXT_AND_OUTLINE_CHAPTERS",
        "body_scope": "BODY_TEXT_STYLE_OR_REVIEWED_REPORT_ASSIGNMENT",
        "report_role_review": "HASH_BOUND_MANUAL_ASSIGNMENTS",
        "chapter_matching": "OUTLINE_LEVEL_1_EXACT_NAMES_OR_REVIEWED_REPORT_ASSIGNMENT",
        "max_upload_bytes": MAX_UPLOAD_BYTES,
    }


@router.post("/template-analysis", response_model=TemplateAnalysis)
async def preview_template(file: UploadFile = File(...)):
    if not (file.filename or "").lower().endswith(".docx"):
        raise HTTPException(415, detail={"code": "UNSUPPORTED_INPUT", "message": "Choose a Word .docx template."})
    try:
        data = await read_limited(file)
    except HTTPException as exc:
        if exc.status_code == 413:
            raise HTTPException(413, detail={"code": "INPUT_LIMIT_EXCEEDED", "message": "Maximum template upload size is 20 MB."}) from exc
        raise
    try:
        return await run_in_threadpool(analyze_bytes, data)
    except (InvalidDocxError, ValueError, TypeError, OverflowError) as exc:
        raise HTTPException(422, detail={"code": "INVALID_DOCX", "message": "The template is invalid or exceeds the supported analysis limits."}) from exc
