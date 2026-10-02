# ReportLint

ReportLint compares a Word report with formatting rules from a teacher's Word template. The project contains a Python/FastAPI checking engine, a responsive mobile web app, and a native Android client. The Android client calls the Python server; it does not perform document analysis on the phone.

## What you need

- Git and Python **3.10 or newer**. Check with `git --version` and `python --version` (or `python3 --version`).
- Internet access for the first installation of Python packages.
- A browser for the web app. For the native app, use an Android 8.0+ device or emulator and keep the Python server running.

The GitHub repository is public, so you can clone it without signing in to GitHub.

The demo DOCX files are already in `demo/`. LibreOffice is **not required** for the normal upload and check workflow. It is needed only for the optional pagination tests; pagination is not part of the app's check screen.

## Clone and run on Windows PowerShell

Open PowerShell in a directory where you want the project, then run:

```powershell
git clone https://github.com/Shushant-Kharate/reportlint.git
cd reportlint
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open **http://127.0.0.1:8000/app/** in your browser. Keep that terminal running while using the app; press **Ctrl+C** to stop it. These commands call the virtual environment's Python directly, so PowerShell script activation is unnecessary. If your computer uses the Windows Python launcher, replace the first `python` with `py -3`.

On later starts, you only need:

```powershell
cd reportlint
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## Clone and run on macOS or Linux

```bash
git clone https://github.com/Shushant-Kharate/reportlint.git
cd reportlint
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open **http://127.0.0.1:8000/app/**. On later starts, run the final command again from the `reportlint` directory. If the `venv` module is missing on a Linux distribution, install its matching Python `venv` package using that distribution's package manager, then rerun `python3 -m venv .venv`.

`requirements.txt` lists the API packages, demo generator, tests and optional pagination Python library, and installs this project in editable mode. The runtime bounds are also declared in `pyproject.toml` for package installation. `pip install -r requirements.txt` is the single installation command for a fresh clone.

## Try the three demo documents

| File | Purpose |
| --- | --- |
| `demo/format_template.docx` | Upload this first as the teacher's format. It calls for Times New Roman 12 pt, 1.5 line spacing, 72 pt margins, and four sections. |
| `demo/correct_report.docx` | Uses the required formatting and all four sections. |
| `demo/formatting_errors_report.docx` | Deliberately uses Arial 14 pt, single spacing, 50 pt margins, and omits Methods. |

1. In the web app, open **Templates** and select **Add template**. Choose `demo/format_template.docx`, then **Upload & review**.
2. Review the extracted rules. The demo template should show body font, size, spacing, page layout, and the Introduction, Methods, Results and Conclusion sections. Select **Publish template**.
3. Open **Check**, choose the published template, select `demo/correct_report.docx`, then **Check report**. Expect **100%**, zero errors, and no violations.
4. Select `demo/formatting_errors_report.docx` and check again. Expect a lower score (currently **33.8%**) and issues for font, size, line spacing, margins and the missing Methods section.

The sample documents contain fictional text and can be regenerated with:

```powershell
.venv\Scripts\python.exe scripts/create_demo_files.py
```

Use `.venv/bin/python scripts/create_demo_files.py` on macOS/Linux. Regeneration overwrites only the three files in `demo/`.

## Run tests

Windows:

```powershell
.venv\Scripts\python.exe -m pytest tests -q
```

macOS/Linux:

```bash
.venv/bin/python -m pytest tests -q
```

The tests include the full demo upload and comparison through the API. Four pagination tests skip when LibreOffice's `soffice` command is unavailable. Check `http://127.0.0.1:8000/debug/health` if the app does not connect. If port 8000 is busy, change `--port 8000` to another port and use that same port in the browser or Android server settings.

## Use it from a phone

For the **mobile web app**, run the server on your computer with `--host 0.0.0.0 --port 8000`. Put the phone and computer on the same trusted Wi-Fi network and open `http://YOUR-COMPUTER-LAN-IP:8000/app/` on the phone. Allow inbound port 8000 in the computer's firewall if prompted. The phone's `localhost` refers to the phone, so use the computer's LAN address. The web app can be added to the home screen when served over HTTPS, or on localhost on the same device; plain LAN HTTP may not offer installation in every browser. The app shell may open offline, but checking files requires the server.

For the **native Android app**, see [android/README.md](android/README.md). A successful GitHub Actions run publishes a debug APK artifact named `ReportLint-debug-apk`. In **Templates → Server settings**, use `http://10.0.2.2:8000/` for an emulator on the same computer or `http://YOUR-COMPUTER-LAN-IP:8000/` for a real phone. The backend must still be running. The APK is a test build, not a signed Play Store release.

## Where data goes

- The server stores reviewed template rules in `storage/templates/` under the directory where you start it. Set `REPORTLINT_STORAGE_DIR` if you want a different storage location.
- Uploaded documents are limited to 20 MB and removed after parsing. Reports and check results are not saved.
- This project is designed for a trusted, single-user environment. It has no login or user separation. Add authentication and HTTPS before exposing it as a public service.
- A saved edit to a published template returns it to Draft; publish again to make the new rules available. The web app's **Publish template** button saves edited values first.

## What is checked

The engine checks known font properties, paragraph spacing and alignment, page size and margins, required sections and their order. It reports a category as **Not checked** when there was no applicable rule or resolvable data, and only checked categories contribute to the overall score. It checks formatting rather than the quality or originality of the writing.

Some Word documents still need manual rule review: theme fonts, complex style toggle inheritance, table-cell formatting, contents inside tables, captions, headers/footers, and page number estimation are not fully checked. Use real Word heading styles and confirm the proposed rules before publishing. More details are in [docs/REVIEW.md](docs/REVIEW.md) and [docs/VERIFICATION.md](docs/VERIFICATION.md).

## Complex template development plan

The next development phase is specified in the [technical implementation plan](docs/COMPLEX_TEMPLATE_IMPLEMENTATION_PLAN.md), with a linked [execution checklist and handoff log](docs/COMPLEX_TEMPLATE_BACKLOG.md). It covers interpreting written guidelines, resolving conflicting template evidence, validating complex report structures, pagination, coverage, mobile clients, and release tests. These documents describe planned work; they do not expand the current engine's supported checks.

The first implementation slice is available as an [experimental template analysis preview](docs/TEMPLATE_ANALYSIS_PREVIEW.md). It extracts written property proposals and table-based chapter lists, and shows conflicts with observed formatting. Use `POST /api/v2/template-analysis` from the API docs or the documented inspection CLI. Its candidates are not yet used by the existing report checker.
