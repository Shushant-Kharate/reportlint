from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from starlette.concurrency import run_in_threadpool

from app import storage
from app.analysis.api import preview_template
from app.review.models import ReviewPatch, ReviewRevision, VersionRequest
from app.review.repository import RevisionRepository
from app.review.service import ReviewError, apply_review, publication_blockers, publish
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import re
from pydantic import Field
from app.models.template_analysis import AnalysisModel, SourceEvidence, RequirementDisposition
from app.analysis.service import analyze_bytes
from app.analysis.template_source import inventory_source
from app.analysis.template_baseline import add_baselines
from app.analysis.plain_language import interpret, role_name
from app.ooxml.docx_loader import DocxPackage, InvalidDocxError
from app.uploads import read_limited
from app.review.automatic import (enrich, recognized, automatic_change, summary,
    clarify_draft, questions)
from app.review.service import guard_edit

router = APIRouter(prefix="/api/v2/templates", tags=["V2 template review"])


def get_repository():
    from app.cloud import enabled
    from app.builtin_formats import CatalogRepository
    if enabled():
        from app.review.blob_repository import BlobRevisionRepository
        repository = BlobRevisionRepository()
    else:
        repository = RevisionRepository(storage.STORAGE_DIR / "review.sqlite3")
    return CatalogRepository(repository)


def perform(function, *args):
    try:
        return function(*args)
    except ReviewError as exc:
        raise HTTPException(exc.status, detail={"code": exc.code, "message": str(exc), "blockers": exc.blockers}) from exc


def prepare_upload(data, name, repository):
    reused=recognized(repository,sha256(data).hexdigest())
    if reused:return summary(reused,reused=True)
    analysis=analyze_bytes(data)
    with TemporaryDirectory(prefix='reportlint_prepare_') as directory:
        path=Path(directory)/'format.docx';path.write_bytes(data)
        package=DocxPackage.load(str(path))
        inventory=inventory_source(package)
        sources=list(inventory.paragraphs)
        for table in inventory.tables:
            if table.complex_grid:continue
            for i,row in enumerate(table.rows):
                text=': '.join(' '.join(p.excerpt for p in cell).strip() for cell in row)
                if interpret(text).values:
                    sources.append(SourceEvidence(source_id='table-row-'+sha256((table.path+str(i)).encode()).hexdigest()[:16],path=table.path+'/row/'+str(i),excerpt=text))
        analysis=enrich(analysis,sources)
        from app.ooxml.constants import NS
        if inventory.notices or package.document_tree.xpath('//w:drawing | //w:pict | //w:txbxContent',namespaces=NS):
            sid='automatic-visual-content-question'
            analysis.evidence.append(SourceEvidence(source_id=sid,path='uninterpreted-source-content',excerpt='Some source content is in images, text boxes or tracked changes. Explain any formatting requirements inside it. If the image is only decorative, say: This image is decorative.'))
            analysis.requirement_ledger.append(RequirementDisposition(evidence_id=sid,status='MANUAL_REVIEW'))
        analysis=add_baselines(analysis,package)
    draft=repository.create(name[:120] or 'Uploaded format',analysis)
    revision=repository.change(draft.template_id,draft.revision_id,automatic_change,(draft.version,analysis))
    return summary(revision)


@router.post('/prepare')
async def prepare_template(file: UploadFile=File(...), name: str|None=Form(None), repository=Depends(get_repository)):
    if not (file.filename or '').lower().endswith('.docx'):
        raise HTTPException(415,detail={'code':'UNSUPPORTED_INPUT','message':'Choose a Word .docx format file.'})
    data=await read_limited(file)
    display=(name or '').strip() or (file.filename or 'Format').replace('\\','/').rsplit('/',1)[-1].rsplit('.',1)[0]
    try:
        return await run_in_threadpool(perform,prepare_upload,data,display,repository)
    except (InvalidDocxError,ValueError,TypeError,OverflowError):
        raise HTTPException(422,detail={'code':'INVALID_DOCX','message':'The format is invalid or exceeds the supported analysis limits.'})


