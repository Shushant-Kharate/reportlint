"""Lightweight main-story source inventory; not the complete v2 document IR."""
from dataclasses import dataclass, field
from hashlib import sha256

from app.models.template_analysis import SourceEvidence
from app.ooxml.constants import qn
from app.ooxml.docx_loader import DocxPackage, InvalidDocxError


@dataclass
class SourceTable:
    path: str
    rows: list[list[list[SourceEvidence]]] = field(default_factory=list)
    complex_grid: bool = False


@dataclass
class SourceInventory:
    paragraphs: list[SourceEvidence] = field(default_factory=list)
    tables: list[SourceTable] = field(default_factory=list)
    notices: list[str] = field(default_factory=list)


def paragraph_text(element):
    """Preserve tabs/breaks, omit field instructions and separate text-box stories."""
    pieces = []
    def visit(node):
        if node.tag in {qn("w:del"), qn("w:txbxContent")}:
            return
        if node.tag == qn("w:t"):
            pieces.append(node.text or "")
        elif node.tag == qn("w:tab"):
            pieces.append("\t")
        elif node.tag in {qn("w:br"), qn("w:cr")}:
            pieces.append("\n")
        else:
            for child in node:
                visit(child)
    visit(element)
    return "".join(pieces).strip()


def inventory_source(package: DocxPackage) -> SourceInventory:
    result = SourceInventory()
    text_size = 0
    body = package.document_tree.getroot().find(qn("w:body"))
    unsupported = {qn("w:ins"), qn("w:del"), qn("w:txbxContent"), qn("w:altChunk")}
    if any(node.tag in unsupported for node in body.iter()):
        result.notices.append("Tracked changes, text boxes or imported content require additional review; this preview is not a complete representation of those features.")

    def walk(parent, path, cell=None, depth=0):
        nonlocal text_size
        if depth > 64:
            raise InvalidDocxError("Source nesting exceeds analysis limit")
        counts = {}
        for node in parent:
            tag = node.tag.rsplit("}", 1)[-1]
            ordinal = counts.get(tag, 0)
            counts[tag] = ordinal + 1
            node_path = f"{path}/{tag}[{ordinal}]"
            if node.tag == qn("w:p"):
                if len(result.paragraphs) >= 20000:
                    raise InvalidDocxError("Too many source paragraphs")
                evidence = SourceEvidence(
                    source_id=sha256(node_path.encode()).hexdigest()[:20],
                    path=node_path, excerpt=paragraph_text(node),
                )
                text_size += len(evidence.excerpt)
                if len(evidence.excerpt) > 50000 or text_size > 2000000:
                    raise InvalidDocxError("Source text exceeds analysis limit")
                result.paragraphs.append(evidence)
                if cell is not None:
                    cell.append(evidence)
            elif node.tag == qn("w:tbl"):
                table = SourceTable(path=node_path)
                result.tables.append(table)
                for ri, row in enumerate(node.findall(qn("w:tr"))):
                    row_sources = []
                    for ci, tc in enumerate(row.findall(qn("w:tc"))):
                        cells = []
                        if tc.find(f"{qn('w:tcPr')}/{qn('w:gridSpan')}") is not None or tc.find(f"{qn('w:tcPr')}/{qn('w:vMerge')}") is not None:
                            table.complex_grid = True
                        walk(tc, f"{node_path}/tr[{ri}]/tc[{ci}]", cells, depth + 1)
                        row_sources.append(cells)
                    table.rows.append(row_sources)
            elif node.tag in {qn("w:sdt"), qn("w:sdtContent"), qn("w:customXml")}:
                walk(node, node_path, cell, depth + 1)
    walk(body, "body")
    return result
