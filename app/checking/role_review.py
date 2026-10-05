"""Report-specific role proposals and explicit, hash-bound reviewer assignments."""
from collections import Counter
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Literal

from app.checking.models import ReportRoleReview, RoleDecision
from app.checking.roles import inventory
from app.checking.semantic import title_key
from app.models.template_analysis import AnalysisModel
from app.ooxml.docx_loader import DocxPackage, InvalidDocxError
from app.review.service import ReviewError, canonical_json, snapshot_hash
from app.uploads import MAX_UPLOAD_BYTES


class RoleProposal(AnalysisModel):
    paragraph_index: int
    source_path: str
    excerpt: str
    excerpt_truncated: bool
    detected_role: str
    reviewable: bool
    suggested_role: Literal["BODY", "CHAPTER"] | None = None
    suggested_chapter_index: int | None = None
    proposal_reason: str
    review_status: Literal["PROPOSED"] = "PROPOSED"


class RolePreview(AnalysisModel):
    schema_version: Literal[2] = 2
    analyzer_version: Literal["0.1.0"] = "0.1.0"
    template_id: str
    revision_id: str
    snapshot_sha256: str
    report_sha256: str
    counts: dict[str, int]
    structural_uncertainty: bool
    paragraphs: list[RoleProposal]
    limitations: list[str]


def validate_revision(revision):
    if revision.status != "PUBLISHED" or revision.publication is None:
        raise ReviewError("PUBLISHED_REVISION_REQUIRED", "Publish a reviewed revision before analyzing a report.", status=409)
    if revision.snapshot_sha256 != snapshot_hash(revision):
        raise ReviewError("SNAPSHOT_INTEGRITY_ERROR", "The published snapshot failed its integrity check.", status=500)


def preview_package(revision, package, report_hash):
    validate_revision(revision)
    paragraphs, _, uncertain = inventory(package)
    profile = revision.publication.profile
    chapters = profile.chapters if profile else []
    proposals = []
    for p in paragraphs:
        role, chapter_index, reason = None, None, "No role inferred. Inspect the original report before assigning a role."
        if not p.reviewable:
            reason = "Unsupported content or malformed structure prevents a safe manual override."
        else:
            matches = [c for c in chapters if title_key(p.text) in {title_key(c.name), *map(title_key, c.aliases)}]
            if len(matches) == 1:
                role, chapter_index = "CHAPTER", matches[0].index
                reason = "Text matches a reviewed chapter name/alias. It could still be front matter or a manual contents entry; confirm its role."
            elif len(p.text.split()) >= 12 and p.text.rstrip().endswith((".", "!", "?")):
                role = "BODY"
                reason = "Sentence-like text is a body candidate, but may instead be instructions, a caption, or front matter."
        proposals.append(RoleProposal(paragraph_index=p.index, source_path=p.path, excerpt=p.text[:1000],
            excerpt_truncated=len(p.text) > 1000, detected_role=p.role, reviewable=p.reviewable,
            suggested_role=role, suggested_chapter_index=chapter_index, proposal_reason=reason))
    return RolePreview(template_id=revision.template_id, revision_id=revision.revision_id,
        snapshot_sha256=revision.snapshot_sha256, report_sha256=report_hash,
        counts=dict(Counter(p.role for p in paragraphs)), structural_uncertainty=uncertain, paragraphs=proposals,
        limitations=[
            "Proposals never change report roles automatically. Supply explicit decisions to the check endpoint.",
            "Supported top-level paragraphs can be corrected, including existing body/heading classifications. Tables, fields, unsupported containers, and malformed style chains cannot be overridden.",
            "Text heuristics are proposals only, not calibrated confidence or proof of a paragraph's role.",
            "Decisions apply only to these exact report and published-snapshot hashes; document edits require another preview/review.",
            "No report, preview, or role review is stored. Excerpts may contain private report text.",
        ])


def apply_roles(revision, paragraphs, report_hash, review):
    if review is None:
        return None
    if review.report_sha256 != report_hash or review.snapshot_sha256 != revision.snapshot_sha256:
        raise ReviewError("STALE_ROLE_REVIEW", "The report or published revision differs from the reviewed source. Generate a new preview.", status=409)
    by_index = {p.index: p for p in paragraphs}
    profile = revision.publication.profile
    chapter_ids = {c.index for c in profile.chapters} if profile else set()
    seen = set()
    # Validate all assignments before mutating this transient inventory.
    for decision in review.decisions:
        p = by_index.get(decision.paragraph_index)
        if decision.paragraph_index in seen or p is None or p.path != decision.source_path:
            raise ReviewError("INVALID_ROLE_TARGET", "Role assignments must reference unique paragraphs and their exact source paths.")
        seen.add(decision.paragraph_index)
        if not p.reviewable:
            raise ReviewError("UNSUPPORTED_ROLE_OVERRIDE", "Only safely parsed top-level paragraphs can be assigned a role.")
        if decision.role == "CHAPTER" and decision.chapter_index not in chapter_ids:
            raise ReviewError("INVALID_CHAPTER_ASSIGNMENT", "Select a chapter index from the published profile.")
    for decision in review.decisions:
        p = by_index[decision.paragraph_index]
        p.role = {"BODY": "BODY", "CHAPTER": "HEADING", "EXCLUDE": "REVIEWED_EXCLUSION"}[decision.role]
        p.level = 1 if decision.role == "CHAPTER" else None
        p.chapter_index = decision.chapter_index
        p.reviewed = True
    return sha256(canonical_json(review.model_dump()).encode("utf-8")).hexdigest()


def preview_bytes(revision, data):
    if not data or len(data) > MAX_UPLOAD_BYTES:
        raise InvalidDocxError("Report is empty or exceeds the upload limit")
    with TemporaryDirectory(prefix="reportlint_roles_") as directory:
        path = Path(directory) / "report.docx"
        path.write_bytes(data)
        return preview_package(revision, DocxPackage.load(str(path)), sha256(data).hexdigest())
