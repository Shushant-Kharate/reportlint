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
        "candidate_properties": ["font_family", "font_size", "line_spacing_multiple", "page_size", "margin", "chapter_font_size", "chapter_case", "chapter_bold", "section_font_size", "abstract_word_count", "abstract_keywords",
            "page_number_alignment", "body_page_number_format", "front_page_number_format", "introduction_numbering", "contents_structure", "contents_page_alignment", "illustration_lists", "figure_captions", "table_titles"],
        "chapter_profiles": "TABLE_CANDIDATES_REQUIRING_REVIEW",
        "v2_publication": True,
        "v2_publication_scope": "REVIEWED_SPECIFICATION_SNAPSHOTS",
        "v2_report_checking": True,
        "v2_report_checking_scope": "EXPLICIT_PAGE_SETTINGS_BODY_TEXT_AND_OUTLINE_CHAPTERS",
        "body_scope": "BODY_TEXT_STYLE_OR_REVIEWED_REPORT_ASSIGNMENT",
        "report_role_review": "HASH_BOUND_MANUAL_ASSIGNMENTS",
        "chapter_matching": "NORMALIZED_OUTLINE_HEADINGS_NUMBERED_BANNERS_OR_REVIEWED_ASSIGNMENT",
        "spacing_tolerance_lines": 1 / 240,
        "spacing_near_match_review_lines": 0.01,
        "role_corrections": "SUPPORTED_TOP_LEVEL_PARAGRAPHS_INCLUDING_EXISTING_CLASSIFICATIONS",
        "scoped_checks": ["chapter_font_size", "chapter_case", "chapter_bold", "section_font_size", "abstract_word_count", "abstract_keywords",
            "page_number_alignment", "body_page_number_format", "front_page_number_format", "introduction_numbering", "contents_structure", "contents_page_alignment", "illustration_lists", "figure_captions", "table_titles"],
        "conditional_rules": ["HEADER_ABSENT_TOP_MARGIN_OVERRIDE"],
        "pagination": "STORED_SECTION_AND_INHERITED_PAGE_FIELD_SETTINGS_NOT_RENDERED_PAGE_NUMBERS",
        "figure_caption_absence": "MANUAL_REVIEW_FOR_POSSIBLE_IMAGE_EMBEDDED_CAPTIONS",
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
            raise HTTPException(413, detail={"code": "INPUT_LIMIT_EXCEEDED", "message": f"Maximum template upload size is {MAX_UPLOAD_BYTES // (1024 * 1024)} MB."}) from exc
        raise
    try:
        return await run_in_threadpool(analyze_bytes, data)
    except (InvalidDocxError, ValueError, TypeError, OverflowError) as exc:
        raise HTTPException(422, detail={"code": "INVALID_DOCX", "message": "The template is invalid or exceeds the supported analysis limits."}) from exc
