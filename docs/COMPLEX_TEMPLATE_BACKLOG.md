# ReportLint complex template execution tracker

Created 2026-10-02. Authoritative specification: [COMPLEX_TEMPLATE_IMPLEMENTATION_PLAN.md](COMPLEX_TEMPLATE_IMPLEMENTATION_PLAN.md).

Status: implementation in progress. The first read-only extraction preview is implemented; see [checkpoint details and usage](TEMPLATE_ANALYSIS_PREVIEW.md). The original MVP baseline was `83991c1`, and the planning commit was `0586af7`. Unchecked tasks remain incomplete even where this preview supplies part of their infrastructure.

## How to use this tracker

- Work in dependency order. Select a small task, implement it, run its relevant acceptance checks, then record evidence before checking its box.
- Keep MP requirement IDs, ADR decisions and DEC questions from the master plan in task/PR descriptions and fixture metadata.
- A task that is partially implemented stays unchecked; record the completed portion in the handoff table.
- Block only work that depends on an unresolved decision. Continue independent parser, schema and fixture work.
- Before changing scope or a semantic contract, update the master plan and append the decision below.
- Do not commit original private reports, temporary storage, report artifacts or research PDFs as a side effect of implementing tests.
- Do not convert UNKNOWN, UNSUPPORTED, MANUAL or ERROR to PASS to make a release appear complete.

## M0 Evidence and gold specification

Depends on: no implementation milestone. Relevant specification: sections 1-3, 9, 15, 19-20.

- [x] **M0-01 Source manifest and baseline command.** Implemented `python -m scripts.inspect_template` with optional expected SHA-256 and default redacted output. The [real-template snapshot](benchmarks/mini-project-1a-extraction-0.1.json) records Letter/11.5 pt/72 pt observations and conflicting written proposals. API and repeated CLI outputs were compared; original documents were not copied into Git.
- [ ] **M0-02 Requirement dispositions.** Convert MP-01 through MP-50 into a reviewed inventory with source anchors, modality, profile, expected measurement and checking class. Acceptance: all 50 entries accounted for; difficult requirements remain visible rather than disappearing.
- [ ] **M0-03 Resolve first-slice decisions.** Record DEC-01, DEC-02 and body/page rule interpretations needed for the first extraction slice. Leave other DEC entries explicitly unresolved. Acceptance: no developer guess is represented as a teacher-confirmed rule.
- [ ] **M0-04 Design the compliant complex report.** Define its front matter, chapter tree, tables/figures, captions, fields and page-label scheme using fictional identities. Acceptance: document content is a completed report, not a copy of guideline pages.
- [ ] **M0-05 Benchmark manifest contract.** Define template/profile, input hashes, expected rule IDs, expected target locations, mutation recipe and human-review status. Acceptance: expected findings can be reviewed independently of engine output.
- [ ] **M0-06 Real-report intake plan.** Record which completed reports and human annotations are available, missing or restricted. Acceptance: separate public generated fixtures from private evaluation data and identify the external-validity gap.

M0 exit evidence: reviewed inventory location, unresolved DEC IDs, baseline artifact, fixture design and reviewer record.

## M1 Contracts, states and capability registry

Depends on: M0 inventory. Relevant specification: sections 4-8, 12-13.

