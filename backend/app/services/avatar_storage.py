"""Avatar storage helper.

Avatars are stored under FILES_ROOT/avatars/{user_id}/{uuid}.{ext}. The user
table holds only metadata (path, mime, size, updated_at). Old files are
cleaned up on replace/delete; deletion failures are swallowed so a stale file
never blocks a profile update.
"""
from __future__ import annotations

import logging
import uuid
from typing import Optional

import magic

from app.services.storage import get_storage_backend

logger = logging.getLogger(__name__)

# Avatar-specific limits — stricter than the generic attachment limits.
AVATAR_MAX_BYTES = 2 * 1024 * 1024  # 2 MB

ALLOWED_AVATAR_MIMES = {
    "image/jpeg",
    "image/png",
    "image/webp",
}

_MIME_TO_EXT = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}

AVATAR_ROOT_PREFIX = "avatars"


class AvatarValidationError(Exception):
    """Raised when an uploaded avatar fails validation.

    `status_code` mirrors the HTTP response status the caller should return.
    """

    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def _detect_mime(file_data: bytes) -> str:
    return magic.from_buffer(file_data[:2048], mime=True)


def _build_relative_path(user_id: int, mime_type: str) -> str:
    ext = _MIME_TO_EXT[mime_type]
    return f"{AVATAR_ROOT_PREFIX}/{user_id}/{uuid.uuid4().hex}.{ext}"


def validate_and_save_avatar(
    file_data: bytes,
    declared_mime: Optional[str],
    user_id: int,
) -> dict:
    """Validate the uploaded bytes and persist them to the avatar root.

    Returns a dict with keys ``stored_path``, ``mime_type``, ``file_size``.
    Raises ``AvatarValidationError`` on any validation problem; the caller
    should translate this to an HTTP error.
    """
    if not file_data:
        raise AvatarValidationError(422, "Empty avatar upload")

    if len(file_data) > AVATAR_MAX_BYTES:
        raise AvatarValidationError(413, "Avatar must be 2 MB or smaller")

    declared = (declared_mime or "").lower().split(";")[0].strip()
    if declared not in ALLOWED_AVATAR_MIMES:
        raise AvatarValidationError(
            415,
            "Unsupported avatar type. Use JPG, PNG, or WebP.",
        )

    detected = _detect_mime(file_data)
    if detected not in ALLOWED_AVATAR_MIMES:
        raise AvatarValidationError(
            415,
            f"Avatar content type '{detected}' is not permitted.",
        )

    # Magic must agree with the declared header — guards against renaming
    # a script or SVG as image/png.
    if detected != declared:
        raise AvatarValidationError(
            415,
            "Avatar content does not match the declared image type.",
        )

    rel_path = _build_relative_path(user_id, detected)
    get_storage_backend().write_bytes(rel_path, file_data)

    return {
        "stored_path": rel_path,
        "mime_type": detected,
        "file_size": len(file_data),
    }


def safe_delete_avatar(stored_path: Optional[str]) -> bool:
    """Delete an avatar file only if it lives under the avatar root.

    Returns True if a file was removed, False otherwise. Never raises — a
    missing file or a permission error must not break a profile update.
    """
    if not stored_path:
        return False
    if not stored_path.startswith(f"{AVATAR_ROOT_PREFIX}/"):
        logger.warning("Refusing to delete non-avatar path: %s", stored_path)
        return False
    try:
        return get_storage_backend().delete(stored_path)
    except Exception:
        logger.exception("Failed to delete avatar file: %s", stored_path)
        return False
