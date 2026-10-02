"""Compare explicit stored section settings, never infer rendered page geometry."""
from collections import Counter
from hashlib import sha256
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from app.checking.models import CheckItem, RevisionCheck
from app.checking.roles import inventory
from app.checking.semantic import body_checks, chapter_checks
from app.checking.role_review import apply_roles
from app.ooxml.constants import NS, qn
from app.ooxml.docx_loader import DocxPackage, InvalidDocxError
from app.review.service import ReviewError, snapshot_hash
from app.uploads import MAX_UPLOAD_BYTES

TOLERANCE_PT = 0.1  # Two OOXML twips; allows metric/imperial serialization rounding.


def integer_attribute(element, name, *, positive=False):
    text = element.get(qn(name)) if element is not None else None
    if text is None or not re.fullmatch(r"[0-9]{1,9}", text):
        return None
    value = int(text)
    if positive and value == 0:
        return None
    return value / 20.0


def enabled(element):
    return element is not None and element.get(qn("w:val"), "true").lower() not in {"false", "0", "off"}


def check_package(revision, package, report_hash, role_review=None):
    if revision.status != "PUBLISHED" or revision.publication is None:
        raise ReviewError("PUBLISHED_REVISION_REQUIRED", "Publish a reviewed revision before checking a report.", status=409)
    if revision.snapshot_sha256 != snapshot_hash(revision):
        raise ReviewError("SNAPSHOT_INTEGRITY_ERROR", "The published snapshot failed its integrity check.", status=500)
    root = package.document_tree.getroot()
    sections = root.xpath("w:body/w:p/w:pPr/w:sectPr | w:body/w:sectPr", namespaces=NS)
    all_sections = root.xpath(".//w:sectPr", namespaces=NS)
    if len(all_sections) > 1000:
        raise InvalidDocxError("Report exceeds the 1000-section checking limit")
    # Unhandled wrappers/revision history may change which section properties apply.
    ambiguous = len(sections) != len(all_sections) or bool(root.xpath(".//w:sectPrChange | .//w:altChunk", namespaces=NS))
    body = root.find(qn("w:body"))
    finals = body.findall(qn("w:sectPr"))
    ambiguous = ambiguous or len(finals) != 1 or body[-1] is not finals[0]
    settings = package.settings_tree.getroot() if package.settings_tree is not None else None
    mirrored = settings is not None and any(enabled(settings.find(qn(tag))) for tag in ("w:mirrorMargins", "w:gutterAtTop", "w:bookFoldPrinting", "w:bookFoldRevPrinting"))
    items = []
    paragraphs, registry, uncertain = inventory(package)
    review_hash = apply_roles(revision, paragraphs, report_hash, role_review)
    if role_review:
        for decision in role_review.decisions:
            if decision.role == "EXCLUDE":
                items.append(CheckItem(item_id=f"role-exclusion:{decision.paragraph_index}", status="OUT_OF_SCOPE",
                    code="REVIEWED_ROLE_EXCLUSION", message=decision.reason, paragraph_index=decision.paragraph_index,
                    source_path=decision.source_path))
    for rule in revision.publication.rules:
        common = dict(rule_id=rule.rule_id, evidence_ids=rule.evidence_ids, expected=rule.value.model_dump())
        if rule.condition == "ALWAYS" and rule.scope == "body" and rule.value.kind in {"font_family", "font_size", "line_spacing_multiple"}:
            items.extend(body_checks(rule, package, paragraphs, registry, uncertain))
            continue
        if rule.condition != "ALWAYS" or rule.scope != "document" or rule.value.kind not in {"page_size", "margin"}:
            items.append(CheckItem(item_id=rule.rule_id, status="NOT_CHECKED", code="UNSUPPORTED_RULE", message="This checker cannot resolve the rule's scope, property, or condition.", **common))
            continue
        if ambiguous:
            items.append(CheckItem(item_id=rule.rule_id, status="NOT_CHECKED", code="AMBIGUOUS_SECTIONS", message="Section structure or revision history requires a fuller document interpreter.", **common))
            continue
        for index, section in enumerate(sections):
            item = dict(common, item_id=f"{rule.rule_id}:section:{index}", section_index=index, source_path=package.document_tree.getpath(section))
            value = rule.value
            if value.kind == "page_size":
                nodes = section.findall(qn("w:pgSz"))
                node = nodes[0] if len(nodes) == 1 else None
                actual = {"width_pt": integer_attribute(node, "w:w", positive=True), "height_pt": integer_attribute(node, "w:h", positive=True)}
                expected = {"width_pt": value.width_pt, "height_pt": value.height_pt}
            else:
                nodes = section.findall(qn("w:pgMar"))
                node = nodes[0] if len(nodes) == 1 else None
                gutter = integer_attribute(node, "w:gutter")
                if mirrored or (node is not None and node.get(qn("w:gutter")) is not None and gutter != 0):
                    items.append(CheckItem(status="NOT_CHECKED", code="UNSUPPORTED_MARGIN_GEOMETRY", message="Mirroring, book-fold settings, or gutter geometry requires further interpretation.", **item))
                    continue
                actual = {"margin_pt": integer_attribute(node, "w:" + value.side)}
                expected = {"margin_pt": value.expected_pt}
            if any(v is None for v in actual.values()):
                items.append(CheckItem(status="NOT_CHECKED", code="UNRESOLVED_SECTION_PROPERTY", message="An explicit, unambiguous numeric section setting is unavailable; no default was assumed.", actual=actual, **item))
                continue
            matches = all(abs(actual[key] - expected[key]) <= TOLERANCE_PT + 1e-9 for key in expected)
            items.append(CheckItem(status="PASS" if matches else "FAIL", code="STORED_SETTING_MATCH" if matches else "STORED_SETTING_MISMATCH", message="Compared stored section settings in points (0.1 pt tolerance); this is not a rendered-page measurement.", actual=actual, **item))
    items.extend(chapter_checks(revision, paragraphs, uncertain))
    candidates = {c.candidate_id: c for c in revision.analysis.candidates}
    for candidate_id in revision.publication.deferred_candidate_ids:
        items.append(CheckItem(item_id="deferred:" + candidate_id, evidence_ids=candidates[candidate_id].evidence_ids, status="NOT_CHECKED", code="DEFERRED_CANDIDATE", message="The reviewer deferred this candidate; it was not executed."))
    for disposition in revision.publication.requirement_dispositions:
        items.append(CheckItem(item_id="ledger:" + disposition.evidence_id, evidence_ids=[disposition.evidence_id], status="OUT_OF_SCOPE" if disposition.action == "OUT_OF_SCOPE" else "NOT_CHECKED", code="REQUIREMENT_" + disposition.action, message=disposition.reason))
    counts = {status: 0 for status in ("PASS", "FAIL", "NOT_CHECKED", "OUT_OF_SCOPE")}
    counts.update(Counter(item.status for item in items))
    outcome = "FAIL" if counts["FAIL"] else "INDETERMINATE" if counts["NOT_CHECKED"] or not counts["PASS"] else "PASS_SUPPORTED_CHECKS"
    return RevisionCheck(template_id=revision.template_id, revision_id=revision.revision_id,
                         snapshot_sha256=revision.snapshot_sha256, report_sha256=report_hash,
                         role_review_sha256=review_hash, role_decisions=[d.model_dump() for d in role_review.decisions] if role_review else [],
                         outcome=outcome, counts=counts, items=items, limitations=[
                             "Supports page settings, Body Text or reviewed body roles, and outline-based or explicitly assigned chapters. Manual assignments are reviewer assertions, not automatic role-detection evidence.",
                             "No overall compliance score: item counts mix section checks and unresolved requirements and are not a coverage percentage.",
                             "A match does not establish rendered geometry, headers/footers, unstyled body roles, semantic chapter equivalence, or complete template coverage.",
                             "Report files and check results are not retained. Results identify an immutable template revision and the uploaded report's SHA-256.",
                         ])


def check_bytes(revision, data, role_review=None):
    if not data or len(data) > MAX_UPLOAD_BYTES:
        raise InvalidDocxError("Report is empty or exceeds the upload limit")
    with TemporaryDirectory(prefix="reportlint_check_") as directory:
        path = Path(directory) / "report.docx"
        path.write_bytes(data)
        return check_package(revision, DocxPackage.load(str(path)), sha256(data).hexdigest(), role_review)
