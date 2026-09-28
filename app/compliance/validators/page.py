from app.models.rule_model import Rule
from app.models.result_model import Violation, Location
from app.compliance.validators.base import Validator, within_tolerance


class PageSizeValidator(Validator):
    def validate(self, doc, rule: Rule):
        expected = rule.expected_value
        if expected.get("width_pt") is None or expected.get("height_pt") is None:
            return [], 0
        violations, checks = [], 0
        for index, sec in enumerate(doc.sections):
            if sec.page_width_pt is None or sec.page_height_pt is None:
                continue
            checks += 1
            actual = {"width_pt": sec.page_width_pt, "height_pt": sec.page_height_pt}
            if any(not within_tolerance(actual[k], expected[k], (rule.tolerance or {}).get("pt", 2)) for k in actual):
                violations.append(Violation(rule_id=rule.id, severity=rule.severity, category="PAGE_LAYOUT",
                    message="Page size does not match the template", expected=expected, actual=actual,
                    location=Location(section=f"Document section {index + 1}")))
        return violations, checks


class MarginValidator(Validator):
    def validate(self, doc, rule: Rule):
        violations, checks = [], 0
        for index, sec in enumerate(doc.sections):
            for side, expected in rule.expected_value.items():
                actual = getattr(sec, f"margin_{side}_pt", None)
                if actual is None:
                    continue
                checks += 1
                if not within_tolerance(actual, expected, (rule.tolerance or {}).get("pt", 2)):
                    violations.append(Violation(rule_id=rule.id, severity=rule.severity, category="PAGE_LAYOUT",
                        message=f"{side.capitalize()} margin: expected {expected} pt, found {actual} pt",
                        expected={side: expected}, actual={side: actual},
                        location=Location(section=f"Document section {index + 1}")))
        return violations, checks
