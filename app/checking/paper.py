"""Reviewed conference-paper rules over native main-story evidence.

These validators are selected by typed published rules, never a file name or a
template identifier. Ambiguous roles and generated counters remain review items.
"""
import re
from dataclasses import replace

from app.checking.models import CheckItem
from app.checking.roles import scalar_run
from app.checking.word_structure import (
    active_variants, inherited_stories, numbering, page_fields,
    paragraph_property, text_runs,
)
from app.ooxml.constants import NS, qn

KINDS = {'paper_abstract_size', 'paper_heading_size', 'paper_title_size', 'paper_reference_size',
         'paper_heading_numbering', 'paper_abstract_run_in', 'paper_no_page_numbers',
         'paper_body_alignment', 'paper_caption_numbering', 'paper_keywords'}


def paper_body_paragraphs(paragraphs):
    """Retain conservative roles, exclude separately governed paper regions."""
    abstract = next((p.index for p in paragraphs if re.match(r'^abstract(?:\s*[:—–-]|\s*$)', p.text.strip(), re.I)), None)
    start = next((p.index for p in paragraphs if (abstract is None or p.index > abstract) and
                  (re.match(r'^CHAPTER\s+\d+\b', p.text.strip(), re.I) or
                   (p.role == 'HEADING' and p.level == 1))), None)
    end = next((p.index for p in paragraphs if (start is None or p.index > start) and
                p.role == 'HEADING' and p.text.strip().casefold().rstrip(':') == 'references'), None)
    return [replace(p, scope_uncertain=True) if p.role == 'BODY' and
            ((start is not None and p.index < start) or (end is not None and p.index > end) or
             (abstract is not None and start is None and p.index >= abstract)) else p for p in paragraphs]


