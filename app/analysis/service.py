"""Transient template preview shared by API, CLI and tests."""
from collections import Counter
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

from app.analysis.template_requirements import analyze_template
from app.ooxml.docx_loader import DocxPackage, InvalidDocxError
from app.uploads import MAX_UPLOAD_BYTES


def analyze_bytes(data: bytes):
    if not data or len(data) > MAX_UPLOAD_BYTES:
        raise InvalidDocxError("Template is empty or exceeds the upload limit")
    with TemporaryDirectory(prefix="reportlint_analysis_") as directory:
        path = Path(directory) / "source.docx"
        path.write_bytes(data)
        package = DocxPackage.load(str(path))
        return analyze_template(package, sha256(data).hexdigest())


def redacted_summary(analysis):
    """Do not include paths, source prose, chapter titles or student fields."""
    return {
        "schema_version": analysis.schema_version,
        "extractor_version": analysis.extractor_version,
        "source_sha256": analysis.source_sha256,
        "publication_ready": analysis.publication_ready,
        "property_proposals": [c.model_dump(exclude={"evidence_ids", "note"}) for c in analysis.candidates],
        "conflicts": [c.model_dump() for c in analysis.conflicts],
        "profiles": [{"label": p.label, "chapter_count": len(p.chapters)} for p in analysis.profiles],
        "ledger_counts": dict(Counter(item.status for item in analysis.requirement_ledger)),
        "evidence_count": len(analysis.evidence),
        "notices": analysis.notices,
    }
