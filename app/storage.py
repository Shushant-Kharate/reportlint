"""File-based persistence for Stage 2. No database — deliberately simple,
per the agreed scope: prove the workflow before investing in real storage.
One JSON file per template under STORAGE_DIR/templates/{id}.json.
"""

import json
import os
import re
import tempfile
import logging
from pathlib import Path

from app.models.template_model import Template, TemplateSummary

STORAGE_DIR = Path(os.environ.get("REPORTLINT_STORAGE_DIR", "storage"))
TEMPLATES_DIR = STORAGE_DIR / "templates"


def _path(template_id: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", template_id):
        raise ValueError("Invalid template identifier")
    return TEMPLATES_DIR / f"{template_id}.json"


def _ensure_dirs():
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)


def save_template(template: Template) -> None:
    from app.cloud import enabled, BlobRecords
    if enabled():
        records = BlobRecords("v1")
        _, generation = records.get(template.id)
        records.save(template.id, template.model_dump(mode="json"), generation)
        return
    _ensure_dirs()
    path = _path(template.id)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=TEMPLATES_DIR, suffix=".tmp", delete=False) as output:
            temporary = Path(output.name)
            output.write(template.model_dump_json(indent=2))
        os.replace(temporary, path)
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)


def get_template(template_id: str) -> Template | None:
    from app.cloud import enabled, BlobRecords
    if enabled():
        value, _ = BlobRecords("v1").get(template_id)
        return Template.model_validate(value) if value else None
    try:
        path = _path(template_id)
    except ValueError:
        return None
    try:
        return Template.model_validate_json(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None


def list_templates() -> list[TemplateSummary]:
    from app.cloud import enabled, BlobRecords
    if enabled():
        templates = [Template.model_validate(v) for v in BlobRecords("v1").values()]
        return [TemplateSummary(id=t.id, name=t.name, source_filename=t.source_filename,
            status=t.status, created_at=t.created_at, rule_count=sum(len(getattr(t.ruleset, k))
            for k in ("typography_rules", "paragraph_rules", "page_rules", "structure_rules"))) for t in templates]
    _ensure_dirs()
    summaries = []
    for path in sorted(TEMPLATES_DIR.glob("*.json")):
        try:
            t = Template.model_validate_json(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            logging.getLogger(__name__).warning("Skipping unreadable template %s", path.name)
            continue
        rule_count = (
            len(t.ruleset.typography_rules)
            + len(t.ruleset.paragraph_rules)
            + len(t.ruleset.page_rules)
            + len(t.ruleset.structure_rules)
        )
        summaries.append(TemplateSummary(
            id=t.id, name=t.name, source_filename=t.source_filename,
            status=t.status, created_at=t.created_at, rule_count=rule_count,
        ))
    summaries.sort(key=lambda s: s.created_at, reverse=True)
    return summaries


def delete_template(template_id: str) -> bool:
    from app.cloud import enabled, BlobRecords
    if enabled():
        return BlobRecords("v1").delete(template_id)
    try:
        path = _path(template_id)
    except ValueError:
        return None
    if path.exists():
        path.unlink()
        return True
    return False
