"""Section 10 — Pagination.

Builds AFTER Sections 1-9 pass. Never populates estimated_page unless the
match confidence has actually been verified — see Section 10.4 of the spec.

Approach:
1. Render the .docx to PDF via headless LibreOffice, in an isolated user
   profile per invocation (avoids lock contention if multiple conversions
   run concurrently, and avoids the sandbox hang some shared-profile
   invocations can trigger).
2. Extract per-page text via PyMuPDF (fitz).
3. Match each paragraph's normalized leading text against page text blocks
   to find its most likely page, with a similarity-based confidence score.
"""

import subprocess
import tempfile
import uuid
import os
import shutil
from pathlib import Path
import re
import unicodedata

import fitz  # PyMuPDF
from rapidfuzz import fuzz

from app.models.document_model import DocumentModel


class RenderError(Exception):
    pass


def render_docx_to_pdf(docx_path: str, timeout_sec: int = 60) -> str:
    """Returns path to the rendered PDF. Raises RenderError on failure."""
    outdir = tempfile.mkdtemp(prefix="reportlint_render_")
    profile_dir = tempfile.mkdtemp(prefix="reportlint_lo_")

    cmd = [
        shutil.which("soffice") or "soffice", "--headless", "--convert-to", "pdf",
        "--outdir", outdir,
        f"-env:UserInstallation={Path(profile_dir).as_uri()}",
        docx_path,
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_sec)
    except (OSError, subprocess.TimeoutExpired) as e:
        shutil.rmtree(outdir, ignore_errors=True)
        raise RenderError(f"LibreOffice render timed out after {timeout_sec}s") from e
    finally:
        shutil.rmtree(profile_dir, ignore_errors=True)

    if proc.returncode != 0:
        shutil.rmtree(outdir, ignore_errors=True)
        raise RenderError(f"LibreOffice render failed: {proc.stderr or proc.stdout}")

    base = os.path.splitext(os.path.basename(docx_path))[0]
    pdf_path = os.path.join(outdir, f"{base}.pdf")
    if not os.path.exists(pdf_path):
        shutil.rmtree(outdir, ignore_errors=True)
        raise RenderError(f"Expected output PDF not found at {pdf_path}")
    return pdf_path


def extract_page_texts(pdf_path: str) -> list[str]:
    doc = fitz.open(pdf_path)
    try:
        return [doc[i].get_text() for i in range(len(doc))]
    finally:
        doc.close()


_WS_RE = re.compile(r"\s+")


def _normalize_for_match(text: str) -> str:
    t = unicodedata.normalize("NFKC", text).lower()
    t = _WS_RE.sub(" ", t).strip()
    return t


class PageMatch:
    def __init__(self, paragraph_index: int, page_number: int | None, confidence: float):
        self.paragraph_index = paragraph_index
        self.page_number = page_number  # 1-based, or None if unmatched
        self.confidence = confidence


def match_paragraphs_to_pages(doc: DocumentModel, page_texts: list[str],
                               snippet_len: int = 60,
                               min_confidence: float = 70.0,
                               backtrack_pages: int = 1) -> list[PageMatch]:
    """For each paragraph, find the page whose text contains the best fuzzy
    match of the paragraph's leading snippet. Returns one PageMatch per
    paragraph; page_number is None (not a guess) when the best score falls
    below min_confidence.

    IMPORTANT: matching is monotonic. A linear document's paragraphs appear
    in the same order as pages, so search starts from
    max(0, last_matched_page_index - backtrack_pages) rather than page 0
    every time. Without this, repeated text (e.g. a student's name
    appearing on the title page, certificate, AND declaration pages) causes
    every later occurrence to incorrectly match the FIRST occurrence's page
    — verified empirically against the real fixture, where names appearing
    near paragraph 162 were wrongly matched to page 1 instead of their
    actual later page under a naive independent-lookup approach.
    """
    norm_pages = [_normalize_for_match(t) for t in page_texts]
    results = []
    last_matched_page_idx = 0  # 0-based

    for p in doc.paragraphs:
        snippet = _normalize_for_match(p.text)[:snippet_len]
        # Empirical finding against the real fixture: short, generic,
        # single-word snippets (e.g. "ACKNOWLEDGEMENT") produce spuriously
        # high partial_ratio scores against unrelated pages, because a short
        # query is easy to align with SOME substring of a large page's text
        # by chance. Multi-word snippets >= ~15 normalized chars did not
        # show this failure mode in manual spot-checking. This threshold is
        # therefore a measured finding, not an arbitrary guess — but it is
        # still a heuristic; treat confidence as approximate, not exact.
        if len(snippet) < 15:
            results.append(PageMatch(p.index, None, 0.0))
            continue

        search_start = max(0, last_matched_page_idx - backtrack_pages)
        best_page_idx, best_score = None, 0.0
        for i in range(search_start, len(norm_pages)):
            score = fuzz.partial_ratio(snippet, norm_pages[i])
            if score > best_score:
                best_score = score
                best_page_idx = i

        if best_score >= min_confidence and best_page_idx is not None:
            results.append(PageMatch(p.index, best_page_idx + 1, round(best_score, 1)))
            last_matched_page_idx = best_page_idx
        else:
            results.append(PageMatch(p.index, None, round(best_score, 1)))

    return results
