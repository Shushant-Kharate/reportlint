# Reviewed template revisions (v2)

This checkpoint adds persistent review and immutable specification publication to the extraction preview. A subsequent [revision-pinned checker](REVISION_REPORT_CHECKS.md) now evaluates explicit section page settings only. There is no mobile v2 review screen; the existing web/Android checker still uses v1 templates. No new package is required: persistence uses Python's SQLite library.

## Run the workflow

Install and start the backend using the repository README, then open `http://127.0.0.1:8000/docs` and use the **V2 template review** endpoints. These operations are synchronous; the planned asynchronous job API is not implemented.

1. Execute `POST /api/v2/templates` with a DOCX format file and optional name. A successful response is HTTP 201 and contains a persisted DRAFT with `template_id`, `revision_id`, `version: 0`, and `analysis`. The source file is removed after parsing, but extracted text is retained in the revision.
2. Read `analysis.candidates`, their linked `evidence`, conflicting values, detected `requirement_ledger` entries, and proposed `profiles`. Written requirements and observed formatting remain separate. Publication never implicitly chooses between them.
3. Execute `PATCH /api/v2/templates/{template_id}/revisions/{revision_id}` with decisions. Always send the current `expected_version`. Copy actual IDs from the response; the placeholders below are illustrative. Each successful patch increments the version, merges submitted candidate/ledger decisions, and records the patch in the audit log. Omitted decisions remain unchanged; a supplied profile replaces the previous profile review.

```json
{
  "expected_version": 0,
  "candidates": [
    {"candidate_id": "COPY_CANDIDATE_ID", "action": "APPROVE", "reason": "The written instruction explicitly requires this value."}
  ],
  "ledger": [
    {"evidence_id": "COPY_LEDGER_EVIDENCE_ID", "action": "DEFERRED", "reason": "The remaining instructions require a later validator."}
  ],
  "profile": {
    "profile_id": null,
    "reason": "No chapter profile is approved for this specification.",
    "chapters": []
  }
}
```

Candidate actions are `APPROVE`, `REJECT`, or `DEFER`. Reasons must contain 5–2000 characters. Ledger actions are `ACKNOWLEDGED_PARTIAL`, `DEFERRED`, `MANUAL`, or `OUT_OF_SCOPE`; each needs a reason. A ledger acknowledgement does not approve every instruction in its paragraph and is not proof of complete requirement coverage.

To select a profile, supply its actual `profile_id` and review every extracted chapter exactly once using `index` (zero based), `name`, `aliases` (list of strings), and `required` (boolean). For example, a chapter object can be `{"index": 0, "name": "Introduction", "aliases": [], "required": true}`. A name or alias cannot identify two chapters. Suggested subtopics are not automatically promoted to required chapters. Selecting no profile requires the explicit null decision above when profile proposals exist.

4. Execute `GET /api/v2/templates/{template_id}/revisions/{revision_id}/blockers`. Every candidate and detected ledger entry needs a decision, and profiles need explicit review. Different approved values for the same property block publication, including overlapping general and conditional assertions. Resolve them by rejecting or deferring one interpretation with a reason. At least one property or chapter must remain selected.
5. Execute `POST /api/v2/templates/{template_id}/revisions/{revision_id}/publish` with `{"expected_version": CURRENT_VERSION}`. It atomically stores a PUBLISHED snapshot, compiled property contracts, retained unsupported/deferred requirements, audit event, and SHA-256 integrity hash, and updates the template's published-revision pointer. New compiler 0.2 publications advertise limited checking availability; consult live capabilities for the exact scope. Historical snapshots retain their original metadata.
6. To change a published specification, execute `POST /api/v2/templates/{template_id}/revisions/{revision_id}/fork` without a body. The new DRAFT inherits the analysis and review decisions, has version 0 and a new revision number, and links to its parent. Publishing it changes the current pointer without modifying the old snapshot. Inspect history with `GET /api/v2/templates/{template_id}/revisions`; list templates with `GET /api/v2/templates`.

## Error and execution contracts

- HTTP 409 `REVISION_CONFLICT`: reload the latest draft and reconcile the edit; do not blindly retry using a new version.
- HTTP 409 `IMMUTABLE_REVISION`: fork the published revision before editing.
- HTTP 409 `PUBLICATION_BLOCKED`: inspect `detail.blockers` and finish review.
- HTTP 422: invalid decision, profile, schema, or source input; HTTP 404: template/revision not found, including a revision addressed under the wrong template.
- HTTP 503 `UNSUPPORTED_DATABASE_VERSION`: use the application version matching that database; do not reset the version marker.
- HTTP 500 `SNAPSHOT_INTEGRITY_ERROR`: stored published content failed its hash check and must be investigated/restored.

Compiled rules preserve candidate/evidence links and conditions. `PROPERTY_CONTRACT` means values were compiled, not that a report validator ran. Body rules remain `PENDING_BODY_SCOPE`; conditional rules remain `UNSUPPORTED_CONDITION`. A no-header margin never silently becomes a global margin. Conflicts in the original extraction remain an unchanged record; the separate review decisions determine the published selection.

## Persistence and privacy

The database is `review.sqlite3` under `REPORTLINT_STORAGE_DIR` (default `storage/`). It retains extracted source excerpts, chapter titles, decisions, reasons, and revision history; treat it as private document data. Preview-only `POST /api/v2/template-analysis` still does not persist anything. No retention/delete API, authentication, reviewer identity verification, v1 JSON migration, or shared multi-user deployment is implemented in this slice. V1 JSON templates remain independent.

SQLite transactions serialize writes; expected versions prevent lost updates. Database triggers reject normal updates/deletions of published revisions. The hash detects accidental content changes; it is not a digital signature or protection against an administrator who can rewrite the database. Back up using SQLite's backup API, or stop the server before copying the database. Keep private databases and original supplied documents out of Git.

## Verification

The backend suite passes 99 tests, with four optional LibreOffice tests skipped on this machine. Review tests exercise persistence/reopening, conflicting approvals, evidence deduplication, retained conditions, missing reviews, concurrent edits, atomic failure rollback, immutable snapshots, corruption detection, revision ownership, fork/republish, API schema validation, and future database versions. The original Mini Project format is also tested locally through upload and storage reopening without publishing unapproved interpretations.

The subsequent checker executes a limited subset with explicit coverage. Next work remains document/role contracts, more validators, and client review/checking integration. Publication here completes a backend slice, not a full roadmap milestone.
