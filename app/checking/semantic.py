"""Scoped formatting and exact reviewed chapter matching."""
from app.checking.models import CheckItem
from app.checking.roles import nodes, paragraph_spacing, scalar_run
from app.ooxml.constants import NS, qn
from app.checking.headings import BANNER, title_key, chapter_titles, single_character_variant


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
        if paragraph.scope_uncertain and not paragraph.reviewed:
            items.append(CheckItem(item_id=f"{rule.rule_id}:p:{paragraph.index}", status="NOT_CHECKED", code="BODY_SCOPE_REVIEW", message="Body Text styling occurs in front matter, an appendix/form, or a sign-off. Review applicability before enforcing body formatting.", **base))
            continue
        if nodes([ppr] + [s.ppr for s in paragraph.styles], "w:numPr"):
            items.append(CheckItem(item_id=f"{rule.rule_id}:p:{paragraph.index}", status="NOT_CHECKED", code="NUMBERED_BODY_UNSUPPORTED", message="Numbering may contribute formatting and is not yet resolved.", **base))
            continue
        if rule.value.kind == "line_spacing_multiple":
            actual = paragraph_spacing(package, paragraph)
            difference = abs(actual["multiplier"] - rule.value.multiplier) if actual and actual["rule"] == "auto" else None
            borderline = difference is not None and 1 / 240 + 1e-9 < difference <= .01 + 1e-9
            status = "NOT_CHECKED" if actual is None or borderline else "PASS" if difference is not None and difference <= 1 / 240 + 1e-9 else "FAIL"
            code = "BODY_SPACING_TOLERANCE_REVIEW" if borderline else "BODY_SPACING_" + status
            message = ("Spacing differs by more than one OOXML line unit but no more than 0.01 lines. The template does not define rounding tolerance; reviewer confirmation is needed, not an automatic pass or failure."
                       if borderline else "Compared inherited/default spacing; automatic matches allow one OOXML line unit (1/240). Larger discrepancies fail; close differences up to 0.01 lines require review.")
            items.append(CheckItem(item_id=f"{rule.rule_id}:p:{paragraph.index}", status=status, code=code, message=message, actual=actual, **base))
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


def chapter_checks(revision, paragraphs, uncertain):
    profile = revision.publication.profile
    if not profile or not profile.chapters:
        return []
    source = next(p for p in revision.analysis.profiles if p.profile_id == profile.profile_id)
    titles = chapter_titles(paragraphs)
    top = [p for p in paragraphs if p.index in titles]
    items, locations = [], []
    for chapter in sorted(profile.chapters, key=lambda c: c.index):
        keys = {title_key(t) for t in [chapter.name, *chapter.aliases]}
        found = [p for p in top if p.chapter_index == chapter.index or (p.chapter_index is None and title_key(titles[p.index]) in keys)]
        variants = [p for p in top if p.chapter_index is None and BANNER.match(p.text.strip())
                    and any(single_character_variant(titles[p.index], key) for key in keys)]
        corroboration = {}
        if not found:
            for anchor in variants:
                boundary = min((p.index for p in top if p.index > anchor.index), default=len(paragraphs))
                exact = [p for p in paragraphs if anchor.index < p.index < boundary
                         and p.role == 'HEADING' and p.level > anchor.level and title_key(p.text) in keys]
                if exact:
                    found.append(anchor)
                    corroboration[anchor.index] = exact[0].index
        questionable = [p for p in paragraphs if p.chapter_index is None and title_key(p.text) in keys and p.role not in {"TABLE", "FIELD", "FIELD_OR_CONTENTS", "EMPTY", "REVIEWED_EXCLUSION"} and p not in found]
        common = dict(item_id=f"profile:{profile.profile_id}:chapter:{chapter.index}", evidence_ids=source.chapters[chapter.index].evidence_ids, expected={"name": chapter.name, "required": chapter.required}, actual={"matches": len(found), "paragraph_indices": [p.index for p in found]})
        # A repeated lower-level subsection is not a second chapter when a
        # uniquely matched, structurally trusted chapter already exists.
        if len(found) == 1:
            anchor = found[0]
            next_chapter = min((p.index for p in top if p.index > anchor.index), default=len(paragraphs))
            next_text = next((p for p in paragraphs if p.index > anchor.index and p.text.strip()), None)
            banner = BANNER.fullmatch(anchor.text.strip())
            split_title = next_text.index if banner and not banner[1] and next_text else None
            questionable = [p for p in questionable if not (p.index == split_title or
                (p.role == "HEADING" and p.level > anchor.level and anchor.index < p.index < next_chapter))]
        if uncertain or questionable or (not found and variants):
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
        common['actual']['corroborating_heading_indices'] = list(corroboration.values())
        items.append(CheckItem(status=status, code=code, message="Matched trusted chapter headings or reviewed assignments. A one-character banner variant needs an exact lower-level heading inside the same chapter to corroborate presence; an uncorroborated variant remains unchecked.", **common))
        if corroboration:
            anchor = next(p for p in found if p.index in corroboration)
            items.append(CheckItem(item_id=f"profile:{profile.profile_id}:chapter:{chapter.index}:spelling", status='NOT_CHECKED',
                code='CHAPTER_TITLE_VARIANT_REVIEW', message='Chapter presence is corroborated, but the banner has a one-character spelling difference. Review the title spelling.',
                paragraph_index=anchor.index, source_path=anchor.path, expected={'name': chapter.name}, actual={'banner': anchor.text}))
    complete = all(i.status in {"PASS", "OUT_OF_SCOPE"} for i in items if i.code != 'CHAPTER_TITLE_VARIANT_REVIEW')
    if len(locations) > 1:
        ordered = [p for _, p in locations] == sorted(p for _, p in locations)
        status = "FAIL" if not ordered else "PASS" if complete else "NOT_CHECKED"
    else:
        status = "PASS" if complete and locations else "NOT_CHECKED"
    items.append(CheckItem(item_id="profile:" + profile.profile_id + ":order", status=status, code="CHAPTER_ORDER_" + status, message="Compared the relative order of uniquely matched reviewed chapters; missing or ambiguous chapters prevent a complete order pass.", actual={"matched_chapter_indices": [c for c, _ in sorted(locations, key=lambda pair: pair[1])]}))
    return items