@router.post('/{template_id}/revisions/{revision_id}/automate')
def automate_revision(template_id: str,revision_id: str,request: VersionRequest,repository=Depends(get_repository)):
    revision=perform(repository.get,template_id,revision_id)
    if revision.status=='PUBLISHED':return summary(revision)
    perform(guard_edit,revision,request.expected_version)
    known=recognized(repository,revision.analysis.source_sha256)
    if known:return summary(known,reused=True)
    analysis=enrich(revision.analysis,revision.analysis.evidence)
    result=perform(repository.change,template_id,revision_id,automatic_change,(request.expected_version,analysis))
    return summary(result)


@router.get('/{template_id}/revisions/{revision_id}/preparation')
def preparation_summary(template_id: str,revision_id: str,repository=Depends(get_repository)):
    return summary(perform(repository.get,template_id,revision_id))


class ClarificationRequest(AnalysisModel):
    expected_version: int=Field(ge=0)
    explanation: str=Field(min_length=5,max_length=12000)
    evidence_id: str|None=Field(default=None,max_length=100)


@router.post('/{template_id}/revisions/{revision_id}/clarify')
def clarify_revision(template_id: str,revision_id: str,request: ClarificationRequest,repository=Depends(get_repository)):
    original=perform(repository.get,template_id,revision_id)
    if original.version!=request.expected_version:
        raise HTTPException(409,detail={'code':'REVISION_CONFLICT','message':'The format changed. Reopen it before explaining this instruction.'})
    entry=next((t for t in repository.list_templates() if t['id']==template_id),None)
    if entry and not entry.get('builtin') and original.status=='PUBLISHED' and entry.get('published_revision_id')!=revision_id:
        raise HTTPException(409,detail={'code':'REVISION_CONFLICT','message':'A newer format version is available. Open it before adding another explanation.'})
    if request.evidence_id and request.evidence_id not in {q['evidence_id'] for q in questions(original)}:
        raise HTTPException(409,detail={'code':'STALE_QUESTION','message':'This instruction no longer needs clarification. Reopen the format.'})
    parsed=interpret(request.explanation)
    effective_text=request.explanation
    if not parsed.values and not parsed.chapters and not parsed.ambiguity and request.evidence_id and not role_name(effective_text):
        context=next(e.excerpt for e in original.analysis.evidence if e.source_id==request.evidence_id)
        role=role_name(context)
        if role:
            label={'body':'Body text','abstract':'Abstract','title':'Paper title','heading':'Main headings','reference':'References'}[role]
            effective_text=label+': '+request.explanation
            parsed=interpret(effective_text)
        elif re.search(r'\b(?:paper|page)\b',context,re.I) and re.search(r'\b(?:A4|Letter)\b',effective_text,re.I):
            effective_text='Paper size: '+request.explanation
            parsed=interpret(effective_text)
    if parsed.ambiguity or not (parsed.values or parsed.chapters or parsed.ignore_instruction and request.evidence_id):
        raise HTTPException(422,detail={'code':'CLARIFICATION_UNRESOLVED','message':parsed.ambiguity or
            'I could not turn that explanation into a supported rule. Include its role and value, for example: Body text must use Arial at 12 pt with 1.5 line spacing.'})
    from app.analysis.template_requirements import property_key, same_value
    from app.models.template_analysis import RuleCandidate
    proposals=[RuleCandidate(candidate_id=str(i),scope=s,value=v,origin='EXPLICIT_PROSE',evidence_ids=['clarification']) for i,(s,v) in enumerate(parsed.values)]
    if any(property_key(a)==property_key(b) and not same_value(a,b) for i,a in enumerate(proposals) for b in proposals[i+1:]):
        raise HTTPException(422,detail={'code':'CONFLICTING_EXPLANATION','message':'Your explanation gives different values for the same property. Specify one value and scope.'})
    # Validate before forking, so rejected explanations do not create empty revisions.
    draft=perform(repository.fork,template_id,revision_id) if original.status=='PUBLISHED' else original
    sid='clarification-'+sha256((request.explanation+'|'+str(request.evidence_id)+'|'+draft.revision_id).encode()).hexdigest()[:24]
    source=SourceEvidence(source_id=sid,part='user-clarification',path='clarifications/'+(request.evidence_id or 'additional-rule'),excerpt=effective_text)
    updated=perform(repository.change,draft.template_id,draft.revision_id,clarify_draft,(draft.version,source,parsed,request.evidence_id))
    return summary(updated)


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
