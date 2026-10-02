# Scoped body and chapter checks

Checker **0.2.0** extends the existing revision-pinned report endpoint with conservative body formatting and chapter checks. New publications use compiler **0.3.0** metadata. Previously published specifications keep their original contents and hashes and can still be checked. No dependency or installation command changes are required.

This document describes the style-based checkpoint. Current checker **0.3.0** also accepts [explicit report-specific role reviews](MANUAL_REPORT_ROLE_REVIEW.md) for supported unstyled paragraphs. Without a review, the conservative behavior below remains unchanged.

## Use the feature

Follow the [review workflow](TEMPLATE_REVISION_REVIEW.md), then upload a report using the [revision check endpoint](REVISION_REPORT_CHECKS.md). The web/Android UI has not yet been connected to this v2 flow; use the API's `/docs` interface.

In Word, use **Body Text** for actual prose and **Heading 1** for chapter titles. A custom paragraph style may inherit from either style. Review the template's body font, size and spacing proposals, select the correct report profile, and explicitly review chapter names, aliases and requiredness before publishing. Changing a report's styles is a preparation step, not an automatic repair performed by this checker.

For a title such as `Chapter 1: Introduction`, add that entire title as a reviewed alias of `Introduction` when needed. Matching folds case and whitespace; it does not remove numbering, punctuation, or words. Generated numbering is not evaluated, though a heading's text can still match when its generated prefix is stored separately by Word.

## Paragraph inventory and scope

The checker walks main-story paragraphs in document order, including paragraphs in tables, and preserves their XPath and zero-based paragraph index. Table paragraphs occupy positions in this index but are excluded from chapter/body targets. Headers, footers, footnotes and endnotes are outside this inventory. It is not the full document IR specified in the roadmap.

Roles are based on explicit structure:

- `BODY`: paragraph style is Body Text or inherits from it, with no conflicting heading outline level.
- `HEADING`: effective paragraph outline level is 0–8 (reported as heading levels 1–9), resolved from direct paragraph properties and the style inheritance chain. Direct outline level 9 suppresses inherited heading status.
- Contents styles and fields, including field results spanning paragraphs, do not count as actual chapters. Generic field-bearing prose remains unresolved body coverage instead of silently disappearing. Ordinary hyperlinks remain available for body-run checking.
- Title, Subtitle and Caption styles are excluded from body checks. Unstyled Normal paragraphs, missing/cyclic style references, unsupported containers, tracked changes, and mixed drawing content remain unresolved rather than being guessed from font size or words.

Body rules emit `INCOMPLETE_BODY_SCOPE` when possible body paragraphs remain unresolved, structural interpretation is uncertain, or no explicit body targets exist. A report with no body targets cannot receive a body-rule pass. Tables and other stories are not implicitly certified by checking main-story prose.

## Body formatting

For unconditional reviewed body rules, the checker compares:

| Property | Supported resolution |
| --- | --- |
| Font family | Direct run → character style chain → paragraph style chain → document defaults, for explicit ASCII font slots. |
| Font size | The same precedence for scalar size, in points. |
| Multiple line spacing | Direct paragraph → paragraph style chain → document defaults; explicit exact/at-least spacing does not satisfy a multiple-spacing requirement. |

Every nonempty supported run is checked, including runs inside hyperlinks. A short wrong-size phrase is not hidden by a paragraph's dominant font. Results include `paragraph_index`, `run_index` where relevant, expected/actual values, template evidence IDs, and the specific paragraph/run XPath. Font names compare case-insensitively; font sizes use 0.1 pt tolerance and multiple spacing allows one Word line-spacing unit (1/240).

Theme-dependent fonts, non-ASCII script selection, hidden/complex-script run properties, malformed values, and unresolved styles produce `NOT_CHECKED`. Numbered body paragraphs remain unchecked because numbering styles can contribute formatting. These checks compare stored effective scalar properties; they do not measure rendered line heights, resolve theme files, or implement full Word style semantics.

## Chapters

The selected profile is matched to main-story heading-level-1 paragraphs using exact reviewed names and aliases. It reports:

- `CHAPTER_PRESENT` for a unique, trusted match.
- `MISSING_CHAPTER` when a required exact title is absent from an otherwise available trusted heading inventory.
- `DUPLICATE_CHAPTER` for repeated trusted matches.
- `AMBIGUOUS_CHAPTER` for a matching title at an unresolved/lower-level location or uncertain document structure.
- `NO_TRUSTED_CHAPTER_HEADINGS` when there is no reliable chapter inventory.
- `OPTIONAL_CHAPTER_ABSENT` as out of scope when an optional chapter is absent.

A contents/table mention cannot replace a chapter. Relative order is checked using the profile's chapter indices and the locations of unique matches. Missing or ambiguous chapters prevent a complete order pass; a demonstrable inversion can still fail. Extra unreviewed chapter titles are allowed. Chapter subtopics, semantic title equivalence, manual heading recognition, combined/split headings, numbering correctness, and nested chapter requirements are not implemented.

## Limits, results and testing

The parser rejects reports exceeding 10,000 main-story paragraphs, 20,000 main-story runs, or 5,000 styles, in addition to existing file/section limits. Style inheritance chains over 100 entries remain unresolved. Unsupported content never contributes a success item for a guessed property.

The existing `FAIL`, `INDETERMINATE`, and `PASS_SUPPORTED_CHECKS` outcomes still apply. Counts now also include paragraph/run/chapter items and remain unsuitable as a compliance percentage. Ledger requirements stay visible even when a supported property passes; passing these checks does not establish complete complex-template compliance.

Validation: **140 backend tests passed**, with four optional LibreOffice tests skipped because the renderer is unavailable locally. New cases cover inherited paragraph/character styles, mixed runs, hyperlink runs, exact-versus-multiple spacing, theme/script abstention, cyclic/missing styles, numbered paragraphs, custom outline styles, direct outline overrides, contents/inline fields, table mentions, aliases, optional/missing/duplicate/reordered chapters, and paragraph ordering around tables. No OCR, NLP or deep-learning model was added. The next gaps are richer body/front-matter role interpretation and a mobile v2 review/check workflow.

The original Mini Project template was inspected locally without publishing interpretations or saving its contents into Git. Its role inventory contains 124 unknown, 192 empty and 180 table paragraphs, with no trusted Body Text/outline headings. This confirms the present style-based path does not yet resolve that document's manual formatting. Those counts describe the format file, not a completed student report or a compliance result.
