# Real-document improvements: checker 0.4.0

This release addresses defects found by comparing an independent audit with a real DOCX check. Private documents and extracted report contents are not included in this repository. Regression fixtures are fictional.

| Root cause | Change | Remaining boundary |
| --- | --- | --- |
| Exact chapter names and outline level 1 only | Normalize trailing punctuation, numbered chapter prefixes and acknowledgement variants; recognize split chapter banners at other heading levels | Typos and semantic synonyms still require reviewed aliases or role assignments |
| Existing classifications could not be corrected | Allow hash-bound role corrections on safely parsed body/heading/other paragraphs | Fields, tables, drawings and malformed styles remain protected |
| Missing inherited spacing treated as unknown | Resolve default single spacing when line settings are absent throughout a valid style chain | Numbered body formatting and rendered line heights remain unsupported |
| Body Text mistaken for universal applicability | Front matter before chapter banners, references/appendix regions and sign-offs require scope review | Explicit review determines applicability; no broad semantic classifier is claimed |
| Chapter typography missing from rule model | Reviewed chapter_font_size and chapter_case proposals and validators | Explicit numbered banners only |
| Abstract validation missing | Reviewed abstract_word_count and abstract_keywords proposals and validators | Unique heading and bounded region; exact whitespace count and nonempty Keywords label only |
| Different tolerance policies | Expose the existing 1/240-line tolerance in result messages and capabilities | 1.50833 remains a failure against 1.5; tolerance was not relaxed to fit a report |

## Compatibility and use

New extraction uses version 0.2.0, compilation 0.4.0 and checking 0.4.0. Published snapshots retain their original contents and hashes. Re-upload the format and review the new proposals to enable additional validators. Manual/deferred source requirements are never silently executed. Candidate-bearing paragraphs remain in the source ledger because other instructions in the same paragraph may be unsupported.

The existing mobile web review flow displays the new proposals and results. `/api/v2/capabilities` lists supported properties. Existing classified paragraphs now appear as reviewable where structurally safe; decisions remain tied to exact report and template hashes.

## Real-file benchmark

The original template snapshot no longer produces the three false missing-section findings. Five required sections are recognized automatically; the misspelled literature heading remains ambiguous. One explicit role correction recognizes all six in order. All six previously unchecked default-spaced body paragraphs now fail the required 1.5 spacing check.

After the four new written proposals are reviewed, the checker detects seven chapter-size failures, seven chapter-case failures, an abstract-length mismatch and missing labeled keywords. Detection increases from four to nine of the original twenty failed audit criteria. This is one selected benchmark, not general accuracy or total-report compliance. Repeated run/section counts must not be converted into a compliance percentage.

## Remaining causes and implementation order

1. Conditional margins need section-aware header presence/inheritance. The no-header alternative remains unsupported.
2. Page numbering needs footer/field interpretation, Roman/Arabic formats, restarts and first-page suppression.
3. Generated numbering and section roles must be resolved before section/subsection typography and contents reconciliation.
4. Figures/tables need association with captions and lists; captions embedded in images require additional evidence.
5. Abstract chapter overviews and other semantic content require dedicated checks with explicit uncertainty.
6. Actual page positions, contents page references, geometric gaps and widow/orphan checks need rendering. Physical binding/paper requirements need external inspection.
7. Requirement-level scoring needs explicit applicability and unknowns rather than repeated XML-item totals.

## Tests

Run `python -m pytest -q`. `tests/test_real_world_regressions.py` covers banners, split titles, punctuation, default spacing, tolerance policy, role correction, cover scope, reviewed chapter/abstract checks and abstention without an abstract boundary. Existing tests protect table/field false matches, malformed input, revision integrity and review hashes.
