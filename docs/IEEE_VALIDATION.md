# IEEE conference baseline and real-paper test

ReportLint includes **IEEE Conference — US Letter (reviewed baseline)**. It is a limited, reviewed baseline, not an IEEE certification service or a claim to check every IEEE venue's requirements. Conference, journal, A4 and US Letter formats differ.

## Sources and provenance

- IEEE's conference-template page: https://www.ieee.org/conferences/publishing/templates.html
- IEEE CAI's explanation and links to the standard Letter and A4 variants: https://cai.ieee.org/2025/manuscript-templates-for-conference-proceedings/
- Exact Word file downloaded from an IEEE-hosted conference site: https://attend.ieee.org/e12-2025/wp-content/uploads/sites/684/conference-template-letter.docx
- Packaged source SHA-256: `4589779a1a74782dc5a7a657a9907f243c9dd54510cb6c154acaf24cc9079852`. Its bytes are unchanged. The compiler reads Strict OOXML namespaces and unit-bearing measurements in memory.

The real test paper is Christian Forster, Matia Pizzoli and Davide Scaramuzza, **SVO: Fast Semi-Direct Monocular Visual Odometry**, 2014 IEEE International Conference on Robotics and Automation (ICRA), pp. 15–22. Publication is independently confirmed by IEEE: https://doi.org/10.1109/ICRA.2014.6906584

The tested file is the authors' university-hosted PDF, not a reconstructed Word document: https://rpg.ifi.uzh.ch/docs/ICRA14_Forster.pdf

- Size: 1,469,859 bytes; eight pages.
- SHA-256: `0f0b223d8dfbb11db1623144b748cd5156450e6baed023a54e31706dcafcdb41`.
- The PDF is used locally for testing and is not redistributed in this repository or bundled with the app. The current generic template is a baseline comparison, not a retrospective ruling on ICRA 2014's venue-specific acceptance requirements.

## What was reviewed before publication

The extractor proposed the correct Letter paper size, but its appearance heuristic also proposed 8 pt as a body size. The source explicitly uses small figure-label/reference styles; its Body Text style does not provide an unambiguous numeric font-size value through the supported inheritance chain. The 8 pt sample was rejected rather than enforced or replaced by a guessed size.

The published rules are Letter paper size (612 × 792 pt), the observed Times New Roman body family, and a reviewed two-column main-text layout. The Word file has differing section-specific side margins and special author/table layouts. Global margin and spacing samples were rejected as automatic rules; the instruction ledger keeps those requirements for manual review. This curation is reproducible with:

```powershell
python -m scripts.build_ieee_builtin PATH_TO_THE_EXACT_SOURCE.docx
```

The build utility records explicit review decisions and refuses an unexpected main-text font. It is not a general automatic approval workflow. A custom copy can be created through the app and must be published before checking.

## Independent inspection compared with app output

The original PDF was visually inspected, including pages 1, 6 and 8. All eight pages have Letter geometry and visible two-column organization. Page 6 has extensive charts in its right column; page 8 has a photograph, concluding prose and references. Those pages do not supply enough comparable long prose in both columns for the conservative column detector.

| Requirement | App result | Interpretation |
|---|---|---|
| Letter page dimensions | 8 passes | Native PDF MediaBoxes measure 612 × 792 pt. |
| Two-column prose | 6 passes, 2 unresolved | Pages 6 and 8 remain manual; charts/references are not mislabeled as single-column failures. |
| Body font identity/style | 8 unresolved | Font names and size histograms are returned as prose samples. They do not prove Word body-role assignments or exact font equivalence. |
| Other source instructions | 18 manual items | Includes requirements beyond the executable baseline. |

Total: **14 PASS, 0 FAIL, 28 NOT_CHECKED, 0 OUT_OF_SCOPE**, or 42 check items. The outcome is **INDETERMINATE**. This is not a percentage, an assertion that the paper has no errors, or IEEE PDF eXpress approval. The 28 unresolved/manual items are not 28 detected mistakes.

