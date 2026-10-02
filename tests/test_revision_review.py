from concurrent.futures import ThreadPoolExecutor
import json
import sqlite3

from docx import Document
from fastapi.testclient import TestClient
import pytest

from app.analysis.service import analyze_bytes
from app.main import app
from app.review.api import get_repository
from app.review.models import CandidateDecision, LedgerDecision, ProfileReview, ChapterReview, ReviewPatch
from app.review.repository import RevisionRepository
from app.review.service import ReviewError, apply_review, publish, snapshot_hash
from tests.test_template_analysis import complex_format, encoded


@pytest.fixture
def repository(tmp_path):
    return RevisionRepository(tmp_path / "review.sqlite3")


@pytest.fixture
def client(repository):
    app.dependency_overrides[get_repository] = lambda: repository
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_repository, None)


@pytest.fixture
def draft(repository):
    return repository.create("Synthetic format", analyze_bytes(encoded(complex_format())))


def complete_patch(draft, *, conditional=False):
    candidates = []
    for c in draft.analysis.candidates:
        action = "APPROVE" if c.origin == "EXPLICIT_PROSE" else "REJECT"
        if c.value.kind == "margin" and c.value.side == "top" and c.origin == "EXPLICIT_PROSE":
            action = "APPROVE" if (c.condition == "HEADER_ABSENT") == conditional else "DEFER"
        candidates.append(CandidateDecision(candidate_id=c.candidate_id, action=action, reason="Synthetic reviewer decision for this test profile."))
    profile = draft.analysis.profiles[0]
    return ReviewPatch(
        expected_version=draft.version, candidates=candidates,
        ledger=[LedgerDecision(evidence_id=e.evidence_id, action="MANUAL" if e.status == "MANUAL_REVIEW" else "DEFERRED", reason="Other instructions remain for later review; this is partial coverage.") for e in draft.analysis.requirement_ledger],
        profile=ProfileReview(profile_id=profile.profile_id, reason="Use the report index; synopsis and suggested subtopics are not approved.", chapters=[ChapterReview(index=i, name=c.title, required=True) for i, c in enumerate(profile.chapters)]),
    )


def reviewed(repository, draft, **kwargs):
    return repository.change(draft.template_id, draft.revision_id, apply_review, complete_patch(draft, **kwargs))


def test_upload_persists_extraction_without_publishing(client, repository):
    response = client.post("/api/v2/templates", files={"file": ("format.docx", encoded(complex_format()))}, data={"name": "Draft test"})
    assert response.status_code == 201
    value = response.json()
    assert value["status"] == "DRAFT"
    assert value["snapshot_sha256"] is None
    loaded = RevisionRepository(repository.path).get(value["template_id"], value["revision_id"])
    assert loaded.analysis.model_dump() == value["analysis"]
    assert client.get("/api/v2/templates").json()[0]["published_revision_id"] is None


def test_unreviewed_publication_blocked_with_no_mutation(repository, draft):
    with pytest.raises(ReviewError) as error:
        repository.change(draft.template_id, draft.revision_id, publish, 0)
    assert error.value.code == "PUBLICATION_BLOCKED"
    assert {b["code"] for b in error.value.blockers} >= {"UNREVIEWED_CANDIDATE", "UNREVIEWED_REQUIREMENT", "PROFILE_REVIEW_REQUIRED"}
    assert repository.get(draft.template_id, draft.revision_id).model_dump() == draft.model_dump()


def test_review_and_publish_preserves_reasons_evidence_and_hash(repository, draft):
    edited = reviewed(repository, draft)
    result = repository.change(draft.template_id, draft.revision_id, publish, edited.version)
    assert result.status == "PUBLISHED"
    assert result.version == 2
    assert result.snapshot_sha256 == snapshot_hash(result)
    assert result.publication.report_checking_available is True
    assert result.publication.deferred_candidate_ids
    assert result.publication.requirement_dispositions
    assert [e.action for e in result.audit] == ["CREATE", "REVIEW", "PUBLISH"]
    assert result.audit[1].patch.candidates[0].reason
    assert repository.get(draft.template_id, draft.revision_id).model_dump() == result.model_dump()
    assert repository.list_templates()[0]["published_revision_id"] == result.revision_id


