from hashlib import sha256

import pymupdf
import pytest
from fastapi.testclient import TestClient

from app.builtin_formats import builtin, CatalogRepository, DIRECTORY
from app.checking.pdf import check_pdf, InvalidPdfError
from app.ooxml.docx_loader import DocxPackage
from app.ooxml.constants import NS
from app.review.repository import RevisionRepository
from app.review.service import ReviewError, snapshot_hash

IEEE = 'builtin-ieee-conference-letter'
PROSE = ('This fictional paragraph describes a measured process and explains its results in ordinary prose. '
         'The example uses several complete sentences so that layout evidence is distinct from a heading or caption. ') * 15


def pdf(layout='two', width=612, height=792, pages=2):
    doc = pymupdf.open()
    for _ in range(pages):
        page = doc.new_page(width=width,height=height)
        if layout == 'two':
            for x0,x1 in [(45,295),(317,567)]:
                assert page.insert_textbox((x0,80,x1,700),PROSE[:1800],fontsize=10,fontname='Times-Roman') >= 0
        elif layout == 'single':
            for y in [80,270,460]:
                assert page.insert_textbox((45,y,567,y+170),PROSE[:1100],fontsize=10,fontname='Times-Roman') >= 0
    data = doc.tobytes()
    doc.close()
    return data


def test_ieee_curated_publication_rejects_caption_size_as_body_rule():
    r = builtin(IEEE)
    assert snapshot_hash(r) == r.snapshot_sha256
    assert sha256((DIRECTORY/'ieee-conference-letter.docx').read_bytes()).hexdigest() == r.analysis.source_sha256
    assert {x.value.kind for x in r.publication.rules} == {'page_size','font_family','body_columns'}
    sampled = next(c for c in r.analysis.candidates if c.value.kind == 'font_size')
    assert sampled.value.expected_pt == 8
    assert next(d for d in r.candidate_decisions if d.candidate_id == sampled.candidate_id).action == 'REJECT'


def test_strict_template_measurements_and_text_are_read_without_rewriting_source():
    path = DIRECTORY/'ieee-conference-letter.docx'
    before = path.read_bytes()
    package = DocxPackage.load(str(path))
    sizes = package.document_tree.xpath('//w:sectPr/w:pgSz',namespaces=NS)
    assert all(n.get('{'+NS['w']+'}w') == '12240' for n in sizes)
    assert all(n.get('{'+NS['w']+'}h') == '15840' for n in sizes)
    assert 'This template, modified' in ''.join(package.document_tree.getroot().itertext())
    assert path.read_bytes() == before


def test_ieee_source_is_not_failed_by_its_own_reviewed_baseline():
    from app.checking.service import check_bytes
    result = check_bytes(builtin(IEEE),(DIRECTORY/'ieee-conference-letter.docx').read_bytes())
    assert result.counts['PASS'] > 0 and result.counts['FAIL'] == 0


def test_two_column_pdf_and_manual_typography_are_separate():
    result = check_pdf(builtin(IEEE),pdf())
    assert result.report_format == 'pdf' and result.outcome == 'INDETERMINATE'
    assert result.counts['FAIL'] == 0
    assert sum(i.code == 'PDF_TWO_COLUMN_PROSE' and i.status == 'PASS' for i in result.items) == 2
    assert all(i.status == 'NOT_CHECKED' for i in result.items if i.expected and i.expected['kind'] == 'font_family')
    assert {i.page_number for i in result.items if i.code == 'PDF_PAGE_SIZE'} == {1,2}


def test_wrong_page_size_is_a_real_failure():
    result = check_pdf(builtin(IEEE),pdf(width=595,height=842))
    assert result.outcome == 'FAIL'
    assert all(i.status == 'FAIL' for i in result.items if i.code == 'PDF_PAGE_SIZE')


def test_sustained_single_column_prose_after_first_page_is_detected():
    result = check_pdf(builtin(IEEE),pdf(layout='single'))
    failures = [i for i in result.items if i.code == 'PDF_SINGLE_COLUMN_PROSE']
    assert failures and failures[0].status == 'FAIL' and failures[0].page_number == 2


def test_blank_or_image_page_is_not_called_bad_column_layout():
    result = check_pdf(builtin(IEEE),pdf(layout='blank'))
    assert result.counts['FAIL'] == 0
    assert any(i.code == 'PDF_TEXT_OR_PROSE_UNAVAILABLE' and i.status == 'NOT_CHECKED' for i in result.items)


@pytest.mark.parametrize('change',['crop','rotate'])
def test_crop_and_rotation_do_not_claim_page_compliance(change):
    doc = pymupdf.open(stream=pdf(),filetype='pdf')
    if change == 'crop':
        doc[0].set_cropbox((20,20,590,770))
    else:
        doc[0].set_rotation(90)
    data = doc.tobytes();doc.close()
    result = check_pdf(builtin(IEEE),data)
    assert any(i.page_number == 1 and i.code == 'PDF_CROP_OR_ROTATION_REVIEW' and i.status == 'NOT_CHECKED' for i in result.items)


@pytest.mark.parametrize('data',[b'not a PDF',b'%PDF-broken'])
def test_invalid_pdf_is_rejected(data):
    with pytest.raises(InvalidPdfError):
        check_pdf(builtin(IEEE),data)


def test_encrypted_pdf_is_rejected():
    doc = pymupdf.open(stream=pdf(),filetype='pdf')
    data = doc.tobytes(encryption=pymupdf.PDF_ENCRYPT_AES_256,owner_pw='owner-secret',user_pw='reader-secret')
    doc.close()
    with pytest.raises(InvalidPdfError):
        check_pdf(builtin(IEEE),data)


def test_ieee_catalog_is_read_only_and_custom_copy_is_a_draft(tmp_path):
    catalog = CatalogRepository(RevisionRepository(tmp_path/'test.db'))
    assert sum(t.get('builtin',False) for t in catalog.list_templates()) == 2
    original = builtin(IEEE)
    with pytest.raises(ReviewError):
        catalog.change(IEEE,original.revision_id,None,None)
    copy = catalog.fork(IEEE,original.revision_id)
    assert copy.status == 'DRAFT' and copy.template_id != IEEE


def test_api_checks_original_pdf_and_refuses_word_role_decisions(tmp_path,monkeypatch):
    from app.main import app
    from app import storage
    monkeypatch.setattr(storage,'STORAGE_DIR',tmp_path)
    revision = builtin(IEEE)
    route = f'/api/v2/templates/{IEEE}/revisions/{revision.revision_id}'
    with TestClient(app) as client:
        response = client.post(route+'/check',files={'file':('paper.pdf',pdf(),'application/pdf')})
        assert response.status_code == 200 and response.json()['report_format'] == 'pdf'
        assert client.post(route+'/check',files={'file':('paper.pdf',pdf())},data={'role_review':'{}'}).status_code == 422
        assert client.post(route+'/role-preview',files={'file':('paper.pdf',pdf())}).status_code == 415
        downloaded = client.get('/api/builtin-formats/ieee-conference-letter/source')
        assert downloaded.content == (DIRECTORY/'ieee-conference-letter.docx').read_bytes()
        assert client.get('/api/builtin-formats/unknown/source').status_code == 404
