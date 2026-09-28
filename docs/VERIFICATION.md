# Verification record

Date: 28 September 2026

- Python: 49 passed, 4 skipped. The skips are optional LibreOffice rendering tests; LibreOffice is not installed on this computer.
- Reproducible demo: `demo/format_template.docx` infers the intended font, size, spacing, page layout and four required sections. Through both the API and mobile web UI, `correct_report.docx` scores 100% with zero errors; `formatting_errors_report.docx` scores 33.8% with 14 errors, including the missing Methods section.
- JavaScript syntax: passed (`node --check static/app.js`).
- Browser: complete upload → review → edit → publish → report check passed in headless Chrome with Playwright. Saved rule values were fetched from the real backend to verify persistence. Untrusted template names remained literal text. No JavaScript exceptions occurred.
- Responsive: checked 320, 390, 768 and 1280 CSS pixel widths; no horizontal overflow in the report-results state. Mobile check, template list and review screenshots were also inspected.
- Android: GitHub Actions runs `assembleDebug lintDebug`, and uploads a debug APK on success. Check the latest Actions run for the exact commit status. No emulator/physical-device execution was performed here.
- Packaging: nested Python packages and static resources are declared in `pyproject.toml`; CI installs the package before running tests.

## Visual comparison ledger

Reference: generated three-screen mobile concept, retained with the handoff outputs. The reference board is 1476×1066 with approximately 490px-wide panels; implementation uses a 390×844 CSS viewport. The board was visually compared at its original image dimensions, rather than claiming a pixel-perfect native-size match to each panel.

| Aspect | Reference and rendered evidence | Result |
| --- | --- | --- |
| Palette | White background, navy text, teal primary action | Implemented and inspected |
| Typography | Strong compact heading, muted supporting copy, readable control labels | Implemented with local system fonts; no remote font dependency |
| Check layout | Template selector, document picker, primary action and privacy note | Same order; real empty-state help is an intentional addition |
| Navigation | Two fixed bottom tabs | Implemented with safe-area spacing; no mobile overflow |
| Rule editing | Editable values, severity choices, grouped sections | Implemented; full-width fields repaired after inspection |
| Spacing and controls | Open whitespace, 48px touch controls, restrained rounded borders | Inspected on the final mobile screenshots |
| Copy | Check headline, intro, labels and primary CTA | Matches reference; supporting header text and real data/error messages are intentional additions |
| Review density | Reference compresses multiple rule controls into one panel | Deliberately expanded into accessible per-rule editors; scrollable, with no fixed screenshot-as-interface |

Initial in-app-browser inspection succeeded, but the file chooser timed out and viewport clicks were unreliable. Continued with agent-browser and Chrome/Playwright. The concept and latest implementation images were opened with the image viewer for direct comparison. The implementation follows the reference's mobile design language with the functional deviations above; no claim of exact pixel identity or native Android visual verification is made.
