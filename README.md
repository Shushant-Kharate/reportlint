# ReportLint

ReportLint checks a Word report against a teacher-reviewed format template. It identifies formatting and section issues; it does not grade writing, detect plagiarism, or automatically rewrite a report.

## Use it

1. Open **Templates**, upload a teacher's `.docx` format, and review the proposed rules.
2. Correct values, choose severity, and remove incorrect required sections. Publish the template.
3. Open **Check**, choose the published template, and upload the student's `.docx` report.
4. Read the score and specific issues. **Not checked** means no applicable checks ran in that category.

## Run the backend and web app

Python 3.10+ is required. From the project directory:

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[test]"
.venv\Scripts\python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

On macOS/Linux, use `.venv/bin/python` instead. Open http://localhost:8000/app/.

The web app has a responsive mobile layout and a home-screen install manifest. Installation requires HTTPS (or localhost on the development computer). A phone on the same Wi-Fi can use `http://YOUR-COMPUTER-IP:8000/app/` in its browser; use HTTPS for an installable hosted version. The app shell can load offline, but templates, uploads, and checks require the server.

## Native Android app

See [android/README.md](android/README.md). GitHub Actions builds a debug APK and runs Android lint. Download `ReportLint-debug-apk` from a successful Actions run. The native app also requires a running backend; the APK does not contain the Python engine.

## Data and deployment

- Templates persist in `storage/templates/`, configurable with `REPORTLINT_STORAGE_DIR`.
- Incoming files are limited to 20 MB. Temporary document files are removed after parsing, including error paths. Original report files and results are not retained.
- JSON writes are atomic, filenames are validated, XML external entities are disabled, and ZIP expansion is bounded.
- This remains a single-user/trusted-network tool with no accounts or authorization. Do not expose it as a public multi-user service without adding authentication, per-user storage and appropriate upload/request limits at the reverse proxy.
- Draft templates can be checked through the API for teacher previews. Student-facing screens only list published templates. Saving changed rules returns a template to draft; publishing from the UI saves edits first.

## Engine coverage

Implemented: font family/size, bold/italic, paragraph alignment, multiple/exact line spacing, before/after spacing, first-line indentation, page size and margins across document sections, required section presence and ordering. Body rules include short non-heading paragraphs.

The score averages only categories with actual checks, renormalizing their weights. Errors carry a full penalty; warnings carry 0.4. No applicable checks gives a numeric API score of zero and **Not scored** in the UI. Unknown formatting is not counted as passed. Typography occurrence counts represent text runs, not unique paragraphs.

Still limited: theme-font resolution, complete OOXML toggle semantics, table-cell typography, table-based contents extraction, complex numbering, nested structure requirements, and figures/captions/header/footer checks. Heuristic heading recognition is conservative; use real Word heading styles for custom section names. The teacher must review inferred rules. Pagination is optional, requires LibreOffice and PyMuPDF, and is not integrated into the checking API; page numbers are not claimed.

## Tests

```powershell
.venv\Scripts\python -m pytest tests -q
```

Optional renderer tests skip when `soffice` is unavailable. See [docs/REVIEW.md](docs/REVIEW.md) for the changes and verification record.

## Layout

- `app/ooxml`: DOCX parsing and inherited styles
- `app/rules`: template rule inference and section matching
- `app/compliance`: validators and scoring
- `app/api_routes.py`: template/review/check endpoints
- `static`: mobile web app and install manifest
- `android`: Kotlin / Jetpack Compose client
- `tests`: original fixtures and regression tests
