from pydantic import BaseModel
from app.models.rule_model import Severity


class Location(BaseModel):
    section: str | None = None
    paragraph_index: int | None = None
    table_index: int | None = None
    text_preview: str | None = None
    estimated_page: int | None = None  # always null until Section 10 exists


class Violation(BaseModel):
    rule_id: str
    severity: Severity
    category: str
    message: str
    expected: dict
    actual: dict | None = None
    location: Location = Location()
    affected_count: int = 1
    affected_paragraph_indices: list[int] = []


class CategoryScore(BaseModel):
    category: str
    score: float
    checks_performed: int
    error_count: int
    warning_count: int


class ComplianceResult(BaseModel):
    overall_score: float
    category_scores: list[CategoryScore]
    violations: list[Violation]
    total_checks_passed: int
    total_errors: int
    total_warnings: int
