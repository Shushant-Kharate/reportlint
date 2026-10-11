# Real-document retest: checker 0.5.0

This release closes gaps found by comparing an independent OOXML/image audit with the application on the same private format and report. Source documents, personal report contents, extracted images and real-file screenshots are not published. All committed regression fixtures are fictional.

## Measured result

On the selected benchmark, automatic detection increases from **9/20 to 18/20 independently failed criteria**. “Detected” means the checker reports at least one genuine failure belonging to that criterion. It does not establish every instance, every clause, general accuracy, total report compliance or grading correctness. The underlying submitted document was not edited.

The nine newly detected categories are conditional top margin, footer-number alignment, front-matter numeral format, Introduction restart/first-number suppression, first-level section font size, contents numbering/page-reference structure, contents reference alignment, missing table list, and missing numbered table titles. Contents completeness remains partial even though bullet/range violations are detected.

The real result contains 1,505 PASS, 324 FAIL, 180 NOT_CHECKED and 37 OUT_OF_SCOPE check items. Repeated section/run instances are grouped into 20 issue groups in Flutter. Neither group counts nor item counts are independent requirement totals or percentages.

## Root causes and implementation

| Difference | Cause | Fix and boundary |
|---|---|---|
| No-header top margin deferred | Conditional alternative conflicted with general margin; header inheritance was missing | Reviewed HEADER_ABSENT top margin overrides the general value only when active inherited headers are blank. Broken references and mixed first/even variants abstain. |
| Pagination absent | Footer story parts and PAGE instructions were never interpreted | Load internal header/footer relationships; resolve link-to-previous, first/even variants, PAGE fields and format switches. Compare alignment, Roman/decimal formatting, Introduction restart and first-footer suppression. Cached field numbers are never trusted. |
| Five wrong section sizes missed | Decimal numbering lived in Word numbering definitions, while outline levels disagreed with numbering depth | Resolve numId/abstractNum/level overrides. Select short bold numbered headings conservatively; compare decimal depth 2/3 against reviewed size rules. Do not map Heading 3 directly to subsection depth. |
| Chapter bold unverified | No typed rule or inherited toggle resolver | Check chapter-banner/title runs, including split titles and inherited bold/caps properties. Capitalized chapter-number labels are excluded from title-case tests. |
| Contents bullets/ranges/alignment missed | Table paragraphs excluded from body checking | Dedicated native, unmerged contents-table checks for decimal entries, single references and right paragraph alignment. Shared page references, merged cells, generated contents fields and missing completeness evidence remain unchecked. |
| Missing table list/titles missed | Figures/tables lacked region-aware associations | Locate main-story objects after explicit chapter banners, excluding cover/auxiliary objects. Check separate list headings after Contents and adjacent native chapter-numbered captions/titles. Counter sequence, list contents and physical caption gaps remain unchecked. |
| Misspelled chapter stayed ambiguous | Exact title matching lacked corroboration | A one-character banner variant can establish presence only with an exact lower-level title inside the same chapter span. Retain a separate spelling-review item. Synonyms, uncorroborated typos and evidence from another chapter do not pass. |
| Near-spacing disagreement | Engine and analyst used different unspecified tolerances | Keep the strict 1/240-line match. Values outside it but within 0.01 lines request tolerance review; larger differences fail. Default-single body paragraphs still fail a required 1.5 multiplier. |
| Repeated findings look like hundreds of unrelated errors | Every section/run rendered a separate card | Group by rule, status, code, expected value and message. Expand every location with its own actual value/path; original counts, individual view and export remain intact. |

## Remaining differences

- Chapterwise abstract coverage requires semantic evaluation with evidence and uncertainty; word count/keywords do not prove it.
- Four diagrams have no native numbered captions. Independent image inspection confirmed actual absence, but the app reports NOT_CHECKED because a caption could be embedded in an image. OCR absence alone cannot prove it missing.
- Full contents-to-body coverage, generated counter evaluation, rendered page references, physical geometry and widow/orphan checks require further interpreters/rendering. Physical binding/paper inspection is outside DOCX validation.
- Body scope remains conservative. Tables, fields, ambiguous styles, front matter, appendix forms and sign-offs must not silently receive generic body rules.

## Compatibility and reproduction

Extractor 0.3.0 and compiler/checker 0.5.0 add typed reviewed requirements. Old published specifications retain their stored contents/hashes. Re-upload the format and explicitly review/publish the new proposals to enable the added checks. Written instructions are evidence for proposed requirements, not commands to execute. Observed sample styling is not automatically institutional authority. Unsupported source spans retain manual/deferred ledger decisions.

Run from the repository root:

```sh
python -m pytest -q
cd frontend
flutter analyze
flutter test
flutter build web --base-href /app/ --no-web-resources-cdn
```

`tests/test_structural_gaps.py` covers conditional overrides, inherited/broken/mixed headers, footer inheritance, PAGE switches and unsupported wrappers, plain content-control PAGE fields, numeral formats/restarts/suppression, decimal depth versus prose/outline levels, inherited caps, captions and duplicate/generated numbers, contents bullets/ranges/shared references, list ordering and optional/negated extraction. `tests/test_real_world_regressions.py` also protects spacing policy and corroborated/uncorroborated chapter spelling differences.

Verification completed locally: 201 Python tests passed (four optional tests skipped), Flutter analysis clean, 10 Flutter tests passed and production web build succeeded. Actual Flutter report upload/check, grouped location expansion, Not checked filter and JSON export were exercised at 390×844 and 1280×960. UI findings exactly matched the API items, with no browser errors. This does not claim physical Android/iOS execution or rendered DOCX geometry.

OOXML behavior references: [header inheritance](https://learn.microsoft.com/en-us/dotnet/api/documentformat.openxml.wordprocessing.headerreference?view=openxml-3.0.1), [footer inheritance](https://learn.microsoft.com/en-us/dotnet/api/documentformat.openxml.wordprocessing.footerreference?view=openxml-3.0.1), [page-number settings](https://learn.microsoft.com/en-us/dotnet/api/documentformat.openxml.wordprocessing.pagenumbertype?view=openxml-3.0.1).