def test_conflicting_approvals_block_publish(repository, draft):
    patch = complete_patch(draft)
    observed_size = next(c for c in draft.analysis.candidates if c.origin == "OBSERVED_APPEARANCE" and c.value.kind == "font_size")
    next(d for d in patch.candidates if d.candidate_id == observed_size.candidate_id).action = "APPROVE"
    edited = repository.change(draft.template_id, draft.revision_id, apply_review, patch)
    with pytest.raises(ReviewError) as error:
        repository.change(draft.template_id, draft.revision_id, publish, edited.version)
    assert any(b["code"] == "CONFLICTING_APPROVALS" for b in error.value.blockers)
    assert repository.get(draft.template_id, draft.revision_id).status == "DRAFT"


def test_equivalent_approved_values_do_not_duplicate_rules(repository, draft):
    patch = complete_patch(draft)
    font = next(c for c in draft.analysis.candidates if c.origin == "OBSERVED_APPEARANCE" and c.value.kind == "font_family")
    next(d for d in patch.candidates if d.candidate_id == font.candidate_id).action = "APPROVE"
    edited = repository.change(draft.template_id, draft.revision_id, apply_review, patch)
    result = repository.change(draft.template_id, draft.revision_id, publish, edited.version)
    rules = [r for r in result.publication.rules if r.value.kind == "font_family"]
    assert len(rules) == 1
    assert len(rules[0].candidate_ids) == 2
    assert len(rules[0].evidence_ids) == 2


def test_conditional_rules_are_retained_as_unsupported(repository, draft):
    edited = reviewed(repository, draft, conditional=True)
    result = repository.change(draft.template_id, draft.revision_id, publish, edited.version)
    conditional = [r for r in result.publication.rules if r.condition == "HEADER_ABSENT"]
    assert len(conditional) == 1
    assert conditional[0].readiness == "UNSUPPORTED_CONDITION"
    assert conditional[0].value.expected_pt == pytest.approx(30 * 72 / 25.4)
    assert all(r.readiness == "PENDING_BODY_SCOPE" for r in result.publication.rules if r.scope == "body")


def test_stale_edits_and_simultaneous_writers_are_not_lost(repository, draft):
    patch = ReviewPatch(expected_version=0, candidates=[CandidateDecision(candidate_id=draft.analysis.candidates[0].candidate_id, action="DEFER", reason="Need a teacher to clarify this value.")])
    def write():
        try:
            return repository.change(draft.template_id, draft.revision_id, apply_review, patch).version
        except ReviewError as error:
            return error.code
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: write(), range(2)))
    assert sorted(map(str, results)) == ["1", "REVISION_CONFLICT"]
    assert len(repository.get(draft.template_id, draft.revision_id).audit) == 2


def test_published_snapshots_immutable_in_domain_and_database(repository, draft):
    edited = reviewed(repository, draft)
    result = repository.change(draft.template_id, draft.revision_id, publish, edited.version)
    with pytest.raises(ReviewError) as error:
        repository.change(draft.template_id, draft.revision_id, apply_review, ReviewPatch(expected_version=result.version))
    assert error.value.code == "IMMUTABLE_REVISION"
    with repository.connection() as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("UPDATE revisions SET version=999 WHERE id=?", (result.revision_id,))
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("DELETE FROM revisions WHERE id=?", (result.revision_id,))
    assert repository.get(draft.template_id, draft.revision_id).snapshot_sha256 == result.snapshot_sha256


def test_fork_preserves_original_and_publication_pointer(repository, draft):
    edited = reviewed(repository, draft)
    original = repository.change(draft.template_id, draft.revision_id, publish, edited.version)
    child = repository.fork(original.template_id, original.revision_id)
    assert child.revision_number == 2 and child.version == 0
    assert child.parent_revision_id == original.revision_id
    assert child.publication is None and child.snapshot_sha256 is None
    assert child.candidate_decisions == original.candidate_decisions
    assert repository.list_templates()[0]["published_revision_id"] == original.revision_id
    republished = repository.change(child.template_id, child.revision_id, publish, 0)
    assert republished.snapshot_sha256 != original.snapshot_sha256
    assert repository.get(original.template_id, original.revision_id).model_dump() == original.model_dump()
    assert repository.list_templates()[0]["published_revision_id"] == child.revision_id


