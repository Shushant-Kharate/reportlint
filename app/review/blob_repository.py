"""Cloud implementation of the existing reviewed-revision repository contract."""
from uuid import uuid4
from app.cloud import BlobRecords
from app.review.models import AuditEvent, ReviewRevision
from app.review.service import ReviewError, now, snapshot_hash


class BlobRevisionRepository:
    def __init__(self, records=None):
        self.records = records or BlobRecords("v2")

    def state(self, template_id):
        state, generation = self.records.get(template_id)
        if state is None:
            raise ReviewError("TEMPLATE_NOT_FOUND", "Template not found.", status=404)
        return state, generation

    @staticmethod
    def revision(state, revision_id):
        value = next((r for r in state["revisions"] if r["revision_id"] == revision_id), None)
        if value is None:
            raise ReviewError("REVISION_NOT_FOUND", "Template revision not found.", status=404)
        revision = ReviewRevision.model_validate(value)
        if revision.status == "PUBLISHED" and revision.snapshot_sha256 != snapshot_hash(revision):
            raise ReviewError("SNAPSHOT_INTEGRITY_ERROR", "The published snapshot failed its integrity check.", status=500)
        return revision

    def create(self, name, analysis):
        if len(self.records.values()) >= 20:
            raise ReviewError("WORKSPACE_LIMIT", "This workspace already has 20 formats. Export your saved specifications before adding more.", status=409)
        revision = ReviewRevision(template_id=uuid4().hex, revision_id=uuid4().hex,
            revision_number=1, name=name, analysis=analysis,
            audit=[AuditEvent(version=0, timestamp=now(), action="CREATE")])
        state = {"id": revision.template_id, "name": name, "created_at": now(),
                 "published_revision_id": None, "revisions": [revision.model_dump()]}
        self.records.save(revision.template_id, state, -1)
        return revision

    def get(self, template_id, revision_id):
        state, _ = self.state(template_id)
        return self.revision(state, revision_id)

    def list_templates(self):
        return sorted([{
            "id": s["id"], "name": s["name"], "created_at": s["created_at"],
            "published_revision_id": s["published_revision_id"],
            "latest_revision_number": max(r["revision_number"] for r in s["revisions"]),
        } for s in self.records.values()], key=lambda s: (s["created_at"], s["id"]), reverse=True)

    def list_revisions(self, template_id):
        state, _ = self.state(template_id)
        return [{"id": r["revision_id"], "number": r["revision_number"], "status": r["status"], "version": r["version"]}
                for r in sorted(state["revisions"], key=lambda r: r["revision_number"], reverse=True)]

    def change(self, template_id, revision_id, operation, argument):
        state, generation = self.state(template_id)
        original = self.revision(state, revision_id)
        if original.status == "PUBLISHED":
            raise ReviewError("IMMUTABLE_REVISION", "Published revisions cannot be changed. Create a new draft.", status=409)
        updated = operation(original, argument)
        state["revisions"] = [updated.model_dump() if r["revision_id"] == revision_id else r for r in state["revisions"]]
        if updated.status == "PUBLISHED":
            state["published_revision_id"] = revision_id
        self.records.save(template_id, state, generation)
        return updated

    def fork(self, template_id, revision_id):
        state, generation = self.state(template_id)
        original = self.revision(state, revision_id)
        if original.status != "PUBLISHED":
            raise ReviewError("PUBLISHED_SOURCE_REQUIRED", "Create a new draft from a published revision.", status=409)
        revision = original.model_copy(deep=True)
        revision.parent_revision_id = original.revision_id
        revision.revision_id = uuid4().hex
        revision.revision_number = max(r["revision_number"] for r in state["revisions"]) + 1
        revision.version, revision.status = 0, "DRAFT"
        revision.publication = revision.snapshot_sha256 = None
        revision.audit = [AuditEvent(version=0, timestamp=now(), action="FORK")]
        state["revisions"].append(revision.model_dump())
        self.records.save(template_id, state, generation)
        return revision