A controlled in-memory copy of the original paper changed only page 1's MediaBox to A4. The API returned exactly one confirmed paper-size failure on page 1. Synthetic tests also detect sustained single-column prose on a later page, and retain blank/illustrated, cropped and rotated pages for review rather than inventing geometry conclusions. The original paper is unchanged.

## Use and reproduce

1. Open the deployed app and select **Check report**.
2. Choose **IEEE Conference — US Letter (reviewed baseline)**.
3. Download the original paper from its university link and upload that `.pdf` directly.
4. Review confirmed measurements separately from **Needs review** items. Expand locations for PDF page numbers and download the JSON result.

PDF report checking is experimental: native page dimensions and sustained two-column prose evidence are supported. Original DOCX margins, body styles, font roles, spacing, citation correctness, captions, author layout and semantic requirements are not fully inferred from a PDF. No OCR or learned model is used. Scans without usable prose remain unresolved. PDF limits are 100 pages, two million extracted characters and the existing upload/request limit (4 MB hosted, 20 MB local).

With Playwright and its matching Chromium browser installed, the actual Flutter upload/check/export path can be repeated with:

```powershell
node scripts/verify_ieee_pdf.cjs http://127.0.0.1:8000 PATH_TO_ORIGINAL_PAPER.pdf OUTPUT_DIRECTORY
```

The script checks the original PDF hash, counts, correct template selection, PDF-specific UI, and exact JSON export. It does not generate or substitute a paper. `NODE_PATH` may be needed when Playwright is installed outside the repository, as described in the Flutter verification documentation.

## DOCX wrong-format regression fixed on 27 October 2026

A real mini-project DOCX checked against the IEEE baseline previously returned 735 passes, no failures and 77 unresolved items. Its 37 stored sections use Letter paper, and the selected body runs use Times New Roman, so those matches were legitimate. The problem was a missing DOCX executor for the already-approved `body_columns` rule. It was reported as unsupported instead of comparing the report's single-column body sections against two columns.

Checker 0.6.1 maps main-story paragraphs to their stored section definitions and evaluates column counts for substantive body prose. Explicit/reviewed body paragraphs are preferred. Multiple substantial unstyled prose paragraphs can establish layout scope without being promoted into font-role assignments. Covers, author blocks, captions, tables, references and sparse sections remain unresolved when body applicability cannot be established. Reviewed paragraph exclusions are respected. Equal-width counts, the single-column default, and consistent explicit unequal-width definitions are supported; malformed or ambiguous definitions remain manual. This is based on the [OOXML column specification](https://learn.microsoft.com/en-us/dotnet/api/documentformat.openxml.wordprocessing.columns.equalwidth).

The same private mini-project report now returns **735 PASS, 13 FAIL, 100 NOT_CHECKED**. The 13 confirmed failures are single-column body sections requiring two columns, grouped as one issue type. They occur in Word sections 4, 9, 10, 14–17, 27, 28, 31–33 and 37. These are section indices, not rendered page numbers. The report itself is not distributed. The higher unresolved item count reflects per-section column scope results, not additional detected mistakes.

Controls verify that changing only the body column setting from one to two removes the failure, that matching fonts and paper size do not conceal wrong columns, and that one-column author blocks or full-width captions are not automatically failed. The original IEEE Word template still has zero confirmed failures. The original SVO PDF remains at 14 passes, no failures and 28 unresolved items. Other IEEE checks remain limited; this fix does not add a complete IEEE rulebook.

The Flutter interface explains a mismatch as “2 columns” required versus “1 column in this Word section,” with source-editing guidance. An indeterminate result now explicitly states that zero confirmed issues is not a clean result.

```powershell
node scripts/verify_ieee_docx.cjs http://127.0.0.1:8000 PATH_TO_SINGLE_COLUMN_REPORT.docx OUTPUT_DIRECTORY
```

This regression exercises actual file selection, report checking and JSON export. The output contains report evidence and should remain outside the public repository.
