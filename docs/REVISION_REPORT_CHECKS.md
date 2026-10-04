# Revision-pinned report checks

The first checker checkpoint (0.1.0) compared explicit page dimensions and simple margin settings in every recognized DOCX section. Current checker **0.3.0** additionally supports [scoped body/chapter checks](SCOPED_BODY_AND_CHAPTER_CHECKS.md) and [reviewed roles for manually formatted reports](MANUAL_REPORT_ROLE_REVIEW.md); the page-setting behavior below remains unchanged. Captions, page numbering and rendered pages remain unsupported. The [complex web interface](COMPLEX_WEB_WORKFLOW.md) uses v2; the basic interface and native Android app remain on v1.

## Run a check

1. Start the server using the main README and open `http://127.0.0.1:8000/docs`.
2. Create, review and publish a template through [V2 template review](TEMPLATE_REVISION_REVIEW.md). Record its `template_id` and `revision_id`.
3. Under **V2 report checks**, execute `POST /api/v2/templates/{template_id}/revisions/{revision_id}/check`, supplying the student's DOCX in the `file` field. The operation is synchronous and returns HTTP 200 for a completed check, including reports with violations. A DRAFT returns HTTP 409. Unsupported extensions return 415; malformed documents return 422; uploads over 20 MB return 413.
4. Read `outcome`, `items`, `counts`, and `limitations`. Save the response yourself if needed: reports and results are not retained by the server.

Every result identifies `checker_version`, the template revision, its `snapshot_sha256`, and the uploaded report's `report_sha256`. The API never substitutes the latest revision. Existing compiler 0.1/0.2 snapshots remain readable/checkable with their original hashes even if their historical publication metadata describes narrower capabilities. Live `/api/v2/capabilities` reports current execution support. New publications use compiler 0.3 metadata; old snapshots are not rewritten.

## Interpret the result

| Status | Meaning |
| --- | --- |
| `PASS` | This stored setting matched the approved value within tolerance. |
| `FAIL` | A supported setting differed from the approved value. |
| `NOT_CHECKED` | The requirement is unsupported, deferred, manual, or its report data could not be resolved. |
| `OUT_OF_SCOPE` | The reviewer explicitly excluded this detected requirement, with a recorded reason. |

`FAIL` as the overall outcome means at least one violation was found; other requirements may still be unchecked. `INDETERMINATE` means no supported violation was found but something remains unchecked, or no check passed. `PASS_SUPPORTED_CHECKS` means only the selected supported checks passed; it never certifies full template compliance.

There is no compliance percentage. Counts combine section/paragraph/run/chapter results with unresolved rule/ledger items, so they cannot be used as a requirement coverage percentage. Each approved rule yields at least one item; every deferred candidate and reviewed source-ledger disposition remains represented. Rejected candidates remain in the template audit history and are not report requirements. Chapter profiles use the limited outline-based matching described in the scoped-check guide.

For an executable rule, the result carries its `rule_id`, source-template `evidence_ids`, expected value, actual value, zero-based `section_index`, and an XPath into `word/document.xml`. A section index is not a physical page number. A margin's actual value is `margin_pt`; page-size values are `width_pt` and `height_pt`. Values are in points, with a fixed tolerance of 0.1 pt (two Word twips) to allow unit-conversion rounding.

## Boundaries and abstention

- For page geometry, only unconditional document-scope page-size and margin rules execute. Conditional rules remain unchecked. Body rules execute only for the supported explicit styles described in the scoped-check guide.
- Each recognized section is checked independently; a matching first section cannot hide a wrong second section. Width and height are compared in their stored order, without silently rotating a landscape page.
- Missing, duplicate, negative, or unsupported noninteger section settings are unresolved. The checker does not invent Word defaults or inherited values.
- Mirrored margins, book-fold settings, and nonzero or invalid gutter values prevent margin evaluation. Page-size comparison can still run independently.
- Unhandled section wrappers, section-change history, external document chunks, or a missing/ambiguous final section cause abstention. Reports with more than 1000 section-property elements are rejected as exceeding this checker's limit.
- These are stored document settings, not measurements of the printed text area. Passing a top-margin check does not prove correct header placement or rendered spacing. No renderer, OCR, deep learning, or NLP model is added by this slice.

## Verification and next work

Synthetic tests exercise matching settings, a second-section violation, bounded numeric tolerance, invalid/missing/duplicate properties, unresolved section structure, gutters/mirroring, deferred and out-of-scope requirements, revision integrity, old snapshot compatibility, API errors and nonmutation. The original private template and research PDFs remain outside Git.

The subsequent scoped-check checkpoint adds a limited ordered paragraph inventory and explicit style-based body/chapter validators. Broader role interpretation remains pending. Client integration should expose the same limited coverage rather than converting these counts to a global score. These checkpoints are partial progress toward the roadmap, not completion of a milestone.
