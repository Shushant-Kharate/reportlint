# ReportLint for Android

A Kotlin / Jetpack Compose app with **Check**, **Templates**, and a rule-review screen. Uses the FastAPI backend in the parent directory.

## Install a test APK

Download `ReportLint-debug-apk` from a successful GitHub Actions run, extract `app-debug.apk`, and install it on Android 8.0 or newer. This is a debug-signed test build, not a Play Store release.

Start the backend first. In **Templates → Server settings**, use:

- Android emulator: `http://10.0.2.2:8000/`
- Real phone on the computer's Wi-Fi: `http://YOUR-COMPUTER-IP:8000/`
- Hosted backend: its HTTPS address

If the phone cannot connect, check the server binding, address, and local firewall permissions. A phone's localhost points to the phone, not the computer.

## Build

Requires JDK 17 and Android SDK platform/build tools 34. Open this folder in Android Studio, or set `ANDROID_HOME` and run:

```powershell
.\gradlew.bat assembleDebug lintDebug
```

macOS/Linux: `./gradlew assembleDebug lintDebug`. The official Gradle wrapper is included. The APK is written to `app/build/outputs/apk/debug/app-debug.apk`.

## Behavior

Upload a template, review/edit its formatting values and required sections, then save as draft or publish. The check screen lists published templates. Uploads are bounded to 20 MB and temporary cache files are removed after each request. Server URLs are validated before saving, network errors are displayed, and deletion asks for confirmation.

The engine runs on the server. There is no offline analysis, account system, or submission history. HTTP is enabled for local development. Add authenticated HTTPS hosting and release signing before distributing beyond a trusted test group. Successful compilation/lint does not replace testing on a real phone.
