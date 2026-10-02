from typing import Literal

from pydantic import Field, model_validator

from app.models.template_analysis import AnalysisModel, RequirementValue, TemplateAnalysis


class CandidateDecision(AnalysisModel):
    candidate_id: str
    action: Literal["APPROVE", "REJECT", "DEFER"]
    reason: str = Field(min_length=5, max_length=2000)


class LedgerDecision(AnalysisModel):
    evidence_id: str
    action: Literal["ACKNOWLEDGED_PARTIAL", "DEFERRED", "MANUAL", "OUT_OF_SCOPE"]
    reason: str = Field(min_length=5, max_length=2000)


class ChapterReview(AnalysisModel):
    index: int = Field(ge=0)
    name: str = Field(min_length=1, max_length=200)
    aliases: list[str] = Field(default_factory=list, max_length=20)
    required: bool

    @model_validator(mode="after")
    def aliases_nonempty(self):
        if any(not alias.strip() or len(alias) > 200 for alias in self.aliases):
            raise ValueError("Chapter aliases must be nonempty and at most 200 characters")
        return self


class ProfileReview(AnalysisModel):
    profile_id: str | None
    reason: str = Field(min_length=5, max_length=2000)
    chapters: list[ChapterReview] = Field(default_factory=list, max_length=500)


class ReviewPatch(AnalysisModel):
    expected_version: int = Field(ge=0)
    candidates: list[CandidateDecision] = Field(default_factory=list, max_length=500)
    ledger: list[LedgerDecision] = Field(default_factory=list, max_length=20000)
    profile: ProfileReview | None = None


class VersionRequest(AnalysisModel):
    expected_version: int = Field(ge=0)


class CompiledRule(AnalysisModel):
    rule_id: str
    candidate_ids: list[str]
    evidence_ids: list[str]
    scope: Literal["body", "document"]
    condition: Literal["ALWAYS", "HEADER_ABSENT"]
    value: RequirementValue
    readiness: Literal["PROPERTY_CONTRACT", "PENDING_BODY_SCOPE", "UNSUPPORTED_CONDITION"]


class Publication(AnalysisModel):
    compiler_version: Literal["0.1.0"] = "0.1.0"
    rules: list[CompiledRule]
    profile: ProfileReview | None = None
    deferred_candidate_ids: list[str]
    requirement_dispositions: list[LedgerDecision]
    limitations: list[str]
    report_checking_available: Literal[False] = False


class AuditEvent(AnalysisModel):
    version: int
    timestamp: str
    action: Literal["CREATE", "REVIEW", "PUBLISH", "FORK"]
    patch: ReviewPatch | None = None


class ReviewRevision(AnalysisModel):
    schema_version: Literal[2] = 2
    template_id: str
    revision_id: str
    revision_number: int = Field(ge=1)
    parent_revision_id: str | None = None
    name: str
    status: Literal["DRAFT", "PUBLISHED"] = "DRAFT"
    version: int = 0
    analysis: TemplateAnalysis
    candidate_decisions: list[CandidateDecision] = Field(default_factory=list)
    ledger_decisions: list[LedgerDecision] = Field(default_factory=list)
    profile_review: ProfileReview | None = None
    audit: list[AuditEvent] = Field(default_factory=list)
    publication: Publication | None = None
    snapshot_sha256: str | None = None
