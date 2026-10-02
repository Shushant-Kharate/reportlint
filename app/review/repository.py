"""SQLite revision store. V1 JSON templates are left untouched."""
from contextlib import contextmanager
from pathlib import Path
import sqlite3
from uuid import uuid4

from app.review.models import AuditEvent, ReviewRevision
from app.review.service import ReviewError, canonical_json, now, snapshot_hash


DDL = """
CREATE TABLE IF NOT EXISTS templates (
 id TEXT PRIMARY KEY, name TEXT NOT NULL, published_revision_id TEXT,
 created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS revisions (
 id TEXT PRIMARY KEY, template_id TEXT NOT NULL REFERENCES templates(id),
 number INTEGER NOT NULL, status TEXT NOT NULL CHECK(status IN ('DRAFT','PUBLISHED')),
 version INTEGER NOT NULL, document_json TEXT NOT NULL,
 UNIQUE(template_id, number)
);
CREATE INDEX IF NOT EXISTS revision_template ON revisions(template_id, number);
CREATE TRIGGER IF NOT EXISTS immutable_publication
BEFORE UPDATE ON revisions WHEN OLD.status = 'PUBLISHED'
BEGIN SELECT RAISE(ABORT, 'Published revisions are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_publication_delete
BEFORE DELETE ON revisions WHEN OLD.status = 'PUBLISHED'
BEGIN SELECT RAISE(ABORT, 'Published revisions are immutable'); END;
"""


class RevisionRepository:
    def __init__(self, path: Path):
        self.path = Path(path)

    @contextmanager
    def connection(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 1):
                raise ReviewError("UNSUPPORTED_DATABASE_VERSION", "This application cannot open this review database version.", status=503)
            connection.executescript(DDL)
            if version == 0:
                connection.execute("PRAGMA user_version = 1")
            yield connection
        finally:
            connection.close()  # Uncommitted failed operations are rolled back.

    @staticmethod
    def load(connection, template_id, revision_id):
        row = connection.execute("SELECT document_json FROM revisions WHERE template_id=? AND id=?", (template_id, revision_id)).fetchone()
        if row is None:
            raise ReviewError("REVISION_NOT_FOUND", "Template revision not found.", status=404)
        revision = ReviewRevision.model_validate_json(row["document_json"])
        if revision.status == "PUBLISHED" and revision.snapshot_sha256 != snapshot_hash(revision):
            raise ReviewError("SNAPSHOT_INTEGRITY_ERROR", "The published snapshot failed its integrity check.", status=500)
        return revision

    @staticmethod
    def insert(connection, revision):
        connection.execute("INSERT INTO revisions VALUES (?,?,?,?,?,?)", (
            revision.revision_id, revision.template_id, revision.revision_number,
            revision.status, revision.version, canonical_json(revision.model_dump()),
        ))

    def create(self, name, analysis):
        template_id, revision_id = uuid4().hex, uuid4().hex
        revision = ReviewRevision(
            template_id=template_id, revision_id=revision_id, revision_number=1,
            name=name, analysis=analysis,
            audit=[AuditEvent(version=0, timestamp=now(), action="CREATE")],
        )
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("INSERT INTO templates VALUES (?,?,NULL,?)", (template_id, name, now()))
            self.insert(connection, revision)
            connection.commit()
        return revision

    def get(self, template_id, revision_id):
        with self.connection() as connection:
            return self.load(connection, template_id, revision_id)

    def list_templates(self):
        with self.connection() as connection:
            return [dict(row) for row in connection.execute(
                "SELECT t.*, (SELECT MAX(number) FROM revisions r WHERE r.template_id=t.id) AS latest_revision_number FROM templates t ORDER BY created_at DESC, id"
            )]

    def list_revisions(self, template_id):
        with self.connection() as connection:
            if connection.execute("SELECT id FROM templates WHERE id=?", (template_id,)).fetchone() is None:
                raise ReviewError("TEMPLATE_NOT_FOUND", "Template not found.", status=404)
            return [dict(row) for row in connection.execute(
                "SELECT id, number, status, version FROM revisions WHERE template_id=? ORDER BY number DESC", (template_id,)
            )]

    def change(self, template_id, revision_id, operation, argument):
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            revision = self.load(connection, template_id, revision_id)
            updated = operation(revision, argument)
            connection.execute("UPDATE revisions SET status=?, version=?, document_json=? WHERE id=?", (
                updated.status, updated.version, canonical_json(updated.model_dump()), revision_id,
            ))
            if updated.status == "PUBLISHED":
                connection.execute("UPDATE templates SET published_revision_id=? WHERE id=?", (revision_id, template_id))
            connection.commit()
            return updated

    def fork(self, template_id, revision_id):
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            original = self.load(connection, template_id, revision_id)
            if original.status != "PUBLISHED":
                raise ReviewError("PUBLISHED_SOURCE_REQUIRED", "Create a new draft from a published revision.", status=409)
            number = connection.execute("SELECT MAX(number) FROM revisions WHERE template_id=?", (template_id,)).fetchone()[0] + 1
            revision = ReviewRevision.model_validate(original.model_dump())
            revision.parent_revision_id = original.revision_id
            revision.revision_id = uuid4().hex
            revision.revision_number = number
            revision.version = 0
            revision.status = "DRAFT"
            revision.publication = None
            revision.snapshot_sha256 = None
            revision.audit = [AuditEvent(version=0, timestamp=now(), action="FORK")]
            self.insert(connection, revision)
            connection.commit()
            return revision
