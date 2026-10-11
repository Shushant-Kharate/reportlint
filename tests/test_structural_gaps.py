"""Fictional positive/negative/ambiguous examples for real-audit coverage gaps."""
from io import BytesIO
import base64
import zipfile

import pytest
from docx import Document
from docx.enum.section import WD_SECTION_START
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.shared import Mm, Pt
from lxml import etree

from app.analysis.service import analyze_bytes
from app.checking.service import check_bytes
from app.ooxml.constants import NS, qn
from app.review.models import CandidateDecision, LedgerDecision, ReviewPatch
from app.review.repository import RevisionRepository
from app.review.service import apply_review, publish, snapshot_hash
from tests.test_template_analysis import encoded


def reviewed(tmp_path, *instructions):
    template = Document()
    template.add_paragraph('Guidelines for project report format')
    for instruction in instructions:
        template.add_paragraph(instruction)
    repo = RevisionRepository(tmp_path / 'structure.sqlite3')
    draft = repo.create('Fictional structural format', analyze_bytes(encoded(template)))
    patch = ReviewPatch(expected_version=0,
        candidates=[CandidateDecision(candidate_id=c.candidate_id,
            action='APPROVE' if c.origin == 'EXPLICIT_PROSE' else 'REJECT',
            reason='Verified fictional instruction, not observed template appearance.') for c in draft.analysis.candidates],
        ledger=[LedgerDecision(evidence_id=e.evidence_id, action='DEFERRED',
            reason='Other instructions in this source remain outside the test scope.') for e in draft.analysis.requirement_ledger])
    edited = repo.change(draft.template_id, draft.revision_id, apply_review, patch)
    return repo.change(draft.template_id, draft.revision_id, publish, edited.version)


def fields(doc, instruction='PAGE', first=False, section=None):
    section = section or doc.sections[-1]
    footer = section.first_page_footer if first else section.footer
    footer.is_linked_to_previous = False
    p = footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    field = OxmlElement('w:fldSimple')
    field.set(qn('w:instr'), instruction)
    p._p.append(field)
    return p


def codes(result, kind):
    return [i for i in result.items if i.expected and i.expected.get('kind') == kind]


MARGINS = ('Top Margin: 15 mm', 'When header is not used the top margin shall be 30 mm.')
PAGINATION = ('Page numbering in the text of the report shall be Hindu-Arabic numerals at the center of the footer.',
    'Pagination for pages before the Introduction chapter shall be in lower case Roman numerals.',
    'Page number “1” for the first page of the Introduction chapter shall not appear in print; only the second page will bear the number “2”.')
CAPTIONS = 'Table number and title will be placed above the table while the figure number and caption will be located below the figure.'
CONTENTS = 'The contents shall enlist the titles of the chapters, section and subsection using decimal notation with corresponding page number against them, flushed to the right.'


def test_conditional_margin_override_publishes_and_preserves_snapshot(tmp_path):
    revision = reviewed(tmp_path, *MARGINS)
    assert len([r for r in revision.publication.rules if r.value.kind == 'margin']) == 2
    before = revision.model_dump_json()
    doc = Document()
    doc.sections[0].top_margin = Mm(30)
    result = check_bytes(revision, encoded(doc))
    margins = codes(result, 'margin')
    assert {i.status for i in margins} == {'PASS', 'OUT_OF_SCOPE'}
    assert next(i for i in margins if i.status == 'PASS').expected['expected_pt'] == pytest.approx(30 * 72 / 25.4)
    assert revision.model_dump_json() == before
    assert revision.snapshot_sha256 == snapshot_hash(revision)
    doc.sections[0].top_margin = Mm(15)
    assert any(i.status == 'FAIL' and i.expected['expected_pt'] > 80 for i in codes(check_bytes(revision, encoded(doc)), 'margin'))


def test_inherited_used_header_selects_general_margin(tmp_path):
    revision = reviewed(tmp_path, *MARGINS)
    doc = Document()
    doc.sections[0].header.paragraphs[0].text = 'Running chapter title'
    doc.sections[0].top_margin = Mm(15)
    doc.add_section(WD_SECTION_START.NEW_PAGE).top_margin = Mm(15)
    result = check_bytes(revision, encoded(doc))
    assert len([i for i in codes(result, 'margin') if i.status == 'PASS']) == 2
    assert not any(i.status == 'FAIL' for i in codes(result, 'margin'))


