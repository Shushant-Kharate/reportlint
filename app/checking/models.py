from typing import Literal

from pydantic import Field, model_validator

from app.models.template_analysis import AnalysisModel


class RoleDecision(AnalysisModel):
    paragraph_index: int = Field(ge=0)
    source_path: str = Field(min_length=1, max_length=1000)
    role: Literal["BODY", "CHAPTER", "EXCLUDE"]
    chapter_index: int | None = Field(default=None, ge=0)
    reason: str = Field(min_length=5, max_length=2000)

    @model_validator(mode="after")
    def chapter_binding(self):
        if (self.role == "CHAPTER") != (self.chapter_index is not None):
            raise ValueError("Only CHAPTER assignments require a chapter_index")
        return self


class ReportRoleReview(AnalysisModel):
    report_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    snapshot_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    decisions: list[RoleDecision] = Field(max_length=10000)


class CheckItem(AnalysisModel):
    item_id: str
    rule_id: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    status: Literal["PASS", "FAIL", "NOT_CHECKED", "OUT_OF_SCOPE"]
    code: str
    message: str
    section_index: int | None = None
    paragraph_index: int | None = None
    run_index: int | None = None
    source_path: str | None = None
    expected: dict | None = None
    actual: dict | None = None


class RevisionCheck(AnalysisModel):
    schema_version: Literal[2] = 2
    checker_version: Literal["0.4.0"] = "0.4.0"
    template_id: str
    revision_id: str
    snapshot_sha256: str
    report_sha256: str
    role_review_sha256: str | None = None
    role_decisions: list[RoleDecision] = Field(default_factory=list)
    outcome: Literal["FAIL", "INDETERMINATE", "PASS_SUPPORTED_CHECKS"]
    counts: dict[str, int]
    items: list[CheckItem]
    limitations: list[str]
