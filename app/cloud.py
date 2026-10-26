"""Anonymous browser workspaces and durable, private Vercel Blob records."""
from contextvars import ContextVar
import json
import logging
import os
import re
import secrets
from http.cookies import SimpleCookie
from urllib.parse import urlsplit

from starlette.responses import JSONResponse
from app.review.service import ReviewError, canonical_json

workspace = ContextVar("reportlint_workspace", default=None)
COOKIE = "reportlint_workspace"
REQUEST_LIMIT = 4 * 1024 * 1024


def enabled():
    return os.environ.get("REPORTLINT_CLOUD") == "1" or os.environ.get("VERCEL") == "1"


class WorkspaceMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not enabled():
            return await self.app(scope, receive, send)
        headers = dict(scope.get("headers", []))
        origin = headers.get(b"origin", b"").decode()
        host = headers.get(b"host", b"").decode()
        if scope["method"] not in ("GET", "HEAD", "OPTIONS") and origin and urlsplit(origin).netloc != host:
            return await JSONResponse({"detail": "Use this site's own application to change formats."}, 403)(scope, receive, send)
        try:
            too_large = int(headers.get(b"content-length", b"0")) > REQUEST_LIMIT
        except ValueError:
            too_large = True
        if too_large:
            return await JSONResponse({"detail": "Hosted requests must be under 4 MB, including paragraph-review data."}, 413)(scope, receive, send)
        cookies = SimpleCookie()
        try:
            cookies.load(headers.get(b"cookie", b"").decode())
        except Exception:
            pass
        supplied = cookies.get(COOKIE)
        identifier = supplied.value if supplied and re.fullmatch(r"[a-f0-9]{64}", supplied.value) else secrets.token_hex(32)
        token = workspace.set(identifier)

        async def send_scoped(message):
            if message["type"] == "http.response.start":
                message["headers"] = list(message.get("headers", []))
                if not supplied or supplied.value != identifier:
                    cookie = SimpleCookie()
                    cookie[COOKIE] = identifier
                    cookie[COOKIE]["path"] = "/"
                    cookie[COOKIE]["httponly"] = True
                    cookie[COOKIE]["samesite"] = "Lax"
                    cookie[COOKIE]["max-age"] = 60 * 60 * 24 * 365
                    if scope.get("scheme") == "https" or os.environ.get("VERCEL") == "1":
                        cookie[COOKIE]["secure"] = True
                    message["headers"].append((b"set-cookie", cookie.output(header="").strip().encode()))
                if scope["path"].startswith(("/api/", "/debug/")):
                    message["headers"].append((b"cache-control", b"private, no-store"))
            await send(message)
        try:
            await self.app(scope, receive, send_scoped)
        finally:
            workspace.reset(token)


class BlobRecords:
    """Append-only generations avoid read caches and lost concurrent updates.

    Existing generations are never overwritten. Competing writes to the next
    generation must fail instead of silently replacing another saved edit.
    """
    def __init__(self, kind, owner=None, sdk=None):
        owner = owner or workspace.get()
        if not owner or not re.fullmatch(r"[a-f0-9]{64}", owner):
            raise ReviewError("WORKSPACE_REQUIRED", "Open the application to start a private workspace.", status=401)
        self.prefix = f"reportlint/{owner}/{kind}/"
        if sdk is None:
            from vercel.blob import sync as sdk
        self.sdk = sdk

    def path(self, identifier):
        if not re.fullmatch(r"[a-zA-Z0-9_-]{1,80}", identifier):
            raise ReviewError("INVALID_IDENTIFIER", "Invalid format identifier.", status=404)
        return self.prefix + identifier + "/"

    def latest(self, prefix):
        selected = {}
        try:
            for entry in self.sdk.query_blobs(prefix=prefix):
                tail = entry.pathname.removeprefix(self.prefix)
                match = re.fullmatch(r"([a-zA-Z0-9_-]{1,80})/([0-9]{10})\.json", tail)
                if match:
                    identifier, generation = match.group(1), int(match.group(2))
                    if identifier not in selected or generation > selected[identifier][0]:
                        selected[identifier] = (generation, entry.pathname)
            return selected
        except Exception as exc:
            self.unavailable(exc)

    @staticmethod
    def unavailable(exc):
        logging.getLogger(__name__).error("Private format storage failed (%s)", type(exc).__name__)
        raise ReviewError("STORAGE_UNAVAILABLE", "Saved formats are temporarily unavailable. Please try again later.", status=503) from exc

    def get(self, identifier):
        selected = self.latest(self.path(identifier))
        if identifier not in selected:
            return None, -1
        generation, path = selected[identifier]
        try:
            return json.loads(self.sdk.get_blob(path, access="private").body), generation
        except Exception as exc:
            self.unavailable(exc)

    def save(self, identifier, value, generation):
        if generation >= 200:
            raise ReviewError("FORMAT_HISTORY_LIMIT", "This format reached its saved-edit limit. Export it before starting another format.", status=409)
        path = self.path(identifier) + f"{generation + 1:010d}.json"
        try:
            self.sdk.put_blob(path, canonical_json(value).encode(), access="private", content_type="application/json", allow_overwrite=False, add_random_suffix=False)
        except Exception as exc:
            # SDK 0.5 maps the service's already-existing upload response to a
            # generic HTTP 400. Recognize that specific response, not every 400.
            already_exists = (getattr(exc, "status_code", None) == 400
                              and str(exc).startswith("Vercel Blob: This blob already exists,"))
            if already_exists or getattr(exc, "status_code", None) in (409, 412) or getattr(exc, "code", "") in ("blob_already_exists", "blob_exists", "precondition_failed"):
                raise ReviewError("REVISION_CONFLICT", "This format changed elsewhere. Reload the saved draft before retrying.", status=409) from exc
            self.unavailable(exc)

    def values(self):
        records = []
        for identifier in self.latest(self.prefix):
            value, _ = self.get(identifier)
            if value is not None:
                records.append(value)
        return records

    def delete(self, identifier):
        prefix = self.path(identifier)
        try:
            paths = [b.pathname for b in self.sdk.query_blobs(prefix=prefix)]
            if paths:
                self.sdk.delete_blob(paths)
            return bool(paths)
        except Exception as exc:
            self.unavailable(exc)
