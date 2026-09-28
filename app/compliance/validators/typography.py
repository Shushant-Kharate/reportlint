from app.models.document_model import Confidence
from app.models.rule_model import Rule, Severity
from app.models.result_model import Violation, Location
from app.compliance.validators.base import Validator, paragraphs_in_scope, within_tolerance


def _group_violations(offending: list[tuple], rule: Rule, category: str, message: str,
                       expected: dict, actual_fn) -> list[Violation]:
    if not offending:
        return []
    indices = [p.index for p, _r in offending]
    preview_p, preview_r = offending[0]
    return [Violation(
        rule_id=rule.id, severity=rule.severity, category=category, message=message,
        expected=expected, actual=actual_fn(offending[0][1]),
        location=Location(paragraph_index=preview_p.index,
                           text_preview=preview_p.text[:80]),
        affected_count=len(indices), affected_paragraph_indices=list(dict.fromkeys(indices)),
    )]


class FontFamilyValidator(Validator):
    def validate(self, doc, rule: Rule):
        expected = rule.expected_value.get("font")
        if expected is None:
            return [], 0
        checks = 0
        offending = []
        for p in paragraphs_in_scope(doc, rule.scope, rule.section_ref):
            for r in p.runs:
                if r.font_name is None or not r.text.strip():
                    continue
                checks += 1
                if r.font_name and r.font_name != expected:
                    offending.append((p, r))
        violations = _group_violations(
            offending, rule, "TYPOGRAPHY", f"Incorrect body font (expected {expected})",
            {"font": expected}, lambda r: {"font": r.font_name})
        return violations, checks


class FontSizeValidator(Validator):
    def validate(self, doc, rule: Rule):
        expected = rule.expected_value.get("size_pt")
        if expected is None:
            return [], 0
        tol = (rule.tolerance or {}).get("pt", 0.25)
        checks = 0
        offending = []
        for p in paragraphs_in_scope(doc, rule.scope, rule.section_ref):
            for r in p.runs:
                if r.font_size_pt is None or not r.text.strip():
                    continue
                checks += 1
                if r.font_size_pt is not None and not within_tolerance(r.font_size_pt, expected, tol):
                    offending.append((p, r))
        violations = _group_violations(
            offending, rule, "TYPOGRAPHY", f"Incorrect font size (expected {expected}pt)",
            {"size_pt": expected}, lambda r: {"size_pt": r.font_size_pt})
        return violations, checks


class BoldValidator(Validator):
    def validate(self, doc, rule: Rule):
        expected = rule.expected_value.get("bold")
        if expected is None:
            return [], 0
        checks = 0
        offending = []
        for p in paragraphs_in_scope(doc, rule.scope, rule.section_ref):
            for r in p.runs:
                if r.bold is None or not r.text.strip():
                    continue
                checks += 1
                if r.bold is not None and r.bold != expected:
                    offending.append((p, r))
        violations = _group_violations(
            offending, rule, "TYPOGRAPHY", f"Bold expected={expected}",
            {"bold": expected}, lambda r: {"bold": r.bold})
        return violations, checks


class ItalicValidator(Validator):
    def validate(self, doc, rule: Rule):
        expected = rule.expected_value.get("italic")
        if expected is None:
            return [], 0
        checks = 0
        offending = []
        for p in paragraphs_in_scope(doc, rule.scope, rule.section_ref):
            for r in p.runs:
                if r.italic is None or not r.text.strip():
                    continue
                checks += 1
                if r.italic is not None and r.italic != expected:
                    offending.append((p, r))
        violations = _group_violations(
            offending, rule, "TYPOGRAPHY", f"Italic expected={expected}",
            {"italic": expected}, lambda r: {"italic": r.italic})
        return violations, checks
