import sys
import json
from app.ooxml.docx_loader import DocxPackage
from app.ooxml.structure_extractor import build_document_model, extract_sections


def main(path):
    pkg = DocxPackage.load(path)
    doc = build_document_model(pkg, path)
    print(f"Paragraphs: {len(doc.paragraphs)}  Tables: {len(doc.tables)}  Images: {len(doc.images)}")
    print(f"doc_default_font={doc.doc_default_font_name} size={doc.doc_default_font_size_pt}")
    print(f"sections(page): {doc.sections}")
    print("\n--- Headings detected ---")
    for p in doc.paragraphs:
        if p.is_heading:
            print(f"[{p.index:4d}] L{p.heading_level} ({p.heading_source:9s}) "
                  f"style={p.style_name!r:20s} align={p.alignment.value:8s} "
                  f"text={p.text[:60]!r}")

    print("\n--- Section tree (top-level) ---")
    tree = extract_sections(doc)
    for s in tree:
        print(f"'{s.heading_text}' -> norm='{s.heading_text_normalized}' "
              f"paras[{s.start_paragraph_index}:{s.end_paragraph_index}] "
              f"subsections={[c.heading_text for c in s.subsections]}")

    print("\n--- Sample resolved runs (first 15 non-empty) ---")
    count = 0
    for p in doc.paragraphs:
        for r in p.runs:
            if r.text.strip():
                print(f"  p{p.index} conf={r.confidence.value:9s} font={r.font_name!r} "
                      f"size={r.font_size_pt} bold={r.bold} text={r.text[:40]!r}")
                count += 1
                break
        if count >= 15:
            break


if __name__ == "__main__":
    main(sys.argv[1])
