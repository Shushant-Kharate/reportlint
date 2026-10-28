# ReportLint

ReportLint checks DOCX reports against reviewed formatting requirements and supports a limited native-PDF measurement path. **All application screens use Flutter**, shared by Android and web, with an iOS project for macOS builds. Python/FastAPI remains the checking backend. The previous HTML/JavaScript UI and Kotlin Compose client have been retired.

**Live app:** [Open ReportLint](https://reportlint-shushantkharate-3779s-projects.vercel.app/app/). The Mini Project 1A format is ready to select. Hosted uploads have a 4 MB combined request limit; local installations retain their 20 MB document limit.

The **IEEE Conference — US Letter** reviewed baseline is also available. [Real IEEE paper test and supported PDF checks](docs/IEEE_VALIDATION.md) explains the original SVO paper case, source downloads and unresolved requirements. Template uploads remain DOCX; report uploads can be DOCX or PDF. The PDF path does not certify full IEEE compliance.

## Requirements

For hosted deployment, see [Vercel deployment and storage setup](docs/VERCEL_DEPLOYMENT.md). The Mini Project 1A format is now included as a read-only built-in, with a reviewed specification and customizable draft copies.

- Git and Python 3.10 or newer.
- **Flutter 3.47.6 stable (Dart 3.13.5)**, the version pinned in CI. Install from https://docs.flutter.dev/install and add `flutter/bin` to PATH. Run `flutter --version` and `flutter doctor`.
- Internet access for first-time Python, Flutter and build dependencies.
- Android Studio/Android SDK plus Java 17 for Android builds. These are **not needed for the web build**.
- macOS and Xcode for iOS. iOS cannot be built on Windows.

Flutter dependencies are in `frontend/pubspec.yaml` with an application lockfile. Python dependencies are in `requirements.txt`. Flutter is an SDK and cannot be installed through pip/requirements.txt.

## Clone and run: Windows PowerShell

```powershell
git clone https://github.com/Shushant-Kharate/reportlint.git
cd reportlint
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
cd frontend
flutter pub get
flutter build web --base-href /app/ --no-web-resources-cdn
cd ..
.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open **http://127.0.0.1:8000/app/**. Keep the server running. Stop it with Ctrl+C. If Python is available through the Windows launcher, use `py -3 -m venv .venv` for the environment step.

On subsequent starts, run only the final server command. Rebuild Flutter after frontend edits and restart the backend after the first build. The generated web build is not committed; a fresh clone must build it or download the `ReportLint-Flutter-web` CI artifact into `frontend/build/web/`.

## Clone and run: macOS/Linux

```bash
git clone https://github.com/Shushant-Kharate/reportlint.git
cd reportlint
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cd frontend
flutter pub get
flutter build web --base-href /app/ --no-web-resources-cdn
cd ..
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open the same `/app/` URL. Install your distribution's Python venv package if `python3 -m venv` is unavailable. The Python API works independently at `/docs`; `/app/` returns an explicit setup message when the Flutter build is missing. `REPORTLINT_WEB_DIR` can point at another built Flutter web directory. Older `/app/complex.html` links redirect to Flutter.

## Android

Start the Python backend, then in a second terminal:

```bash
cd frontend
flutter pub get
flutter devices
flutter run -d DEVICE_ID
# Or build an installable test APK:
flutter build apk --debug
```

The APK is `frontend/build/app/outputs/flutter-apk/app-debug.apk`. CI also publishes **ReportLint-Flutter-debug-apk**. This is a debug/test APK, not a signed store release.

Use the app's Server settings:
- Android emulator on this computer: `http://10.0.2.2:8000` (default).
- Physical phone: run the backend with `--host 0.0.0.0`, connect to the same Wi-Fi and enter `http://YOUR-COMPUTER-LAN-IP:8000`. Allow the backend port through your firewall if needed.
- Production: use an HTTPS server. Only debug Android builds allow development HTTP. Native clients do not require browser CORS configuration.

The Flutter Android package is `com.reportlint.reportlint_flutter`; it installs separately from the retired Kotlin app. Signing and store distribution are not configured. The checking engine always runs on the server.

## Flutter web development

To hot-reload the frontend on a separate origin, allow that exact origin before starting the backend:

```powershell
$env:REPORTLINT_CORS_ORIGINS='http://localhost:5173'
.venv/Scripts/python.exe -m uvicorn app.main:app --port 8000
# In another terminal:
cd frontend
flutter run -d chrome --web-port 5173 --dart-define=API_URL=http://127.0.0.1:8000
```

On macOS/Linux use `REPORTLINT_CORS_ORIGINS=http://localhost:5173 .venv/bin/python -m uvicorn app.main:app --port 8000`. Multiple allowed origins are comma-separated. CORS is disabled by default; serving the web build from FastAPI uses the same origin and needs no CORS settings. If using `127.0.0.1:5173`, allow that exact origin too. An HTTPS page cannot call an HTTP backend.

`API_URL` is an optional compile-time default. Web otherwise uses its current origin; Android uses the emulator address. A server explicitly saved in Settings takes precedence. No API credentials belong in a Flutter build.

## Main workflow: complex formats

1. **Formats → Add format document**: select the teacher's DOCX. The filename supplies its name; there is no approval form in this path.
2. The app prepares supported rules automatically. An identical known format reuses its published rules; a saved private version retains your previous clarifications. Clear written requirements take priority over conflicting sample appearance. Consistent named body styles and section settings can supply explicitly labelled example baselines.
3. Select **Check a report** immediately when supported rules are ready. Conflicting instructions appear as individual questions. Other unsupported requirements remain visible under **Other requirements not checked automatically**.
4. For a question, explain what the instruction means in ordinary English, for example `Body text must use Arial at 12 pt with 1.5 line spacing.` A short answer can use the selected instruction's role. Explain every requirement for that instruction because a complete explanation replaces its earlier interpretation. Unsupported explanations retain your text and show an error; they do not become invented rules.
5. Upload a report DOCX or PDF and inspect issues, matches and unchecked findings. The hosted request limit is 4 MB; local uploads allow 20 MB. PDF checks cover a narrower measured property set.
6. Optionally **Review paragraph roles** to confirm body/chapter/excluded roles. Changing the report or revision clears those report-specific decisions.
7. Export the result and specification as JSON. Explanations create immutable new versions; earlier results retain their original specification.

**Advanced rule review** retains the original approve/reject/defer workflow for users who need it. Its selected decisions require a reason, but ordinary automatic setup does not. See [automatic preparation and supported language](docs/AUTOMATIC_PREPARATION.md). The English interpreter is deterministic and local: it does not run a trained language model or OCR, and it cannot understand every arbitrary requirement.

Item counts are **not a compliance percentage**. The v2 engine supports stored page settings, conditional no-header top margins, scoped body formatting, chapter recognition and typography, decimal section sizes, abstract length/keywords, inherited footer PAGE settings, native contents entry formatting, separate illustration-list headings and native caption/title associations. Results group repeated findings while retaining every location. Full contents completeness, semantic abstract coverage, image-embedded captions and rendered geometry remain incomplete. See the [latest real-document comparison and limitations](docs/REAL_DOCUMENT_RETEST.md) and [previous improvements](docs/REAL_DOCUMENT_IMPROVEMENTS.md).

## Reading results

Results use plain-language **Required**, **Found**, and **How to fix it** explanations. Search by issue, value or location, and switch between **Needs fixing**, **Needs review**, **Passed**, and **Not applicable**. Repeated checks share a compact location summary; expand it to inspect every original location. Word sections and paragraph indexes are not rendered page numbers.

Word field instructions, XML paths, original checker messages and other raw values are available under **Technical details**. **Download results** preserves the original result and reviewed specification as JSON. Display wording does not change the checker verdict or uncertainty.

Automatic setup keeps applied rules, clarification questions and unsupported manual requirements distinct. Advanced review additionally exposes the original proposals and their recorded decisions. A source instruction can be marked covered only when its executable representation or explicit replacement can be verified.

## Three-file demonstration

The same fictional documents are in `demo/` and bundled with Flutter:

| File | Purpose |
| --- | --- |
| `format_template.docx` | Basic teacher format |
| `correct_report.docx` | Correct example |
| `formatting_errors_report.docx` | Deliberate font, spacing, margin and structure errors |

Open **Basic checker and demo files → Try demo template**. Review the rules, publish the basic template, then use **Check correct demo** and **Check error demo**. You can also upload your own basic template/report and edit inferred values. Basic checking uses the original v1 engine and its limited legacy score; that score is not full complex-template compliance. The correct demo currently yields 100 with no violations; the error demo yields 33.8 with violations.

Regenerate the root demo files with `python scripts/create_demo_files.py`, then copy those three DOCX files into `frontend/assets/demo/` before rebuilding Flutter.

## Tests and builds

```bash
# Repository root, using your activated Python environment:
python -m pytest -q
cd frontend
flutter analyze
flutter test
flutter build web --base-href /app/ --no-web-resources-cdn
flutter build apk --debug
```

Four optional Python pagination tests skip without LibreOffice. Flutter tests exercise HTTP errors, upload validation, multipart role-review binding, review/publication and mobile result rendering. CI tests Python and Flutter and publishes web/APK artifacts. The optional browser smoke test is documented in `frontend/README.md`.

The iOS project is included for the shared Flutter UI, but requires independent macOS/device validation, provisioning and signing. It is not claimed as a tested iOS release.

## Storage and troubleshooting

- `storage/templates/` holds v1 template rules; `storage/review.sqlite3` holds v2 extracted source excerpts, decisions and immutable revisions. Configure `REPORTLINT_STORAGE_DIR` before starting the server to use a different location.
- Uploaded reports are processed temporarily. Reports/results/paragraph reviews are not retained by the API. The client retains the current report in memory while its check screen is open; the server address alone is persisted locally. JSON exports can contain private report excerpts.
- `/debug/health` checks backend connectivity. API docs are at `/docs`. If a port is busy, change it in uvicorn and in Flutter Server settings.
- A missing Flutter web build produces HTTP 503 at `/app/`; build first and restart the backend.
- Flutter/Gradle may download platform artifacts on the first build. Run `flutter doctor` and install the SDK components it reports.
- Local mode remains a trusted, single-user MVP. Vercel mode isolates custom formats in anonymous browser workspaces backed by private Blob storage; it does not provide account login or cross-device synchronization. See the deployment guide for cookie retention, history and hosted upload limits.

## Project map

- `frontend/`: all application UI in Dart/Flutter; Android/iOS runner files are platform hosts only.
- `app/`: Python API, extraction, review and checking engine.
- `tests/`: backend tests; `frontend/test/`: Flutter tests.
- `demo/`: public fictional demonstration files.
- `docs/`: engine design, review contracts and remaining implementation work.

The [implementation plan](docs/COMPLEX_TEMPLATE_IMPLEMENTATION_PLAN.md) and [backlog](docs/COMPLEX_TEMPLATE_BACKLOG.md) include historical checkpoints. The Flutter migration replaces their old HTML/Kotlin frontend assumptions; it does not mark unfinished engine milestones complete.
