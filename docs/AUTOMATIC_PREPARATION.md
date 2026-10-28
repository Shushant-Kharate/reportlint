# Automatic format preparation

The default workflow is upload format, check supported rules, and explain only unclear instructions. It does not require approving every proposal or typing an audit reason. Advanced manual review remains available.

## Interpretation and precedence

The application reuses an identical published format within the current workspace, including private clarifications. Packaged Mini Project and IEEE formats provide a fallback when no matching private version exists. Recognition uses the DOCX byte hash, so renaming a file is harmless but editing or resaving it can require fresh analysis. No files from other private workspaces are searched.

For unseen formats, bounded English interpretation proposes typed values from ordinary paragraphs and supported table rows. Explicit, unconflicted instructions are applied automatically. Supported example patterns include:

```text
Use A4 paper.
Body text must use Times New Roman at 12 pt with 1.5 line spacing.
Body text should use two columns and justified alignment.
All margins must be 1 inch.
Top margin: 25 mm.
Abstract text must use 9 pt.
Main headings must use uppercase Roman numerals.
No page numbers.
Required chapters: Introduction, Methods, Results, Conclusion.
```

Consistent formatting from explicitly identified Body Text paragraphs can supply family, size and spacing baselines. Consistent stored sections can supply page settings; substantive body prose establishes column applicability. These are labelled observed baselines, subordinate to written instructions. A dominant font sampled from captions or guidance is never promoted automatically. Conflicting explicit values, alternatives, conditional scopes, tolerances and unsupported document regions remain questions. Suggested chapter tables do not become mandatory chapter lists without an explicit instruction.

The interpreter records unmatched wording rather than claiming that a partly parsed paragraph is fully covered. Clear but unsupported instructions remain manual; confusing the user into repeatedly rephrasing an unavailable physical/semantic check would not make it executable. Content in images, text boxes and tracked changes is surfaced explicitly when not interpreted. The process uses local deterministic English patterns and OOXML analysis, with no learned confidence score, LLM request or OCR dependency.

## Plain-language explanations

Open a question and describe what it should require. A selected body-font question supplies body context for an answer such as `Use Arial at 12 pt.` An additional requirement entered without a selected question should identify its own scope. Your exact explanation is retained, with inferred role context made explicit in its source evidence.

A complete targeted explanation replaces that instruction's earlier interpretation. Include every requirement that should apply. New values supersede conflicting old values; corroborated deferred values can become executable. Unsupported residual clauses remain visible. To exclude an item intentionally, a targeted explanation may say `This instruction does not apply.` or `This image is decorative.` This is a recorded user decision, not an automatic dismissal of document content.

Rejected explanations do not create extra versions. Successful changes to a published format create a new private draft and published snapshot. The older snapshot remains intact. Stale versions and conflicting explanations are rejected. Re-uploading the same file in the same workspace reuses the saved explanation; browser-cookie workspace limits still apply on the hosted application.

`COVERED` source dispositions are checked by the compiler. The text must have a complete supported interpretation represented by approved rules or an explicit, supported replacement. It cannot be used as a checkbox to hide an unknown requirement. PDF output still records unsupported native-DOCX properties separately.

## API and compatibility

* `POST /api/v2/templates/prepare`: multipart DOCX and optional name; returns readiness, revision, rules and pending items.
* `GET .../revisions/{revision_id}/preparation`: read the same summary.
* `POST .../revisions/{revision_id}/automate`: prepare a saved draft using its retained evidence.
* `POST .../revisions/{revision_id}/clarify`: `expected_version`, `explanation`, optional `evidence_id`.

The original `POST /api/v2/templates` still creates an unapproved draft for advanced workflows and API compatibility. Existing published snapshots remain valid. Automatic specifications use compiler 0.6.0; DOCX results use checker 0.8.0. This change requires no new runtime dependencies or paid inference service.

## Verification

Tests cover known-source reuse, written-versus-observed conflicts, alternative fonts, numbered/conditional scope, table fields, image warnings, private explanation persistence, immutable snapshots, stale requests, unsupported coverage claims and changed report verdicts. Flutter tests cover direct access to checking, targeted explanation payloads, visible errors and preserved input.

The real browser regression starts with the packaged IEEE source and verifies 19 reused rules without an approval form. An unseen fictional format yields eight rules and one font question. An invalid answer is rejected while retaining input. `Use Arial at 12 pt` adds the ninth rule, removes the question, and changes a Times New Roman report from zero confirmed failures to two font-run failures. Re-upload retains that revision, and the old snapshot is unchanged.

```text
python -m pytest -q
cd frontend
flutter analyze
flutter test
```

The browser script is `scripts/verify_automatic_setup.cjs SERVER_URL FIXTURES_DIRECTORY OUTPUT_DIRECTORY`; fixtures are fictional DOCX files named `unseen-format.docx` and `report.docx`. Keep browser exports outside the repository. Counts measure these cases; they do not establish complete interpretation or general accuracy on arbitrary institutional formats. Manual requirements never count as compliance passes.
