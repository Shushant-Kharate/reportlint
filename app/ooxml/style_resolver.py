"""Effective Style Resolver.

Resolves the real, rendered font/size/bold/italic/underline for a run, and
alignment/line-spacing/spacing/indentation for a paragraph, by walking the
OOXML inheritance chain:

    run direct formatting
      -> run's character style (+ its w:basedOn chain)
        -> paragraph's paragraph style (+ its w:basedOn chain)
          -> styles.xml docDefaults
            -> UNKNOWN (never guessed)

python-docx's run.font.name/.size are NOT used here on purpose — they return
None for the (very common) case where formatting is inherited rather than
set directly on the run, which is exactly the ambiguity this module exists
to resolve.
"""

from dataclasses import dataclass
from lxml import etree
from app.ooxml.constants import qn, twips_to_pt, halfpt_to_pt
from app.models.document_model import Confidence, Alignment


@dataclass
class StyleEntry:
    style_id: str
    style_type: str  # "paragraph" | "character" | "table" | "numbering"
    name: str | None
    based_on: str | None
    is_default: bool
    rpr: etree._Element | None
    ppr: etree._Element | None


class StyleRegistry:
    def __init__(self, styles_tree):
        self.styles: dict[str, StyleEntry] = {}
        self.default_paragraph_style_id: str | None = None
        if styles_tree is not None:
            self._parse(styles_tree)

    def _parse(self, styles_tree):
        root = styles_tree.getroot() if hasattr(styles_tree, "getroot") else styles_tree
        for style_el in root.findall(qn("w:style")):
            style_id = style_el.get(qn("w:styleId"))
            style_type = style_el.get(qn("w:type"))
            is_default = style_el.get(qn("w:default")) == "1"
            name_el = style_el.find(qn("w:name"))
            name = name_el.get(qn("w:val")) if name_el is not None else None
            based_on_el = style_el.find(qn("w:basedOn"))
            based_on = based_on_el.get(qn("w:val")) if based_on_el is not None else None
            rpr = style_el.find(qn("w:rPr"))
            ppr = style_el.find(qn("w:pPr"))
            entry = StyleEntry(style_id, style_type, name, based_on, is_default, rpr, ppr)
            self.styles[style_id] = entry
            if style_type == "paragraph" and is_default:
                self.default_paragraph_style_id = style_id

    def get(self, style_id: str | None) -> StyleEntry | None:
        if style_id is None:
            return None
        return self.styles.get(style_id)

    def display_name(self, style_id: str | None) -> str | None:
        entry = self.get(style_id)
        return entry.name if entry else None

    def _walk_chain(self, style_id: str | None, attr: str) -> list[etree._Element]:
        """attr is 'rpr' or 'ppr'. Returns elements nearest-first, guarding
        against circular basedOn references."""
        chain = []
        visited = set()
        current = style_id
        while current and current not in visited:
            visited.add(current)
            entry = self.styles.get(current)
            if entry is None:
                break
            el = getattr(entry, attr)
            if el is not None:
                chain.append(el)
            current = entry.based_on
        return chain

    def resolve_rpr_chain(self, style_id: str | None) -> list[etree._Element]:
        return self._walk_chain(style_id, "rpr")

    def resolve_ppr_chain(self, style_id: str | None) -> list[etree._Element]:
        return self._walk_chain(style_id, "ppr")


def get_doc_defaults(styles_tree) -> tuple[str | None, float | None, etree._Element | None]:
    """Returns (font_name, font_size_pt, doc_default_ppr_element)."""
    if styles_tree is None:
        return None, None, None
    root = styles_tree.getroot() if hasattr(styles_tree, "getroot") else styles_tree
    rpr_default = root.find(f"{qn('w:docDefaults')}/{qn('w:rPrDefault')}/{qn('w:rPr')}")
    ppr_default = root.find(f"{qn('w:docDefaults')}/{qn('w:pPrDefault')}/{qn('w:pPr')}")

    font_name = None
    font_size = None
    if rpr_default is not None:
        rfonts = rpr_default.find(qn("w:rFonts"))
        if rfonts is not None:
            font_name = rfonts.get(qn("w:ascii")) or rfonts.get(qn("w:hAnsi"))
        sz = rpr_default.find(qn("w:sz"))
        if sz is not None:
            font_size = halfpt_to_pt(sz.get(qn("w:val")))
    return font_name, font_size, ppr_default