- [ ] **M1-01 Document IR schema.** Add v2 source anchors, stories, ordered blocks, effective property provenance, semantic role candidates and capabilities. Acceptance: round-trip example documents preserve ordering, table nesting and missing-versus-false values.
- [ ] **M1-02 Typed rule schemas.** Define discriminated payloads, scopes, obligation, conditions, evidence, tolerance, support and review state. Acceptance: reject invalid units, nonfinite values, unknown fields and unsupported arbitrary expressions.
- [ ] **M1-03 Evaluation/result schemas.** Define all seven evaluation states, verdicts, per-target ledger, findings, coverage and render spans. Acceptance: UNKNOWN and NOT_APPLICABLE cannot be represented by the same default value.
- [ ] **M1-04 Capability registry.** Map rule kinds to required parsing/rendering capabilities and versions. Acceptance: unsupported requirements are returned explicitly before and during checking.
- [ ] **M1-05 Scoring contract.** Implement pure calculations from hand-written ledger examples, including partial evidence, zero checks, repeated target groups and manual checks. Acceptance: results match independent calculations and never imply complete compliance with unknown mandatory checks.
- [ ] **M1-06 Template revision/job contracts.** Define immutable revision identity, draft lock version, job state transitions and error codes. Acceptance: invalid transitions and published edits are rejected by contract validation.
- [ ] **M1-07 Shared golden API fixtures.** Check in synthetic JSON responses for clean, failed, partial, unknown, expired and unsupported cases. Acceptance: Python validates them; browser/Android contract tests can consume the same examples.

M1 exit evidence: schema versions, generated schema/OpenAPI snapshots, scoring examples and passing contract tests.

## M2 DOCX parsing, effective properties and semantic roles

Depends on: M1. Relevant specification: section 6; preserves existing parser protections.

- [ ] **M2-01 Package-part and relationship access.** Read supported themes, numbering, headers/footers and auxiliary stories with path/relationship validation. Acceptance: missing optional parts remain distinguishable from malformed required parts; external targets are not fetched.
- [ ] **M2-02 Ordered block walker.** Walk paragraphs/tables in document order, including nested tables and merged-cell structure. Acceptance: each content node occurs exactly once in traversal and keeps a stable source anchor.
- [ ] **M2-03 Text and special elements.** Preserve tabs, line/page breaks, hyperlinks, content controls, bookmarks and field instructions/results. Acceptance: supported wrappers do not silently hide text; unsupported revisions/text boxes produce capability diagnostics.
- [ ] **M2-04 Effective style resolver.** Cover direct/inherited properties, based-on chains, explicit false/zero, supported toggles, theme fonts and script slots. Acceptance: independent OOXML fixtures verify supported combinations; unresolved properties are not guessed.
- [ ] **M2-05 Numbering model.** Resolve abstract numbering, list levels, start/restart overrides and displayed prefixes. Acceptance: generated chapter/section numbers are available even when absent from paragraph text.
- [ ] **M2-06 Section ranges and headers/footers.** Correctly assign terminating/final sectPr ranges, first/even/default variants, links and page-number settings. Acceptance: a two-section document applies different margins and numbering to the correct blocks.
- [ ] **M2-07 Role analysis and indexes.** Classify front matter, actual headings, contents/list entries, body, captions and template instructions with evidence. Acceptance: a TOC mention does not become an actual chapter; repeated headings survive indexing.
- [ ] **M2-08 Drawing/object representation.** Capture inline and anchored extents and anchors, decorative-role candidates and support limitations. Acceptance: an anchored figure cannot receive a verified visual position from paragraph order alone.
- [ ] **M2-09 Parser regression and budget tests.** Exercise limits, malformed XML/ZIPs, deep/nested content and existing fixtures. Acceptance: bounded failures have stable codes, and old behavior changes are explicitly explained.

M2 exit evidence: IR snapshots, role confusion cases, property tests and unsupported-feature matrix.

## M3 Template interpretation, decisions and compilation

Depends on: M2 and M1 rules. Relevant specification: sections 7-9, DEC-01 through DEC-09.

