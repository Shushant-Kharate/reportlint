# Flutter migration and verification

All product screens now live in `frontend/lib/`. The Python FastAPI checking engine and its published-format protocol remain the backend. The old `static/` HTML application and `android/` Kotlin Compose application are retired; their source remains in Git history. Android Kotlin and iOS Swift files in `frontend/` are generated platform hosts, not separate product interfaces.

## Supported workflows

- Format library, DOCX upload, revision selection and server settings.
- Explicit candidate decisions with reasons, source evidence and conflict descriptions.
- Chapter-profile review, aliases, requiredness and source-ledger dispositions.
- Save draft, publication blockers, version-conflict messages, immutable publication and new draft creation.
- Published-format report upload, paragraph-role preview and explicit corrections bound to report/snapshot hashes.
- Result status/counts, filters, expected/actual values, evidence, limitations and JSON export including the checked revision.
- Basic template editing and the three bundled synthetic demonstration files.
- Unsaved-change protection on format review screens. Only the server address persists on the device; uploaded report bytes and role decisions are session state.

Web assets, renderer resources and fonts are served locally after the build. FastAPI serves the Flutter build at `/app/`; the old complex-workflow URL redirects there. The former service worker retires its own legacy caches. A missing build produces an explicit setup response, not a broken legacy page. Separate browser development origins must be explicitly allowlisted through `REPORTLINT_CORS_ORIGINS`.

## Verification on 2026-10-06

- Python: **177 passed, 4 skipped**. Skips require the optional LibreOffice integration. One existing Starlette/httpx deprecation warning remains.
- Flutter static analysis: no issues.
- Flutter unit/widget tests cover upload limits, server origin validation, multipart/hash-bound review payloads, timeout before response headers, stale draft errors, connection failure, retaining a reason typed before choosing a decision, publication and mobile result rendering.
- Production Flutter web build succeeds with bundled fonts and `--no-web-resources-cdn`.
- Real Chromium browser, desktop 1280×960 and mobile 390×844: basic demo upload/publication, correct report score **100**, incorrect report score **33.8**, JSON download matches the backend, no JavaScript page errors. These are legacy basic-engine scores, not whole-document compliance percentages.
- Real Chromium browser, mobile 390×844: fictional complex report file picker upload, paragraph preview, explicit cover exclusion with reason, report check and export including the correct revision. Result: **5 failing check items, 19 unchecked, 1 excluded**, no invented percentage, no JavaScript page errors. This deliberately partial role review is a UI integration fixture, not an accuracy benchmark.
- Screenshots inspected for mobile layout, readable result cards, controls and scroll behavior. Browser evidence is saved outside the public repository.

The complex browser smoke test seeds the fictional format review/publication through HTTP. Flutter review editing/publication is separately covered by widget tests; this does not claim exhaustive browser coverage of every review combination. The uploaded personal reports are not used or published by these UI tests.

## Reproduce browser tests

Start a built web app and backend using a fresh, isolated storage directory. Use the root README for setup. Install Playwright/Chromium in your chosen Node tooling environment, then run from the repository root:

```bash
python -m scripts.create_web_qa_fixtures /tmp/reportlint-fixtures
node scripts/verify_flutter_web.cjs http://127.0.0.1:8000 /tmp/reportlint-browser-results
node scripts/verify_flutter_complex.cjs http://127.0.0.1:8000 /tmp/reportlint-fixtures /tmp/reportlint-browser-results
```

Replace `/tmp/...` with absolute Windows paths in PowerShell. Set `NODE_PATH` when Playwright is installed outside the repository, and optionally `REPORTLINT_BROWSER_PATH` for a specific Chromium executable. These tests create fictional templates in the selected backend storage. They do not delete existing data; use isolated storage.

## Platform boundaries

CI builds Flutter web and an Android debug APK. The GitHub Actions run and artifacts are the build receipt. A compiled debug APK is not a physical-device test or a signed app-store release. iOS is scaffolded but remains unbuilt/unverified here because it needs macOS/Xcode, signing and device testing. No document-analysis engine is embedded for offline operation.

The migration changes the client framework. It does not add OCR/deep learning, claim complete arbitrary-template support, or resolve requirements that the engine honestly reports as unchecked. The prior real-document detector fixes remain in the backend and regression tests.