@pytest.mark.parametrize('change', ['mixed_first', 'broken_relationship', 'duplicate_reference'])
def test_uncertain_header_never_selects_a_margin(tmp_path, change):
    revision = reviewed(tmp_path, *MARGINS)
    doc = Document()
    section = doc.sections[0]
    section.header.paragraphs[0].text = 'Header'
    if change == 'mixed_first':
        section.different_first_page_header_footer = True
        section.first_page_header.is_linked_to_previous = False
    elif change == 'broken_relationship':
        section._sectPr.find(qn('w:headerReference')).set(qn('r:id'), 'missing')
    else:
        original = section._sectPr.find(qn('w:headerReference'))
        section._sectPr.append(etree.fromstring(etree.tostring(original)))
    results = codes(check_bytes(revision, encoded(doc)), 'margin')
    assert all(i.status == 'NOT_CHECKED' for i in results)
    assert all(i.code == 'HEADER_CONDITION_UNRESOLVED' for i in results)


def pagination_doc():
    doc = Document()
    doc.add_paragraph('Declaration', style='Title')
    doc.add_paragraph('Fictional declaration text.')
    front = doc.sections[0]
    fmt = OxmlElement('w:pgNumType'); fmt.set(qn('w:fmt'), 'lowerRoman'); front._sectPr.append(fmt)
    fields(doc, section=front)
    body = doc.add_section(WD_SECTION_START.NEW_PAGE)
    body.different_first_page_header_footer = True
    body.first_page_footer.is_linked_to_previous = False
    fmt = body._sectPr.find(qn('w:pgNumType'))
    fmt.set(qn('w:fmt'), 'decimal'); fmt.set(qn('w:start'), '1')
    fields(doc, section=body)
    doc.add_heading('Chapter 1 Introduction', 2)
    doc.add_paragraph('Fictional body content.')
    return doc


def test_correct_footer_formats_restart_suppression_and_alignment(tmp_path):
    revision = reviewed(tmp_path, *PAGINATION)
    result = check_bytes(revision, encoded(pagination_doc()))
    assert len([i for i in codes(result, 'page_number_alignment') if i.status == 'PASS']) == 2
    assert all(i.status in {'PASS', 'OUT_OF_SCOPE'} for i in codes(result, 'page_number_alignment'))
    assert [i.status for i in codes(result, 'front_page_number_format')] == ['PASS']
    assert codes(result, 'body_page_number_format')[0].status == 'PASS'
    assert codes(result, 'introduction_numbering')[0].status == 'PASS'


def test_wrong_inherited_footer_and_missing_restart_are_detected(tmp_path):
    revision = reviewed(tmp_path, *PAGINATION)
    doc = pagination_doc()
    doc.sections[0]._sectPr.find(qn('w:pgNumType')).set(qn('w:fmt'), 'decimal')
    doc.sections[-1].different_first_page_header_footer = False
    doc.sections[-1]._sectPr.find(qn('w:pgNumType')).attrib.pop(qn('w:start'))
    doc.sections[-1].footer.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
    result = check_bytes(revision, encoded(doc))
    assert codes(result, 'front_page_number_format')[0].status == 'FAIL'
    assert codes(result, 'introduction_numbering')[0].status == 'FAIL'
    assert any(i.status == 'FAIL' for i in codes(result, 'page_number_alignment'))


def test_field_format_switch_overrides_section_and_nested_field_abstains(tmp_path):
    revision = reviewed(tmp_path, *PAGINATION)
    doc = pagination_doc()
    field = doc.sections[0].footer.paragraphs[0]._p.find(qn('w:fldSimple'))
    field.set(qn('w:instr'), r'PAGE \* Arabic')
    assert codes(check_bytes(revision, encoded(doc)), 'front_page_number_format')[0].status == 'FAIL'
    field.set(qn('w:instr'), 'IF PAGE = 1 "" PAGE')
    assert codes(check_bytes(revision, encoded(doc)), 'front_page_number_format')[0].status == 'NOT_CHECKED'


def test_plain_footer_content_control_is_supported(tmp_path):
    revision = reviewed(tmp_path, PAGINATION[0])
    doc = Document(); doc.add_heading('Chapter 1 Introduction', 2)
    p = fields(doc)
    sdt = OxmlElement('w:sdt'); content = OxmlElement('w:sdtContent'); sdt.append(content)
    parent = p._p.getparent(); parent.remove(p._p); content.append(p._p); parent.append(sdt)
    assert codes(check_bytes(revision, encoded(doc)), 'page_number_alignment')[0].status == 'PASS'


def add_numbering(doc, p, pattern='%1.%2', fmt='decimal', level=1):
    root = doc.part.numbering_part.element
    abstract = OxmlElement('w:abstractNum'); abstract.set(qn('w:abstractNumId'), '100')
    lvl = OxmlElement('w:lvl'); lvl.set(qn('w:ilvl'), str(level))
    f = OxmlElement('w:numFmt'); f.set(qn('w:val'), fmt); lvl.append(f)
    t = OxmlElement('w:lvlText'); t.set(qn('w:val'), pattern); lvl.append(t); abstract.append(lvl); root.append(abstract)
    num = OxmlElement('w:num'); num.set(qn('w:numId'), '100')
    aid = OxmlElement('w:abstractNumId'); aid.set(qn('w:val'), '100'); num.append(aid); root.append(num)
    np = OxmlElement('w:numPr')
    for tag, val in [('ilvl', str(level)), ('numId', '100')]:
        el = OxmlElement('w:' + tag); el.set(qn('w:val'), val); np.append(el)
    p._p.get_or_add_pPr().append(np)