- [ ] **M3-01 Source-region classification.** Separate guideline prose, front-matter examples, index table and synopsis table. Acceptance: body font extraction is not dominated by instruction text or cover labels.
- [ ] **M3-02 Explicit property extraction.** Parse paper dimensions, font/size, margins and spacing with original units and source spans. Acceptance: the supplied source proposes A4 and 12 pt and preserves the observed contradictory values.
- [ ] **M3-03 Conditional/modality extraction.** Parse required/recommended/optional language and header/indentation/dedication conditions. Acceptance: an optional header is not mandatory; an unresolved condition remains UNKNOWN.
- [ ] **M3-04 Table-based structure extraction.** Read T0 chapter hierarchy and T3 synopsis guidance as separate candidates/profiles. Acceptance: main chapters are found without treating descriptions and every slash-separated phrase as required headings.
- [ ] **M3-05 Role-specific appearance sampling.** Keep confidence, sample size and observed values separate from authority. Acceptance: appearance cannot silently override confirmed explicit prose.
- [ ] **M3-06 Unit normalization and ambiguity detection.** Cover mm/pt conversion, multiple/exact spacing and ambiguous physical measurements. Acceptance: 6 mm versus 22 pt and conditional margin geometry require review rather than silent arithmetic substitution.
- [ ] **M3-07 Conflict and requirement ledgers.** Track all extracted/unclassified normative spans and competing interpretations. Acceptance: no mandatory unclassified instruction is silently dropped during publication.
- [ ] **M3-08 Review-domain operations.** Confirm, reject, defer, split, add supported rule and resolve conflict with reasons. Acceptance: every rule value edit preserves decision/evidence history and creates a draft when needed.
- [ ] **M3-09 Rule compiler and publication blockers.** Validate payloads, capability requirements, scopes, dependency DAG and overlaps. Acceptance: unresolved hard conflicts block publication; acknowledged unsupported checks remain in coverage.
- [ ] **M3-10 First full extraction demonstration.** Upload the real format through the domain/API path and inspect the reviewed candidate output. Acceptance: document evidence, candidate rules, conflict list and selected profile are coherent and reproducible.

M3 exit evidence: extraction diff from baseline, reviewed candidate fixture, conflict examples, publication tests and resolved decision IDs.

## M4 Core complex-report validators

Depends on: M3; generated report fixture from M0. Relevant specification: sections 9-10 and 12.

- [ ] **M4-01 Scope/prerequisite resolver.** Select semantic roles and profile targets with three-state applicability. Acceptance: empty mandatory targets do not pass and missing chapters do not produce phantom formatting checks.
- [ ] **M4-02 Constrained section matcher.** Exact/alias matches, parent/level constraints, cardinality, one-to-one assignment and ambiguity states. Acceptance: repeated subsection names, combined titles, reordered chapters and TOC-only chapters behave correctly. Covers MP-37,38,44-48.
- [ ] **M4-03 Body typography and paragraph rules.** Apply all effective runs and conditional indentation/separation to the correct body scope. Acceptance: short/mixed-format paragraphs are covered; title/front-matter exceptions do not trigger false body violations. Covers MP-02-04,16,17.
- [ ] **M4-04 Page property rules.** Compare A4 and approved section margins with explicit conditional handling. Acceptance: later-section violations are found and unsupported physical interpretations remain unknown. Covers MP-01,05,06.
- [ ] **M4-05 Heading and chapter-title properties.** Handle number/title pairs, semantic levels, bold/alignment/size and spacing properties. Acceptance: 18/16/14 pt expectations apply to correct roles; no heuristic title is automatically trusted. Covers MP-21,22,24-26.
- [ ] **M4-06 Front-matter fields and placeholders.** Check required fields, permitted cardinality and consistency with high-specificity placeholder patterns. Acceptance: changing fictional names preserves compliance, while an unreplaced explicit placeholder fails. Covers MP-33-38,45,49 at property/structure level.
- [ ] **M4-07 Abstract and auxiliary sections.** Implement reviewed count policy and presence/order checks; separate summary quality from structural evidence. Acceptance: counter conventions and selected profile are reproducible. Covers MP-39,40,44,47.
- [ ] **M4-08 Evaluation ledger and findings.** Generate expected/actual evidence, stable target identities, grouping-independent counts and prerequisite reasons. Acceptance: every fail is traceable and repeated traversal cannot inflate penalties.
- [ ] **M4-09 Complex compliant fixture and mutations.** Generate and independently inspect the first completed report and all M4 single-fault cases. Acceptance: clean fixture has no unexpected hard findings; each mutation triggers its expected rule.

