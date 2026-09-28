from app.models.document_model import DocumentModel
from app.models.rule_model import RuleSet, RuleType
from app.models.result_model import ComplianceResult
from app.compliance.validators.typography import (
    FontFamilyValidator, FontSizeValidator, BoldValidator, ItalicValidator)
from app.compliance.validators.paragraph import (
    AlignmentValidator, LineSpacingValidator, ParagraphSpacingValidator, IndentationValidator)
from app.compliance.validators.page import PageSizeValidator, MarginValidator
from app.compliance.validators.structure import StructureValidator
from app.compliance.scoring import compute_scores

VALIDATOR_REGISTRY = {
    RuleType.FONT_FAMILY: FontFamilyValidator(),
    RuleType.FONT_SIZE: FontSizeValidator(),
    RuleType.BOLD: BoldValidator(),
    RuleType.ITALIC: ItalicValidator(),
    RuleType.ALIGNMENT: AlignmentValidator(),
    RuleType.LINE_SPACING_MULTIPLE: LineSpacingValidator(),
    RuleType.LINE_SPACING_EXACT: LineSpacingValidator(),
    RuleType.SPACING_BEFORE: ParagraphSpacingValidator(),
    RuleType.SPACING_AFTER: ParagraphSpacingValidator(),
    RuleType.INDENTATION: IndentationValidator(),
    RuleType.PAGE_SIZE: PageSizeValidator(),
    RuleType.MARGIN: MarginValidator(),
}

RULE_TYPE_TO_CATEGORY = {
    RuleType.FONT_FAMILY: "TYPOGRAPHY", RuleType.FONT_SIZE: "TYPOGRAPHY",
    RuleType.BOLD: "TYPOGRAPHY", RuleType.ITALIC: "TYPOGRAPHY",
    RuleType.ALIGNMENT: "PARAGRAPH_FORMATTING",
    RuleType.LINE_SPACING_MULTIPLE: "PARAGRAPH_FORMATTING",
    RuleType.LINE_SPACING_EXACT: "PARAGRAPH_FORMATTING",
    RuleType.SPACING_BEFORE: "PARAGRAPH_FORMATTING",
    RuleType.SPACING_AFTER: "PARAGRAPH_FORMATTING",
    RuleType.INDENTATION: "PARAGRAPH_FORMATTING",
    RuleType.PAGE_SIZE: "PAGE_LAYOUT", RuleType.MARGIN: "PAGE_LAYOUT",
    RuleType.CAPTION_PRESENCE: "CAPTIONS_NUMBERING",
}


class ComplianceEngine:
    def __init__(self, ruleset: RuleSet):
        self.ruleset = ruleset

    def run(self, doc: DocumentModel) -> ComplianceResult:
        all_rules = (self.ruleset.typography_rules
                     + self.ruleset.paragraph_rules
                     + self.ruleset.page_rules)

        violations = []
        category_checks: dict[str, int] = {}

        for rule in all_rules:
            # Only apply rules the teacher (or auto-extraction) actually
            # proposed with enough confidence to enforce — INFO-severity
            # unresolved rules are informational only, not enforced.
            if rule.severity.value == "INFO":
                continue
            validator = VALIDATOR_REGISTRY.get(rule.type)
            if validator is None:
                continue
            v, checks = validator.validate(doc, rule)
            violations.extend(v)
            category = RULE_TYPE_TO_CATEGORY.get(rule.type, "TYPOGRAPHY")
            category_checks[category] = category_checks.get(category, 0) + checks

        struct_violations, struct_checks = StructureValidator().validate(
            doc, self.ruleset.structure_rules)
        violations.extend(struct_violations)
        category_checks["STRUCTURE"] = category_checks.get("STRUCTURE", 0) + struct_checks

        overall, category_scores = compute_scores(violations, category_checks)

        total_errors = sum(v.affected_count for v in violations if v.severity.value == "ERROR")
        total_warnings = sum(v.affected_count for v in violations if v.severity.value == "WARNING")
        total_checks = sum(category_checks.values())
        total_passed = max(0, total_checks - total_errors - total_warnings)

        return ComplianceResult(
            overall_score=overall,
            category_scores=category_scores,
            violations=violations,
            total_checks_passed=total_passed,
            total_errors=total_errors,
            total_warnings=total_warnings,
        )
