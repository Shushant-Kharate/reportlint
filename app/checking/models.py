from typing import Literal

from pydantic import Field

from app.models.template_analysis import AnalysisModel


class CheckItem(AnalysisModel):
    item_id: str
    rule_id: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    status: Literal["PASS", "FAIL", "NOT_CHECKED", "OUT_OF_SCOPE"]
    code: str
    message: str
    section_index: int | None = None
    source_path: str | None = None
    expected: dict | None = None
    actual: dict | None = None


class RevisionCheck(AnalysisModel):
    schema_version: Literal[2] = 2
    checker_version: Literal["0.1.0"] = "0.1.0"
    template_id: str
    revision_id: str
    snapshot_sha256: str
    report_sha256: str
    outcome: Literal["FAIL", "INDETERMINATE", "PASS_SUPPORTED_CHECKS"]
    counts: dict[str, int]
    items: list[CheckItem]
    limitations: list[str]