M4 exit evidence: golden result JSON, mutation manifest, false-positive review and unresolved rule coverage.

## M5 Captions, numbering, contents and references

Depends on: M4, table/field/object IR. Relevant specification: sections 10.5-10.6; MP-23,27-32,41-43.

- [ ] **M5-01 Table/figure semantic entities.** Preserve one entity for split tables, distinguish logos and support anchored figures. Acceptance: tables with merged/nested cells and decorative images receive correct identities.
- [ ] **M5-02 Caption association.** Match caption to object with sequence, chapter context and fields; detect ambiguous associations. Acceptance: unrelated captions cannot satisfy missing captions across chapter boundaries.
- [ ] **M5-03 Caption numbering.** Validate chapter prefixes, resets, duplicates and missing sequence positions under the approved policy. Acceptance: typed and generated numbering have equivalent semantics.
- [ ] **M5-04 Structural caption placement.** Check supported inline/table above-below ordering and defer uncertain floating geometry. Acceptance: limitations are explicit; rendered position is not guessed.
- [ ] **M5-05 Contents/list extraction and membership.** Parse manual tables, paragraphs and fields, then compare to actual headings/objects. Acceptance: missing/extra entries and wrong levels are detected without a false chapter-presence pass.
- [ ] **M5-06 Cross-reference/attribution scope.** Validate supported REF/SEQ/typed references and known reproduction cases. Acceptance: unknown originality/provenance never becomes an unsupported accusation.
- [ ] **M5-07 Positive alternatives and mutation tests.** Cover Figure/Fig aliases, optional empty lists, legal extra rows, duplicate headings and caption faults. Acceptance: findings and grouping are deterministic; page-dependent checks remain explicitly pending M6.

M5 exit evidence: caption association fixtures, sequence tests, TOC/list results and capability declarations.

## M6 Rendering, pagination and spatial checks

Depends on: M2, M4, M5. Relevant specification: section 11; DEC-04-08 and DEC-10.

- [ ] **M6-01 Rendering environment and worker.** Pin runtime/fonts/options, isolate profile and directories, bound resources and prohibit external fetches. Acceptance: repeated conversion is fingerprinted; timeout/crash cleanup is reliable.
- [ ] **M6-02 PDF layout representation.** Extract page dimensions, spans/boxes and supported object geometry with explicit coordinates/rotation. Acceptance: coordinates align with previews and printed labels remain distinct from physical pages.
- [ ] **M6-03 Document-to-page alignment.** Implement context-aware matching with split-paragraph support and calibrated ambiguity thresholds. Acceptance: repeated names/headings map correctly or remain unknown; no default page guesses.
- [ ] **M6-04 Page-number validation.** Evaluate Roman/Arabic transitions, suppressed first labels and centered footer positions. Acceptance: correct and mutated multi-section fixtures cover first/even/default header/footer inheritance. Covers MP-10-13,15,37.
- [ ] **M6-05 Chapter and paragraph geometry.** Check actual new-page starts, approved chapter offset, spacing and widow/orphan cases with reliable mappings. Acceptance: properties alone cannot prove visual compliance. Covers MP-14,16,18-22,26.
- [ ] **M6-06 Caption/cover placement and text regions.** Check object/caption geometry, approved logo/title/name regions and header/footer/text-area rules. Acceptance: missing fonts or unsupported anchored objects invalidate affected geometry checks rather than passing them. Covers MP-06-09,29,30,32-35.
- [ ] **M6-07 TOC/list page consistency and stale fields.** Compare visible references to printed page labels under an explicit field-update policy. Acceptance: updating a field during render does not hide an original stale-field defect. Covers MP-42,43.
- [ ] **M6-08 Reference-render comparison.** Compare supported cases against institutional Word-generated reference PDFs if available. Acceptance: document renderer-specific limits; do not claim cross-renderer equivalence without evidence.
- [ ] **M6-09 Mandatory renderer CI and benchmark.** Run actual conversions on clean, mutated, ambiguous and failure fixtures. Acceptance: this lane fails if required dependencies are missing instead of skipping required coverage.

