import sys
from app.ooxml.docx_loader import DocxPackage
from app.ooxml.structure_extractor import build_document_model
from app.pagination.libreoffice_render import (
    render_docx_to_pdf, extract_page_texts, match_paragraphs_to_pages)


def main(path):
    pkg = DocxPackage.load(path)
    doc = build_document_model(pkg, path)

    print(f"Rendering {path} via LibreOffice...")
    pdf_path = render_docx_to_pdf(path)
    print(f"Rendered to {pdf_path}")

    page_texts = extract_page_texts(pdf_path)
    print(f"PDF has {len(page_texts)} pages")

    matches = match_paragraphs_to_pages(doc, page_texts)

    matched = sum(1 for m in matches if m.page_number is not None)
    print(f"\nMatched {matched}/{len(matches)} paragraphs "
          f"({100 * matched / len(matches):.1f}%)")

    print(f"\n{'idx':>4} {'page':>5} {'conf':>6}  text")
    for m in matches:
        p = doc.paragraphs[m.paragraph_index]
        if not p.text.strip():
            continue
        page_str = str(m.page_number) if m.page_number else "?"
        print(f"{m.paragraph_index:4d} {page_str:>5} {m.confidence:6.1f}  {p.text[:60]!r}")


if __name__ == "__main__":
    main(sys.argv[1])
