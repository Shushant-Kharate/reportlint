"""Stored DOCX columns, scoped to sections containing substantive body prose.

OOXML column definitions: https://learn.microsoft.com/en-us/dotnet/api/documentformat.openxml.wordprocessing.columns.equalwidth
No report identity, file name or template-ID shortcut is used.
"""
import re

from app.checking.models import CheckItem
from app.ooxml.constants import qn


def column_count(section):
    entries = section.findall(qn('w:cols'))
    if not entries:
        return 1, 'No column override: the section uses one column.'
    if len(entries) != 1:
        return None, 'Conflicting column definitions.'
    cols = entries[0]
    equal = cols.get(qn('w:equalWidth'), 'true').lower()
    if equal not in {'true','on','1','false','off','0'}:
        return None, 'Invalid equal-width setting.'
    raw = cols.get(qn('w:num'))
    if raw is not None and (not re.fullmatch(r'[1-9][0-9]?',raw) or int(raw)>45):
        return None, 'Invalid column count.'
    children = cols.findall(qn('w:col'))
    if equal in {'false','off','0'}:
        if not children or len(children)>45 or (raw is not None and int(raw)!=len(children)):
            return None, 'Unequal column definitions are missing or inconsistent.'
        if any(not re.fullmatch(r'[1-9][0-9]{0,8}',c.get(qn('w:w'),'')) for c in children):
            return None, 'Unequal column widths are unresolved.'
        return len(children), 'Counted explicit unequal-width columns.'
    if raw is None and children:
        return None, 'Column children without an explicit count require review.'
    return int(raw) if raw is not None else 1, 'Resolved the equal-width count (one when omitted).'


def body_samples(paragraphs):
    explicit, sampled = [], []
    for p in paragraphs:
        words = re.findall(r"[A-Za-z]+(?:['’-][A-Za-z]+)?",p.text)
        if p.role == 'BODY' and (not p.scope_uncertain or p.reviewed) and len(words)>=12:
            explicit.append((p,len(words)))
        elif p.role == 'UNKNOWN' and p.reviewable and len(words)>=50:
            names = [s.name.casefold() for s in p.styles if s.name]
            if any(any(term in n for term in ('caption','reference','bibliograph','author','affiliation','title','abstract','footnote')) for n in names):
                continue
            if re.match(r'\s*(?:\[\d+\]|Fig(?:ure)?\.?\s*\d|Table\s+[IVX\d])',p.text,re.I):
                continue
            if re.search(r'[.!?](?:\s|$)',p.text):
                sampled.append((p,len(words)))
    if sum(n for _,n in explicit)>=80:
        return [p for p,_ in explicit], 'Explicit/reviewed body paragraphs'
    if len(sampled)>=2 and sum(n for _,n in sampled)>=150:
        return [p for p,_ in sampled], 'Multiple substantial main-story prose paragraphs; not a font-role assignment'
    return [], 'No substantive body-prose scope established in this section'


def column_checks(rule,package,paragraphs,sections,ambiguous):
    common = dict(rule_id=rule.rule_id,evidence_ids=rule.evidence_ids,expected=rule.value.model_dump())
    if ambiguous:
        return [CheckItem(item_id=rule.rule_id+':columns',status='NOT_CHECKED',code='DOCX_COLUMN_STRUCTURE_REVIEW',
            message='Section boundaries or tracked section changes are ambiguous; column applicability was not guessed.',**common)]
    by_element = {p.element:p for p in paragraphs}
    groups, current = [], []
    body = package.document_tree.getroot().find(qn('w:body'))
    for child in body:
        if child.tag == qn('w:p'):
            if child in by_element:
                current.append(by_element[child])
            ppr = child.find(qn('w:pPr'))
            if ppr is not None and ppr.find(qn('w:sectPr')) is not None:
                groups.append(current);current=[]
        elif child.tag == qn('w:sectPr'):
            groups.append(current);current=[]
    if len(groups)!=len(sections):
        return [CheckItem(item_id=rule.rule_id+':mapping',status='NOT_CHECKED',code='DOCX_COLUMN_STRUCTURE_REVIEW',
            message='Body text could not be mapped to its section settings safely.',**common)]
    items = []
    for index,(section,group) in enumerate(zip(sections,groups)):
        samples,basis = body_samples(group)
        actual = {'scope_basis':basis,'sample_paragraph_indices':[p.index for p in samples[:8]]}
        base = dict(common,item_id=f'{rule.rule_id}:columns:section:{index}',section_index=index,
                    source_path=package.document_tree.getpath(section))
        if not samples:
            items.append(CheckItem(status='NOT_CHECKED',code='DOCX_COLUMN_SCOPE_REVIEW',
                message='Author blocks, covers, references, figures and sparse sections are not forced into the body-column rule.',actual=actual,**base))
            continue
        count,detail = column_count(section)
        actual.update(observed_columns=count,definition=detail)
        items.append(CheckItem(status='NOT_CHECKED' if count is None else 'PASS' if count==rule.value.count else 'FAIL',
            code='DOCX_COLUMN_DEFINITION_REVIEW' if count is None else 'DOCX_BODY_COLUMNS_MATCH' if count==rule.value.count else 'DOCX_BODY_COLUMNS_MISMATCH',
            message=f'This section contains substantive body prose. Required {rule.value.count} columns; found {count if count is not None else "an unresolved definition"}. {detail}',
            actual=actual,**base))
    return items
