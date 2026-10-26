from hashlib import sha256
from types import SimpleNamespace

from fastapi.testclient import TestClient
import pytest

from app.builtin_formats import CatalogRepository, builtin, DIRECTORY
from app.cloud import BlobRecords, WorkspaceMiddleware, COOKIE
from app.review.blob_repository import BlobRevisionRepository
from app.review.models import ReviewPatch
from app.review.repository import RevisionRepository
from app.review.service import ReviewError, apply_review, publish, snapshot_hash


class FakeBlob:
    def __init__(self):
        self.files = {}

    def query_blobs(self, prefix):
        return [SimpleNamespace(pathname=p) for p in self.files if p.startswith(prefix)]

    def get_blob(self, path, **kwargs):
        assert kwargs["access"] == "private"
        return SimpleNamespace(body=self.files[path])

    def put_blob(self, path, value, **kwargs):
        assert kwargs["access"] == "private" and kwargs["allow_overwrite"] is False
        if path in self.files:
            error = RuntimeError("Another writer saved this generation")
            error.status_code = 409
            raise error
        self.files[path] = value

    def delete_blob(self, paths):
        for p in paths:
            del self.files[p]


def records(sdk, owner="a" * 64):
    return BlobRecords("v2", owner=owner, sdk=sdk)


def test_private_records_persist_and_are_isolated():
    sdk = FakeBlob()
    first = records(sdk)
    first.save("format", {"name": "Private instructions"}, -1)
    assert records(sdk).get("format") == ({"name": "Private instructions"}, 0)
    assert records(sdk, "b" * 64).values() == []
    assert records(sdk, "b" * 64).get("format") == (None, -1)
    assert all("Private instructions" not in k for k in sdk.files)


def test_concurrent_saves_do_not_overwrite():
    sdk = FakeBlob()
    a, b = records(sdk), records(sdk)
    a.save("format", {"version": 0}, -1)
    _, generation = b.get("format")
    a.save("format", {"version": 1}, generation)
    with pytest.raises(ReviewError) as error:
        b.save("format", {"version": "lost edit"}, generation)
    assert error.value.code == "REVISION_CONFLICT"
    assert a.get("format")[0]["version"] == 1


def test_generation_listing_uses_numeric_order_and_not_cached_record():
    sdk = FakeBlob()
    store = records(sdk)
    for n in range(12):
        store.save("format", {"version": n}, n - 1)
    assert records(sdk).get("format") == ({"version": 11}, 11)


@pytest.mark.parametrize("message,expected", [
    ("This blob already exists, use `allowOverwrite: true` if you want to overwrite it.", "REVISION_CONFLICT"),
    ("Invalid upload options", "STORAGE_UNAVAILABLE"),
])
def test_sdk_generic_bad_request_classification(message, expected):
    from vercel.blob.errors import BlobError
    class RejectUpload(FakeBlob):
        def put_blob(self, *args, **kwargs):
            raise BlobError(message, status_code=400, code="bad_request")
    with pytest.raises(ReviewError) as exc:
        records(RejectUpload()).save("format", {}, -1)
    assert exc.value.code == expected


def test_cloud_revision_round_trip_publish_and_fork():
    sdk = FakeBlob()
    repo = BlobRevisionRepository(records(sdk))
    original = builtin()
    draft = repo.create("User format", original.analysis)
    patch = ReviewPatch(expected_version=0, candidates=original.candidate_decisions,
                        ledger=original.ledger_decisions, profile=original.profile_review)
    edited = repo.change(draft.template_id, draft.revision_id, apply_review, patch)
    published = repo.change(draft.template_id, draft.revision_id, publish, edited.version)
    other_process = BlobRevisionRepository(records(sdk))
    assert other_process.get(draft.template_id, draft.revision_id).snapshot_sha256 == snapshot_hash(published)
    assert other_process.list_templates()[0]["published_revision_id"] == draft.revision_id
    with pytest.raises(ReviewError):
        other_process.change(draft.template_id, draft.revision_id, publish, published.version)
    forked = other_process.fork(draft.template_id, draft.revision_id)
    assert forked.status == "DRAFT" and forked.revision_number == 2
    assert forked.parent_revision_id == draft.revision_id
    assert other_process.get(draft.template_id, draft.revision_id).model_dump() == published.model_dump()


def test_unreviewed_cloud_publication_is_blocked():
    repo = BlobRevisionRepository(records(FakeBlob()))
    draft = repo.create("Unreviewed", builtin().analysis)
    with pytest.raises(ReviewError) as error:
        repo.change(draft.template_id, draft.revision_id, publish, 0)
    assert error.value.code == "PUBLICATION_BLOCKED"
    assert repo.get(draft.template_id, draft.revision_id).status == "DRAFT"


def test_builtin_matches_source_and_copy_is_private_draft(tmp_path):
    catalog = CatalogRepository(RevisionRepository(tmp_path / "review.db"))
    source = builtin()
    assert sha256((DIRECTORY / "mini-project-1a.docx").read_bytes()).hexdigest() == source.analysis.source_sha256
    with pytest.raises(ReviewError) as error:
        catalog.change(source.template_id, source.revision_id, publish, source.version)
    assert error.value.code == "BUILTIN_READ_ONLY"
    copy = catalog.fork(source.template_id, source.revision_id)
    assert copy.template_id != source.template_id and copy.status == "DRAFT"
    assert copy.publication is None and copy.candidate_decisions == source.candidate_decisions
    assert catalog.get(source.template_id, source.revision_id).snapshot_sha256 == source.snapshot_sha256


def test_built_in_api_is_ready_to_check_and_source_downloads(tmp_path, monkeypatch):
    import app.main as main
    from app import storage
    monkeypatch.setattr(storage, "STORAGE_DIR", tmp_path)
    with TestClient(main.app) as client:
        templates = client.get("/api/v2/templates").json()
        entry = next(t for t in templates if t.get("builtin"))
        revision = client.get(f"/api/v2/templates/{entry['id']}/revisions/{entry['published_revision_id']}").json()
        assert revision["status"] == "PUBLISHED"
        download = client.get("/api/builtin-formats/mini-project-1a/source")
        assert download.status_code == 200
        assert sha256(download.content).hexdigest() == builtin().analysis.source_sha256


def test_workspace_cookie_and_cross_site_protection(monkeypatch):
    from fastapi import FastAPI
    from app.cloud import workspace
    monkeypatch.setenv("REPORTLINT_CLOUD", "1")
    app = FastAPI()
    app.add_middleware(WorkspaceMiddleware)

    @app.get("/api/who")
    def who():
        return {"workspace": workspace.get()}

    with TestClient(app) as first, TestClient(app) as second:
        response = first.get("/api/who")
        assert "HttpOnly" in response.headers["set-cookie"]
        assert "samesite=lax" in response.headers["set-cookie"].lower()
        a = response.json()["workspace"]
        assert first.get("/api/who").json()["workspace"] == a
        assert second.get("/api/who").json()["workspace"] != a
        assert first.post("/api/who", headers={"Origin": "https://another.example"}).status_code == 403
        assert first.post("/api/who", headers={"Content-Length": str(4 * 1024 * 1024 + 1)}).status_code == 413


def test_invalid_blob_identifiers_and_missing_workspace_are_rejected():
    with pytest.raises(ReviewError):
        BlobRecords("v2", owner="../../someone")
    with pytest.raises(ReviewError):
        records(FakeBlob()).get("../someone")
