# IEEE format gap audit

Tested 27 October 2026 against the original privately supplied Mini Project 1B DOCX. The student report, Word rendering, excerpts and full exports remain outside this public repository.

## Cause and outcome

IEEE revision 1 published only three executable requirements: Letter paper, Times New Roman body family, and two body columns. Paper size and many font-family matches were genuine. The earlier column repair produced one issue group, but no requirements for body size, spacing, margins or paper structure had been published. Selecting a format named IEEE could not make these missing requirements executable.

Revision 2 now has **19 individually evidenced rules**. Checker 0.7.0 adds native DOCX paper executors. The real Flutter upload/check/export flow reports **16 issue groups and 15 review groups** for this file.

| Same original file | Pass items | Fail items | Unresolved items | Confirmed issue groups |
|---|---:|---:|---:|---:|
| Revision 1 with column executor | 735 | 13 | 100 | 1 |
| Revision 2 with paper executors | 655 | 1,095 | 225 | 16 |

The failures include repeated run, paragraph and section checks: **1,095 items are not 1,095 independent mistakes**. The pass count changes because abstract/front matter/references are kept outside paper-body rules. Additional explicit checks also add review items. None of these counts is a compliance percentage or general accuracy measurement.

## Independent inspection and app comparison

The original OOXML, inherited styles and numbering definitions were inspected alongside a read-only Microsoft Word export. Word rendered 46 pages on this machine. Pages 1, 4, 9, 21 and 44 were visually inspected for the cover, abstract, chapter opening, native figure caption and references. This local Word rendering supports the audit; the deployed DOCX checker does not run Word.

Requirements refer to the reviewed Letter baseline, not every IEEE venue. App section/paragraph indices are not physical page numbers.

| Requirement | Independent observation | Earlier app | Updated app |
|---|---|---|---|
| Two body columns | Substantive body sections use one | Found | 13 safely scoped section failures |
| Body size 10 pt | Main Body Text uses 12 pt | Missing rule | 615 supported run failures across 60 paragraphs |
| Body spacing 0.95 lines | 1.5, 1.5083 or inherited single spacing | Missing rule | 67 paragraph failures |
| Justified body | Many paragraphs inherit left alignment | Missing rule/executor | 73 paragraph failures |
| Top margin 54 pt | 65–91 pt | Missing rule | 37 section failures |
| Bottom margin 72 pt | 35 pt | Missing rule | 37 section failures |
| Left margin 44.5–45.5 pt | 72 pt | Missing rule | 37 section failures |
| Right margin 44.5–45.5 pt | 18 pt | Missing rule | 37 section failures |
| Abstract text 9 pt | 14 pt, visually confirmed on page 4 | Missing rule/executor | 28 run failures in one paragraph |
| Run-in Abstract label | Separate ABSTRACT heading and prose | Missing rule/executor | Confirmed mismatch |
| Keywords / Index Terms | No nonempty label before next heading | Missing rule/executor | Missing baseline component |
| Main heading size 10 pt | Seven CHAPTER banners use 16 pt | Missing rule/executor | 15 run failures across seven banners |
| Roman main-heading numbers | CHAPTER 1 through CHAPTER 7 | No paper numbering rule | Seven numbering failures |
| No added pagination | Active inherited footer PAGE field; rendered numbers visible | No absence-of-pagination rule | Field detected across 37 sections |
| Reference-entry size 8 pt | Entries and continuation use 12 pt | No separate reference rule | 89 supported run failures across six paragraphs |
| Paper caption numbering | Native Fig 3.1 label | Chapter-caption rules cannot express paper numbering | One confirmed native label mismatch |

Some features really match: Letter paper and many Times New Roman runs. Reference numbering also uses a generated `[%1]` definition, confirmed as bracketed labels in the Word rendering. Reading only visible DOCX text would falsely suggest that reference numbers were absent. This audit does not classify those labels as wrong.

## Remaining differences and detection limits

