"""Conservative main-story paragraph roles; no visual or lexical heading guesses."""
from dataclasses import dataclass
import re

from app.ooxml.constants import NS, qn
from app.ooxml.docx_loader import InvalidDocxError
from app.ooxml.style_resolver import StyleRegistry


@dataclass
class Paragraph:
    index: int
    path: str
    element: object
    text: str
    role: str
    level: int | None
    styles: list
    reviewable: bool = False
    chapter_index: int | None = None


def style_chain(registry, style_id, kind):
    chain, seen = [], set()
    while style_id:
        if style_id in seen or len(seen) >= 100:
            return None
        seen.add(style_id)
        entry = registry.get(style_id)
        if entry is None or entry.style_type != kind:
            return None
        chain.append(entry)
        style_id = entry.based_on
    return chain


def nodes(elements, tag):
    return [child for el in elements if el is not None for child in el.findall(qn(tag))]


def first_property(elements, tag):
    for el in elements:
        if el is not None:
            found = el.findall(qn(tag))
            if found:
                return found[0] if len(found) == 1 else None
    return None


def inventory(package):
    registry = StyleRegistry(package.styles_tree)
    body = package.document_tree.getroot().find(qn("w:body"))
    elements = body.xpath(".//w:p", namespaces=NS)
    if len(elements) > 10000:
        raise InvalidDocxError("Report exceeds the 10000-paragraph role limit")
    if len(body.xpath(".//w:r", namespaces=NS)) > 20000:
        raise InvalidDocxError("Report exceeds the 20000-run role limit")
    result, field_depth = [], 0
    uncertain_structure = bool(body.xpath(".//w:altChunk | .//w:ins | .//w:del | .//w:moveFrom | .//w:moveTo | .//w:sdt | .//w:customXml", namespaces=NS))
    style_elements = package.styles_tree.getroot().findall(qn("w:style")) if package.styles_tree is not None else []
    if len(style_elements) > 5000:
        raise InvalidDocxError("Report exceeds the 5000-style role limit")
    ids = [s.get(qn("w:styleId")) for s in style_elements]
    defaults = [s.get(qn("w:styleId")) for s in style_elements
                if s.get(qn("w:type")) == "paragraph" and s.get(qn("w:default"), "").lower() in {"1", "true", "on"}]
    if len(defaults) == 1:
        registry.default_paragraph_style_id = defaults[0]
    broken_registry = len(ids) != len(set(ids)) or len(defaults) > 1
    uncertain_structure = uncertain_structure or broken_registry
    for index, p in enumerate(elements):
        text = "".join((node.text or "") if node.tag == qn("w:t") else "\t" if node.tag == qn("w:tab") else "\n"
                       for node in p.xpath("./w:r/* | ./w:hyperlink/w:r/*", namespaces=NS)
                       if node.tag in {qn("w:t"), qn("w:tab"), qn("w:br"), qn("w:cr")})
        ppr = p.find(qn("w:pPr"))
        styles = nodes([ppr], "w:pStyle")
        style_id = styles[0].get(qn("w:val")) if len(styles) == 1 else registry.default_paragraph_style_id
        chain = style_chain(registry, style_id, "paragraph") if len(styles) <= 1 else None
        if styles and not style_id:
            chain = None
        if broken_registry:
            chain = None
        role, level = "UNKNOWN", None
        field = field_depth > 0 or bool(p.xpath(".//w:fldSimple | .//w:fldChar | .//w:instrText", namespaces=NS))
        for marker in p.xpath(".//w:fldChar", namespaces=NS):
            kind = marker.get(qn("w:fldCharType"))
            if kind == "begin":
                field_depth += 1
            elif kind == "end":
                field_depth = max(0, field_depth - 1)
        names = [s.name.casefold().strip() for s in chain or [] if s.name]
        if p.getparent() is not body:
            role = "TABLE" if p.xpath("ancestor::w:tbl", namespaces=NS) else "UNSUPPORTED_CONTAINER"
        elif any(re.fullmatch(r"toc\s*\d+|table of (?:figures|contents)", n) for n in names):
            role = "FIELD_OR_CONTENTS"
        elif field:
            role = "FIELD"
        elif not text.strip():
            role = "EMPTY"
        elif chain is not None:
            outline = first_property([ppr] + [s.ppr for s in chain], "w:outlineLvl")
            raw = outline.get(qn("w:val")) if outline is not None else None
            if raw is not None and re.fullmatch(r"[0-8]", raw):
                role, level = "HEADING", int(raw) + 1
            elif (raw is None or raw == "9") and any(n in {"body text", "bodytext"} for n in names):
                role = "BODY"
            elif any(n in {"title", "subtitle", "caption"} for n in names):
                role = "OTHER"
        allowed = {qn("w:" + name) for name in ("pPr", "r", "hyperlink", "bookmarkStart", "bookmarkEnd", "proofErr", "permStart", "permEnd")}
        unsafe = (
            any(child.tag not in allowed for child in p)
            or len(p.findall(qn("w:pPr"))) > 1
            or any(len(el.findall(qn("w:outlineLvl"))) > 1 for el in [ppr] + [s.ppr for s in chain or []] if el is not None)
            or p.xpath(".//w:pPrChange | .//w:rPrChange | .//w:ins | .//w:del | .//w:drawing | .//w:pict | .//w:object", namespaces=NS)
        )
        if p.getparent() is body and role not in {"FIELD", "FIELD_OR_CONTENTS", "EMPTY"} and unsafe:
            role, level = "UNKNOWN", None
        reviewable = role == "UNKNOWN" and chain is not None and p.getparent() is body and not unsafe and bool(text.strip())
        result.append(Paragraph(index, package.document_tree.getpath(p), p, text, role, level, chain or [], reviewable))
    return result, registry, uncertain_structure


