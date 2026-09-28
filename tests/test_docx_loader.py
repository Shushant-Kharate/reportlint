import pytest
from app.ooxml.docx_loader import DocxPackage, InvalidDocxError

FIXTURE = "tests/fixtures/mini_project_1a_format.docx"


def test_loads_real_fixture():
    pkg = DocxPackage.load(FIXTURE)
    assert pkg.document_tree.getroot().tag.endswith("}document")
    assert pkg.styles_tree is not None


def test_corrupted_zip_raises_clean_error(tmp_path):
    bad = tmp_path / "bad.docx"
    bad.write_bytes(b"not a zip file at all")
    with pytest.raises(InvalidDocxError):
        DocxPackage.load(str(bad))


def test_zip_missing_document_xml_raises(tmp_path):
    import zipfile
    bad = tmp_path / "bad2.docx"
    with zipfile.ZipFile(bad, "w") as zf:
        zf.writestr("hello.txt", "not a docx")
    with pytest.raises(InvalidDocxError):
        DocxPackage.load(str(bad))
