"""Bounded upload parsing. No document is retained after parsing."""
import tempfile
from pathlib import Path
from fastapi import HTTPException, UploadFile
from starlette.concurrency import run_in_threadpool
from app.ooxml.docx_loader import DocxPackage, InvalidDocxError
from app.ooxml.structure_extractor import build_document_model

MAX_UPLOAD_BYTES = 20 * 1024 * 1024


async def read_limited(upload: UploadFile, limit: int = MAX_UPLOAD_BYTES) -> bytes:
    chunks = []
    size = 0
    while chunk := await upload.read(64 * 1024):
        size += len(chunk)
        if size > limit:
            raise HTTPException(413, f"File too large. Maximum size is {limit // (1024 * 1024)} MB.")
        chunks.append(chunk)
    return b"".join(chunks)


def _parse(data: bytes, filename: str):
    with tempfile.TemporaryDirectory(prefix="reportlint_upload_") as directory:
        path = Path(directory) / "document.docx"
        path.write_bytes(data)
        try:
            return build_document_model(DocxPackage.load(str(path)), filename)
        except (InvalidDocxError, ValueError, TypeError, OverflowError) as exc:
            raise HTTPException(400, "The document is invalid or contains unsupported formatting.") from exc


async def parse_upload(upload: UploadFile):
    filename = (upload.filename or "").replace("\\", "/").rsplit("/", 1)[-1]
    if not filename.lower().endswith(".docx"):
        raise HTTPException(400, "Choose a Word .docx file.")
    data = await read_limited(upload)
    if not data:
        raise HTTPException(400, "The selected file is empty.")
    return await run_in_threadpool(_parse, data, filename)
