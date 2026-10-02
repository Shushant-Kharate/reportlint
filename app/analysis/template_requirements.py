"""Conservative first-slice extraction: proposals and evidence, never approval.

Only explicit body font/size/spacing, paper size and margin statements are
parsed. Other instructional spans remain visible in the requirement ledger.
"""
import re
from hashlib import sha256

from app.analysis.template_source import inventory_source
from app.models.template_analysis import (
    TemplateAnalysis, RuleCandidate, Conflict, RequirementDisposition,
    SourceEvidence, FontValue, SizeValue, SpacingValue, PageValue, MarginValue,
    ChapterCandidate, ProfileCandidate,
)
from app.ooxml.structure_extractor import build_document_model
from app.ooxml.constants import qn
from app.ooxml.docx_loader import InvalidDocxError
from app.rules.rule_extractor import infer_body_typography


NUMBER = r"\d+(?:\.\d+)?"
UNIT = r"(?:mm|millimet(?:er|re)s?|cm|centimet(?:er|re)s?|inches|inch|in|pts?|points?)"
NORMATIVE = re.compile(r"\b(?:shall|must|should|required|requirement|standard font|when|if)\b", re.I)
START = re.compile(r"(?:guidelines.*(?:report|format)|(?:formatting|report) (?:requirements|guidelines)|format specifications)", re.I)
END = re.compile(r"^(?:specimen|sample report|example report|appendix)\b", re.I)
FIELD = re.compile(r"^(?:(?:top|bottom|left|right) margin|font(?: size)?|line spacing)\s*:", re.I)
MARGIN = re.compile(rf"\b(top|bottom|left|right)\s+margin\s*(?::|(?:shall|must|should)\s+be|is)\s*({NUMBER})\s*({UNIT})\b", re.I)


def points(value, unit):
    value = float(value)
    unit = unit.casefold()
    if unit.startswith("mm") or unit.startswith("millimet"):
        return value * 72 / 25.4
    if unit.startswith("cm") or unit.startswith("centimet"):
        return value * 720 / 25.4
    if unit.startswith("in"):
        return value * 72
    return value


def property_key(candidate):
    value = candidate.value
    return (candidate.scope, value.kind, getattr(value, "side", ""))


def same_value(left, right):
    a, b = left.value.model_dump(), right.value.model_dump()
    if a.keys() != b.keys():
        return False
    for key in a:
        if isinstance(a[key], (int, float)):
            # Numerical equivalence, not a compliance tolerance.
            if abs(a[key] - b[key]) > 0.02:
                return False
        elif isinstance(a[key], str):
            if a[key].casefold() != b[key].casefold():
                return False
        elif a[key] != b[key]:
            return False
    return True


def find_conflicts(candidates):
    conflicts = []
    for i, left in enumerate(candidates):
        for right in candidates[i + 1:]:
            if property_key(left) != property_key(right) or same_value(left, right):
                continue
            if left.origin == right.origin == "OBSERVED_APPEARANCE":
                continue  # Different sections may legitimately differ.
            ids = [left.candidate_id, right.candidate_id]
            suggested = None
            if left.origin != right.origin:
                kind = "PROSE_APPEARANCE"
                proposed = left if left.origin == "EXPLICIT_PROSE" else right
                suggested = proposed.candidate_id
                explanation = "Written guidance differs from observed formatting. Review the written value, its scope and any conditions before approving a rule."
            elif left.condition != right.condition:
                kind = "CONDITIONAL_OVERRIDE"
                explanation = "A general value and a conditional alternative overlap. Review the intended conditions and physical measurements; neither value is approved."
            else:
                kind = "COMPETING_REQUIREMENTS"
                explanation = "The source proposes different values for the same property and scope. Review whether a missing scope or exception explains the difference."
            conflicts.append(Conflict(
                conflict_id="conflict-" + sha256("|".join(ids).encode()).hexdigest()[:16],
                kind=kind, candidate_ids=ids, suggested_candidate_id=suggested,
                explanation=explanation,
            ))
            if len(conflicts) > 2000:
                raise InvalidDocxError("Too many conflicting proposals for this preview")
    return conflicts


