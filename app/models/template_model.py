from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, Field
import uuid

from app.models.rule_model import RuleSet


class TemplateStatus(str, Enum):
    DRAFT = "DRAFT"          # extracted, awaiting teacher review
    PUBLISHED = "PUBLISHED"  # teacher confirmed, usable for checking reports


class Template(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str
    source_filename: str
    status: TemplateStatus = TemplateStatus.DRAFT
    ruleset: RuleSet
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class TemplateSummary(BaseModel):
    """Lightweight listing shape — omits the full ruleset."""
    id: str
    name: str
    source_filename: str
    status: TemplateStatus
    created_at: str
    rule_count: int
