# ReportLint — Android (Stage 3)

Minimal 3-screen Kotlin + Jetpack Compose app: **Templates** (upload/list),
**Review** (edit extracted rules, publish), **Check** (upload a student
report against a published template, view scored results). Talks to the
Stage 1/2 FastAPI backend in `../` over HTTP via Retrofit.

## Important: this was written, not compiled

The sandbox this was built in has no Android SDK and no access to
`dl.google.com`/`maven.google.com` (only PyPI/npm/crates package registries
are reachable), so **I could not run a Gradle build or the Android Gradle
Plugin here.** Every file was written by hand against known-correct
Kotlin/Compose/Retrofit APIs and reviewed line-by-line for import and
signature correctness, but treat this as "should compile" rather than
"verified to compile." Open it in Android Studio and expect to fix a small
number of import/version mismatches — Android Studio's own tooling
(quick-fix imports, version catalogs, AGP upgrade assistant) will resolve
those far faster than I can without a real build.

## Prerequisites

- Android Studio (Koala/2024.1+ recommended)
- JDK 17 (bundled with recent Android Studio)
- The Stage 1/2 backend running — see `../README` / project root

## Running it

1. **Start the backend** from the repo root:
   ```bash
   cd ..
   PYTHONPATH=. uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```
   `--host 0.0.0.0` matters if you're testing on a real device over Wi-Fi,
   not just the emulator.

2. **Open `android/` in Android Studio** (File → Open, pick this folder).
   Let it sync Gradle — first sync will download AGP 8.5.2 / Gradle 8.7 /
   Kotlin 1.9.24 and all the Compose/Retrofit dependencies from Google's
   and Maven Central's repos, so needs real internet access (unlike the
   sandbox this was built in).

3. **Run on an emulator**: the app defaults to `http://10.0.2.2:8000/`,
   which is the emulator's alias for your host machine's `localhost`. If
   your backend is running on the same machine as Android Studio, this
   should work with zero configuration.

4. **Run on a real device**: device and computer need to be on the same
   Wi-Fi network. Find your computer's LAN IP (`ipconfig` / `ifconfig` /
   System Settings → Network) and set it in the app: tap the gear icon on
   the Templates screen, enter e.g. `http://192.168.1.23:8000/`.

## What's actually implemented

- `TemplatesScreen` — list templates (status badge, rule count), upload a
  new `.docx` via the system file picker (Storage Access Framework), open
  a template for review, delete a template.
- `ReviewScreen` — the mandatory teacher-review step: every extracted
  formatting rule can be included/excluded and re-severitized; every
  extracted required section can be deselected (this is where a teacher
  fixes the known over-firing issue — title-page lines like "By" or
  "Guided by" getting picked up as required sections) or a new one added
  by name. Save as Draft or Publish.
- `CheckScreen` — pick a published template, pick a report `.docx`, see
  the score, per-category breakdown, and the full grouped violation list
  with severity badges and text previews.

## What's deliberately NOT implemented (matches the agreed Stage 3 scope)

- No auth, no user accounts, no roles — same as the backend
- No offline/local database — everything is fetched live from the server;
  closing the app loses no data (it all still lives server-side) but there's
  also no offline viewing
- `expected_value` / `tolerance` on formatting rules are shown read-only
  (`Map<String, Any?>.toString()`), not deep-editable in the UI — a teacher
  can toggle a rule on/off and change its severity, but changing e.g. the
  exact expected font size requires the Stage 2 web UI for now. Extending
  `ReviewScreen` with per-rule-type input fields (a number field for
  `FONT_SIZE`, a text field for `FONT_FAMILY`, etc.) is the natural next
  increment here.
- No push notifications, no background sync, no submission history/versioning

## Architecture notes

- **No Hilt** — manual DI via `ReportLintApp` (Application subclass) holding
  a `ServerConfig` and `ReportLintRepository` singleton. Justified by scope:
  3 screens, no multi-module structure.
- **No Room** — nothing is cached locally; every screen re-fetches from the
  API. Fine for a lab-scale tool used by one teacher/class at a time.
- **Gson over kotlinx.serialization** — chosen so `Map<String, Any?>` fields
  (the free-form `expected_value`/`tolerance`/`actual` JSON on the backend,
  which varies by `RuleType`) deserialize without needing a sealed-class
  hierarchy per rule type. Trade-off: `Any?` values aren't type-safe on the
  Kotlin side, which is why `ReviewScreen` treats them as read-only.
