from app.models.rule_model import Rule
from app.models.result_model import Violation, Location
from app.compliance.validators.base import Validator, paragraphs_in_scope, within_tolerance


def _group(offending, rule, category, message, expected, actual_fn):
    if not offending:
        return []
    preview = offending[0]
    return [Violation(
        rule_id=rule.id, severity=rule.severity, category=category, message=message,
        expected=expected, actual=actual_fn(preview),
        location=Location(paragraph_index=preview.index, text_preview=preview.text[:80]),
        affected_count=len(offending), affected_paragraph_indices=[p.index for p in offending],
    )]


class AlignmentValidator(Validator):
    def validate(self, doc, rule: Rule):
        expected = rule.expected_value.get("alignment")
        if expected is None:
            return [], 0
        checks, offending = 0, []
        for p in paragraphs_in_scope(doc, rule.scope, rule.section_ref):
            if p.alignment.value == "unknown":
                continue
            checks += 1
            if p.alignment.value != expected:
                offending.append(p)
        return _group(offending, rule, "PARAGRAPH_FORMATTING",
                       f"Alignment expected={expected}", {"alignment": expected},
                       lambda p: {"alignment": p.alignment.value}), checks


class LineSpacingValidator(Validator):
    def validate(self, doc, rule: Rule):
        exact = rule.type.value == "LINE_SPACING_EXACT"
        key = "pt" if exact else "multiplier"
        expected = rule.expected_value.get(key)
        if expected is None:
            return [], 0
        checks, offending = 0, []
        for p in paragraphs_in_scope(doc, rule.scope, rule.section_ref):
            if p.line_spacing is None and p.line_spacing_exact_pt is None:
                continue
            checks += 1
            actual = p.line_spacing_exact_pt if exact else p.line_spacing
            correct_mode = p.line_spacing_rule == "exact" if exact else p.line_spacing_rule in ("auto", None)
            if not correct_mode or actual is None or not within_tolerance(actual, expected, (rule.tolerance or {}).get("pt", .25) if exact else .05):
                offending.append(p)
        return _group(offending, rule, "PARAGRAPH_FORMATTING",
                      f"Line spacing expected={expected}{'pt (exact)' if exact else 'x'}", {key: expected},
                      lambda p: {"mode": p.line_spacing_rule, "pt": p.line_spacing_exact_pt, "multiplier": p.line_spacing}), checks


class ParagraphSpacingValidator(Validator):
    """Handles SPACING_BEFORE / SPACING_AFTER via rule.type."""
    def validate(self, doc, rule: Rule):
        key = "before_pt" if rule.type.value == "SPACING_BEFORE" else "after_pt"
        attr = "spacing_before_pt" if key == "before_pt" else "spacing_after_pt"
        expected = rule.expected_value.get(key)
        if expected is None:
            return [], 0
        tol = (rule.tolerance or {}).get("pt", 1.0)
        checks, offending = 0, []
        for p in paragraphs_in_scope(doc, rule.scope, rule.section_ref):
            val = getattr(p, attr)
            if val is None:
                continue
            checks += 1
            if not within_tolerance(val, expected, tol):
                offending.append(p)
        return _group(offending, rule, "PARAGRAPH_FORMATTING",
                       f"{key} expected={expected}pt", {key: expected},
                       lambda p: {key: getattr(p, attr)}), checks


class IndentationValidator(Validator):
    def validate(self, doc, rule: Rule):
        expected = rule.expected_value.get("first_line_indent_pt")
        if expected is None:
            return [], 0
        tol = (rule.tolerance or {}).get("pt", 2.0)
        checks, offending = 0, []
        for p in paragraphs_in_scope(doc, rule.scope, rule.section_ref):
            if p.first_line_indent_pt is None:
                continue
            checks += 1
            if not within_tolerance(p.first_line_indent_pt, expected, tol):
                offending.append(p)
        return _group(offending, rule, "PARAGRAPH_FORMATTING",
                       f"First-line indent expected={expected}pt",
                       {"first_line_indent_pt": expected},
                       lambda p: {"first_line_indent_pt": p.first_line_indent_pt}), checks
