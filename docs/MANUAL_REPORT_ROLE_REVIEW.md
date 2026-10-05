# Reviewing manually formatted reports

**0.4.0 update:** safely parsed existing BODY/HEADING/OTHER classifications can now be corrected too. Unsupported fields, tables, drawings and malformed styles remain non-reviewable. See [current improvements](REAL_DOCUMENT_IMPROVEMENTS.md); the original 0.3 checkpoint below described unresolved paragraphs only.

Checker **0.3.0** can use explicitly reviewed roles for supported paragraphs that use Normal or other nonsemantic styles. A report no longer has to be restyled in Word just to identify body paragraphs and chapters. A [mobile web review screen](COMPLEX_WEB_WORKFLOW.md) now exposes this workflow; the API instructions below remain useful for integrations. Automatic semantic understanding of arbitrary report layouts is not implemented.

## Workflow in the API docs

Start the server using the README, open `http://127.0.0.1:8000/docs`, and first create a published template through [template revision review](TEMPLATE_REVISION_REVIEW.md). Choose the correct chapter profile and approve its requirements.

1. Under **V2 report checks**, execute `POST /api/v2/templates/{template_id}/revisions/{revision_id}/role-preview` with the student's DOCX as `file`.
2. Inspect its paragraphs alongside the original report. Each entry includes a zero-based `paragraph_index`, exact `source_path`, excerpt, detected role, `reviewable` flag, optional suggested role/chapter, and proposal reason. Excerpts are limited to 1000 characters; `excerpt_truncated` tells you when to consult the document for the remainder. Tabs and line breaks are preserved.
3. Build the JSON review below using the **actual hashes, indices and paths returned by the preview**. These example paths/indices are illustrative. Add decisions only after checking the original document. A suggestion is not an approval and is never applied automatically.
4. Execute the existing `POST /api/v2/templates/{template_id}/revisions/{revision_id}/check` endpoint with the same unchanged DOCX in `file` and this JSON text in its optional multipart `role_review` field. Ordinary checks without this field retain the existing style-based behavior.

```json
{
  "report_sha256": "COPY_64_CHARACTER_REPORT_HASH",
  "snapshot_sha256": "COPY_64_CHARACTER_PUBLISHED_SNAPSHOT_HASH",
  "decisions": [
    {
      "paragraph_index": 0,
      "source_path": "/w:document/w:body/w:p[1]",
      "role": "EXCLUDE",
      "reason": "This paragraph is a cover-page label, not body prose."
    },
    {
      "paragraph_index": 1,
      "source_path": "/w:document/w:body/w:p[2]",
      "role": "CHAPTER",
      "chapter_index": 0,
      "reason": "This is the actual first chapter title after the cover."
    },
    {
      "paragraph_index": 2,
      "source_path": "/w:document/w:body/w:p[3]",
      "role": "BODY",
      "reason": "This is prose within the reviewed chapter."
    }
  ]
}
```

`chapter_index` refers to the chapter's zero-based index in the published profile, not its position in the report. It is required for CHAPTER and forbidden for BODY/EXCLUDE. Every decision needs a reason of 5–2000 characters. Each paragraph may appear only once. The review permits at most 10,000 decisions and the API rejects JSON text over 2 MB; the HTTP multipart parser may impose a smaller per-part limit.

## Suggestions and reviewer responsibility

Exact matches to reviewed chapter names/aliases are proposed as CHAPTER. Sentence-like paragraphs of at least 12 words ending in `.`, `!`, or `?` are proposed as BODY. These are simple heuristics, not confidence estimates. Guideline instructions can look like body prose, and a manual contents entry can look like a chapter. Both still require individual review. Other eligible paragraphs may be assigned manually even when there is no suggestion.

A CHAPTER decision can explicitly associate a differently worded report title with a reviewed chapter, with a reason. This does not edit the template's aliases or teach the engine to infer equivalent titles elsewhere. Repeated assignments to the same chapter produce duplicate-chapter findings. Use EXCLUDE with a reason for a verified cover label, caption, instruction or manual contents mention. Exclusions appear as `OUT_OF_SCOPE` result items and never silently disappear.

Only unresolved, supported top-level paragraphs are eligible. Already resolved Word styles, tables, field results, unsupported containers, drawing content, and malformed/cyclic style references cannot be overridden. Assignments do not resolve global document uncertainty or bypass unsupported theme fonts, script selection, numbering or rendering. Unreviewed potential body paragraphs remain `NOT_CHECKED`.

## Integrity and results

Both source hashes must match the uploaded report and selected published snapshot. Editing or re-saving a DOCX can change its hash, even if its visible text looks identical. Generate a fresh preview and review when this happens. A mismatch returns HTTP 409 `STALE_ROLE_REVIEW`.

Invalid/duplicate indices or paths return HTTP 422 `INVALID_ROLE_TARGET`; unsupported paragraphs return `UNSUPPORTED_ROLE_OVERRIDE`; unknown profile chapter indices return `INVALID_CHAPTER_ASSIGNMENT`. Malformed review JSON returns `INVALID_ROLE_REVIEW`. All decisions are validated before any transient paragraph role is changed.

The result includes `role_decisions` and `role_review_sha256`, as well as the report/snapshot hashes and checker version. Together these make the inputs to the check reproducible. A hash is an integrity identifier, not a digital signature, verified reviewer identity, or evidence that the human decision was correct. Ordinary role and formatting errors remain distinguishable: a manually confirmed body paragraph may still fail its font-size check.

Reports, previews, and role decisions are not persisted by these endpoints; save the review JSON/result yourself if needed. The original report and published template remain unchanged. Preview excerpts and saved review reasons can contain private information. The existing trusted-local-user deployment model remains unchanged.

## Verification and remaining work

Tests cover unstyled reports, nonautomatic proposals, mixed outcomes after review, repeated titles, manual chapter mapping, exclusions, stale file/revision hashes, bad paths/indices, strict schemas, unsupported override attempts, inheritance, and the multipart API flow.

The supplied Mini Project format has 124 supported unresolved top-level paragraphs eligible for this review mechanism, plus 192 empty and 180 table paragraphs. This was inspected locally without assigning any roles or publishing interpretations. The format file is not a completed student report, and eligibility is not proof that its instructions can all be checked.

The mobile web interface is now available. Richer automatic role candidates, advanced validators, durable jobs and native Android integration remain pending. This checkpoint does not complete the roadmap's semantic role milestone or full complex-template support.
