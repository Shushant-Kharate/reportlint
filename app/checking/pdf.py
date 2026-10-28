"""Bounded native-PDF measurements. Never reconstruct DOCX styles from a PDF."""
from collections import Counter
from hashlib import sha256
import re

import pymupdf

from app.checking.models import CheckItem, RevisionCheck
from app.review.service import ReviewError, snapshot_hash


class InvalidPdfError(ValueError):
    pass


def prose_lines(blocks):
    """Collect long prose candidates as evidence, not confirmed paragraph roles."""
    result = []
    for block_id, block in enumerate(blocks):
        lines = block.get("lines", [])
        text = " ".join(s.get("text", "") for line in lines for s in line.get("spans", []))
        if len(re.findall(r"[A-Za-z]", text)) < 200 or len(lines) < 3:
            continue
        if re.match(r"\s*(?:Fig(?:ure)?\.?\s*\d|Table\s+[IVX\d]|\[\d+\])", text, re.I):
            continue
        for line in lines:
            spans = line.get("spans", [])
            line_text = "".join(s.get("text", "") for s in spans)
            if len(re.findall(r"[A-Za-z]", line_text)) >= 35:
                result.append((block_id, line, spans))
    return result


def check_pdf(revision, data):
    if revision.status != "PUBLISHED" or revision.publication is None:
        raise ReviewError("PUBLISHED_REVISION_REQUIRED", "Publish a reviewed format first.", status=409)
    if revision.snapshot_sha256 != snapshot_hash(revision):
        raise ReviewError("SNAPSHOT_INTEGRITY_ERROR", "The format failed its integrity check.", status=500)
    if not data.startswith(b"%PDF-"):
        raise InvalidPdfError("Choose a valid PDF file.")
    try:
        document = pymupdf.open(stream=data, filetype="pdf")
    except (RuntimeError, ValueError) as exc:
        raise InvalidPdfError("The PDF could not be opened.") from exc
    items = []
    try:
        if document.needs_pass or not 1 <= len(document) <= 100:
            raise InvalidPdfError("Use an unencrypted PDF with 1–100 pages.")
        if document.is_repaired:
            raise InvalidPdfError("The PDF needs repair. Export a clean PDF before checking it.")
        extracted = 0
        for index, page in enumerate(document):
            blocks = page.get_text("dict", flags=pymupdf.TEXTFLAGS_DICT & ~pymupdf.TEXT_PRESERVE_IMAGES)["blocks"]
            lines = prose_lines(blocks)
            extracted += sum(len(s.get("text", "")) for b in blocks for line in b.get("lines", []) for s in line.get("spans", []))
            if extracted > 2_000_000:
                raise InvalidPdfError("The PDF exceeds the supported text limit.")
            fonts, sizes = Counter(), Counter()
            for _, _, spans in lines:
                for span in spans:
                    weight = len(span.get("text", ""))
                    fonts[span.get("font", "unknown")] += weight
                    sizes[round(span.get("size", 0), 2)] += weight
            geometry_safe = page.rotation == 0 and page.cropbox == page.mediabox
            for rule in revision.publication.rules:
                expected = rule.value.model_dump()
                kind = rule.value.kind
                common = dict(item_id=f"pdf:{rule.rule_id}:page:{index+1}", rule_id=rule.rule_id,
                              evidence_ids=rule.evidence_ids, expected=expected,
                              page_number=index+1, source_path=f"PDF/page[{index+1}]")
                if kind == "page_size" and rule.scope == "document" and rule.condition == "ALWAYS":
                    actual = {"width_pt": page.mediabox.width, "height_pt": page.mediabox.height}
                    match = abs(actual["width_pt"]-rule.value.width_pt) <= 0.5 and abs(actual["height_pt"]-rule.value.height_pt) <= 0.5
                    items.append(CheckItem(status=("PASS" if match else "FAIL") if geometry_safe else "NOT_CHECKED",
                        code="PDF_PAGE_SIZE" if geometry_safe else "PDF_CROP_OR_ROTATION_REVIEW",
                        message="Compared the PDF MediaBox with the reviewed paper size (0.5 pt tolerance). Cropped or rotated pages require review.", actual=actual, **common))
                elif kind == "body_columns" and rule.condition == "ALWAYS" and rule.value.count == 2 and geometry_safe:
                    middle = page.rect.width / 2
                    left = [line for _, line, _ in lines if line["bbox"][2] <= middle-4]
                    right = [line for _, line, _ in lines if line["bbox"][0] >= middle+4]
                    overlapping = sum(any(abs(l["bbox"][1]-r["bbox"][1]) < 5 for r in right) for l in left)
                    wide = [(b, line) for b, line, spans in lines if line["bbox"][0] < middle-60 and line["bbox"][2] > middle+60
                            and len("".join(s.get("text", "") for s in spans)) >= 90]
                    observed = len(left) >= 8 and len(right) >= 8 and overlapping >= 4
                    single = index > 0 and len(wide) >= 12 and len({b for b, _ in wide}) >= 3 and len(left)+len(right) < 4
                    items.append(CheckItem(status="PASS" if observed else "FAIL" if single else "NOT_CHECKED",
                        code="PDF_TWO_COLUMN_PROSE" if observed else "PDF_SINGLE_COLUMN_PROSE" if single else "PDF_COLUMN_LAYOUT_REVIEW",
                        message="Measured sustained long-prose lines in two columns. Full-width figures, headings and short pages are not rejected. This sample does not establish every object's placement.",
                        actual={"observed_columns": 2 if observed else 1 if single else None,
                                "left_prose_lines":len(left), "right_prose_lines":len(right), "wide_prose_lines":len(wide)}, **common))
                else:
                    actual = {"prose_sample_fonts":dict(fonts.most_common(8)),
                              "prose_sample_sizes_pt":{str(k):v for k,v in sizes.most_common(8)}} if kind in {"font_family", "font_size", "line_spacing_multiple"} else None
                    items.append(CheckItem(status="NOT_CHECKED", code="PDF_SOURCE_PROPERTY_REVIEW",
                        message="PDF evidence does not establish the original Word style, body-role assignment, exact source margins or line-spacing setting. Prose font samples are evidence for manual review, not a compliance verdict.", actual=actual, **common))
            if not lines:
                items.append(CheckItem(item_id=f"pdf:no-prose:{index+1}",page_number=index+1,status="NOT_CHECKED",
                    code="PDF_TEXT_OR_PROSE_UNAVAILABLE",message="No reliable long-prose sample was found. This may be a scanned or mostly illustrated page; OCR is not run."))
        for disposition in revision.publication.requirement_dispositions:
            if disposition.action == 'COVERED':
                continue
            items.append(CheckItem(item_id="pdf:ledger:"+disposition.evidence_id,evidence_ids=[disposition.evidence_id],
                status="OUT_OF_SCOPE" if disposition.action == "OUT_OF_SCOPE" else "NOT_CHECKED",
                code="REQUIREMENT_"+disposition.action,message=disposition.reason))
        for candidate_id in revision.publication.deferred_candidate_ids:
            candidate = next(c for c in revision.analysis.candidates if c.candidate_id == candidate_id)
            items.append(CheckItem(item_id="pdf:deferred:"+candidate_id,evidence_ids=candidate.evidence_ids,status="NOT_CHECKED",
                code="DEFERRED_CANDIDATE",message="This proposed requirement was deferred by its reviewer."))
        if revision.publication.profile and revision.publication.profile.chapters:
            items.append(CheckItem(item_id="pdf:chapters",status="NOT_CHECKED",code="PDF_CHAPTER_REVIEW",
                message="The Word chapter profile is not automatically resolved from PDF text."))
        counts = {s:0 for s in ("PASS","FAIL","NOT_CHECKED","OUT_OF_SCOPE")}
        counts.update(Counter(i.status for i in items))
        outcome = "FAIL" if counts["FAIL"] else "INDETERMINATE" if counts["NOT_CHECKED"] or not counts["PASS"] else "PASS_SUPPORTED_CHECKS"
        return RevisionCheck(checker_version="0.6.0",report_format="pdf",template_id=revision.template_id,revision_id=revision.revision_id,
            snapshot_sha256=revision.snapshot_sha256,report_sha256=sha256(data).hexdigest(),outcome=outcome,counts=counts,items=items,
            limitations=["Experimental native-PDF path: paper size and sustained two-column prose evidence only. Not IEEE PDF eXpress certification or a whole-paper compliance grade.",
                        "Original Word margins, body styles, typography roles, line spacing, captions, citations, author layout and venue-specific exceptions require review. Font samples are not automatic body-font verdicts.",
                        "Scanned text is not OCR-processed. Cropped/rotated geometry and sparse or ambiguous layouts remain unresolved. Inputs are limited to 100 pages and two million extracted characters.",
                        "The original uploaded PDF is checked directly, without conversion to DOCX. Files and results are processed temporarily."])
    finally:
        document.close()
