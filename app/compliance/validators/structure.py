from app.models.rule_model import RequiredSectionRule, Severity
from app.models.result_model import Violation, Location
from app.ooxml.structure_extractor import extract_sections
from app.rules.section_catalog import match_section, DEFAULT_ALIASES


def _flatten(secs):
    out = []
    for s in secs:
        out.append(s)
        out.extend(_flatten(s.subsections))
    return out


class StructureValidator:
    def validate(self, doc, rules: list[RequiredSectionRule]) -> tuple[list, int]:
        tree = extract_sections(doc)
        all_secs = _flatten(tree)
        candidates = {s.heading_text_normalized: s for s in all_secs}

        violations = []
        checks = 0
        matched_order = []  # (rule.order_index, matched section start index)

        for rule in sorted(rules, key=lambda r: r.order_index):
            if not rule.required or rule.severity == Severity.INFO:
                continue
            checks += 1
            aliases = rule.aliases or DEFAULT_ALIASES.get(rule.canonical_name, [])
            match = match_section(rule.canonical_name, aliases, candidates)
            if match is None:
                violations.append(Violation(
                    rule_id=f"REQUIRED_SECTION_{rule.canonical_name.replace(' ', '_')}",
                    severity=rule.severity, category="STRUCTURE",
                    message=f"Required section not found: '{rule.canonical_name}'",
                    expected={"section": rule.canonical_name}, actual=None,
                    location=Location(section=None),
                ))
                continue
            if match.match_type == "FUZZY":
                violations.append(Violation(
                    rule_id=f"REQUIRED_SECTION_{rule.canonical_name.replace(' ', '_')}",
                    severity=Severity.WARNING, category="STRUCTURE",
                    message=(f"Section found via fuzzy match ('{match.heading_text}', "
                              f"score={match.score}) — confirm this is "
                              f"'{rule.canonical_name}'"),
                    expected={"section": rule.canonical_name},
                    actual={"matched_heading": match.heading_text},
                    location=Location(section=match.heading_text),
                ))
            sec = candidates.get(
                rule.canonical_name,
                next((s for s in all_secs if s.heading_text == match.heading_text), None))
            if sec is not None:
                matched_order.append((rule.order_index, sec.start_paragraph_index))

        matched_order.sort(key=lambda t: t[0])
        para_positions = [t[1] for t in matched_order]
        if len(para_positions) > 1:
            checks += 1
        if para_positions != sorted(para_positions):
            violations.append(Violation(
                rule_id="SECTION_ORDER", severity=Severity.WARNING, category="STRUCTURE",
                message="Matched required sections do not appear in the expected order",
                expected={"order": [r.canonical_name for r in sorted(rules, key=lambda r: r.order_index)]},
                actual=None, location=Location(section=None),
            ))

        return violations, checks
