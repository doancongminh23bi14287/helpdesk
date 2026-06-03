"""File storage service for ticket attachments."""
import hashlib
import os
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Tuple

from fastapi import UploadFile, HTTPException

from app import config

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

ALLOWED_MIME_PREFIXES = ("image/", "text/", "application/pdf", "application/zip",
                          "application/x-zip", "application/octet-stream")


def _org_hash(org_id: int) -> str:
    return hashlib.md5(str(org_id).encode()).hexdigest()[:16]


def _sanitize_filename(name: str) -> str:
    name = os.path.basename(name)
    name = re.sub(r"[^\w\.\-]", "_", name)
    name = name.lstrip(".")
    return name[:200] or "file"


def save_attachment(file_data: bytes, org_id: int, original_filename: str, mime_type: str) -> Tuple[str, int]:
    """
    Save file to disk. Returns (relative_path, file_size).
    relative_path is relative to FILES_ROOT.
    """
    if len(file_data) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large (max 10 MB)")

    if not any(mime_type.startswith(p) for p in ALLOWED_MIME_PREFIXES):
        raise HTTPException(status_code=415, detail=f"File type not allowed: {mime_type}")

    org_hash = _org_hash(org_id)
    now = datetime.utcnow()
    date_path = now.strftime("%Y/%m/%d")
    safe_name = _sanitize_filename(original_filename)
    unique_name = f"{uuid.uuid4().hex}_{safe_name}"

    rel_path = f"{org_hash}/{date_path}/{unique_name}"
    abs_dir = Path(config.FILES_ROOT) / org_hash / date_path
    abs_dir.mkdir(parents=True, exist_ok=True)

    abs_path = abs_dir / unique_name
    with open(abs_path, "wb") as f:
        f.write(file_data)

    return rel_path, len(file_data)


def get_attachment_path(file_path: str) -> Path:
    """Return absolute Path for a relative file_path."""
    return Path(config.FILES_ROOT) / file_path


def delete_attachment(file_path: str) -> bool:
    """Delete a file. Returns True if deleted, False if not found."""
    abs_path = get_attachment_path(file_path)
    try:
        abs_path.unlink()
        return True
    except FileNotFoundError:
        return False