@pytest.mark.parametrize("kind", ["missing_candidate", "duplicate_candidate", "missing_evidence", "missing_profile", "missing_chapter", "ambiguous_alias"])
def test_invalid_review_does_not_write_partial_edits(repository, draft, kind):
    patch = complete_patch(draft)
    if kind == "missing_candidate":
        patch.candidates[0].candidate_id = "missing"
    elif kind == "duplicate_candidate":
        patch.candidates.append(patch.candidates[0])
    elif kind == "missing_evidence":
        patch.ledger[0].evidence_id = "missing"
    elif kind == "missing_profile":
        patch.profile.profile_id = "missing"
    elif kind == "missing_chapter":
        patch.profile.chapters.pop()
    else:
        patch.profile.chapters[1].aliases = [patch.profile.chapters[0].name]
    with pytest.raises(ReviewError):
        repository.change(draft.template_id, draft.revision_id, apply_review, patch)
    assert repository.get(draft.template_id, draft.revision_id).model_dump() == draft.model_dump()


def test_api_errors_version_and_revision_ownership(client, draft):
    base = f"/api/v2/templates/{draft.template_id}/revisions/{draft.revision_id}"
    assert client.get(base + "/blockers").json()["can_publish"] is False
    response = client.post(base + "/publish", json={"expected_version": 0})
    assert response.status_code == 409 and response.json()["detail"]["code"] == "PUBLICATION_BLOCKED"
    response = client.patch(base, json={"expected_version": 0, "candidates": [{"candidate_id": "bad", "action": "APPROVE", "reason": "test reason"}]})
    assert response.status_code == 422
    response = client.patch(base, json={"expected_version": 0, "candidates": [], "execute": "arbitrary operation"})
    assert response.status_code == 422
    assert client.get(base.replace(draft.template_id, "other-template")).status_code == 404


def test_api_complete_review_fork_flow(client, draft):
    base = f"/api/v2/templates/{draft.template_id}/revisions/{draft.revision_id}"
    edited = client.patch(base, json=complete_patch(draft).model_dump())
    assert edited.status_code == 200
    assert client.get(base + "/blockers").json()["can_publish"] is True
    response = client.post(base + "/publish", json={"expected_version": edited.json()["version"]})
    assert response.status_code == 200
    assert response.json()["snapshot_sha256"]
    assert client.get(base + "/blockers").json()["can_publish"] is False
    assert client.patch(base, json={"expected_version": 2}).status_code == 409
    child = client.post(base + "/fork")
    assert child.status_code == 201
    assert len(client.get(f"/api/v2/templates/{draft.template_id}/revisions").json()) == 2


def test_future_database_version_not_overwritten(repository):
    with repository.connection() as connection:
        connection.execute("PRAGMA user_version = 99")
    with pytest.raises(ReviewError) as error:
        repository.list_templates()
    assert error.value.code == "UNSUPPORTED_DATABASE_VERSION"


def test_empty_specification_cannot_publish(repository):
    d = Document()
    d.add_paragraph("A short ordinary sample.")
    draft = repository.create("Empty selection", analyze_bytes(encoded(d)))
    patch = ReviewPatch(expected_version=0, candidates=[CandidateDecision(candidate_id=c.candidate_id, action="REJECT", reason="No normative evidence for this example.") for c in draft.analysis.candidates])
    updated = repository.change(draft.template_id, draft.revision_id, apply_review, patch)
    with pytest.raises(ReviewError) as error:
        repository.change(draft.template_id, draft.revision_id, publish, updated.version)
    assert {b["code"] for b in error.value.blockers} == {"EMPTY_SPECIFICATION"}


def test_reviewed_values_do_not_hide_unreviewed_requirements(repository, draft):
    patch = complete_patch(draft)
    patch.ledger = []
    patch.profile = None
    updated = repository.change(draft.template_id, draft.revision_id, apply_review, patch)
    with pytest.raises(ReviewError) as error:
        repository.change(draft.template_id, draft.revision_id, publish, updated.version)
    assert {b["code"] for b in error.value.blockers} == {"UNREVIEWED_REQUIREMENT", "PROFILE_REVIEW_REQUIRED"}


def test_corrupted_published_snapshot_is_detected(repository, draft):
    edited = reviewed(repository, draft)
    result = repository.change(draft.template_id, draft.revision_id, publish, edited.version)
    # Simulate out-of-band file tampering, bypassing the normal SQL guard.
    with repository.connection() as connection:
        connection.execute("DROP TRIGGER immutable_publication")
        value = result.model_dump()
        value["name"] = "Tampered name"
        connection.execute("UPDATE revisions SET document_json=? WHERE id=?", (json.dumps(value), result.revision_id))
    with pytest.raises(ReviewError) as error:
        repository.get(result.template_id, result.revision_id)
    assert error.value.code == "SNAPSHOT_INTEGRITY_ERROR"
