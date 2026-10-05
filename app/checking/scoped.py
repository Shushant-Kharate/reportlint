"""Reviewed chapter and abstract rules. Unresolved structure stays unchecked."""
import re

from app.checking.headings import BANNER, chapter_titles, title_key
from app.checking.models import CheckItem
from app.checking.roles import scalar_run
from app.ooxml.constants import NS

KINDS = {"chapter_font_size", "chapter_case", "abstract_word_count", "abstract_keywords"}


def scoped_checks(rule, package, paragraphs, registry, uncertain):
    base = dict(rule_id=rule.rule_id, evidence_ids=rule.evidence_ids, expected=rule.value.model_dump())

    def item(suffix, status, message, p=None, actual=None):
        return CheckItem(item_id=rule.rule_id + ':' + suffix, status=status,
                         code=rule.value.kind.upper() + '_' + status, message=message,
                         paragraph_index=p.index if p else None, source_path=p.path if p else None,
                         actual=actual, **base)

    if uncertain:
        return [item('scope', 'NOT_CHECKED', 'Unsupported document structure prevents reliable scoped checking.')]
    titles = chapter_titles(paragraphs)
    if rule.value.kind.startswith('chapter_'):
        # Explicit chapter banners distinguish chapters from front-matter headings.
        targets = [p for p in paragraphs if p.index in titles and BANNER.match(p.text.strip())]
        if not targets:
            return [item('scope', 'NOT_CHECKED', 'No explicit numbered chapter banners found; chapter typography scope needs review.')]
        results = []
        for p in targets:
            parts = [p]
            banner = BANNER.fullmatch(p.text.strip())
            if not banner[1]:
                parts.append(next(q for q in paragraphs if q.index > p.index and q.text.strip()))
            if rule.value.kind == 'chapter_case':
                raw = banner[1] or parts[-1].text
                letters = [c for c in raw if c.isalpha()]
                status = 'PASS' if any(c.islower() for c in letters) and any(c.isupper() for c in letters) else 'FAIL' if letters else 'NOT_CHECKED'
                results.append(item(str(p.index), status, 'Chapter title must contain upper- and lowercase letters; chapter-number label excluded.', p, {'title': raw}))
            else:
                values = [scalar_run(package, registry, part, r, 'font_size') for part in parts
                          for r in part.element.xpath('./w:r | ./w:hyperlink/w:r', namespaces=NS)
                          if ''.join(r.xpath('./w:t/text()', namespaces=NS)).strip()]
                mismatches = [v for v in values if v is not None and abs(v-rule.value.expected_pt) > .1]
                status = 'FAIL' if mismatches else 'NOT_CHECKED' if not values or None in values else 'PASS'
                results.append(item(str(p.index), status, 'Compared all chapter-banner text runs with the approved chapter size.', p, {'sizes_pt': sorted(set(v for v in values if v is not None)), 'unresolved_runs': values.count(None)}))
        return results

    starts = [p for p in paragraphs if p.role in {'HEADING', 'UNKNOWN'} and title_key(p.text) == 'abstract']
    if len(starts) != 1:
        return [item('scope', 'NOT_CHECKED', 'A unique abstract heading is required.')]
    start = starts[0]
    boundaries = [p for p in paragraphs if p.index > start.index and
                  (p.role == 'HEADING' or (p.role == 'UNKNOWN' and title_key(p.text) in {'contents', 'table of contents', 'index'}))]
    if not boundaries:
        return [item('scope', 'NOT_CHECKED', 'No trustworthy end of the abstract region found.', start)]
    end = boundaries[0]
    selected = [p for p in paragraphs if start.index < p.index < end.index and p.text.strip()]
    if any(p.role not in {'BODY', 'UNKNOWN'} for p in selected):
        return [item('scope', 'NOT_CHECKED', 'Abstract includes unsupported or excluded content.', start)]
    texts = [p.text for p in selected]
    keyword = re.compile(r'^\s*key\s*words\s*:\s*(\S.*)$', re.I)
    if rule.value.kind == 'abstract_keywords':
        present = any(keyword.match(t) for t in texts)
        return [item('abstract', 'PASS' if present else 'FAIL', 'Checked for a nonempty Keywords: line within the abstract region.', start, {'keyword_label_found': present})]
    count = sum(len(t.split()) for t in texts if not keyword.match(t))
    return [item('abstract', 'PASS' if count == rule.value.expected_words else 'FAIL', 'Whitespace-delimited abstract words excluding the heading and labeled keyword lines; exact reviewed target.', start, {'word_count': count})]
