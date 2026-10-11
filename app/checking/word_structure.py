"""Bounded OOXML structure helpers. Cached field results are never page truth."""
import posixpath
import re

from app.ooxml.constants import NS, qn
from app.checking.roles import nodes, style_chain


def on_off(element):
    if element is None:
        return False
    value = element.get(qn('w:val'), 'true').lower()
    return True if value in {'true', '1', 'on'} else False if value in {'false', '0', 'off'} else None


def paragraph_property(package, paragraph, tag, default=None):
    defaults = package.styles_tree.getroot().find('w:docDefaults/w:pPrDefault/w:pPr', NS) if package.styles_tree is not None else None
    for props in [paragraph.element.find(qn('w:pPr'))] + [s.ppr for s in paragraph.styles] + [defaults]:
        if props is not None:
            found = props.findall(qn(tag))
            if len(found) > 1:
                return None
            if found:
                return found[0].get(qn('w:val'), default)
    return default


def run_flag(package, registry, paragraph, run, flag):
    """Resolve toggle properties including toggles in based-on style chains."""
    rpr = run.find(qn('w:rPr'))
    rstyles = nodes([rpr], 'w:rStyle')
    if len(rstyles) > 1:
        return None
    chars = style_chain(registry, rstyles[0].get(qn('w:val')) if rstyles else None, 'character')
    if chars is None:
        return None
    defaults = package.styles_tree.getroot().find('w:docDefaults/w:rPrDefault/w:rPr', NS) if package.styles_tree is not None else None
    value = False
    if defaults is not None:
        found = defaults.findall(qn('w:' + flag))
        if len(found) > 1:
            return None
        value = on_off(found[0]) if found else False
    for props in [s.rpr for s in reversed(paragraph.styles)] + [s.rpr for s in reversed(chars)]:
        if props is None:
            continue
        found = props.findall(qn('w:' + flag))
        if len(found) > 1 or (found and on_off(found[0]) is None):
            return None
        if found and on_off(found[0]):
            value = not value
    if rpr is not None:
        found = rpr.findall(qn('w:' + flag))
        if len(found) > 1:
            return None
        if found:
            value = on_off(found[0])
    return value


def text_runs(paragraph):
    return [r for r in paragraph.element.xpath('./w:r | ./w:hyperlink/w:r', namespaces=NS)
            if ''.join(r.xpath('./w:t/text()', namespaces=NS)).strip()]


def numbering(package, paragraph):
    """Resolve level definition/override, not generated counter values."""
    num_id, ilvl = None, None
    for props in [paragraph.element.find(qn('w:pPr'))] + [s.ppr for s in paragraph.styles]:
        if props is None:
            continue
        found = props.findall(qn('w:numPr'))
        if len(found) > 1:
            return None
        if found:
            for key in ('numId', 'ilvl'):
                child = found[0].find(qn('w:' + key))
                if child is not None:
                    if key == 'numId' and num_id is None:
                        num_id = child.get(qn('w:val'))
                    if key == 'ilvl' and ilvl is None:
                        ilvl = child.get(qn('w:val'))
    if num_id in {None, '0'} or package.numbering_tree is None:
        return None
    ilvl = ilvl or '0'
    if not re.fullmatch(r'\d{1,8}', num_id) or not re.fullmatch(r'[0-8]', ilvl):
        return None
    root = package.numbering_tree.getroot()
    nums = root.xpath('w:num[@w:numId=$n]', namespaces=NS, n=num_id)
    if len(nums) != 1:
        return None
    aid = nums[0].find(qn('w:abstractNumId'))
    if aid is None:
        return None
    abstracts = root.xpath('w:abstractNum[@w:abstractNumId=$n]', namespaces=NS, n=aid.get(qn('w:val')))
    if len(abstracts) != 1 or abstracts[0].find(qn('w:numStyleLink')) is not None:
        return None
    overrides = nums[0].xpath('w:lvlOverride[@w:ilvl=$l]/w:lvl', namespaces=NS, l=ilvl)
    levels = overrides or abstracts[0].xpath('w:lvl[@w:ilvl=$l]', namespaces=NS, l=ilvl)
    if len(levels) != 1:
        return None
    fmt, label = levels[0].find(qn('w:numFmt')), levels[0].find(qn('w:lvlText'))
    if fmt is None or label is None:
        return None
    return {'num_id': num_id, 'level': int(ilvl), 'format': fmt.get(qn('w:val')),
            'pattern': label.get(qn('w:val')), 'level_element': levels[0]}


