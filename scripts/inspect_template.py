"""Inspect local template requirements without saving documents or publishing rules.

Run from the repository root: python -m scripts.inspect_template template.docx
"""
import argparse
import hashlib
import json
from pathlib import Path

from app.analysis.service import analyze_bytes, redacted_summary
from app.ooxml.docx_loader import InvalidDocxError
from app.uploads import MAX_UPLOAD_BYTES


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("template", type=Path)
    parser.add_argument("--expected-sha256", help="Fail if the source differs from the reviewed source manifest")
    parser.add_argument("--include-evidence", action="store_true", help="Include source text in output; do not publish private evidence")
    args = parser.parse_args(argv)
    try:
        if args.template.suffix.lower() != ".docx":
            parser.error("Choose a .docx file")
        with args.template.open("rb") as stream:
            data = stream.read(MAX_UPLOAD_BYTES + 1)
        digest = hashlib.sha256(data).hexdigest()
        if args.expected_sha256 and digest != args.expected_sha256.lower():
            parser.error("Source SHA-256 does not match the expected manifest")
        analysis = analyze_bytes(data)
    except (OSError, InvalidDocxError, ValueError, TypeError, OverflowError) as exc:
        parser.error(f"Unable to inspect template ({type(exc).__name__}); verify the input and analysis limits")
    output = analysis.model_dump() if args.include_evidence else redacted_summary(analysis)
    print(json.dumps(output, indent=2, ensure_ascii=True, allow_nan=False))


if __name__ == "__main__":
    main()