SECTION_SIZES = 'The Section and SubSection titles along with their numbers in 5 and 4mm (16 and 14 pt) fonts, respectively, in bold face shall be flushed to the left.'


def test_generated_decimal_sections_are_checked_but_outline_depth_is_not_assumed(tmp_path):
    revision = reviewed(tmp_path, SECTION_SIZES)
    doc = Document(); doc.add_heading('Chapter 1 Introduction', 2)
    repeated = doc.add_heading('Introduction', 3); repeated.runs[0].font.size = Pt(16)
    p = doc.add_paragraph('Architecture', style='List Paragraph')
    p.runs[0].bold = True; p.runs[0].font.size = Pt(14); add_numbering(doc, p)
    doc.add_paragraph('Body paragraph after the heading.')
    result = check_bytes(revision, encoded(doc))
    failed = [i for i in codes(result, 'section_font_size') if i.status == 'FAIL']
    assert len(failed) == 1 and failed[0].paragraph_index == 2 and failed[0].actual['depth'] == 2
    p.runs[0].font.size = Pt(16)
    assert not any(i.status == 'FAIL' for i in codes(check_bytes(revision, encoded(doc)), 'section_font_size'))


def test_numbered_prose_is_not_a_section_heading(tmp_path):
    revision = reviewed(tmp_path, SECTION_SIZES)
    doc = Document(); doc.add_heading('Chapter 1 Introduction', 2)
    p = doc.add_paragraph('A numbered paragraph describes ordinary steps.', style='List Paragraph')
    p.runs[0].font.size = Pt(12); add_numbering(doc, p)
    assert all(i.status == 'NOT_CHECKED' for i in codes(check_bytes(revision, encoded(doc)), 'section_font_size'))


def test_small_caps_mixed_text_does_not_pass_chapter_case(tmp_path):
    revision = reviewed(tmp_path, 'Chapter number and title shall be printed in font size (18pt), using both upper and lower case.')
    doc = Document(); p = doc.add_heading('Chapter 1 Introduction', 2)
    p.runs[0].font.size = Pt(18); p.runs[0].font.small_caps = True
    assert codes(check_bytes(revision, encoded(doc)), 'chapter_case')[0].status == 'FAIL'
    p.runs[0].font.small_caps = False
    assert codes(check_bytes(revision, encoded(doc)), 'chapter_case')[0].status == 'PASS'


def test_caps_on_chapter_number_label_does_not_fail_mixed_title(tmp_path):
    revision = reviewed(tmp_path, 'Chapter number and title shall be printed in font size (18pt), using both upper and lower case.')
    doc = Document(); p = doc.add_heading('', 2)
    p.add_run('  CHAPTER 1').font.all_caps = True
    p.add_run(' ')
    p.add_run('Introduction').font.all_caps = False
    assert codes(check_bytes(revision, encoded(doc)), 'chapter_case')[0].status == 'PASS'


