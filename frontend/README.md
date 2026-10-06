# ReportLint Flutter frontend

Shared Material 3 UI for Android and web, with an iOS runner for macOS builds. Tested toolchain: Flutter 3.47.6 stable / Dart 3.13.5. See the root README for complete backend setup, server addresses, CORS and deployment instructions.

```bash
flutter pub get
flutter analyze
flutter test
flutter build web --base-href /app/ --no-web-resources-cdn
flutter build apk --debug
```

Serve `build/web/` through FastAPI `/app/`. For development use `flutter run -d chrome --web-port 5173 --dart-define=API_URL=http://127.0.0.1:8000` with that browser origin explicitly allowed by the backend. Android defaults to `http://10.0.2.2:8000`; override in Settings. Release Android builds require HTTPS; only the debug host allows development HTTP.

## Source layout

- `lib/api.dart`: validated server origin, bounded DOCX inputs, multipart uploads, typed API errors.
- `lib/app.dart`: format library, revision selection, server settings.
- `lib/review.dart`: proposal/evidence/conflict review, chapter profiles, source dispositions, immutable publication and forking.
- `lib/checking.dart`: report checks, hash-bound role correction, result filters and export.
- `lib/simple.dart`: original basic-checking workflow and the three bundled demo files.
- `lib/widgets.dart`: shared responsive Material widgets and file selection.

No WebView or embedded legacy HTML is used. Generated HTML/JavaScript under `build/web/` is Flutter compiler output. The Android Kotlin and iOS Swift entry points contain no product UI.

## Browser smoke test

With a built Flutter web client and an isolated running backend, install Playwright in a disposable tooling directory (`npm install playwright`, `npx playwright install chromium`) and run the repository's `scripts/verify_flutter_web.cjs`. Set NODE_PATH if Playwright is outside the repository. Tests create a fictional demo template and do not upload private reports. Screenshots and results belong outside the repository.

## Platform limits

Android APK creation and Flutter web compilation are configured in CI. A debug APK is not a store-ready signed release. iOS needs macOS/Xcode, HTTPS or an explicit local-network development configuration, provisioning and device testing. No offline document-analysis engine is bundled. Server-address preferences survive restarts; report bytes and role reviews remain session state.

Detailed migration coverage and browser reproduction commands: [Flutter verification](../docs/FLUTTER_MIGRATION.md).
