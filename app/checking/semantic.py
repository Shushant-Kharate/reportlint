"""Scoped formatting and exact reviewed chapter matching."""
from app.checking.models import CheckItem
from app.checking.roles import nodes, paragraph_spacing, scalar_run
from app.ooxml.constants import NS, qn


def body_checks(rule, package, paragraphs, registry, uncertain):
    common = dict(rule_id=rule.rule_id, evidence_ids=rule.evidence_ids, expected=rule.value.model_dump())
    targets = [p for p in paragraphs if p.role == "BODY"]
    items = []
    unresolved = [p for p in paragraphs if p.role in {"UNKNOWN", "UNSUPPORTED_CONTAINER", "FIELD"} and p.text.strip()]
    if unresolved or uncertain or not targets:
        items.append(CheckItem(item_id=rule.rule_id + ":scope", status="NOT_CHECKED", code="INCOMPLETE_BODY_SCOPE", message="Only explicit Body Text styles or reviewed report-specific assignments are selected. Other potential body content remains unresolved.", actual={"selected_paragraphs": len(targets), "unresolved_paragraphs": len(unresolved)}, **common))
    for paragraph in targets:
        ppr = paragraph.element.find(qn("w:pPr"))
        base = dict(common, paragraph_index=paragraph.index, source_path=paragraph.path)
        if nodes([ppr] + [s.ppr for s in paragraph.styles], "w:numPr"):
            items.append(CheckItem(item_id=f"{rule.rule_id}:p:{paragraph.index}", status="NOT_CHECKED", code="NUMBERED_BODY_UNSUPPORTED", message="Numbering may contribute formatting and is not yet resolved.", **base))
            continue
        if rule.value.kind == "line_spacing_multiple":
            actual = paragraph_spacing(package, paragraph)
            status = "NOT_CHECKED" if actual is None else "PASS" if actual["rule"] == "auto" and abs(actual["multiplier"] - rule.value.multiplier) <= 1 / 240 + 1e-9 else "FAIL"
            items.append(CheckItem(item_id=f"{rule.rule_id}:p:{paragraph.index}", status=status, code="BODY_SPACING_" + status, message="Compared stored spacing on a resolved body paragraph; unresolved properties are not defaulted.", actual=actual, **base))
        else:
            runs = paragraph.element.xpath("./w:r | ./w:hyperlink/w:r", namespaces=NS)
            for index, run in enumerate(runs):
                if not "".join(run.xpath("./w:t/text()", namespaces=NS)).strip():
                    continue
                actual = scalar_run(package, registry, paragraph, run, rule.value.kind)
                expected = rule.value.font if rule.value.kind == "font_family" else rule.value.expected_pt
                match = (actual.casefold() == expected.casefold() if isinstance(actual, str) else abs(actual - expected) <= 0.1) if actual is not None else False
                status = "NOT_CHECKED" if actual is None else "PASS" if match else "FAIL"
                items.append(CheckItem(item_id=f"{rule.rule_id}:p:{paragraph.index}:r:{index}", status=status, code="BODY_RUN_" + status, message="Compared scalar formatting of a nonempty Latin body run; theme or script ambiguity remains unchecked.", actual={"value": actual}, **dict(base, run_index=index, source_path=package.document_tree.getpath(run))))
    return items


def title_key(text):
    # Whitespace/case only. Number prefixes and punctuation require reviewed aliases.
    return " ".join(text.casefold().split())


def chapter_checks(revision, paragraphs, uncertain):
    profile = revision.publication.profile
    if not profile or not profile.chapters:
        return []
    source = next(p for p in revision.analysis.profiles if p.profile_id == profile.profile_id)
    top = [p for p in paragraphs if p.role == "HEADING" and p.level == 1]
    items, locations = [], []
    for chapter in sorted(profile.chapters, key=lambda c: c.index):
        keys = {title_key(t) for t in [chapter.name, *chapter.aliases]}
        found = [p for p in top if p.chapter_index == chapter.index or (p.chapter_index is None and title_key(p.text) in keys)]
        questionable = [p for p in paragraphs if p.chapter_index is None and title_key(p.text) in keys and p.role not in {"TABLE", "FIELD", "FIELD_OR_CONTENTS", "EMPTY", "REVIEWED_EXCLUSION"} and p not in found]
        common = dict(item_id=f"profile:{profile.profile_id}:chapter:{chapter.index}", evidence_ids=source.chapters[chapter.index].evidence_ids, expected={"name": chapter.name, "required": chapter.required}, actual={"matches": len(found), "paragraph_indices": [p.index for p in found]})
        if uncertain or questionable:
            status, code = "NOT_CHECKED", "AMBIGUOUS_CHAPTER"
        elif len(found) > 1:
            status, code = "FAIL", "DUPLICATE_CHAPTER"
        elif found:
            status, code = "PASS", "CHAPTER_PRESENT"
            locations.append((chapter.index, found[0].index))
            common.update(paragraph_index=found[0].index, source_path=found[0].path)
        elif not top:
            status, code = "NOT_CHECKED", "NO_TRUSTED_CHAPTER_HEADINGS"
        elif chapter.required:
            status, code = "FAIL", "MISSING_CHAPTER"
        else:
            status, code = "OUT_OF_SCOPE", "OPTIONAL_CHAPTER_ABSENT"
        items.append(CheckItem(status=status, code=code, message="Matched outline-level-1 exact names/aliases or explicit report-specific chapter assignments; contents/table mentions do not count.", **common))
    complete = all(i.status in {"PASS", "OUT_OF_SCOPE"} for i in items)
    if len(locations) > 1:
        ordered = [p for _, p in locations] == sorted(p for _, p in locations)
        status = "FAIL" if not ordered else "PASS" if complete else "NOT_CHECKED"
    else:
        status = "PASS" if complete and locations else "NOT_CHECKED"
    items.append(CheckItem(item_id="profile:" + profile.profile_id + ":order", status=status, code="CHAPTER_ORDER_" + status, message="Compared the relative order of uniquely matched reviewed chapters; missing or ambiguous chapters prevent a complete order pass.", actual={"matched_chapter_indices": [c for c, _ in sorted(locations, key=lambda pair: pair[1])]}))
    return items