* **Title and authors:** the visible cover title is 20 pt and student-name lines are 16 pt. The bundled paper-title style is 24 pt. This file begins with Normal-style cover text and misuses heading/title styles elsewhere. The app leaves title applicability unresolved instead of selecting the Declaration or certificate title and generating a false error. Author geometry and first-page component placement need rendered-layout analysis.
* **Front matter and whitespace:** certificate, declaration, index and standalone chapter pages differ visibly from the paper specimen. Absence from a specimen alone does not establish a universal prohibition. Physical gaps and page breaks need rendering. No arbitrary page cap is imposed on the 46-page rendering.
* **Figures/tables:** one editable figure label is classified. Embedded captions, complete caption coverage, exact object placement and physical gaps remain manual. Missing editable text does not prove missing text inside an image.
* **References and meaning:** reference accuracy, complete citation correspondence, abstract meaning, scientific quality and grammar are not established by these formatting validators.
* **Uncertain native roles:** unstyled text, fields, numbering contributions, complex scripts and broken style chains retain review status. Supported local matches do not establish whole-document compliance.
* **PDF:** new typography rules are native DOCX checks. PDFs still receive measured page/layout checks and explicit unsupported-property review items.

These are remaining engineering gaps; this change does not establish complete IEEE compliance or reliability on unseen venues.

## Source and review policy

The unchanged [IEEE-hosted Letter Word template](https://attend.ieee.org/e12-2025/wp-content/uploads/sites/684/conference-template-letter.docx) controls page settings, role styles, abstract layout, caption conventions and the pagination instruction. SHA-256 remains `4589779a1a74782dc5a7a657a9907f243c9dd54510cb6c154acaf24cc9079852`.

BodyText and Heading1 omit explicit sizes in the supported chains. **10 pt body and main-heading instructions from section IV-A, page 3 of the [IEEE PVSC 47 template](https://ieee-pvsc.org/PVSC47/downloads/2020_manuscript_template_PVSC.pdf)** supply those two reviewed values. This supplement is recorded in source evidence. Its author size, abstract word cap, deadlines and page limit are not imported. Abstract 9 pt, title 24 pt and references 8 pt come from the bundled Word styles. Body spacing is the stored 228/240 = 0.95 multiple.

The reviewed side-margin interval admits the source's 44.65/45.35 pt variants; it is an explicit review policy, not a mandatory IEEE tolerance. The shown Keywords line is a baseline requirement, with Index Terms accepted as equivalent. There is no inferred abstract word-count cap.

Evidence distinguishes document XML, style XML and external guidelines. The old observed 8 pt sample remains rejected as a body-size rule. Every added rule is separately approved through the ordinary compiler. Remaining clauses in source-ledger passages still need manual review.

## Verification

The Python suite passes **258 tests**, with four optional rendering tests skipped. Twenty new paper cases cover positive controls, independent property mutations, role separation, active footer fields, source margin variants and historical snapshots. Flutter analysis and 22 tests pass; the web release build succeeds. Browser verification selects revision 2, uploads the original report, checks its SHA-256 and verifies unchanged JSON export at desktop and mobile widths.

Controls:

* Original IEEE Word template: **163 pass, zero fail, 195 unresolved**. Omitted sizes remain unresolved.
* Fully specified synthetic paper: no confirmed failures; single-property mutations produce the relevant failures.
* Original IEEE SVO PDF: **14 pass, zero fail, 156 unresolved**. The expanded unsupported PDF rule set increases review items.
* Original Mini Project baseline on this report: unchanged at **1,505 pass, 324 fail, 180 unresolved, 37 inapplicable**.

Revision 1 remains archived unchanged and addressable; revision 2 is the catalog default. Old custom snapshots do not silently acquire rules. The v2 builder preserves matching snapshots and refuses to overwrite different revision-2 content.

Run `python -m pytest -q`, then `flutter analyze` and `flutter test` in `frontend`. Actual upload/export flows can be repeated with Playwright:

```text
node scripts/verify_ieee_docx.cjs SERVER_URL PATH_TO_PRIVATE_REPORT.docx OUTPUT_OUTSIDE_REPOSITORY
node scripts/verify_ieee_pdf.cjs SERVER_URL PATH_TO_ORIGINAL_SVO.pdf OUTPUT_OUTSIDE_REPOSITORY
```
