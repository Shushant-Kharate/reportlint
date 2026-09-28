"""Orchestrates DocxPackage + EffectiveStyleResolver into a DocumentModel,
then derives heading/section structure from the resolved paragraphs."""

import re
from dataclasses import dataclass, field
from lxml import etree

from app.ooxml.constants import qn, twips_to_pt, emu_to_inch
from app.ooxml.docx_loader import DocxPackage
from app.ooxml.style_resolver import StyleRegistry, EffectiveStyleResolver, get_doc_defaults
from app.models.document_model import (
    DocumentModel, ParagraphModel, RunModel, TableModel, ImageModel,
    SectionPropertiesModel, Confidence,
)

HEADING_STYLE_RE = re.compile(r"^Heading\s?([1-9])$", re.IGNORECASE)


def _paragraph_text(p_el) -> str:
    texts = p_el.findall(f".//{qn('w:t')}")
    return "".join(t.text or "" for t in texts)


def _detect_heading(style_name: str | None, outline_level: int | None,
                     bold: bool | None, font_size_pt: float | None,
                     body_font_size: float | None, alignment, text: str):
    """Returns (is_heading, heading_level, heading_source)."""
    if style_name:
        m = HEADING_STYLE_RE.match(style_name)
        if m:
            return True, int(m.group(1)), "STYLE"
        if style_name.strip().lower() == "title":
            return True, 1, "STYLE"

    if outline_level is not None and 0 <= outline_level <= 8:
        return True, outline_level + 1, "OUTLINE"

    # Heuristics must not promote names and cover-page labels to chapters.
    # Unstyled headings are recognized only from the section vocabulary.
    from app.models.document_model import Alignment
    from app.rules.section_catalog import DEFAULT_ALIASES, normalize_heading
    known = set(DEFAULT_ALIASES) | {"index", "contents", "table of contents", "list of figures", "list of tables"}
    known.update(alias for aliases in DEFAULT_ALIASES.values() for alias in aliases)
    size_bigger = body_font_size is not None and font_size_pt is not None and font_size_pt >= body_font_size + 1
    if normalize_heading(text) in known and (size_bigger or bold or alignment == Alignment.CENTER):
        return True, 2, "HEURISTIC"

    return False, None, None


def build_document_model(pkg: DocxPackage, filename: str) -> DocumentModel:
    registry = StyleRegistry(pkg.styles_tree)
    doc_default_font, doc_default_size, doc_default_ppr = get_doc_defaults(pkg.styles_tree)
    resolver = EffectiveStyleResolver(registry, doc_default_font, doc_default_size, doc_default_ppr)

    body = pkg.document_tree.getroot().find(qn("w:body"))

    # ---- Pass 1: sections (sectPr) ----
    sections: list[SectionPropertiesModel] = []
    for sectPr in body.findall(f".//{qn('w:sectPr')}"):
        sections.append(_parse_sect_pr(sectPr))
    if not sections:
        sections.append(SectionPropertiesModel())

    # ---- Pass 2: paragraphs (rough pass to get body font size mode for heuristic) ----
    para_elements = [el for el in body if el.tag in (qn("w:p"), qn("w:tbl"))]

    prelim_sizes: list[float] = []
    for el in para_elements:
        if el.tag != qn("w:p"):
            continue
        p_style_el = el.find(f"{qn('w:pPr')}/{qn('w:pStyle')}")
        style_id = p_style_el.get(qn("w:val")) if p_style_el is not None else None
        for r_el in el.findall(qn("w:r")):
            rs = resolver.resolve_run(r_el, style_id)
            if rs.font_size_pt is not None:
                prelim_sizes.append(rs.font_size_pt)
    body_font_size_mode = _mode(prelim_sizes) if prelim_sizes else None

    # ---- Pass 3: full paragraph/table/image build ----
    paragraphs: list[ParagraphModel] = []
    tables: list[TableModel] = []
    images: list[ImageModel] = []

    p_index = 0
    t_index = 0
    img_index = 0
    for el in para_elements:
        if el.tag == qn("w:p"):
            para_model, has_image = _build_paragraph(
                el, p_index, registry, resolver, body_font_size_mode)
            paragraphs.append(para_model)
            if has_image:
                for width_in, height_in in has_image:
                    images.append(ImageModel(
                        index=img_index, preceding_paragraph_index=p_index,
                        width_in=width_in, height_in=height_in,
                        caption_text=_find_caption(paragraphs, p_index, "figure"),
                    ))
                    img_index += 1
            p_index += 1
        elif el.tag == qn("w:tbl"):
            rows = el.findall(qn("w:tr"))
            cols = rows[0].findall(qn("w:tc")) if rows else []
            tables.append(TableModel(
                index=t_index,
                preceding_paragraph_index=p_index - 1 if p_index > 0 else None,
                row_count=len(rows), col_count=len(cols),
                caption_text=_find_caption(paragraphs, p_index - 1, "table"),
            ))
            t_index += 1

    return DocumentModel(
        source_filename=filename,
        paragraphs=paragraphs,
        tables=tables,
        images=images,
        sections=sections,
        doc_default_font_name=doc_default_font,
        doc_default_font_size_pt=doc_default_size,
    )


def _mode(values: list[float]) -> float:
    from collections import Counter
    return Counter(values).most_common(1)[0][0]


def _find_caption(paragraphs, near_index, kind):
    if near_index is None or near_index < 0:
        return None
    pattern = re.compile(rf"^\s*{kind}\s*\d*[:.\-]", re.IGNORECASE)
    # check next paragraph first (common), then previous
    for idx in (near_index + 1, near_index):
        if 0 <= idx < len(paragraphs) and pattern.match(paragraphs[idx].text):
            return paragraphs[idx].text
    return None


