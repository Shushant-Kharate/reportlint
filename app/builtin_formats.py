"""Packaged format snapshots are read-only; custom copies need publication."""
from functools import lru_cache
from hashlib import sha256
from pathlib import Path
from app.review.models import ReviewRevision, ReviewPatch
from app.review.service import ReviewError, apply_review, snapshot_hash

DIRECTORY = Path(__file__).parent / "builtins"
BUILTIN_ID = "builtin-mini-project-1a"
BUILTINS = {BUILTIN_ID: "mini-project-1a", "builtin-ieee-conference-letter": "ieee-conference-letter"}


@lru_cache(maxsize=16)
def builtin(template_id=BUILTIN_ID, revision_id=None):
    stem = BUILTINS.get(template_id)
    if stem is None:
        raise ReviewError("TEMPLATE_NOT_FOUND", "Built-in format not found.", status=404)
    filename = stem + ('.v1' if template_id == 'builtin-ieee-conference-letter' and revision_id == template_id + '-v1' else '')
    revision = ReviewRevision.model_validate_json((DIRECTORY / (filename + ".json")).read_bytes())
    if revision_id is not None and revision.revision_id != revision_id:
        raise ReviewError('REVISION_NOT_FOUND', 'Template revision not found.', status=404)
    if revision.status != "PUBLISHED" or revision.snapshot_sha256 != snapshot_hash(revision):
        raise RuntimeError("The built-in format failed snapshot validation")
    if revision.template_id != template_id or sha256((DIRECTORY / (stem + ".docx")).read_bytes()).hexdigest() != revision.analysis.source_sha256:
        raise RuntimeError("The built-in source does not match its specification")
    return revision


class CatalogRepository:
    def __init__(self, repository):
        self.repository = repository

    def create(self, *args):
        return self.repository.create(*args)

    def list_templates(self):
        shared = []
        for identifier in BUILTINS:
            r = builtin(identifier)
            shared.append({"id": r.template_id, "name": r.name, "created_at": r.audit[0].timestamp,
                           "published_revision_id": r.revision_id, "latest_revision_number": r.revision_number, "builtin": True})
        return shared + self.repository.list_templates()

    def list_revisions(self, template_id):
        if template_id in BUILTINS:
            r = builtin(template_id)
            revisions = [r]
            if template_id == 'builtin-ieee-conference-letter' and r.revision_number > 1:
                revisions.append(builtin(template_id, template_id + '-v1'))
            return [{"id": x.revision_id, "number": x.revision_number, "status": x.status, "version": x.version} for x in revisions]
        return self.repository.list_revisions(template_id)

    def get(self, template_id, revision_id):
        if template_id in BUILTINS:
            r = builtin(template_id, revision_id)
            if revision_id != r.revision_id:
                raise ReviewError("REVISION_NOT_FOUND", "Template revision not found.", status=404)
            return r.model_copy(deep=True)
        return self.repository.get(template_id, revision_id)

    def change(self, template_id, *args):
        if template_id in BUILTINS:
            raise ReviewError("BUILTIN_READ_ONLY", "This built-in format is read-only. Create a draft copy to customize it.", status=403)
        return self.repository.change(template_id, *args)

    def fork(self, template_id, revision_id):
        if template_id not in BUILTINS:
            return self.repository.fork(template_id, revision_id)
        original = self.get(template_id, revision_id)
        draft = self.repository.create(original.name + " (custom copy)", original.analysis)
        patch = ReviewPatch(expected_version=0, candidates=original.candidate_decisions,
                            ledger=original.ledger_decisions, profile=original.profile_review)
        return self.repository.change(draft.template_id, draft.revision_id, apply_review, patch)