def _first_non_none(*values):
    for v in values:
        if v is not None:
            return v
    return None


class ResolvedRunStyle:
    def __init__(self):
        self.font_name = None
        self.font_size_pt = None
        self.bold = None
        self.italic = None
        self.underline = None
        self.confidence = Confidence.UNKNOWN


class ResolvedParagraphStyle:
    def __init__(self):
        self.alignment = Alignment.UNKNOWN
        self.line_spacing = None
        self.line_spacing_rule = None
        self.line_spacing_exact_pt = None
        self.spacing_before_pt = None
        self.spacing_after_pt = None
        self.left_indent_pt = None
        self.right_indent_pt = None
        self.first_line_indent_pt = None


def _extract_rfonts(rpr_el):
    if rpr_el is None:
        return None
    rfonts = rpr_el.find(qn("w:rFonts"))
    if rfonts is None:
        return None
    return rfonts.get(qn("w:ascii")) or rfonts.get(qn("w:hAnsi"))


def _extract_sz(rpr_el):
    if rpr_el is None:
        return None
    sz = rpr_el.find(qn("w:sz"))
    if sz is None:
        return None
    return halfpt_to_pt(sz.get(qn("w:val")))


def _extract_toggle(rpr_el, tag):
    """w:b / w:i / w:u presence-with-no-val => True. val='0'/'false' => False.
    Element absent => None (not explicit at this level)."""
    if rpr_el is None:
        return None
    el = rpr_el.find(qn(tag))
    if el is None:
        return None
    val = el.get(qn("w:val"))
    if val is None:
        return True
    return val not in ("0", "false", "none")


