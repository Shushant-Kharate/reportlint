"""Reviewed structural requirements with explicit abstention at interpretation gaps."""
import re

from app.checking.headings import BANNER, chapter_titles, title_key
from app.checking.models import CheckItem
from app.checking.roles import Paragraph, scalar_run, style_chain
from app.checking.word_structure import (
    active_variants, field_format, inherited_stories, numbering, on_off,
    page_fields, paragraph_property, run_flag, section_map, text_runs,
)
from app.ooxml.constants import NS, qn

KINDS = {'chapter_bold', 'section_font_size', 'page_number_alignment',
         'body_page_number_format', 'front_page_number_format', 'introduction_numbering',
         'contents_structure', 'contents_page_alignment', 'illustration_lists',
         'figure_captions', 'table_titles'}
CAPTION = re.compile(r'^\s*(?:fig(?:ure)?\.?|table)\s+(\d+)\.(\d+)\s*[:.\-–—]?\s+(\S.*)$', re.I)


def named_heading(p):
    return p.role in {'HEADING', 'UNKNOWN'} or (p.role == 'OTHER' and
        any((s.name or '').casefold() in {'title', 'subtitle'} for s in p.styles))


def main_bounds(paragraphs):
    titles = chapter_titles(paragraphs)
    anchors = [p for p in paragraphs if p.index in titles and BANNER.match(p.text.strip())]
    start = min((p.index for p in anchors), default=None)
    end = min((p.index for p in paragraphs if start is not None and p.index > start
               and p.role == 'HEADING' and (title_key(p.text) in {'references', 'acknowledgement'}
               or title_key(p.text).startswith('appendix'))), default=len(paragraphs))
    return start, end, anchors


def section_headings(package, paragraphs, registry):
    start, end, _ = main_bounds(paragraphs)
    if start is None:
        return []
    result = []
    for p in paragraphs:
        if not start < p.index < end or p.role not in {'HEADING', 'UNKNOWN'} or BANNER.match(p.text.strip()):
            continue
        if p.reviewed and p.role != 'HEADING':
            continue
        literal = re.match(r'^\s*\d+(?:\.\d+){1,2}\.?\s+\S', p.text)
        number = numbering(package, p)
        depth = len(re.match(r'^\s*(\d+(?:\.\d+)+)', p.text)[1].split('.')) if literal else None
        if number and number['format'] == 'decimal':
            pattern = (number['pattern'] or '').rstrip('.')
            tokens = re.findall(r'%([1-9])', pattern)
            if pattern == '.'.join('%' + str(i) for i in range(1, len(tokens) + 1)) and 2 <= len(tokens) <= 3:
                depth = len(tokens)
        # Outline style numbers often disagree with decimal depth (for example,
        # repeated chapter labels styled Heading 3). Never infer section depth
        # from Heading N alone.
        if depth not in {2, 3}:
            continue
        runs = text_runs(p)
        trusted = p.role == 'HEADING' or (runs and len(p.text.split()) <= 25
            and not p.text.rstrip().endswith(('.', '?', '!'))
            and all(run_flag(package, registry, p, r, 'b') is True for r in runs))
        if trusted:
            result.append((p, depth, number))
    return result


