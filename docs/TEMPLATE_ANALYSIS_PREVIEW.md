# Complex template analysis preview

Implemented checkpoint: extraction preview 0.1.0, started 2026-10-02. This is the first executable slice of the [implementation plan](COMPLEX_TEMPLATE_IMPLEMENTATION_PLAN.md), not the complete complex-report checker.

## What works now

- The parser builds source references for main-story paragraphs and table-cell paragraphs, preserving line breaks and nested-table identity.
- Conservative English patterns propose body font, body font size, multiple line spacing, named paper dimensions and margins from written instructions.
- Stored appearance is returned separately. A template that says A4/12 pt but uses Letter/11.5 pt produces explicit disagreement records.
- Conditional no-header margin instructions retain their condition. General and conditional top-margin values are flagged for interpretation, not combined into an approved rule.
- Report-index and synopsis tables yield separate proposed chapter lists. Subsequent lines in a topic cell remain suggested topics with undecided requiredness; slash-separated text is not automatically split into aliases.
- Unsupported instructional text remains in a review ledger where detected, including manual inspection requirements. Candidate-bearing paragraphs can contain additional unsupported requirements.
- Typed response models reject nonfinite/invalid numeric values, unknown payload fields, duplicate IDs and missing evidence references.
- Preview processing uses temporary storage and the existing bounded DOCX loader. It does not save or publish a template.

All candidates remain PROPOSED, all conflicts remain UNRESOLVED, and `publication_ready` is always false. The existing `/api/templates` report-checking flow continues to use its existing rules. The preview is not yet connected to either client's rule editor or report checker.

## Try the API

Start the server using the main README. Open `http://127.0.0.1:8000/docs`, find **Experimental template analysis**, expand `POST /api/v2/template-analysis`, select **Try it out**, upload a DOCX format and execute it.

The JSON response contains `candidates`, `evidence`, `conflicts`, `profiles`, `requirement_ledger`, and `notices`. A candidate's evidence IDs resolve to source paths and excerpts. A suggested conflict resolution is only a proposal and does not approve anything.

`GET /api/v2/capabilities` lists actual capabilities. The subsequent [revision review API](TEMPLATE_REVISION_REVIEW.md) supports publication of reviewed specification snapshots, and [revision-pinned checks](REVISION_REPORT_CHECKS.md) evaluate explicit section page settings plus [scoped body/chapter properties](SCOPED_BODY_AND_CHAPTER_CHECKS.md). The preview endpoint stays synchronous and read-only; the later asynchronous template/job API in the plan remains future work.

## Repeatable CLI inspection

From the repository root in an installed virtual environment:

```powershell
.venv\Scripts\python.exe -m scripts.inspect_template "C:\path\to\format.docx"
```

On macOS/Linux, use `.venv/bin/python` with the same arguments. Add `--expected-sha256 HASH` to fail when a file differs from the recorded source. Add `--include-evidence` only when the full source excerpts are needed; that output may contain private document text.

Default output excludes the input filename/path, source prose, chapter titles and student fields. It preserves proposed property values, IDs, conflicts and counts. It is not a general-purpose anonymizer: review property values before sharing output.

## Real-template verification

The locally supplied Mini Project format was checked through the new API and two repeated CLI runs. Source identity is recorded in the master plan. Results matched across those paths:

| Output | Observed result |
| --- | --- |
| Explicit written property proposals | 9 |
| Stored appearance observations | 8 |
| Unresolved property conflicts | 8 |
| Report-index entries | 6, including references and acknowledgements |
| Synopsis entries | 9 |
| Detected instructional spans still unclassified | 23 |
| Detected candidate-bearing spans requiring review | 7 |
| Detected manual-review spans | 3 |

These are extraction counts, not a compliance percentage or proof that all requirements were found. In particular, the 33 detected ledger spans are not interchangeable with the plan's 50 requirement groups. One span can contain several requirements, and unsupported language may still be missed.

The [redacted extraction snapshot](benchmarks/mini-project-1a-extraction-0.1.json) records the result without copying the original DOCX or research papers into Git. It includes the problematic observed 11.5 pt/Letter/72 pt values alongside the explicit prose proposals.

## Tests and remaining boundaries

Checkpoint validation on 2026-10-02: `python -m pytest tests -q` passed **78 tests**; four existing optional LibreOffice tests were skipped because the renderer is unavailable locally. The installed FastAPI/Starlette test stack emitted an existing HTTPX deprecation warning. OpenAPI generation, documentation links and snapshot structure also passed validation. No new dependency was installed for this implementation.

`tests/test_template_analysis.py` uses fictional DOCX inputs. Tests cover contradictions, conditional margins, unit conversion, separate chapter profiles, preservation of unresolved wording, negation/alternatives, sentence boundaries, merged-table abstention, numeric validation, evidence integrity, determinism, CLI source hashes, API errors and non-persistence.

The real-file run caught an extraction regression where an unrelated `or above` in the paper-quality sentence suppressed the following A4 requirement. Extraction now scopes that alternative check to the paper-size sentence, and a synthetic regression test preserves the behavior.

The source inventory is not yet the full v2 document IR. It does not implement semantic formatting for all stories, complete style inheritance, source-region segmentation, generated numbering, rendered page locations or automatic approval. Generic negation/alternatives and merged index tables are intentionally left for review. No NLP model, deep-learning model or OCR dependency was added in this slice.

The subsequent revision-review checkpoint adds source dispositions, profile decisions and immutable specification publication. Fuller document/role contracts and rule execution remain pending. The benchmark snapshot above records the original extraction checkpoint, including its historical notices. Keep unchecked tasks in the execution tracker visible until their complete acceptance criteria are met.