def object_doc():
    doc = Document(); doc.add_heading('Index', 1)
    toc = doc.add_table(rows=4, cols=3)
    for cell, text in zip(toc.rows[0].cells, ['Sr. No.', 'Topic', 'Page No.']): cell.text = text
    toc.cell(1, 0).text = '1'; toc.cell(1, 1).text = 'Introduction'
    toc.cell(1, 2).text = '3'; toc.cell(1, 2).paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
    toc.cell(2, 0).text = '2'; toc.cell(2, 1).text = 'Design'; toc.cell(2, 2).text = '4'
    toc.cell(2, 2).paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
    toc.cell(3, 0).text = '1.1'; toc.cell(3, 1).text = '1.1 Architecture'; toc.cell(3, 2).text = '3'
    toc.cell(3, 2).paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
    doc.add_heading('List of Figures', 1); doc.add_heading('List of Tables', 1)
    doc.add_heading('Chapter 1 Introduction', 2)
    doc.add_paragraph('1.1 Architecture', style='Heading 3')
    doc.add_picture(BytesIO(base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aC2sAAAAASUVORK5CYII=')))
    doc.add_paragraph('Fig 1.1 Fictional diagram', style='Caption')
    doc.add_paragraph('Table 1.1 Fictional results', style='Caption')
    t = doc.add_table(rows=2, cols=2); t.cell(0,0).text = 'Name'; t.cell(1,0).text = 'Example'
    return doc


def test_native_contents_captions_and_separate_lists_can_pass(tmp_path):
    revision = reviewed(tmp_path, CONTENTS, CAPTIONS,
        'Two separate lists of Figure captions and Table titles along with their numbers shall follow the Contents.')
    result = check_bytes(revision, encoded(object_doc()))
    for kind in ['contents_structure', 'contents_page_alignment', 'figure_captions', 'table_titles', 'illustration_lists']:
        checked = [i for i in codes(result, kind) if not i.item_id.endswith(':completeness')]
        assert checked and all(i.status == 'PASS' for i in checked), kind


def test_native_contents_ranges_alignment_and_bullets_fail(tmp_path):
    revision = reviewed(tmp_path, CONTENTS)
    doc = object_doc(); table = doc.tables[0]
    table.cell(1,2).text = '3 - 5'; table.cell(1,2).paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
    p = table.cell(1,1).add_paragraph('Architecture'); add_numbering(doc, p, pattern='-', fmt='bullet', level=0)
    result = check_bytes(revision, encoded(doc))
    failed = [i for i in codes(result, 'contents_structure') if i.status == 'FAIL']
    assert len(failed) == 2
    assert any(i.status == 'FAIL' for i in codes(result, 'contents_page_alignment'))


def test_shared_contents_page_reference_cannot_certify_individual_entries(tmp_path):
    revision = reviewed(tmp_path, CONTENTS)
    doc = object_doc(); doc.tables[0].cell(1,1).add_paragraph('1.1 Architecture')
    result = check_bytes(revision, encoded(doc))
    row = next(i for i in codes(result, 'contents_structure') if i.item_id.endswith('0:1:page'))
    assert row.status == 'NOT_CHECKED'


def test_illustration_lists_before_contents_fail(tmp_path):
    revision = reviewed(tmp_path, 'Two separate lists of Figure captions and Table titles shall follow the Contents.')
    doc = object_doc(); heading = next(p for p in doc.paragraphs if p.text == 'List of Tables')
    heading._p.getparent().remove(heading._p); doc._element.body.insert(0, heading._p)
    assert any(i.status == 'FAIL' and i.actual['list'] == 'list of tables' for i in codes(check_bytes(revision, encoded(doc)), 'illustration_lists'))


def test_missing_table_title_and_list_fail_but_image_caption_absence_needs_review(tmp_path):
    revision = reviewed(tmp_path, CAPTIONS,
        'Two separate lists of Figure captions and Table titles shall follow the Contents.')
    doc = object_doc()
    for p in list(doc.paragraphs):
        if p.text.startswith(('Fig ', 'Table ', 'List of Tables')): p._p.getparent().remove(p._p)
    result = check_bytes(revision, encoded(doc))
    assert codes(result, 'table_titles')[0].status == 'FAIL'
    assert codes(result, 'figure_captions')[0].status == 'NOT_CHECKED'
    assert any(i.status == 'FAIL' for i in codes(result, 'illustration_lists'))


@pytest.mark.parametrize('change', ['wrong_chapter', 'duplicate_number', 'generated_field'])
def test_caption_counter_contradictions_and_cached_fields(tmp_path, change):
    revision = reviewed(tmp_path, CAPTIONS)
    doc = object_doc(); caption = next(p for p in doc.paragraphs if p.text.startswith('Fig '))
    if change == 'wrong_chapter': caption.text = 'Fig 3.1 Wrong chapter'
    elif change == 'duplicate_number':
        image = next(p for p in doc.paragraphs if p._p.xpath('.//w:drawing'))
        body = doc._element.body
        body.insert(len(body)-1, etree.fromstring(etree.tostring(image._p)))
        doc.add_paragraph('Fig 1.1 Duplicate')
    else:
        f = OxmlElement('w:fldSimple'); f.set(qn('w:instr'), 'SEQ Figure'); caption._p.append(f)
    statuses = [i.status for i in codes(check_bytes(revision, encoded(doc)), 'figure_captions')]
    assert ('NOT_CHECKED' if change == 'generated_field' else 'FAIL') in statuses


def test_negated_and_optional_structural_instructions_do_not_become_required_rules():
    doc = Document(); doc.add_paragraph('Guidelines for project report format')
    doc.add_paragraph('Page numbering shall not be Hindu-Arabic numerals at the center of the footer.')
    doc.add_paragraph('Two separate lists of Figure captions and Table titles may follow the Contents.')
    doc.add_paragraph('Chapter number and title must not be printed in bold face.')
    kinds = {c.value.kind for c in analyze_bytes(encoded(doc)).candidates if c.origin == 'EXPLICIT_PROSE'}
    assert not kinds & {'chapter_bold', 'page_number_alignment', 'body_page_number_format', 'illustration_lists'}