def _build_paragraph(p_el, index, registry, resolver, body_font_size_mode):
    p_style_el = p_el.find(f"{qn('w:pPr')}/{qn('w:pStyle')}")
    style_id = p_style_el.get(qn("w:val")) if p_style_el is not None else None
    style_name = registry.display_name(style_id) if style_id else None

    outline_el = p_el.find(f"{qn('w:pPr')}/{qn('w:outlineLvl')}")
    outline_level = int(outline_el.get(qn("w:val"))) if outline_el is not None else None

    para_style = resolver.resolve_paragraph(p_el, style_id)

    runs: list[RunModel] = []
    has_image_dims = []
    for r_el in p_el.findall(f".//{qn('w:r')}"):
        run_style = resolver.resolve_run(r_el, style_id)
        text = "".join(t.text or "" for t in r_el.findall(qn("w:t")))
        runs.append(RunModel(
            text=text,
            font_name=run_style.font_name,
            font_size_pt=run_style.font_size_pt,
            bold=run_style.bold,
            italic=run_style.italic,
            underline=run_style.underline,
            confidence=run_style.confidence,
        ))
        for extent in r_el.findall(f".//{qn('wp:extent')}"):
            has_image_dims.append((emu_to_inch(extent.get("cx")), emu_to_inch(extent.get("cy"))))

    text = "".join(r.text for r in runs)

    # Representative font/size for heading heuristic = first run with a value
    rep_font_size = next((r.font_size_pt for r in runs if r.font_size_pt is not None), None)
    rep_bold = next((r.bold for r in runs if r.bold is not None), None)

    is_heading, heading_level, heading_source = _detect_heading(
        style_name, outline_level, rep_bold, rep_font_size,
        body_font_size_mode, para_style.alignment, text)

    return ParagraphModel(
        index=index, text=text, style_name=style_name, style_id=style_id,
        outline_level=outline_level,
        alignment=para_style.alignment,
        line_spacing=para_style.line_spacing,
        line_spacing_rule=para_style.line_spacing_rule,
        line_spacing_exact_pt=para_style.line_spacing_exact_pt,
        spacing_before_pt=para_style.spacing_before_pt,
        spacing_after_pt=para_style.spacing_after_pt,
        left_indent_pt=para_style.left_indent_pt,
        right_indent_pt=para_style.right_indent_pt,
        first_line_indent_pt=para_style.first_line_indent_pt,
        runs=runs,
        is_heading=is_heading,
        heading_level=heading_level,
        heading_source=heading_source,
    ), has_image_dims


def _parse_sect_pr(sectPr, start_index=0) -> SectionPropertiesModel:
    pg_sz = sectPr.find(qn("w:pgSz"))
    pg_mar = sectPr.find(qn("w:pgMar"))
    width = height = None
    orientation = None
    if pg_sz is not None:
        w_val = pg_sz.get(qn("w:w"))
        h_val = pg_sz.get(qn("w:h"))
        width = twips_to_pt(w_val) if w_val else None
        height = twips_to_pt(h_val) if h_val else None
        orientation = pg_sz.get(qn("w:orient"), "portrait")

    def m(attr):
        if pg_mar is None:
            return None
        v = pg_mar.get(qn(f"w:{attr}"))
        return twips_to_pt(v) if v is not None else None

    return SectionPropertiesModel(
        page_width_pt=width, page_height_pt=height, orientation=orientation,
        margin_top_pt=m("top"), margin_bottom_pt=m("bottom"),
        margin_left_pt=m("left"), margin_right_pt=m("right"),
        margin_header_pt=m("header"), margin_footer_pt=m("footer"),
        applies_from_paragraph_index=start_index,
    )


# ---------------- Section tree (DocumentSection) ----------------

@dataclass
class DocumentSection:
    heading_text: str
    heading_text_normalized: str
    heading_level: int
    start_paragraph_index: int
    end_paragraph_index: int | None = None
    paragraph_indices: list[int] = field(default_factory=list)
    subsections: list["DocumentSection"] = field(default_factory=list)


def extract_sections(doc: DocumentModel) -> list[DocumentSection]:
    from app.rules.section_catalog import normalize_heading

    headings = [p for p in doc.paragraphs if p.is_heading]
    top_level: list[DocumentSection] = []
    stack: list[DocumentSection] = []

    def close_at_or_above(level, end_idx):
        while stack and stack[-1].heading_level >= level:
            closed = stack.pop()
            closed.end_paragraph_index = end_idx

    for h in headings:
        close_at_or_above(h.heading_level, h.index)
        sec = DocumentSection(
            heading_text=h.text,
            heading_text_normalized=normalize_heading(h.text),
            heading_level=h.heading_level,
            start_paragraph_index=h.index,
        )
        if stack:
            stack[-1].subsections.append(sec)
        else:
            top_level.append(sec)
        stack.append(sec)

    total_paras = len(doc.paragraphs)
    close_at_or_above(1, total_paras)

    # assign paragraph_indices per section (flat, includes nested content too
    # for the parent; validators needing "own text only" can subtract children)
    all_sections: list[DocumentSection] = []

    def collect(secs):
        for s in secs:
            all_sections.append(s)
            collect(s.subsections)

    collect(top_level)
    for s in all_sections:
        end = s.end_paragraph_index if s.end_paragraph_index is not None else total_paras
        s.paragraph_indices = list(range(s.start_paragraph_index, end))

    return top_level
