# Deploy ReportLint to Vercel

The deployed app uses the same Flutter frontend and Python/FastAPI engine as the local app. Vercel promotes the compiled Flutter `StaticFiles` mount to its CDN at `/app/`. Python runs as a Vercel Function; its local disk is not used for saved formats. `[tool.vercel.fastapi.static] cdn = true` explicitly allows public assets to bypass the workspace middleware; API requests still pass through it.

## Prepare the account and project

1. Sign in with `vercel login`. Use an account with permission to create projects in your chosen team.
2. From this repository, run `vercel link --yes --scope YOUR_TEAM --project reportlint` (create the project if prompted).
3. Create and connect a **private** Vercel Blob store: `vercel blob create-store reportlint-formats --access private --yes`.
4. Verify the store connection supplies `BLOB_READ_WRITE_TOKEN` or `BLOB_STORE_ID` for Production and Preview. The SDK supports both the connected store token and short-lived OIDC credentials. Do not copy tokens into the code or Flutter settings.
5. Select the FastAPI framework and the repository root. The checked-in `vercel.json` and `pyproject.toml` configure the entrypoint and build. Python 3.12 is pinned in `.python-version`.

## Build and release

`scripts/vercel-build.sh` downloads Flutter 3.47.6 using the official release index, verifies the archive checksum, and builds Flutter with a `/app/` base path and a 4 MB hosted request limit. FastAPI's `/app/` mount is collected after that build. The SDK and generated web files are not committed.

Run the backend tests, `flutter analyze`, `flutter test`, and a release web build first. Deploy a staged production build using `vercel deploy --prod --skip-domain`, test the actual deployed app, then release it with `vercel promote DEPLOYMENT_URL`. A successful local test is not a successful deployment.

After release, open `/app/`, confirm `/debug/health`, check a DOCX against the built-in format, and verify that a custom draft survives another request and another function instance. Inspect runtime logs for failed requests. No log drain is configured by this repository.

## Built-in Mini Project 1A format

The supplied format is bundled with its reviewed specification. It appears in Available formats and the Check report selector immediately. Its source can be downloaded at `/api/builtin-formats/mini-project-1a/source`.

The shared built-in entry is read-only. Create a draft copy to customize its reviewed decisions and publish your own revision. Unsupported and manual requirements remain visible; the format is not claimed to be completely machine-checkable. No submitted report is bundled. Provenance is documented in `app/builtins/README.md`.

## Storage and privacy

Cloud mode is selected automatically on Vercel. `REPORTLINT_CLOUD=1` can enable the same behavior elsewhere for integration testing. Local installations retain their existing SQLite/JSON storage.

Each browser receives a random HttpOnly, SameSite workspace cookie. In HTTPS deployments the cookie is Secure. All custom templates, source excerpts and review decisions use that workspace's private Blob prefix. Other workspaces cannot list or change them through the app. Native Flutter clients retain the workspace cookie per server origin. This is anonymous workspace isolation, not account login, identity verification, or cross-device synchronization. Clearing browser data loses access to that workspace. Export important reviewed specifications before clearing it.

Cloud records are append-only generations. Each save creates a new immutable object with overwrite disabled, so competing edits to the same next generation return a conflict. Reads use fresh object names rather than an overwritten cached object. The current small-workspace limits are 20 complex formats and 200 saved generations per format. Saved history remains private in Blob. Uploaded report files, results and paragraph-role reviews are processed transiently and are not saved by this storage layer. User JSON exports may contain report excerpts.

## Hosted size limits

Vercel Functions have a request/response body limit. Hosted requests are capped at 4 MB including the file, multipart overhead and paragraph-review data; the Flutter production build checks the combined size before upload. Local builds retain their 20 MB document limit. Reduce embedded-image sizes if a DOCX exceeds the hosted limit. Large result bodies may also exceed Vercel's response limit; direct-to-storage upload/download support is not implemented.

The optional LibreOffice rendering path is not installed in the Function. Native OOXML checks remain available; rendering-dependent tests and requirements are not represented as verified geometry.

## Release verification (26 October 2026)

- Python: 212 passed; four optional rendering tests skipped.
- Flutter: 19 passed; static analysis clean; release web build succeeded.
- Chromium desktop/mobile browser flows: basic demo scored 100 and 33.8 for the correct and incorrect fixtures; complex upload, paragraph-role correction, checking and exact JSON export passed with no page exceptions.
- Live private Blob operations: create, read, update, competing-save rejection and cleanup passed. The SDK's specific HTTP 400 already-existing-object response is treated as a revision conflict.
- Hosted API: built-in report check returned 1,505 passes, 324 failures, 180 unresolved and 37 inapplicable items (1,007,282 response bytes), matching the local result. These are repeated check-item counts, not a compliance percentage.
- Hosted custom format: copy, publish and reload passed; a separate anonymous workspace received 404 for that private format.
- The first deployment exposed missing generated static assets. Explicit FastAPI CDN promotion and retention of the compiled mount fixed `/app/` and its JavaScript assets, both verified over authenticated HTTP.
