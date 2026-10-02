"""Pure review/compilation operations, independent of database and HTTP."""
from datetime import datetime, timezone
from hashlib import sha256
import json

from app.analysis.template_requirements import property_key, same_value
from app.review.models import (
    AuditEvent, CompiledRule, Publication, ReviewPatch, ReviewRevision,
)


class ReviewError(Exception):
    def __init__(self, code, message, *, status=422, blockers=None):
        super().__init__(message)
        self.code = code
        self.status = status
        self.blockers = blockers or []


def now():
    return datetime.now(timezone.utc).isoformat()


def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def snapshot_hash(revision):
    value = revision.model_dump(exclude={"snapshot_sha256"})
    return sha256(canonical_json(value).encode("utf-8")).hexdigest()


def guard_edit(revision, expected_version):
    if revision.status != "DRAFT":
        raise ReviewError("IMMUTABLE_REVISION", "Published revisions cannot be changed. Create a new draft.", status=409)
    if revision.version != expected_version:
        raise ReviewError("REVISION_CONFLICT", "The draft changed. Reload it before editing.", status=409)


def apply_review(revision: ReviewRevision, patch: ReviewPatch):
    guard_edit(revision, patch.expected_version)
    candidate_ids = {c.candidate_id for c in revision.analysis.candidates}
    evidence_ids = {entry.evidence_id for entry in revision.analysis.requirement_ledger}
    for values, field, allowed in ((patch.candidates, "candidate_id", candidate_ids),
                                   (patch.ledger, "evidence_id", evidence_ids)):
        ids = [getattr(item, field) for item in values]
        if len(ids) != len(set(ids)) or not set(ids) <= allowed:
            raise ReviewError("INVALID_DECISION", "Decisions must refer to unique existing review items.")
    profile = patch.profile
    if profile is not None:
        profiles = {p.profile_id: p for p in revision.analysis.profiles}
        if profile.profile_id is None:
            if profile.chapters:
                raise ReviewError("INVALID_PROFILE", "A declined profile cannot have chapter rules.")
        else:
            selected = profiles.get(profile.profile_id)
            if selected is None:
                raise ReviewError("INVALID_PROFILE", "Choose a profile from this extraction.")
            indices = [c.index for c in profile.chapters]
            if sorted(indices) != list(range(len(selected.chapters))):
                raise ReviewError("INVALID_PROFILE", "Review each chapter exactly once, including optional chapters.")
            names = [c.name.casefold() for c in profile.chapters]
            if len(names) != len(set(names)):
                raise ReviewError("INVALID_PROFILE", "Reviewed chapter names must be distinct within this profile.")
            owners = {}
            for chapter in profile.chapters:
                for text in [chapter.name, *chapter.aliases]:
                    token = " ".join(text.casefold().split())
                    if token in owners and owners[token] != chapter.index:
                        raise ReviewError("INVALID_PROFILE", "An alias cannot identify two different chapters.")
                    owners[token] = chapter.index
    # Work on a validated copy so rejected edits cannot mutate the caller.
    result = ReviewRevision.model_validate(revision.model_dump())
    decisions = {c.candidate_id: c for c in result.candidate_decisions}
    decisions.update({c.candidate_id: c for c in patch.candidates})
    result.candidate_decisions = list(decisions.values())
    ledger = {c.evidence_id: c for c in result.ledger_decisions}
    ledger.update({c.evidence_id: c for c in patch.ledger})
    result.ledger_decisions = list(ledger.values())
    if profile is not None:
        result.profile_review = profile
    result.version += 1
    result.audit.append(AuditEvent(version=result.version, timestamp=now(), action="REVIEW", patch=patch))
    return result


def publication_blockers(revision):
    decisions = {d.candidate_id: d for d in revision.candidate_decisions}
    ledger = {d.evidence_id: d for d in revision.ledger_decisions}
    blockers = []
    for candidate in revision.analysis.candidates:
        if candidate.candidate_id not in decisions:
            blockers.append({"code": "UNREVIEWED_CANDIDATE", "id": candidate.candidate_id})
    for item in revision.analysis.requirement_ledger:
        if item.evidence_id not in ledger:
            blockers.append({"code": "UNREVIEWED_REQUIREMENT", "id": item.evidence_id})
    if revision.analysis.profiles and revision.profile_review is None:
        blockers.append({"code": "PROFILE_REVIEW_REQUIRED"})
    approved = [c for c in revision.analysis.candidates
                if c.candidate_id in decisions and decisions[c.candidate_id].action == "APPROVE"]
    # Check actual approved assertions as well as the extracted conflict list.
    for index, left in enumerate(approved):
        for right in approved[index + 1:]:
            if property_key(left) == property_key(right) and not same_value(left, right):
                blockers.append({"code": "CONFLICTING_APPROVALS", "candidate_ids": [left.candidate_id, right.candidate_id]})
    if not approved and not (revision.profile_review and revision.profile_review.chapters):
        blockers.append({"code": "EMPTY_SPECIFICATION"})
    return blockers


def compile_publication(revision):
    blockers = publication_blockers(revision)
    if blockers:
        raise ReviewError("PUBLICATION_BLOCKED", "Complete the review and resolve conflicting approvals.", status=409, blockers=blockers)
    decisions = {d.candidate_id: d for d in revision.candidate_decisions}
    approved = [c for c in revision.analysis.candidates if decisions[c.candidate_id].action == "APPROVE"]
    rules = []
    for candidate in approved:
        previous = next((r for r in rules if r.scope == candidate.scope
                         and r.condition == candidate.condition and same_value(r, candidate)), None)
        if previous:
            previous.candidate_ids.append(candidate.candidate_id)
            previous.evidence_ids = list(dict.fromkeys(previous.evidence_ids + candidate.evidence_ids))
            continue
        key = "|".join((*property_key(candidate), candidate.condition))
        readiness = ("UNSUPPORTED_CONDITION" if candidate.condition != "ALWAYS" else
                     "PENDING_BODY_SCOPE" if candidate.scope == "body" else "PROPERTY_CONTRACT")
        rules.append(CompiledRule(
            rule_id="rule-" + sha256(key.encode()).hexdigest()[:20],
            candidate_ids=[candidate.candidate_id], evidence_ids=candidate.evidence_ids,
            scope=candidate.scope, condition=candidate.condition, value=candidate.value,
            readiness=readiness,
        ))
    return Publication(
        compiler_version="0.2.0", report_checking_available=True,
        rules=rules, profile=revision.profile_review,
        deferred_candidate_ids=[d.candidate_id for d in revision.candidate_decisions if d.action == "DEFER"],
        requirement_dispositions=revision.ledger_decisions,
        limitations=[
            "This is a reviewed specification snapshot, not a compliance result. V2 checking supports explicit section page settings only; consult live capabilities.",
            "PROPERTY_CONTRACT indicates compiled values only, not a completed validator or verified physical geometry.",
            "Body scopes and conditional rules retain their missing execution capabilities; no condition was flattened.",
            "Extracted requirement coverage is incomplete. Acknowledging partial evidence does not approve every instruction in that source paragraph.",
            "Chapter topics and aliases require further semantic validation; choosing a profile does not prove its report structure can be checked yet.",
        ],
    )


def publish(revision, expected_version):
    guard_edit(revision, expected_version)
    result = ReviewRevision.model_validate(revision.model_dump())
    result.publication = compile_publication(result)
    result.status = "PUBLISHED"
    result.version += 1
    result.audit.append(AuditEvent(version=result.version, timestamp=now(), action="PUBLISH"))
    result.snapshot_sha256 = snapshot_hash(result)
    return result