M6 exit evidence: environment fingerprint, mapping accuracy report, renderer failure tests, verified previews and coverage of all applicable rendered MP rules.

## M7 Persistence, asynchronous jobs and API integration

Depends on: M1; may start alongside M2/M3, integrates M3-M6 before completion. Relevant specification: section 13.

- [ ] **M7-01 Repository interfaces and SQLite schema.** Implement constraints, indexes, migrations and artifact-store keys. Acceptance: published revisions are immutable and identifiers cannot expose arbitrary paths.
- [ ] **M7-02 Legacy migration.** Add dry run, backup manifest, ID mapping, idempotent import and recovery. Acceptance: v1 values/status are preserved without fabricated evidence or upgraded coverage claims.
- [ ] **M7-03 Draft/review/publication transactions.** Add optimistic locks, conflict responses and atomic publication. Acceptance: concurrent edits cannot silently overwrite each other; old check revisions remain stable.
- [ ] **M7-04 Durable queue and worker lifecycle.** Implement leases, bounded retries, stage transitions, cancellation and restart recovery. Acceptance: API disconnect/worker crash leaves a known, recoverable job state.
- [ ] **M7-05 v2 upload/check/status endpoints.** Expose typed contracts, safe errors, capabilities and stage progress. Acceptance: the same engine path drives API checks and benchmark fixtures.
- [ ] **M7-06 Idempotency and cache keys.** Include source, revision, options and engine/render fingerprints. Acceptance: retry does not duplicate work; conflicting key reuse is rejected; differing revisions never reuse incorrect results.
- [ ] **M7-07 Result, evidence and artifact endpoints.** Add filtering/pagination, safe content headers, structured export and expiry behavior. Acceptance: counts match the complete ledger and artifact lookup is constrained to its parent object.
- [ ] **M7-08 Retention and cleanup.** Enforce selected TTL, delete-now, orphan recovery and original/render/preview/result cleanup. Acceptance: failure and cancellation paths leave no unbounded retained files.
- [ ] **M7-09 v1 compatibility and version negotiation.** Support only representable legacy rules; return explicit client-upgrade responses for v2-only revisions. Acceptance: an old Android client cannot silently show incomplete v2 checks as a pass.
- [ ] **M7-10 Operational/API integration tests.** Cover disk-full, bad input, concurrent jobs, migration interruption, renderer failure and expired artifacts. Acceptance: codes are stable and documents are not leaked in logs.

M7 exit evidence: migration replay/rollback record, job recovery tests, OpenAPI examples and retention tests.

## M8 Mobile web and native Android integration

Depends on: stable M1 fixtures and M7 integration. Relevant specification: section 14.

- [ ] **M8-01 Review UI information design.** Build requirement/conflict/manual summaries and source-backed rule cards. Acceptance: a teacher can resolve the A4/Letter conflict without editing JSON.
- [ ] **M8-02 Profile, condition and publication controls.** Expose relevant choices and blockers with units and reasons. Acceptance: unresolved mandatory conflicts cannot publish; acknowledged unsupported checks stay visible.
- [ ] **M8-03 Asynchronous submission/progress.** Add revision selection, idempotent upload, polling/backoff, cancellation and retry. Acceptance: slow networks and reconnects do not duplicate checks or lose job identity.
- [ ] **M8-04 Results and issue detail.** Show verdict, coverage, evaluated-only score, grouped findings, locations, source evidence and manual/unknown explanations. Acceptance: 100% evaluated score with incomplete coverage cannot look fully compliant.
- [ ] **M8-05 Preview/export behavior.** Implement verified page overlays, paragraph-only fallback, expired-artifact state and export download. Acceptance: preview coordinate transforms and displayed labels are correct.
- [ ] **M8-06 Android v2 DTOs and repository.** Add typed contracts, unknown-enum fallback, jobs and revision handling. Acceptance: all golden responses deserialize without converting unknown states to success.
- [ ] **M8-07 Android lifecycle and file handling.** Preserve job/revision across rotation/process recreation and clean cached uploads. Acceptance: offline/resume, file-picker cancellation and expired results have tested recovery.
- [ ] **M8-08 Browser accessibility and responsive workflow.** Test full complex upload/review/publish/check at 320/390/768/1280 px with keyboard/status text. Acceptance: no hidden actions, horizontal overflow or colour-only status information.
- [ ] **M8-09 Android runtime verification.** Run emulator workflow and one physical-device smoke test, record device/API level and backend revision. Acceptance: distinguish runtime evidence from build/lint evidence.
- [ ] **M8-10 Private-data cache behavior.** Verify service worker and preview caching rules. Acceptance: static assets may cache; private API/report artifacts do not persist unintentionally.