def analyze_template(package, source_sha256):
    inventory = inventory_source(package)
    result = TemplateAnalysis(source_sha256=source_sha256, notices=inventory.notices)
    evidence = {}

    def add(value, scope, source, *, origin="EXPLICIT_PROSE", condition="ALWAYS", note=""):
        evidence[source.source_id] = source
        identity = f"{source.source_id}|{scope}|{condition}|{origin}|{value.model_dump_json()}"
        candidate = RuleCandidate(
            candidate_id="candidate-" + sha256(identity.encode()).hexdigest()[:20],
            scope=scope, value=value, condition=condition, origin=origin,
            evidence_ids=[source.source_id], note=note,
        )
        if not any(c.candidate_id == candidate.candidate_id for c in result.candidates):
            if len(result.candidates) >= 500:
                raise InvalidDocxError("Too many property proposals for this preview")
            result.candidates.append(candidate)
        return candidate.candidate_id

    guidelines = False
    body_context = False
    for source in inventory.paragraphs:
        # Table descriptions are processed as independent source spans below;
        # they must not leak heading/context changes into following body text.
        if "/tbl[" in source.path:
            continue
        text = re.sub(r"\s+", " ", source.excerpt).strip()
        if not text:
            continue
        short = len(text) < 120
        if short and START.search(text):
            guidelines = True
            body_context = False
            continue
        if short and END.search(text):
            guidelines = False
            body_context = False
            continue
        if short and re.search(r"(?:type setting|text processing|body text|body formatting)", text, re.I):
            body_context = True
        elif short and re.match(r"^\d+(?:\.\d+)*\s+(?:chapter|section|table|figure|front|auxiliary|abstract)", text, re.I):
            body_context = False

        directive = bool(NORMATIVE.search(text))
        if not directive and not (guidelines and FIELD.search(text)):
            continue
        evidence[source.source_id] = source
        ids = []
        negative_instruction = bool(re.search(r"\b(?:shall|must|should)\s+not\b|\b(?:neither|not be)\b", text, re.I))
        body_rule = bool(re.search(r"\b(?:standard font|body (?:text|font|paragraph))\b", text, re.I)) or (guidelines and body_context)
        # Heading-specific instructions cannot inherit a nearby body context.
        if re.search(r"\b(?:chapter title|section title|subsection|cover|caption)\b", text, re.I):
            body_rule = False
        body_text = next((sentence for sentence in re.split(r"(?<=[.!?])\s+", text)
                          if re.search(r"\b(?:standard font|body (?:text|font|paragraph))\b", sentence, re.I)), text)
        if re.search(r"\b(?:or|either|not|except)\b", body_text, re.I) or negative_instruction:
            body_rule = False
        if body_rule:
            match = re.search(rf"\bfont(?: family)?\s*(?:(?:shall|must|should)\s+be|is|:)\s*([A-Za-z][A-Za-z -]{{1,70}}?)(?=\s+(?:of|at|in)\s+{NUMBER}|\s+{NUMBER}|[,.;]|$)", body_text, re.I)
            if match:
                ids.append(add(FontValue(font=match[1].strip()), "body", source))
            match = re.search(rf"\b({NUMBER})\s*(?:pts?|points?)\b", body_text, re.I)
            if match and float(match[1]) > 0:
                ids.append(add(SizeValue(expected_pt=float(match[1])), "body", source))
            match = re.search(rf"\b({NUMBER})\s*(?:x\s*)?line spacing\b|\bline spacing\s*:\s*({NUMBER})(?!\d|\s*(?:pt|point))", body_text, re.I)
            if match and float(match[1] or match[2]) > 0 and not re.search(r"between paragraphs|vertical space", text, re.I):
                ids.append(add(SpacingValue(multiplier=float(match[1] or match[2])), "body", source))

        page_text = next((sentence for sentence in re.split(r"(?<=[.!?])\s+", text)
                          if re.search(r"\b(?:paper|page)\b", sentence, re.I) and re.search(r"\b(?:A4|Letter)\b", sentence, re.I)), "")
        if page_text and not negative_instruction and not re.search(r"\b(?:or|either)\b", page_text, re.I):
            width, height = ((210 * 72 / 25.4, 297 * 72 / 25.4)
                             if re.search(r"\bA4\b", page_text, re.I) else (612.0, 792.0))
            if "landscape" in page_text.casefold():
                width, height = height, width
            ids.append(add(PageValue(width_pt=width, height_pt=height), "document", source,
                           note="Proposed named paper dimensions; verify orientation and any explicit dimensions in the source."))
            explicit_width = re.search(rf"\bwidth\s*[:=]?\s*({NUMBER})\s*({UNIT})\b", page_text, re.I)
            explicit_height = re.search(rf"\bheight\s*[:=]?\s*({NUMBER})\s*({UNIT})\b", page_text, re.I)
            if explicit_width and explicit_height:
                value = PageValue(width_pt=points(explicit_width[1], explicit_width[2]), height_pt=points(explicit_height[1], explicit_height[2]))
                candidate_id = add(value, "document", source, note="Dimensions explicitly written in the same source; compare with the named paper size.")
                if candidate_id not in ids:
                    ids.append(candidate_id)

        for match in ([] if negative_instruction else MARGIN.finditer(text)):
            condition = "HEADER_ABSENT" if re.search(r"(?:header is not used|no header|without (?:a )?header)", text, re.I) else "ALWAYS"
            ids.append(add(MarginValue(side=match[1].lower(), expected_pt=points(match[2], match[3])),
                           "document", source, condition=condition,
                           note="Review Word text-margin versus physical header/footer geometry before enforcement."))

        disposition = "CANDIDATES_NEED_REVIEW" if ids else (
            "MANUAL_REVIEW" if re.search(r"\b(?:whiteness|embossed|bound copies|printer|gram per|binding)\b", text, re.I) else "UNCLASSIFIED")
        result.requirement_ledger.append(RequirementDisposition(
            evidence_id=source.source_id, status=disposition, candidate_ids=ids,
        ))

    for table in inventory.tables:
        if not table.rows:
            continue
        headings = [" ".join(p.excerpt for p in cell).strip().casefold() for cell in table.rows[0]]
        topic_column = next((i for i, h in enumerate(headings) if h in {"topic", "chapter", "chapter title", "flow of the synopsis"}), None)
        if topic_column is None:
            continue
        if table.complex_grid:
            result.notices.append(f"Merged index table at {table.path} needs manual interpretation; no chapter sequence was guessed.")
            continue
        label = "synopsis" if "synopsis" in headings[topic_column] else "report"
        chapters = []
        for row in table.rows[1:]:
            if topic_column >= len(row):
                continue
            sources = row[topic_column]
            lines = [line.strip() for p in sources for line in p.excerpt.splitlines() if line.strip()]
            if not lines:
                continue
            for source in sources:
                evidence[source.source_id] = source
            number = " ".join(p.excerpt for p in row[0]).strip() if topic_column != 0 else ""
            chapters.append(ChapterCandidate(
                title=lines[0], suggested_topics=lines[1:], number=number or None,
                evidence_ids=[s.source_id for s in sources],
            ))
        if chapters:
            result.profiles.append(ProfileCandidate(
                profile_id="profile-" + sha256(table.path.encode()).hexdigest()[:16],
                label=label, chapters=chapters,
            ))

    # Preserve unrecognized instructions in table cells, including descriptions.
    for source in inventory.paragraphs:
        if "/tbl[" in source.path and NORMATIVE.search(source.excerpt):
            evidence[source.source_id] = source
            result.requirement_ledger.append(RequirementDisposition(evidence_id=source.source_id, status="UNCLASSIFIED"))

    # Existing inference is evidence only, not a normative source in this path.
    doc = build_document_model(package, "source.docx")
    inferred = infer_body_typography(doc)
    observed = SourceEvidence(source_id="observed-body", path="body", excerpt="Dominant formatting sampled by the legacy body heuristic; may include sample or guideline text.")
    for key, factory in (("font", lambda v: FontValue(font=v)), ("size", lambda v: SizeValue(expected_pt=v)), ("line_spacing", lambda v: SpacingValue(multiplier=v))):
        value = inferred[key]["value"]
        if value is not None:
            add(factory(value), "body", observed, origin="OBSERVED_APPEARANCE", note=f"Observed agreement {inferred[key]['agreement_pct']}%; not authority for a rule.")
    section_elements = package.document_tree.getroot().findall(f".//{qn('w:sectPr')}")
    for index, section in enumerate(doc.sections):
        section_path = package.document_tree.getpath(section_elements[index]) if index < len(section_elements) else "body"
        observed = SourceEvidence(source_id=f"observed-section-{index}", path=section_path, excerpt="Stored Word section properties; no claim that these match the written requirements.")
        if section.page_width_pt and section.page_height_pt:
            add(PageValue(width_pt=section.page_width_pt, height_pt=section.page_height_pt), "document", observed, origin="OBSERVED_APPEARANCE")
        for side in ("top", "bottom", "left", "right"):
            value = getattr(section, f"margin_{side}_pt")
            if value is not None and value >= 0:
                add(MarginValue(side=side, expected_pt=value), "document", observed, origin="OBSERVED_APPEARANCE")

    result.conflicts = find_conflicts(result.candidates)
    result.evidence = list(evidence.values())
    result.notices.extend([
            "Extraction preview only: candidates are not approved. Publish a reviewed revision before checking; consult live capabilities for supported page settings, Body Text and outline-chapter checks.",
        "English patterns cover a limited property set. The requirement ledger is an extraction aid, not proof of complete template coverage.",
        "Candidate-bearing paragraphs can contain additional unsupported requirements. Review the full source excerpt.",
        "Table topics are suggestions, not mandatory sections or aliases. Select and review report/synopsis profiles separately.",
    ])
    if not any(c.origin == "EXPLICIT_PROSE" for c in result.candidates):
        result.notices.append("No supported explicit property instructions found; observed appearance has not been promoted to authoritative rules.")
    return TemplateAnalysis.model_validate(result.model_dump())
