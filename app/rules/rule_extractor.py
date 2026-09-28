from collections import Counter
from app.models.document_model import DocumentModel, Confidence
from app.models.rule_model import Rule, RuleSet, RuleType, RuleScope, Severity, RequiredSectionRule
from app.ooxml.structure_extractor import extract_sections

# Confidence thresholds (Section 5.2)
HIGH_CONFIDENCE = 0.90
MEDIUM_CONFIDENCE = 0.60


def _body_candidates(doc: DocumentModel):
    return [
        p for p in doc.paragraphs
        if not p.is_heading and len(p.text.strip()) > 40
    ]


def infer_body_typography(doc: DocumentModel) -> dict:
    candidates = _body_candidates(doc)

    font_counter, size_counter, spacing_counter, align_counter = (
        Counter(), Counter(), Counter(), Counter())

    for p in candidates:
        for r in p.runs:
            weight = max(len(r.text), 1)
            if r.font_name:
                font_counter[r.font_name] += weight
            if r.font_size_pt:
                size_counter[r.font_size_pt] += weight
        if p.line_spacing:
            spacing_counter[p.line_spacing] += 1
        if p.alignment.value != "unknown":
            align_counter[p.alignment.value] += 1

    def summarize(counter):
        total = sum(counter.values())
        if total == 0 or not counter:
            return {"value": None, "confidence": 0.0, "agreement_pct": 0.0, "sample_size": 0}
        value, count = counter.most_common(1)[0]
        conf = count / total
        return {"value": value, "confidence": round(conf, 3),
                "agreement_pct": round(conf * 100, 1), "sample_size": total}

    return {
        "font": summarize(font_counter),
        "size": summarize(size_counter),
        "line_spacing": summarize(spacing_counter),
        "alignment": summarize(align_counter),
    }


def _severity_for_confidence(conf: float) -> tuple[Severity, bool]:
    """Returns (severity, should_propose)."""
    if conf >= HIGH_CONFIDENCE:
        return Severity.ERROR, True
    if conf >= MEDIUM_CONFIDENCE:
        return Severity.WARNING, True
    return Severity.INFO, False  # unresolved — don't propose a hard rule


def extract_typography_rules(doc: DocumentModel) -> list[Rule]:
    inferred = infer_body_typography(doc)
    rules: list[Rule] = []

    if inferred["font"]["value"] is not None:
        sev, propose = _severity_for_confidence(inferred["font"]["confidence"])
        if propose:
            rules.append(Rule(
                id="BODY_FONT", type=RuleType.FONT_FAMILY, scope=RuleScope.BODY,
                expected_value={"font": inferred["font"]["value"]},
                severity=sev, weight=1.0,
                source_confidence=inferred["font"]["confidence"],
                inference_note=(
                    f"{inferred['font']['agreement_pct']}% of sampled body text "
                    f"({inferred['font']['sample_size']} chars) uses this font."
                ),
            ))
    else:
        rules.append(Rule(
            id="BODY_FONT", type=RuleType.FONT_FAMILY, scope=RuleScope.BODY,
            expected_value={"font": None}, severity=Severity.INFO,
            source_confidence=0.0,
            inference_note="UNRESOLVED: body font could not be determined from this "
                            "template (no docDefaults rFonts, minimal explicit run "
                            "fonts). Teacher must set this manually.",
        ))

    if inferred["size"]["value"] is not None:
        sev, propose = _severity_for_confidence(inferred["size"]["confidence"])
        if propose:
            rules.append(Rule(
                id="BODY_SIZE", type=RuleType.FONT_SIZE, scope=RuleScope.BODY,
                expected_value={"size_pt": inferred["size"]["value"]},
                tolerance={"pt": 0.25}, severity=sev,
                source_confidence=inferred["size"]["confidence"],
                inference_note=(
                    f"{inferred['size']['agreement_pct']}% of sampled body text "
                    f"uses {inferred['size']['value']}pt."
                ),
            ))

    if inferred["line_spacing"]["value"] is not None:
        sev, propose = _severity_for_confidence(inferred["line_spacing"]["confidence"])
        if propose:
            rules.append(Rule(
                id="BODY_LINE_SPACING", type=RuleType.LINE_SPACING_MULTIPLE,
                scope=RuleScope.BODY,
                expected_value={"multiplier": inferred["line_spacing"]["value"]},
                severity=sev, source_confidence=inferred["line_spacing"]["confidence"],
                inference_note=(
                    f"{inferred['line_spacing']['agreement_pct']}% of sampled body "
                    f"paragraphs use {inferred['line_spacing']['value']}x line spacing."
                ),
            ))

    return rules