M8 exit evidence: browser recordings/screenshots, accessibility notes, Android test results and client/server compatibility matrix.

## M9 Generalization, packaging and release

Depends on: all required release milestones. Relevant specification: sections 15, 17-18.

- [ ] **M9-01 Requirement-to-test traceability audit.** Verify every MP ID has a tested implementation or explicit disposition. Acceptance: no silent unsupported requirement remains.
- [ ] **M9-02 Held-out benchmark.** Evaluate different templates/reports with human labels and prevent near-duplicate split leakage. Acceptance: publish per-rule/template precision, recall, counts, disagreements and limitations; do not substitute the mutation suite for generalization evidence.
- [ ] **M9-03 Performance/resource benchmark.** Measure cold/warm p50/p95, memory, timeouts and concurrency on the documented reference machine. Acceptance: report actual measurements against provisional targets and tune limits from evidence.
- [ ] **M9-04 Complex demo package.** Ship reviewed format/profile, completed correct report and erroneous report with a documented defect manifest, using fictional data. Acceptance: fresh-clone demonstration produces the documented states/findings.
- [ ] **M9-05 Reproducible installation.** Update Python dependencies, render/font setup, worker startup, container option and cross-platform README. Acceptance: clean-machine walkthrough requires no undocumented global tools or local paths.
- [ ] **M9-06 Release coverage report.** State which checks are property/structure/render/manual/unsupported, the renderer basis, known ambiguities and remaining DEC items. Acceptance: claims match measured coverage and client behavior.
- [ ] **M9-07 Operational readiness.** Exercise backup/restore, TTL cleanup, logs, cancellation and crash recovery. Acceptance: document local trusted deployment; separately gate any public multi-user hosting on authentication/authorization/HTTPS.
- [ ] **M9-08 Final user workflow and artifact verification.** Verify web/native flows, exports, demo links, Git state and release assets. Acceptance: the final handoff links to the tested revision and lists material limits.

M9 exit evidence: versioned release report, complete task/requirement traceability, setup walkthrough and benchmark artifacts.

## Future scope queue

These are intentionally outside the initial complex-DOCX release. Promote one only through an explicit scope update.

- [ ] **F-01 Native PDF report input.** Define which properties are observable, inferred or unavailable before adapting validators.
- [ ] **F-02 PDF guideline/template input.** Extract written requirements and layout evidence with a capability matrix distinct from DOCX.
- [ ] **F-03 Scanned input/OCR.** Establish OCR quality thresholds, language coverage and uncertainty propagation; do not reuse DOCX confidence claims.
- [ ] **F-04 Optional model-assisted candidate extraction.** Measure added coverage against deterministic extraction and enforce evidence/schema/review boundaries.
- [ ] **F-05 Institution-scale deployment.** Authentication, roles, ownership, quotas, privacy/retention administration and workload-driven queue scaling.
- [ ] **F-06 Assisted repair.** Propose separately; preserve originals, use reversible edits and revalidate output before offering corrected documents.
- [ ] **F-07 Offline native analysis.** Separate feasibility/design study; current mobile app depends on the server.