def paper_checks(rule, package, paragraphs, registry, sections, uncertain):
    kind = rule.value.kind
    common = dict(rule_id=rule.rule_id, evidence_ids=rule.evidence_ids, expected=rule.value.model_dump())

    def item(key, status, message, p=None, actual=None, **kwargs):
        return CheckItem(item_id=f'{rule.rule_id}:{key}', status=status,
                         code=kind.upper()+'_'+status, message=message,
                         paragraph_index=p.index if p else None, source_path=p.path if p else None,
                         actual=actual, **common, **kwargs)

    if uncertain:
        return [item('structure', 'NOT_CHECKED', 'Tracked changes, wrapped content or ambiguous section structure require review.')]
    main = [p for p in paragraphs if p.element.getparent().tag == qn('w:body')]
    if kind == 'paper_no_page_numbers':
        items = []
        for story_kind in ('header', 'footer'):
            for i, (section, stories) in enumerate(zip(sections, inherited_stories(package, sections, story_kind))):
                variants = active_variants(package, section)
                fields = [page_fields(stories[v]) for v in variants] if variants else [None]
                present = [f for fs in fields if fs for f in fs]
                # A known PAGE field proves presence even if another variant is unresolved.
                status = 'FAIL' if present else 'NOT_CHECKED'
                items.append(item(f'{story_kind}:{i}', status,
                    'An active inherited header/footer contains a PAGE field; remove pagination for this paper format.' if present else
                    'No supported PAGE field found. Literal page numbers, body-positioned numbers and rendered visibility are not established.',
                    actual={'story': story_kind, 'page_fields': [instruction for _, instruction in present]}, section_index=i))
        return items

    abstracts = [p for p in main if re.match(r'^abstract(?:\s*[:—–-]|\s*$)', p.text.strip(), re.I)]
    heads = [p for p in main if (not abstracts or p.index > abstracts[0].index) and (re.match(r'^CHAPTER\s+\d+\b', p.text.strip(), re.I)
             or (p.role == 'HEADING' and p.level == 1 and p.text.strip().casefold().rstrip(':') not in
                 {'references', 'acknowledgment', 'acknowledgement', 'abstract'}))]
    targets = []
    if kind == 'paper_keywords':
        if len(abstracts) != 1:
            return [item('scope', 'NOT_CHECKED', 'A unique native Abstract region could not be established.')]
        end = next((p.index for p in main if p.index > abstracts[0].index and p.role == 'HEADING'), None)
        if end is None:
            return [item('scope', 'NOT_CHECKED', 'No trustworthy end of the abstract/keywords region found.')]
        region = [p for p in main if abstracts[0].index <= p.index < end]
        present = any(re.search(r'(?:^|\n)\s*(?:key\s*words|index terms)\s*[:—–-]\s*\S', p.text, re.I) for p in region)
        return [item('label', 'PASS' if present else 'FAIL', 'Checked for a nonempty Keywords or Index Terms label in the bounded abstract region.', abstracts[0], {'keyword_label_found': present})]
    if kind.startswith('paper_abstract'):
        if len(abstracts) != 1:
            return [item('scope', 'NOT_CHECKED', 'A unique native Abstract label could not be established.')]
        head = abstracts[0]
        if kind == 'paper_abstract_run_in':
            inline = bool(re.match(r'^abstract\s*[—–-]\s*\S', head.text.strip(), re.I))
            return [item('label', 'PASS' if inline else 'FAIL',
                'The template uses an Abstract label followed by a dash and abstract text in the same paragraph.', head,
                {'run_in': inline, 'label': head.text[:100]})]
        if len(head.text.split()) > 3:
            targets = [head]
        else:
            for p in main:
                if p.index <= head.index:
                    continue
                if p.role == 'HEADING' or re.match(r'^(?:keywords|index terms)\s*[:—–-]', p.text.strip(), re.I):
                    break
                if p.text.strip():
                    targets.append(p)
    elif kind.startswith('paper_heading'):
        targets = heads
    elif kind == 'paper_title_size':
        candidates = [p for p in main if p.text.strip()][:1]
        targets = [p for p in candidates if any(s.name.casefold() in {'title', 'paper title', 'papertitle'} for s in p.styles)]
    elif kind == 'paper_reference_size':
        refs = [p for p in main if p.text.strip().casefold().rstrip(':') == 'references']
        if len(refs) == 1:
            for p in main:
                if p.index <= refs[0].index:
                    continue
                if p.role == 'HEADING' or (targets and not p.text.strip()):
                    break
                if p.text.strip():
                    targets.append(p)
    elif kind == 'paper_body_alignment':
        targets = [p for p in main if p.role == 'BODY' and not p.scope_uncertain and p.reviewable]
    elif kind == 'paper_caption_numbering':
        targets = [p for p in main if p.reviewable and
                   re.match(r'^(?:Fig(?:ure)?\.?|Table)\s+(?:\d+|[IVXLCDM]+)\b', p.text.strip(), re.I)
                   and (len(p.text.split()) < 40 or any('caption' in s.name.casefold() for s in p.styles))]
    if not targets:
        return [item('scope', 'NOT_CHECKED', 'No unambiguous native text in this rule’s role was found. Cover-title inference, image captions and wrapped text require review.')]
    items = []
    for p in targets:
        if kind == 'paper_heading_numbering':
            num = numbering(package, p)
            literal = bool(re.match(r'^[IVXLCDM]+\.\s+\S', p.text.strip()))
            valid = literal or bool(num and num['format'] == 'upperRoman' and re.fullmatch(r'%\d\.', num['pattern'] or ''))
            explicit_wrong = bool(re.match(r'^(?:CHAPTER\s+\d+|\d+[.)]\s)', p.text.strip(), re.I)) or (num is not None and not valid)
            items.append(item(str(p.index), 'PASS' if valid else 'FAIL' if explicit_wrong else 'NOT_CHECKED',
                'Main text headings use uppercase Roman numbering; a Word heading style name does not establish the numbering.', p,
                {'text': p.text[:140], 'numbering_format': num['format'] if num else None, 'pattern': num['pattern'] if num else None}))
        elif kind == 'paper_body_alignment':
            alignment = paragraph_property(package, p, 'w:jc', 'left')
            items.append(item(str(p.index), 'NOT_CHECKED' if alignment is None else 'PASS' if alignment == 'both' else 'FAIL',
                'Compared inherited body paragraph alignment with the template’s justified text.', p, {'alignment': alignment}))
        elif kind == 'paper_caption_numbering':
            text = p.text.strip()
            valid = bool(re.match(r'^Fig\.\s+[1-9]\d*\.(?!\d)', text)) or bool(re.match(r'^TABLE\s+[IVXLCDM]+[.\s]', text))
            # Only classify a clear chapter-decimal label automatically as wrong.
            wrong = bool(re.match(r'^(?:Fig(?:ure)?\.?|Table)\s+\d+\.\d+', text, re.I))
            items.append(item(str(p.index), 'PASS' if valid else 'FAIL' if wrong else 'NOT_CHECKED',
                'Use consecutive Fig. 1. labels and Roman TABLE I labels; chapter-decimal labels do not match this paper format. Image captions remain unchecked.', p, {'caption': text[:180]}))
        else:
            for n, run in enumerate(text_runs(p)):
                size = scalar_run(package, registry, p, run, 'font_size', allow_latin_punctuation=True)
                items.append(item(f'{p.index}:{n}', 'NOT_CHECKED' if size is None else 'PASS' if abs(size-rule.value.expected_pt) <= .1 else 'FAIL',
                    'Compared inherited native text size in this identified paper role.', p, {'value': size}, run_index=n))
    return items