class EffectiveStyleResolver:
    def __init__(self, style_registry: StyleRegistry, doc_default_font: str | None,
                 doc_default_size: float | None, doc_default_ppr: etree._Element | None = None):
        self.registry = style_registry
        self.doc_default_font = doc_default_font
        self.doc_default_size = doc_default_size
        self.doc_default_ppr = doc_default_ppr

    # ---------- RUN ----------
    def resolve_run(self, run_el, paragraph_style_id: str | None) -> ResolvedRunStyle:
        result = ResolvedRunStyle()

        run_rpr = run_el.find(qn("w:rPr")) if run_el is not None else None
        char_style_id = None
        if run_rpr is not None:
            rstyle = run_rpr.find(qn("w:rStyle"))
            if rstyle is not None:
                char_style_id = rstyle.get(qn("w:val"))

        char_chain = self.registry.resolve_rpr_chain(char_style_id) if char_style_id else []
        para_chain = self.registry.resolve_rpr_chain(paragraph_style_id or self.registry.default_paragraph_style_id)

        # Font name
        font_name, font_conf = self._resolve_scalar(
            run_rpr, char_chain, para_chain, _extract_rfonts, self.doc_default_font)
        result.font_name = font_name

        # Font size
        size, size_conf = self._resolve_scalar(
            run_rpr, char_chain, para_chain, _extract_sz, self.doc_default_size)
        result.font_size_pt = size

        # Bold / italic / underline (toggles, nearest-explicit-wins per V1 simplification)
        result.bold, bold_conf = self._resolve_toggle(run_rpr, char_chain, para_chain, "w:b")
        result.italic, italic_conf = self._resolve_toggle(run_rpr, char_chain, para_chain, "w:i")
        result.underline, _u = self._resolve_toggle(run_rpr, char_chain, para_chain, "w:u")

        # Overall confidence = weakest link among font/size (the properties
        # validators actually care about most)
        result.confidence = max([font_conf, size_conf], key=lambda c: _CONF_RANK[c])
        return result

    def _resolve_scalar(self, run_rpr, char_chain, para_chain, extractor, doc_default):
        v = extractor(run_rpr)
        if v is not None:
            return v, Confidence.EXPLICIT
        for el in char_chain:
            v = extractor(el)
            if v is not None:
                return v, Confidence.INHERITED
        for el in para_chain:
            v = extractor(el)
            if v is not None:
                return v, Confidence.INHERITED
        if doc_default is not None:
            return doc_default, Confidence.DEFAULT
        return None, Confidence.UNKNOWN

    def _resolve_toggle(self, run_rpr, char_chain, para_chain, tag):
        v = _extract_toggle(run_rpr, tag)
        if v is not None:
            return v, Confidence.EXPLICIT
        for el in char_chain:
            v = _extract_toggle(el, tag)
            if v is not None:
                return v, Confidence.INHERITED
        for el in para_chain:
            v = _extract_toggle(el, tag)
            if v is not None:
                return v, Confidence.INHERITED
        return False, Confidence.DEFAULT  # absence at every level == not bold/italic

    # ---------- PARAGRAPH ----------
    def resolve_paragraph(self, paragraph_el, style_id: str | None) -> ResolvedParagraphStyle:
        result = ResolvedParagraphStyle()
        ppr = paragraph_el.find(qn("w:pPr")) if paragraph_el is not None else None
        para_chain = self.registry.resolve_ppr_chain(style_id or self.registry.default_paragraph_style_id)
        chain = ([ppr] if ppr is not None else []) + para_chain + \
                ([self.doc_default_ppr] if self.doc_default_ppr is not None else [])

        # Alignment
        for el in chain:
            jc = el.find(qn("w:jc")) if el is not None else None
            if jc is not None:
                val = jc.get(qn("w:val"))
                result.alignment = {
                    "left": Alignment.LEFT, "start": Alignment.LEFT,
                    "center": Alignment.CENTER,
                    "right": Alignment.RIGHT, "end": Alignment.RIGHT,
                    "both": Alignment.JUSTIFY, "justify": Alignment.JUSTIFY,
                }.get(val, Alignment.UNKNOWN)
                break

        # Spacing (before/after/line)
        for el in chain:
            spacing = el.find(qn("w:spacing")) if el is not None else None
            if spacing is None:
                continue
            if result.spacing_before_pt is None and spacing.get(qn("w:before")) is not None:
                result.spacing_before_pt = twips_to_pt(spacing.get(qn("w:before")))
            if result.spacing_after_pt is None and spacing.get(qn("w:after")) is not None:
                result.spacing_after_pt = twips_to_pt(spacing.get(qn("w:after")))
            if result.line_spacing_rule is None and spacing.get(qn("w:line")) is not None:
                line_val = int(spacing.get(qn("w:line")))
                rule = spacing.get(qn("w:lineRule"), "auto")
                result.line_spacing_rule = rule
                if rule == "auto":
                    result.line_spacing = line_val / 240
                else:
                    result.line_spacing_exact_pt = twips_to_pt(line_val)
            if result.spacing_before_pt is not None and result.spacing_after_pt is not None \
                    and result.line_spacing is not None:
                break

        # Indentation
        for el in chain:
            ind = el.find(qn("w:ind")) if el is not None else None
            if ind is None:
                continue
            if result.left_indent_pt is None and ind.get(qn("w:left")) is not None:
                result.left_indent_pt = twips_to_pt(ind.get(qn("w:left")))
            if result.right_indent_pt is None and ind.get(qn("w:right")) is not None:
                result.right_indent_pt = twips_to_pt(ind.get(qn("w:right")))
            if result.first_line_indent_pt is None:
                if ind.get(qn("w:firstLine")) is not None:
                    result.first_line_indent_pt = twips_to_pt(ind.get(qn("w:firstLine")))
                elif ind.get(qn("w:hanging")) is not None:
                    result.first_line_indent_pt = -twips_to_pt(ind.get(qn("w:hanging")))
            if result.left_indent_pt is not None and result.right_indent_pt is not None \
                    and result.first_line_indent_pt is not None:
                break

        return result


_CONF_RANK = {
    Confidence.EXPLICIT: 0,
    Confidence.INHERITED: 1,
    Confidence.DEFAULT: 2,
    Confidence.UNKNOWN: 3,
}
