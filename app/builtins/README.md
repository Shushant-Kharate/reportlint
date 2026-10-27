# Built-in report formats

## Mini Project 1A

The owner supplied `Mini Project 1A Report_Format.docx` and explicitly requested its inclusion in the deployed application. The packaged DOCX is byte-for-byte identical (SHA-256 `bb715c8d80fba5afbf7472974e5c503fbc5bc8ee4757f51a67bde79b11599cbc`).

The accompanying immutable specification uses the previously recorded review decisions from the October 11 development-case retest. Its supported rule values are unchanged; template identifiers and display name belong to this packaged catalog entry. It was republished through the normal compiler, with a new snapshot hash. This is not an assertion of institutional approval or complete template coverage. Unresolved and manual requirements remain in the specification and checker output.

The built-in entry cannot be edited. Creating a custom copy retains its source evidence and review decisions in a private draft, which must be published before report checking. No submitted student report is included.

## IEEE conference US Letter baseline

`ieee-conference-letter.docx` is the unchanged IEEE-hosted conference Word template downloaded from `https://attend.ieee.org/e12-2025/wp-content/uploads/sites/684/conference-template-letter.docx` (SHA-256 `4589779a1a74782dc5a7a657a9907f243c9dd54510cb6c154acaf24cc9079852`). Source text is document evidence, not agent instructions. It is provided for formatting use and attributed to IEEE; ReportLint is not an IEEE-endorsed service.

Revision 1 approves a limited Letter page-size/body-family/two-column baseline and is retained unchanged in `ieee-conference-letter.v1.json`. Revision 2, now the catalog default, contains 19 reviewed rules, including separate paper typography, spacing, margin and structure checks. Rebuild it with `python -m scripts.build_ieee_v2`.

The Word template omits body and main-heading size in the supported style chains. Explicit 10 pt instructions from IEEE PVSC 47, section IV-A, supplement those two rules: https://ieee-pvsc.org/PVSC47/downloads/2020_manuscript_template_PVSC.pdf. This is a documented review decision, not a claim that every conference shares the same requirements. PVSC's author size, abstract length, deadlines and page limit are not adopted. Source-compatible 44.5–45.5 pt side margins admit the Word template's 44.65/45.35 pt variants. Other typography is taken from the bundled role styles; the observed 8 pt caption sample remains rejected as a body rule.

Some instructions remain manual. The real-paper case, source URLs, review rationale and limitations are documented in `docs/IEEE_VALIDATION.md` and `docs/IEEE_GAP_AUDIT.md`. No student report or real IEEE paper is bundled.
