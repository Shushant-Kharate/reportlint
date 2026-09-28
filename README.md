# ReportLint — Stage 1 engine + Stage 2 web harness

## Run it

```bash
pip install -e . --break-system-packages   # or use a venv
pip install fastapi uvicorn python-multipart python-docx lxml rapidfuzz pymupdf --break-system-packages
PYTHONPATH=. uvicorn app.main:app --reload
```

Open http://localhost:8000/ — it redirects to the web app at `/app/`.

## What's here

- **Stage 1** (`app/ooxml`, `app/rules`, `app/compliance`, `app/models`) — the
  document-analysis engine: DOCX parsing, effective-style resolution,
  structure extraction, rule inference, compliance checking, scoring, and
  LibreOffice-based pagination. See `reportlint_stage1_engine_spec.md` for
  the full section-by-section design.
- **Stage 2** (`app/api_routes.py`, `app/storage.py`, `app/models/template_model.py`,
  `static/index.html`) — a minimal web harness around the engine:
  - Upload a teacher's format `.docx` → get a proposed rule set (`DRAFT`)
  - Review rules in the browser: change severities, remove/add required
    sections (the extractor over-fires on title-page text by design —
    this is the intended place to fix that)
  - Publish the template
  - Upload a student report `.docx`, check it against a template, see a
    scored, grouped violation report

No auth, no classes, no database — templates persist as JSON files under
`storage/templates/`. That's deliberate: this stage exists to prove the
end-to-end workflow before investing in a real backend. Stage 3 (Android)
is the next step, reusing this same API.

## Tests

```bash
PYTHONPATH=. pytest tests/ -v
```

32 tests, all passing, run against the real
`tests/fixtures/mini_project_1a_format.docx` template plus synthetic
fixtures for controlled failure-mode testing.

## Known limitations (intentional, documented via tests — not bugs to silently patch)

- Body font is frequently unresolvable from real templates (no
  `docDefaults` rFonts) — surfaces as an `INFO`-severity, unenforced rule
  until a teacher manually confirms it.
- Heading detection heuristic (bold + size/centered) over-fires on
  title-page lines and under-fires on size-only, non-bold headings.
- This specific sample template's real chapter list lives inside an INDEX
  *table*, not as body headings — structure-rule auto-extraction from body
  text alone misses it; teacher review is required either way.
- Pagination: short, generic single-word headings are excluded from page
  matching rather than risk a confidently wrong page number (verified
  empirically, see `app/pagination/libreoffice_render.py`).
- Figures/tables/captions/header-footer validators are not yet built —
  those scoring categories always show 100% (no checks performed).
