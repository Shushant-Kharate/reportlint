from enum import Enum
from pydantic import BaseModel, model_validator
import math


class RuleType(str, Enum):
    FONT_FAMILY = "FONT_FAMILY"
    FONT_SIZE = "FONT_SIZE"
    BOLD = "BOLD"
    ITALIC = "ITALIC"
    ALIGNMENT = "ALIGNMENT"
    LINE_SPACING_MULTIPLE = "LINE_SPACING_MULTIPLE"
    LINE_SPACING_EXACT = "LINE_SPACING_EXACT"
    SPACING_BEFORE = "SPACING_BEFORE"
    SPACING_AFTER = "SPACING_AFTER"
    INDENTATION = "INDENTATION"
    PAGE_SIZE = "PAGE_SIZE"
    MARGIN = "MARGIN"
    REQUIRED_SECTION = "REQUIRED_SECTION"
    SECTION_ORDER = "SECTION_ORDER"
    HEADING_STYLE = "HEADING_STYLE"
    CAPTION_PRESENCE = "CAPTION_PRESENCE"


class Severity(str, Enum):
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


class RuleScope(str, Enum):
    DOCUMENT = "DOCUMENT"
    BODY = "BODY"
    HEADING_1 = "HEADING_1"
    HEADING_2 = "HEADING_2"
    HEADING_3 = "HEADING_3"
    SPECIFIC_SECTION = "SPECIFIC_SECTION"


class Rule(BaseModel):
    id: str
    type: RuleType
    scope: RuleScope
    section_ref: str | None = None
    expected_value: dict
    tolerance: dict | None = None
    severity: Severity
    weight: float = 1.0
    source_confidence: float = 0.0
    inference_note: str = ""
    teacher_confirmed: bool = False


    @model_validator(mode="after")
    def validate_expected(self):
        if self.severity == Severity.INFO:
            return self
        fields = {
            "FONT_FAMILY": {"font": str}, "FONT_SIZE": {"size_pt": float},
            "BOLD": {"bold": bool}, "ITALIC": {"italic": bool},
            "ALIGNMENT": {"alignment": str}, "LINE_SPACING_MULTIPLE": {"multiplier": float},
            "LINE_SPACING_EXACT": {"pt": float}, "SPACING_BEFORE": {"before_pt": float},
            "SPACING_AFTER": {"after_pt": float}, "INDENTATION": {"first_line_indent_pt": float},
            "PAGE_SIZE": {"width_pt": float, "height_pt": float},
            "MARGIN": {key: float for key in self.expected_value},
        }
        required = fields.get(self.type.value)
        if required is None:
            raise ValueError(f"{self.type.value} is not supported; keep it informational")
        if not required or (self.type == RuleType.MARGIN and not set(required) <= {"top", "bottom", "left", "right"}):
            raise ValueError("Specify valid margin sides")
        for key, kind in required.items():
            value = self.expected_value.get(key)
            if kind is float:
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                    raise ValueError(f"{key} must be a finite number")
                if key != "first_line_indent_pt" and value < 0:
                    raise ValueError(f"{key} cannot be negative")
                if key in {"size_pt", "multiplier", "pt", "width_pt", "height_pt"} and value == 0:
                    raise ValueError(f"{key} must be positive")
            elif not isinstance(value, kind) or (kind is str and not value.strip()):
                raise ValueError(f"{key} requires a value of type {kind.__name__}")
        if self.type == RuleType.ALIGNMENT and self.expected_value["alignment"] not in {"left", "right", "center", "justify"}:
            raise ValueError("Invalid alignment")
        if self.scope == RuleScope.SPECIFIC_SECTION and not self.section_ref:
            raise ValueError("A specific section rule needs section_ref")
        for value in (self.tolerance or {}).values():
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                raise ValueError("Tolerance must be finite and nonnegative")
        return self


class RequiredSectionRule(BaseModel):
    canonical_name: str
    aliases: list[str] = []
    required: bool = True
    order_index: int
    parent: str | None = None
    severity: Severity = Severity.ERROR


class RuleSet(BaseModel):
    template_source_filename: str
    typography_rules: list[Rule] = []
    paragraph_rules: list[Rule] = []
    page_rules: list[Rule] = []
    structure_rules: list[RequiredSectionRule] = []
    version: int = 1

    @model_validator(mode="after")
    def unique_rules(self):
        rules = self.typography_rules + self.paragraph_rules + self.page_rules
        if len({r.id for r in rules}) != len(rules):
            raise ValueError("Rule identifiers must be unique")
        names = [r.canonical_name.strip().casefold() for r in self.structure_rules]
        if any(not n for n in names) or len(set(names)) != len(names):
            raise ValueError("Section names must be nonempty and unique")
        return self
