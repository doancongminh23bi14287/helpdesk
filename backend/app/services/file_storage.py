"""File storage service for ticket attachments."""
import hashlib
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

import magic
from fastapi import HTTPException

from app.services.storage import get_storage_backend
from app.core.constants import MAX_FILE_SIZE_BYTES, MAGIC_BYTE_READ_SIZE

MAX_FILE_SIZE = MAX_FILE_SIZE_BYTES

ALLOWED_MIME_PREFIXES = (
    "image/",
    "text/",
    "application/pdf",
    "application/zip",
    "application/x-zip",
    "application/octet-stream",
    # Excel
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml",
    # Word
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml",
    # PowerPoint
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument.presentationml",
)

MIME_MAGIC_WHITELIST = {
    "image/jpeg", "image/png", "image/gif", "image/webp",
    "application/pdf",
    "text/plain",
    "application/zip",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}


def _org_hash(org_id: int) -> str:
    return hashlib.md5(str(org_id).encode()).hexdigest()[:16]


def _sanitize_filename(name: str) -> str:
    name = os.path.basename(name)
    name = re.sub(r"[^\w\.\-]", "_", name)
    name = name.lstrip(".")
    return name[:200] or "file"


def validate_magic_bytes(file_data: bytes, declared_mime: str) -> str:
    """
    Returns the actual MIME type detected from file bytes.
    Raises ValueError if detected type is not in whitelist or
    does not match the declared type's top-level family.
    """
    detected_mime = magic.from_buffer(file_data[:MAGIC_BYTE_READ_SIZE], mime=True)

    if detected_mime not in MIME_MAGIC_WHITELIST:
        raise ValueError(
            f"File content type '{detected_mime}' is not permitted. "
            f"Declared type was '{declared_mime}'."
        )

    # Allow text/* variants to be flexible (UTF-8, ASCII, etc.)
    declared_family = declared_mime.split("/")[0]
    detected_family = detected_mime.split("/")[0]

    if declared_family != detected_family:
        raise ValueError(
            f"File content does not match declared type. "
            f"Declared: '{declared_mime}', Detected: '{detected_mime}'."
        )

    return detected_mime


def compute_sha256(file_data: bytes) -> str:
    """Return the hex SHA-256 checksum of the file contents."""
    return hashlib.sha256(file_data).hexdigest()


def save_attachment(
    file_data: bytes,
    org_id: int,
    original_filename: str,
    mime_type: str,
) -> dict:
    """
    Validate, store, and checksum a file.

    Returns a dict with keys:
      stored_path   — path relative to FILES_ROOT
      file_size     — bytes
      sha256        — hex digest
      detected_mime — MIME type confirmed by magic bytes
    """
    # 1. Size check
    if len(file_data) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large (max 10 MB)")

    # 2. Declared-MIME prefix allowlist (fast, cheap check)
    if not any(mime_type.startswith(p) for p in ALLOWED_MIME_PREFIXES):
        raise HTTPException(status_code=415, detail=f"File type not allowed: {mime_type}")

    # 3. Magic-byte validation
    try:
        actual_mime = validate_magic_bytes(file_data, mime_type)
    except ValueError as exc:
        raise HTTPException(status_code=415, detail=str(exc))

    # 4. Sanitize filename
    safe_name = _sanitize_filename(original_filename)

    # 5. Compute checksum
    checksum = compute_sha256(file_data)

    # 6. Build storage path
    org_hash = _org_hash(org_id)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    date_path = now.strftime("%Y/%m/%d")
    unique_name = f"{uuid.uuid4().hex}_{safe_name}"

    rel_path = f"{org_hash}/{date_path}/{unique_name}"
    # 7. Write file through storage backend. Existing local relative paths are preserved.
    get_storage_backend().write_bytes(rel_path, file_data)

    return {
        "stored_path": rel_path,
        "file_size": len(file_data),
        "sha256": checksum,
        "detected_mime": actual_mime,
    }


def get_attachment_path(file_path: str) -> Path:
    """Return absolute Path for a relative file_path."""
    return get_storage_backend().resolve_path(file_path)


def delete_attachment(file_path: str) -> bool:
    """Delete a file. Returns True if deleted, False if not found."""
    return get_storage_backend().delete(file_path)