def scalar_run(package, registry, paragraph, run, kind):
    """Supported Latin scalar inheritance; theme/script ambiguity remains unknown."""
    text = "".join(run.xpath("./w:t/text()", namespaces=NS))
    if not text.isascii():
        return None
    rpr = run.find(qn("w:rPr"))
    rstyles = nodes([rpr], "w:rStyle")
    if len(rstyles) > 1:
        return None
    char_id = rstyles[0].get(qn("w:val")) if rstyles else None
    chars = style_chain(registry, char_id, "character")
    if chars is None:
        return None
    default = package.styles_tree.getroot().find("w:docDefaults/w:rPrDefault/w:rPr", NS) if package.styles_tree is not None else None
    chain = [rpr] + [s.rpr for s in chars] + [s.rpr for s in paragraph.styles] + [default]
    if any(nodes([props], tag) for props in chain for tag in ("w:cs", "w:rtl", "w:vanish", "w:webHidden")):
        return None
    for props in chain:
        if props is None:
            continue
        found = props.findall(qn("w:rFonts" if kind == "font_family" else "w:sz"))
        if len(found) > 1:
            return None
        if not found:
            continue
        value = found[0]
        if kind == "font_family":
            if value.get(qn("w:asciiTheme")) is not None:
                return None
            font = value.get(qn("w:ascii"))
            if font:
                return font
        else:
            size = value.get(qn("w:val"), "")
            return int(size) / 2 if re.fullmatch(r"[0-9]{1,6}", size) and int(size) > 0 else None
    return None


def paragraph_spacing(package, paragraph):
    ppr = paragraph.element.find(qn("w:pPr"))
    default = package.styles_tree.getroot().find("w:docDefaults/w:pPrDefault/w:pPr", NS) if package.styles_tree is not None else None
    line, rule = None, None
    for props in [ppr] + [s.ppr for s in paragraph.styles] + [default]:
        if props is None:
            continue
        entries = props.findall(qn("w:spacing"))
        if len(entries) > 1:
            return None
        if entries:
            entry = entries[0]
            if line is None:
                line = entry.get(qn("w:line"))
            if rule is None:
                rule = entry.get(qn("w:lineRule"))
    if line is None or not re.fullmatch(r"[0-9]{1,8}", line) or int(line) <= 0:
        return None
    rule = rule or "auto"
    if rule not in {"auto", "exact", "atLeast"}:
        return None
    return {"rule": rule, "multiplier": int(line) / 240 if rule == "auto" else None, "points": int(line) / 20 if rule != "auto" else None}
