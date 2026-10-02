from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from starlette.concurrency import run_in_threadpool

from app.checking.models import RevisionCheck
from app.checking.service import check_bytes
from app.ooxml.docx_loader import InvalidDocxError
from app.review.api import get_repository, perform
from app.uploads import read_limited

router = APIRouter(prefix="/api/v2/templates", tags=["V2 report checks"])


@router.post("/{template_id}/revisions/{revision_id}/check", response_model=RevisionCheck)
async def check_report(template_id: str, revision_id: str, file: UploadFile = File(...), repository=Depends(get_repository)):
    revision = await run_in_threadpool(perform, repository.get, template_id, revision_id)
    if revision.status != "PUBLISHED":
        raise HTTPException(409, detail={"code": "PUBLISHED_REVISION_REQUIRED", "message": "Publish a reviewed revision before checking a report."})
    if not (file.filename or "").lower().endswith(".docx"):
        raise HTTPException(415, detail={"code": "UNSUPPORTED_INPUT", "message": "Choose a Word .docx report."})
    data = await read_limited(file)
    try:
        return await run_in_threadpool(perform, check_bytes, revision, data)
    except (InvalidDocxError, ValueError, TypeError, OverflowError) as exc:
        raise HTTPException(422, detail={"code": "INVALID_DOCX", "message": "The report is invalid or exceeds supported limits."}) from exc