## Requirement and milestone mapping

The complete MP catalog is maintained only in the master plan to avoid divergent copies. This summary assigns implementation responsibility:

| Requirement family | MP IDs | Primary tasks |
| --- | --- | --- |
| Body/page properties | 01-06,16,17 | M3-02/03/06, M4-03/04 |
| Header/footer/text geometry | 07-09,15 | M2-06, M6-04/06 |
| Pagination and chapter starts | 10-14,18-20 | M2-05/06, M6-03/04/05 |
| Heading styling/numbering | 21-27 | M4-05, M5-03/05, M6-05 |
| Tables/figures/captions | 28-32 | M5-01/02/03/04/06, M6-06 |
| Cover/front matter | 33-38,45,49 | M4-06, M6-04/06 |
| Abstract and auxiliary sections | 39,40,44,47 | M4-02/07 |
| Contents and lists | 41-43 | M5-05, M6-07 |
| Main report and synopsis structure | 46,48 | M3-04, M4-02 |
| Physical requirements | 50 | M0-02, M3-07/08, M8-04; remain manual |

## Decision log

No unresolved interpretation has been approved by this planning document. The proposed handling is in master-plan section 19. Append decisions here; do not rewrite previous decisions without recording supersession.

| Date | Decision ID | Chosen interpretation | Evidence/reviewer | Affected rules/tests | Supersedes |
| --- | --- | --- | --- | --- | --- |
| 2026-10-02 | Planning baseline | DOCX-first plan prepared; detailed interpretation decisions remain open | User requested comprehensive implementation plan | MP-01 to MP-50 | None |

## Session handoff log

Append the newest implementation session at the end. Use exact commits and commands where available. Do not record private document content here.

| Date | Completed | Validation | Outstanding/blockers | Next action |
| --- | --- | --- | --- | --- |
| 2026-10-02 | Master plan, source manifest, MP catalog and implementation tracker authored | Documentation consistency checks; no new runtime functionality | Completed student report not yet supplied; DEC interpretations not yet resolved | M0-01 through M0-05, then the first extraction slice |
| 2026-10-02 | First extraction preview: M0-01 complete; partial M1-02/04, M2-02/03, M3-02/04/06/07/10 | Full backend regression suite and actual-template API/CLI comparison; see checkpoint document and tests in the commit containing this row | No v2 publication/checking or client integration yet; MP dispositions and DEC interpretations remain unapproved | Continue M0-02/03 and v2 source/role contracts, then review/publication integration |

Current partial-work details: typed candidates/evidence/conflicts and a preview capability endpoint exist, but they do not complete the full v2 contracts. The lightweight source walker preserves table-cell text and paths, but does not complete the ordered document IR. Prose extraction covers five property families, not all requirements. Chapter tables yield unapproved profile candidates. These tasks stay unchecked until their full gates pass.

Suggested handoff detail for each future session:

```text
Date and code revision:
Tasks completed (with evidence):
Tasks partially completed:
Tests/commands and results:
Database or schema changes:
Decisions resolved and why:
Open failures and affected requirements:
Private fixtures required locally:
Next smallest executable task:
```

## Initial implementation slices

1. **Evidence and contracts:** M0-01/02/04/05 plus the minimum M1 schemas; no UI rewrite.
2. **Prose and table extraction:** core M2 table/source support plus M3-01/02/04/06/07; demonstrate real-template conflicts.
3. **Review and immutable publication:** M3-08/09 and M7 persistence/API slice; keep all interpretations visible.
4. **One complete complex-report check:** M4 scope/structure/property checks plus result ledger and client results.
5. **Caption/TOC expansion:** M5 with controlled mutations.
6. **Rendering integration:** M6 after approved measurement decisions and required renderer tests.
7. **Mobile completion and benchmark:** remaining M8/M9 with fresh-clone and native runtime evidence.

A slice can contain several commits. Branch/PR names are implementation choices; do not create implementation branches or mark these tasks done merely because this plan has been committed.