def section_map(package, paragraphs):
    body = package.document_tree.getroot().find(qn('w:body'))
    section_index, mapping = 0, {}
    by_element = {p.element: p for p in paragraphs}
    groups = []
    current = []
    for child in body:
        ps = [child] if child.tag == qn('w:p') else child.xpath('.//w:p', namespaces=NS)
        for el in ps:
            p = by_element.get(el)
            if p is not None:
                mapping[p.index] = section_index
                current.append(p)
        sect = child.find('w:pPr/w:sectPr', NS) if child.tag == qn('w:p') else child if child.tag == qn('w:sectPr') else None
        if sect is not None:
            groups.append(current)
            current = []
            section_index += 1
    return mapping, groups


def inherited_stories(package, sections, kind):
    previous = {'default': None, 'first': None, 'even': None}
    result = []
    for section in sections:
        current = dict(previous)
        seen = set()
        for ref in section.findall(qn('w:' + kind + 'Reference')):
            variant, rid = ref.get(qn('w:type')), ref.get(qn('r:id'))
            if variant not in current:
                current = {key: False for key in current}
                break
            if variant in seen or rid in package.external_rels or not package.rel_types.get(rid, '').endswith('/' + kind):
                current[variant] = False  # Unknown reference, distinct from an absent/blank story.
            else:
                target = package.rels.get(rid)
                part = posixpath.normpath(target.lstrip('/') if target and target.startswith('/') else 'word/' + (target or ''))
                current[variant] = package.story_parts.get(part, False)
            seen.add(variant)
        previous = current
        result.append(current)
    return result


def active_variants(package, section):
    settings = package.settings_tree.getroot() if package.settings_tree is not None else None
    even = on_off(settings.find(qn('w:evenAndOddHeaders'))) if settings is not None else False
    title = on_off(section.find(qn('w:titlePg')))
    if even is None or title is None:
        return None
    return ['default'] + (['even'] if even else []) + (['first'] if title else [])


def story_used(story):
    if story is False:
        return None
    if story is None:
        return False
    root = story.getroot()
    if root.xpath('.//w:altChunk | .//w:ins | .//w:del | .//*[local-name()="dataBinding" or local-name()="repeatingSection"]', namespaces=NS):
        return None
    return bool(''.join(root.xpath('.//w:t/text()', namespaces=NS)).strip() or
                root.xpath('.//w:drawing | .//w:pict | .//w:instrText | .//w:fldSimple', namespaces=NS))


def header_presence(package, sections):
    stories = inherited_stories(package, sections, 'header')
    result = []
    for section, resolved in zip(sections, stories):
        variants = active_variants(package, section)
        values = [story_used(resolved[v]) for v in variants] if variants else [None]
        # Different header presence on first/odd/even pages cannot be one section margin.
        result.append(None if None in values or len(set(values)) != 1 else values[0])
    return result


def page_fields(story):
    """Return simple PAGE field instructions and their containing paragraph."""
    if story is False:
        return None
    if story is None:
        return []
    root = story.getroot()
    if root.xpath('.//w:altChunk | .//w:ins | .//w:del | .//w:txbxContent | .//*[local-name()="dataBinding" or local-name()="repeatingSection"]', namespaces=NS):
        return None
    result = []
    for p in root.xpath('.//w:p', namespaces=NS):
        instructions = [node.get(qn('w:instr'), '') for node in p.findall('.//' + qn('w:fldSimple'))]
        stack = []
        for node in p.iter():
            if node.tag == qn('w:fldChar'):
                kind = node.get(qn('w:fldCharType'))
                if kind == 'begin':
                    if stack:
                        return None
                    stack.append([])
                elif kind == 'end':
                    if not stack:
                        return None
                    instructions.append(''.join(stack.pop()))
            elif node.tag == qn('w:instrText'):
                if not stack:
                    return None
                stack[-1].append(node.text or '')
        if stack:
            return None
        for instruction in instructions:
            if re.match(r'^\s*PAGE\b', instruction, re.I):
                result.append((p, instruction.strip()))
            elif re.search(r'\bPAGE\b', instruction, re.I):
                return None
    return result


def field_format(instruction, section):
    switches = re.findall(r'\\\*\s+(\w+)', instruction)
    formats = [s for s in switches if s.upper() not in {'MERGEFORMAT', 'CHARFORMAT'}]
    if len(formats) > 1 or re.search(r'\\[^*\s]', instruction):
        return None
    if formats:
        return {'Arabic': 'decimal', 'ARABIC': 'decimal', 'arabic': 'decimal',
                'roman': 'lowerRoman', 'ROMAN': 'upperRoman'}.get(formats[0])
    nodes = section.findall(qn('w:pgNumType'))
    if len(nodes) > 1:
        return None
    return nodes[0].get(qn('w:fmt'), 'decimal') if nodes else 'decimal'
