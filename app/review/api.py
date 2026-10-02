from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from starlette.concurrency import run_in_threadpool

from app import storage
from app.analysis.api import preview_template
from app.review.models import ReviewPatch, ReviewRevision, VersionRequest
from app.review.repository import RevisionRepository
from app.review.service import ReviewError, apply_review, publication_blockers, publish

router = APIRouter(prefix="/api/v2/templates", tags=["V2 template review"])


def get_repository():
    return RevisionRepository(storage.STORAGE_DIR / "review.sqlite3")


def perform(function, *args):
    try:
        return function(*args)
    except ReviewError as exc:
        raise HTTPException(exc.status, detail={"code": exc.code, "message": str(exc), "blockers": exc.blockers}) from exc


@router.post("", status_code=201, response_model=ReviewRevision)
async def create_template(file: UploadFile = File(...), name: str | None = Form(None), repository=Depends(get_repository)):
    analysis = await preview_template(file)
    display_name = (name or "").strip() or (file.filename or "Template").replace("\\", "/").rsplit("/", 1)[-1].rsplit(".", 1)[0]
    return await run_in_threadpool(perform, repository.create, display_name[:120] or "Template", analysis)


@router.get("")
def list_templates(repository=Depends(get_repository)):
    return perform(repository.list_templates)


@router.get("/{template_id}/revisions")
def list_revisions(template_id: str, repository=Depends(get_repository)):
    return perform(repository.list_revisions, template_id)


@router.get("/{template_id}/revisions/{revision_id}", response_model=ReviewRevision)
def get_revision(template_id: str, revision_id: str, repository=Depends(get_repository)):
    return perform(repository.get, template_id, revision_id)


@router.patch("/{template_id}/revisions/{revision_id}", response_model=ReviewRevision)
def review_revision(template_id: str, revision_id: str, patch: ReviewPatch, repository=Depends(get_repository)):
    return perform(repository.change, template_id, revision_id, apply_review, patch)


@router.get("/{template_id}/revisions/{revision_id}/blockers")
def get_blockers(template_id: str, revision_id: str, repository=Depends(get_repository)):
    revision = perform(repository.get, template_id, revision_id)
    blockers = publication_blockers(revision)
    return {"version": revision.version, "status": revision.status, "can_publish": revision.status == "DRAFT" and not blockers, "blockers": blockers}


@router.post("/{template_id}/revisions/{revision_id}/publish", response_model=ReviewRevision)
def publish_revision(template_id: str, revision_id: str, request: VersionRequest, repository=Depends(get_repository)):
    return perform(repository.change, template_id, revision_id, publish, request.expected_version)


@router.post("/{template_id}/revisions/{revision_id}/fork", status_code=201, response_model=ReviewRevision)
def fork_revision(template_id: str, revision_id: str, repository=Depends(get_repository)):
    return perform(repository.fork, template_id, revision_id)