def extract_page_rules(doc: DocumentModel) -> list[Rule]:
    rules = []
    if not doc.sections:
        return rules
    sec = doc.sections[0]  # V1: use first section only; multi-section docs flagged separately
    if sec.page_width_pt and sec.page_height_pt:
        rules.append(Rule(
            id="PAGE_SIZE", type=RuleType.PAGE_SIZE, scope=RuleScope.DOCUMENT,
            expected_value={"width_pt": sec.page_width_pt, "height_pt": sec.page_height_pt},
            tolerance={"pt": 2.0}, severity=Severity.ERROR, source_confidence=1.0,
            inference_note="Read directly from w:sectPr/w:pgSz — deterministic, not inferred.",
        ))
    margins = {
        "top": sec.margin_top_pt, "bottom": sec.margin_bottom_pt,
        "left": sec.margin_left_pt, "right": sec.margin_right_pt,
    }
    if all(v is not None for v in margins.values()):
        rules.append(Rule(
            id="PAGE_MARGINS", type=RuleType.MARGIN, scope=RuleScope.DOCUMENT,
            expected_value=margins, tolerance={"pt": 2.0}, severity=Severity.ERROR,
            source_confidence=1.0,
            inference_note="Read directly from w:sectPr/w:pgMar — deterministic, not inferred.",
        ))
    return rules


def extract_structure_rules(doc: DocumentModel) -> list[RequiredSectionRule]:
    """V1 approach (Section 5.4): only headings detected via real Word STYLE/
    OUTLINE (not the HEURISTIC fallback) or with heading_level <= 2 become
    structure rules — avoids requiring names/front-matter as if they were
    section titles.

    KNOWN LIMITATION on this specific template (see test_structure_extractor.py
    and prior findings): the required chapter list lives inside an INDEX table,
    not as body headings, so this function is expected to extract few or no
    reliable structure rules from THIS template's body text alone. That is
    surfaced via an empty/short result, not papered over with guessed rules.
    """
    tree = extract_sections(doc)
    rules = []
    order = 0
    def flatten(sections):
        for section in sections:
            yield section
            yield from flatten(section.subsections)

    seen = set()
    for sec in flatten(tree):
        heading_para = next(
            (p for p in doc.paragraphs if p.index == sec.start_paragraph_index), None)
        if heading_para is None:
            continue
        reliable = (heading_para.heading_source in ("STYLE", "OUTLINE")
                    or heading_para.heading_level <= 2 and heading_para.heading_source == "HEURISTIC"
                    and len(heading_para.text.strip()) < 40)
        if not reliable or not sec.heading_text_normalized or sec.heading_text_normalized in seen:
            continue
        if (heading_para.style_name or "").lower() == "title":
            continue
        seen.add(sec.heading_text_normalized)
        rules.append(RequiredSectionRule(
            canonical_name=sec.heading_text_normalized,
            required=True, order_index=order,
        ))
        order += 1
    return rules


def extract_ruleset(doc: DocumentModel, filename: str) -> RuleSet:
    return RuleSet(
        template_source_filename=filename,
        typography_rules=extract_typography_rules(doc),
        page_rules=extract_page_rules(doc),
        structure_rules=extract_structure_rules(doc),
    )