def structural_checks(rule, revision, package, paragraphs, registry, uncertain, sections, ambiguous):
    kind = rule.value.kind
    base = dict(rule_id=rule.rule_id, evidence_ids=rule.evidence_ids, expected=rule.value.model_dump())

    def item(suffix, status, message, p=None, actual=None, section_index=None, path=None):
        return CheckItem(item_id=rule.rule_id + ':' + str(suffix), status=status,
            code=kind.upper() + '_' + status, message=message,
            paragraph_index=p.index if p else None,
            source_path=path or (p.path if p else None), section_index=section_index, actual=actual, **base)

    if uncertain:
        return [item('scope', 'NOT_CHECKED', 'Document revision/container structure prevents reliable structural checking.')]
    start, end, anchors = main_bounds(paragraphs)
    if kind == 'section_font_size':
        targets = [(p, n) for p, d, n in section_headings(package, paragraphs, registry) if d == rule.value.depth]
        if not targets:
            return [item('scope', 'NOT_CHECKED', 'No trusted section headings at the approved decimal depth were found.')]
        result = []
        for p, number in targets:
            values = [scalar_run(package, registry, p, r, 'font_size') for r in text_runs(p)]
            status = 'FAIL' if any(v is not None and abs(v - rule.value.expected_pt) > .1 for v in values) else 'NOT_CHECKED' if not values or None in values else 'PASS'
            result.append(item(p.index, status, 'Compared text runs of outline or bold decimal-numbered headings; generated counter values are not reconstructed.', p,
                {'sizes_pt': sorted({v for v in values if v is not None}), 'depth': rule.value.depth,
                 'numbering_pattern': number['pattern'] if number else None, 'unresolved_runs': values.count(None)}))
        return result
    if kind == 'chapter_bold':
        if not anchors:
            return [item('scope', 'NOT_CHECKED', 'No explicit chapter banners found.')]
        result = []
        for p in anchors:
            parts = [p]
            if not BANNER.fullmatch(p.text.strip())[1]:
                following = next((q for q in paragraphs if q.index > p.index and q.text.strip()), None)
                if following is not None:
                    parts.append(following)
            values = [run_flag(package, registry, part, r, 'b') for part in parts for r in text_runs(part)]
            status = 'FAIL' if False in values else 'NOT_CHECKED' if not values or None in values else 'PASS'
            result.append(item(p.index, status, 'Compared inherited chapter-banner bold formatting, including split title lines.', p, {'bold_runs': values}))
        return result

    if kind in {'page_number_alignment', 'body_page_number_format', 'front_page_number_format', 'introduction_numbering'}:
        if ambiguous:
            return [item('scope', 'NOT_CHECKED', 'Ambiguous section boundaries prevent pagination checks.')]
        stories = inherited_stories(package, sections, 'footer')
        mapping, groups = section_map(package, paragraphs)
        titles = chapter_titles(paragraphs)
        intro = [p for p in paragraphs if p.index in titles and title_key(titles[p.index]) == 'introduction']
        if kind != 'page_number_alignment' and len(intro) != 1:
            return [item('scope', 'NOT_CHECKED', 'A unique Introduction chapter is required for numbering scope.')]
        intro_p = intro[0] if intro else None
        declaration = [p for p in paragraphs if named_heading(p) and title_key(p.text) == 'declaration']
        if kind == 'front_page_number_format' and (len(declaration) != 1 or declaration[0].index >= intro_p.index):
            return [item('scope', 'NOT_CHECKED', 'A unique Declaration before Introduction is required to scope auxiliary numbering.')]
        if kind == 'introduction_numbering':
            index = mapping.get(intro_p.index)
            if index is None or index >= len(groups):
                return [item('scope', 'NOT_CHECKED', 'Introduction section could not be resolved.')]
            section = sections[index]
            prior = [p for p in groups[index] if p.index < intro_p.index and p.text.strip()]
            if prior or section.find(qn('w:type')) is not None and section.find(qn('w:type')).get(qn('w:val')) == 'continuous':
                return [item('scope', 'NOT_CHECKED', 'Introduction does not start a distinct section; page start cannot be established without layout.', intro_p, section_index=index)]
            settings = section.findall(qn('w:pgNumType'))
            restart = settings[0].get(qn('w:start')) if len(settings) == 1 else None
            different_first = on_off(section.find(qn('w:titlePg')))
            first = page_fields(stories[index]['first']) if different_first else page_fields(stories[index]['default'])
            regular = page_fields(stories[index]['default'])
            status = 'NOT_CHECKED' if len(settings) > 1 or different_first is None or first is None or regular is None else 'FAIL' if restart != '1' or not different_first or first else 'PASS' if regular else 'NOT_CHECKED'
            return [item('intro', status, 'Checked explicit page restart at 1, different-first-page footer and absence of a first-page PAGE field; later physical page numbers require rendering.', intro_p,
                {'start': restart, 'different_first_page': different_first, 'first_page_fields': len(first) if first is not None else None,
                 'regular_page_fields': len(regular) if regular is not None else None}, index)]
        result = []
        for index, (section, story) in enumerate(zip(sections, stories)):
            ps = groups[index] if index < len(groups) else []
            if kind == 'body_page_number_format' and not any(p.index >= intro_p.index and p.text.strip() for p in ps):
                continue
            if kind == 'front_page_number_format':
                front = [p for p in ps if declaration[0].index <= p.index < intro_p.index and p.text.strip()]
                if not front:
                    continue
                if any(p.index >= intro_p.index and p.text.strip() for p in ps):
                    result.append(item(index, 'NOT_CHECKED', 'Front matter and body share a section; scope-specific PAGE fields need layout interpretation.', actual=None, section_index=index))
                    continue
            variants = active_variants(package, section)
            if variants is None:
                result.append(item(index, 'NOT_CHECKED', 'Malformed first/even-page footer settings.', section_index=index))
                continue
            for variant in variants:
                fields = page_fields(story[variant])
                if fields is None:
                    result.append(item(f'{index}:{variant}', 'NOT_CHECKED', 'Footer relationship or nested/unsupported field instructions could not be resolved.', section_index=index))
                    continue
                if not fields:
                    suppressed = variant == 'first' and bool(page_fields(story['default']))
                    result.append(item(f'{index}:{variant}', 'OUT_OF_SCOPE' if suppressed else 'NOT_CHECKED',
                        'First-page footer contains no PAGE field; no number alignment/format applies there.' if suppressed else
                        'No PAGE field in this active footer; typed numbers and whether this page variant is used require review.', section_index=index))
                for field_index, (el, instruction) in enumerate(fields):
                    if kind == 'page_number_alignment':
                        style = el.find('w:pPr/w:pStyle', NS)
                        chain = style_chain(registry, style.get(qn('w:val')) if style is not None else registry.default_paragraph_style_id, 'paragraph')
                        if chain is None or el.xpath('ancestor::w:tbl', namespaces=NS):
                            actual = None
                        else:
                            p = Paragraph(0, '', el, '', 'FOOTER', None, chain)
                            actual = paragraph_property(package, p, 'w:jc', 'left')
                        expected = rule.value.alignment
                    else:
                        actual = field_format(instruction, section)
                        expected = rule.value.format
                    status = 'NOT_CHECKED' if actual is None else 'PASS' if actual == expected else 'FAIL'
                    result.append(item(f'{index}:{variant}:{field_index}', status, 'Compared active inherited footer PAGE-field settings; cached field numbers are not trusted.',
                        actual={'value': actual, 'footer_variant': variant, 'field_instruction': instruction}, section_index=index,
                        path=story[variant].getpath(el)))
        return result or [item('scope', 'NOT_CHECKED', 'No eligible numbering scope found.')]

    if start is None:
        return [item('scope', 'NOT_CHECKED', 'Explicit chapter banners are required to separate report content from cover and auxiliary objects.')]
    body = package.document_tree.getroot().find(qn('w:body'))
    children = list(body)
    positions = {el: i for i, el in enumerate(children)}
    lookup = {p.element: p for p in paragraphs}

    def nearest_paragraph(position, direction):
        for offset in range(1, 9):
            i = position + direction * offset
            if not 0 <= i < len(children):
                break
            child = children[i]
            if child.tag != qn('w:p'):
                break
            p = lookup.get(child)
            if p and p.element.xpath('.//w:drawing | .//w:pict', namespaces=NS):
                break
            if p and p.text.strip():
                return p
        return None

    def chapter_number(index):
        preceding = [p for p in anchors if p.index < index]
        match = re.match(r'^chapter\s+(\d+)\b', preceding[-1].text.strip(), re.I) if preceding else None
        return int(match[1]) if match else None

    tables = []
    for child in children:
        if child.tag == qn('w:tbl'):
            ps = [lookup[el] for el in child.xpath('.//w:p', namespaces=NS) if el in lookup]
            if ps and start < ps[0].index < end:
                tables.append((child, ps[0]))
    drawings = [p for p in paragraphs if start < p.index < end and p.element.getparent() is body
                and p.element.xpath('./w:r/w:drawing | ./w:r/w:pict', namespaces=NS)]
    if kind == 'illustration_lists':
        results = []
        contents_heads = [p for p in paragraphs if p.index < start and named_heading(p)
                          and title_key(p.text) in {'index', 'contents', 'table of contents'}]
        for name, required, objects in [('list of figures', 'figures', drawings), ('list of tables', 'tables', tables)]:
            heads = [p for p in paragraphs if named_heading(p) and title_key(p.text) == name]
            front = [p for p in heads if p.index < start]
            if not objects:
                status = 'OUT_OF_SCOPE'
            else:
                status = ('FAIL' if not heads else 'NOT_CHECKED' if len(front) != 1 or len(contents_heads) != 1
                          else 'PASS' if front[0].index > contents_heads[0].index else 'FAIL')
            results.append(item(required, status, 'Checked separate auxiliary list heading after contents when corresponding main-story objects exist; list completeness/page accuracy remain unchecked.',
                front[0] if len(front) == 1 else None, {'list': name, 'front_headings': len(front), 'main_story_objects': len(objects)}))
        return results
    if kind in {'figure_captions', 'table_titles'}:
        objects = [(p.element, p) for p in drawings] if kind == 'figure_captions' else tables
        result = []
        used_numbers = set()
        for element, p in objects:
            caption = nearest_paragraph(positions[element], 1 if kind == 'figure_captions' else -1)
            label = 'figure' if kind == 'figure_captions' else 'table'
            match = CAPTION.fullmatch(caption.text.strip()) if caption else None
            correct_label = bool(match and (caption.text.lstrip().lower().startswith('fig') if label == 'figure' else caption.text.lstrip().lower().startswith('table')))
            generated = caption is not None and bool(caption.element.xpath('.//w:instrText | .//w:fldSimple', namespaces=NS))
            chapter = chapter_number(p.index)
            number = (int(match[1]), int(match[2])) if match and correct_label else None
            if generated:
                status, message = 'NOT_CHECKED', 'Adjacent generated caption field found; counter values require field evaluation, not cached text.'
            elif number:
                status = 'NOT_CHECKED' if chapter is None else 'FAIL' if number[0] != chapter or number[1] < 1 or number in used_numbers else 'PASS'
                message = 'Checked native caption position, chapter-number prefix and uniqueness; physical spacing and numbering sequence remain unchecked.'
                used_numbers.add(number)
            elif label == 'figure':
                status, message = 'NOT_CHECKED', 'No numbered native caption below this figure. Inspect the image for an embedded caption; OCR absence cannot certify a missing caption.'
            else:
                status, message = 'FAIL', 'No native chapter-numbered table title immediately above this main-story table.'
            result.append(item(p.index, status, message, p,
                {'caption': caption.text if caption else None, 'native_caption_found': bool(number), 'chapter_number': chapter,
                 'object_path': package.document_tree.getpath(element)}))
        return result or [item('objects', 'OUT_OF_SCOPE', 'No eligible main-story objects found.')]

    headings = [p for p in paragraphs if p.index < start and named_heading(p)
                and title_key(p.text) in {'index', 'contents', 'table of contents'}]
    if len(headings) != 1:
        return [item('scope', 'NOT_CHECKED', 'A unique contents/index heading is required.')]
    head = headings[0]
    stop = min((p.index for p in paragraphs if head.index < p.index < start and named_heading(p)
                and title_key(p.text) in {'list of figures', 'list of tables', 'abbreviations'}), default=start)
    contents_tables = [el for el in children if el.tag == qn('w:tbl') and any(head.index < lookup[p].index < stop for p in el.xpath('.//w:p', namespaces=NS) if p in lookup)]
    if not contents_tables:
        return [item('scope', 'NOT_CHECKED', 'This slice checks native contents tables; field-generated or prose contents need a dedicated interpreter.', head)]
    result, topic_col, page_col = [], None, None
    for table_index, table in enumerate(contents_tables):
        if table.xpath('.//w:vMerge | .//w:gridSpan', namespaces=NS):
            result.append(item(f'table:{table_index}', 'NOT_CHECKED', 'Merged contents cells need grid interpretation.', head))
            continue
        for row_index, row in enumerate(table.findall(qn('w:tr'))):
            cells = row.findall(qn('w:tc'))
            texts = [''.join(c.xpath('.//w:t/text()', namespaces=NS)).strip() for c in cells]
            names = [title_key(t) for t in texts]
            if any(n in {'page no', 'page no.', 'page number', 'page'} for n in names):
                page_col = next(i for i, n in enumerate(names) if n in {'page no', 'page no.', 'page number', 'page'})
                topic_col = next((i for i, n in enumerate(names) if n in {'topic', 'title', 'chapter'}), None)
                continue
            if page_col is None or topic_col is None or max(page_col, topic_col) >= len(cells):
                result.append(item(f'{table_index}:{row_index}:grid', 'NOT_CHECKED', 'No unambiguous contents column header for this row.', head))
                continue
            if not texts[topic_col]:
                continue
            page_ps = [lookup[p] for p in cells[page_col].xpath('.//w:p', namespaces=NS) if p in lookup and lookup[p].text.strip()]
            topic_ps = [lookup[p] for p in cells[topic_col].xpath('.//w:p', namespaces=NS) if p in lookup and lookup[p].text.strip()]
            if kind == 'contents_page_alignment':
                if not page_ps:
                    result.append(item(f'{table_index}:{row_index}', 'NOT_CHECKED', 'No explicit page reference to compare alignment.', topic_ps[0] if topic_ps else head))
                for p in page_ps:
                    value = paragraph_property(package, p, 'w:jc')
                    status = 'NOT_CHECKED' if value is None else 'PASS' if value == 'right' else 'FAIL'
                    result.append(item(p.index, status, 'Compared contents page-reference paragraph alignment; table positioning and physical page accuracy remain unchecked.', p, {'alignment': value, 'page_reference': p.text}))
            else:
                page_ref = texts[page_col]
                single_page = bool(re.fullmatch(r'(?:\d+|[ivxlcdm]+)', page_ref, re.I))
                status = 'PASS' if single_page else 'FAIL' if re.fullmatch(r'\d+\s*[-–—]\s*\d+', page_ref) else 'NOT_CHECKED'
                if single_page and len(topic_ps) != 1:
                    status = 'NOT_CHECKED'
                result.append(item(f'{table_index}:{row_index}:page', status, 'Checked a single typed page reference rather than a chapter page range; correspondence to rendered pages remains unchecked.', topic_ps[0] if topic_ps else head, {'page_reference': page_ref}))
                for entry_index, p in enumerate(topic_ps):
                    number = numbering(package, p)
                    literal = bool(re.match(r'^\s*\d+\.\d+(?:\.\d+)?\s+\S', p.text))
                    decimal = number and number['format'] == 'decimal' and re.fullmatch(r'%1\.%2(?:\.%3)?\.?', number['pattern'] or '')
                    first_col_section = bool(re.fullmatch(r'\d+\.\d+(?:\.\d+)?', texts[0])) if topic_col != 0 else False
                    if entry_index == 0 and not (literal or decimal or first_col_section or number and number['format'] == 'bullet'):
                        continue
                    status = 'PASS' if literal or decimal or first_col_section else 'FAIL' if number and number['format'] == 'bullet' else 'NOT_CHECKED'
                    result.append(item(f'{p.index}:decimal', status, 'Checked decimal section-entry numbering; bullets do not satisfy decimal notation.', p,
                        {'entry': p.text, 'numbering_format': number['format'] if number else None, 'numbering_pattern': number['pattern'] if number else None}))
    if kind == 'contents_structure' and result:
        result.append(item('completeness', 'NOT_CHECKED', 'Individual native entries were checked; correspondence to every body heading and rendered page requires a separate completeness check.', head))
    return result or [item('scope', 'NOT_CHECKED', 'No supported contents entries found.', head)]
