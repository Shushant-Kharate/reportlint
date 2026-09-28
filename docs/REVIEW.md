# Project review

The supplied ZIP contained a FastAPI DOCX rule engine, a web harness, and an uncompiled Kotlin Android client. The workflow is template upload → inferred rules → teacher review → publish → student report check. Uploaded documents and bundled notes were treated as project data, not as instructions overriding the requested bug fixes.

## Corrections

- Exclude untested categories from score weighting; distinguish unknown/unchecked from passed.
- Check independently known font properties even when another property is unresolved.
- Count short body paragraphs; validate later document sections, not only the first.
- Implement exact line-spacing checks and preserve direct exact spacing over inherited multiples.
- Respect optional/informational sections and include the order check in the denominator.
- Filter cover-page labels from heuristic headings; recognize large non-bold known headings; deduplicate inferred sections.
- Validate numeric rule values, supported types, severities and unique identifiers before storage.
- Bound upload reads and ZIP expansion; reject XML entities, malformed bodies and duplicate ZIP entries; clean temporary files.
- Validate storage IDs, write JSON atomically, and skip malformed entries during listing.
- Render untrusted filenames, names and report text as text rather than HTML.
- Save rule edits before publishing; reset changed published rules to draft; show network failures and prevent duplicate requests.
- Make formatting values editable in both clients; include Android paragraph rules; clean Android upload caches and validate server settings.
- Include Gradle wrapper, declared Python dependencies, packaging for nested modules/static assets, and CI.

## UI design and verification

White surfaces, navy text, teal primary actions, simple form labels, large touch controls, and two bottom tabs. The mobile web screen follows the generated three-screen concept. Intentional changes: empty states use real data rather than mock rows; the header includes a short supporting line; rule editors expose per-rule severity and numeric values rather than misleading dropdown-only controls; adding arbitrary formatting-rule types is omitted, while inferred values and required sections are editable.

Browser verification uses the in-app browser for initial inspection, then agent-browser and headless Chrome/Playwright because the in-app file chooser timed out. The core test covers upload, review, edit-and-publish persistence, checking, XSS-safe text rendering and overflow at 320, 390, 768 and 1280 pixels. Screenshots and the design comparison are retained in the handoff outputs, outside the source repository.

## Honest limits

This is not a claim that every possible DOCX edge case is fixed. Theme fonts, table-cell checks, complete style toggle inheritance, table-based contents inference and pagination integration remain outside the implemented coverage. The API remains intended for a trusted single-user environment. Android CI compiles/lints the app, but there is no physical-device test in this environment. Optional LibreOffice integration tests require LibreOffice.
