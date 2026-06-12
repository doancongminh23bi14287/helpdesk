# backend/tests/test_file_storage.py
"""
Unit tests for file_storage.py security features.

Covers:
  - validate_magic_bytes: whitelist enforcement, family-mismatch rejection
  - compute_sha256: deterministic digest
  - save_attachment: size guard, declared-MIME prefix guard, magic-byte
    guard, checksum stored in returned dict
"""
import hashlib
import pytest
from unittest.mock import patch, MagicMock

# ── real PDF bytes (minimal valid PDF header) ─────────────────────────────────
MINIMAL_PDF = b"%PDF-1.4 1 0 obj<</Type /Catalog>>endobj"

# ── fake EXE disguised as PDF ─────────────────────────────────────────────────
FAKE_EXE_AS_PDF = b"MZ" + b"\x00" * 100  # Windows PE header magic bytes

# ── plain-text content ────────────────────────────────────────────────────────
PLAIN_TEXT = b"Hello, world! This is a plain text file."


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_png_bytes() -> bytes:
    """Minimal 1×1 PNG (89 bytes)."""
    import struct, zlib
    def _chunk(tag: bytes, data: bytes) -> bytes:
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = _chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
    idat = _chunk(b"IDAT", zlib.compress(b"\x00\xFF\xFF\xFF"))
    iend = _chunk(b"IEND", b"")
    return sig + ihdr + idat + iend


# ── validate_magic_bytes ──────────────────────────────────────────────────────

def test_valid_pdf_passes_magic_check():
    """A real PDF header is accepted when declared as application/pdf."""
    from app.services.file_storage import validate_magic_bytes

    detected = validate_magic_bytes(MINIMAL_PDF, "application/pdf")
    assert detected == "application/pdf"


def test_renamed_exe_as_pdf_rejected_by_magic():
    """EXE magic bytes declared as application/pdf must be rejected."""
    from app.services.file_storage import validate_magic_bytes

    with pytest.raises(ValueError, match="not permitted"):
        validate_magic_bytes(FAKE_EXE_AS_PDF, "application/pdf")


def test_valid_png_passes_magic_check():
    """A real PNG is accepted when declared as image/png."""
    from app.services.file_storage import validate_magic_bytes

    png_bytes = _make_png_bytes()
    detected = validate_magic_bytes(png_bytes, "image/png")
    assert detected == "image/png"


def test_family_mismatch_rejected():
    """PDF content declared as image/jpeg must be rejected (family mismatch)."""
    from app.services.file_storage import validate_magic_bytes

    with pytest.raises(ValueError, match="does not match declared type"):
        validate_magic_bytes(MINIMAL_PDF, "image/jpeg")


def test_disallowed_mime_rejected():
    """
    A file whose magic-detected MIME is not in MIME_MAGIC_WHITELIST is
    rejected even if the declared type looks fine.
    """
    from app.services.file_storage import validate_magic_bytes

    # EXE magic bytes — detected as application/x-dosexec or similar,
    # which is not in MIME_MAGIC_WHITELIST.
    with pytest.raises(ValueError, match="not permitted"):
        validate_magic_bytes(FAKE_EXE_AS_PDF, "application/octet-stream")


# ── compute_sha256 ────────────────────────────────────────────────────────────

def test_sha256_is_deterministic():
    """Same bytes always produce the same hex digest."""
    from app.services.file_storage import compute_sha256

    digest1 = compute_sha256(PLAIN_TEXT)
    digest2 = compute_sha256(PLAIN_TEXT)
    assert digest1 == digest2
    assert digest1 == hashlib.sha256(PLAIN_TEXT).hexdigest()


def test_sha256_length_is_64_chars():
    """SHA-256 hex digest is always 64 characters."""
    from app.services.file_storage import compute_sha256

    assert len(compute_sha256(b"")) == 64
    assert len(compute_sha256(MINIMAL_PDF)) == 64


# ── save_attachment ───────────────────────────────────────────────────────────

def _mock_storage(tmp_path, monkeypatch):
    """Point FILES_ROOT at a tmp dir so no real disk writes hit /uploads."""
    import app.config as cfg
    monkeypatch.setattr(cfg, "FILES_ROOT", str(tmp_path))


def test_sha256_stored_on_upload(tmp_path, monkeypatch):
    """save_attachment returns the correct sha256 for a valid file."""
    _mock_storage(tmp_path, monkeypatch)
    from app.services.file_storage import save_attachment

    result = save_attachment(MINIMAL_PDF, org_id=1,
                             original_filename="doc.pdf",
                             mime_type="application/pdf")

    expected = hashlib.sha256(MINIMAL_PDF).hexdigest()
    assert result["sha256"] == expected
    assert result["detected_mime"] == "application/pdf"
    assert result["file_size"] == len(MINIMAL_PDF)
    assert result["stored_path"]


def test_oversized_file_rejected(tmp_path, monkeypatch):
    """Files larger than 10 MB raise HTTPException 413."""
    from fastapi import HTTPException
    _mock_storage(tmp_path, monkeypatch)
    from app.services.file_storage import save_attachment, MAX_FILE_SIZE

    big = b"x" * (MAX_FILE_SIZE + 1)
    with pytest.raises(HTTPException) as exc_info:
        save_attachment(big, org_id=1,
                        original_filename="huge.pdf",
                        mime_type="application/pdf")
    assert exc_info.value.status_code == 413


def test_disallowed_declared_mime_rejected(tmp_path, monkeypatch):
    """A declared MIME not matching ALLOWED_MIME_PREFIXES raises HTTPException 415."""
    from fastapi import HTTPException
    _mock_storage(tmp_path, monkeypatch)
    from app.services.file_storage import save_attachment

    with pytest.raises(HTTPException) as exc_info:
        save_attachment(b"data", org_id=1,
                        original_filename="file.exe",
                        mime_type="application/x-msdownload")
    assert exc_info.value.status_code == 415


def test_magic_mismatch_raises_415(tmp_path, monkeypatch):
    """EXE bytes declared as application/pdf raise HTTPException 415 from save_attachment."""
    from fastapi import HTTPException
    _mock_storage(tmp_path, monkeypatch)
    from app.services.file_storage import save_attachment

    with pytest.raises(HTTPException) as exc_info:
        save_attachment(FAKE_EXE_AS_PDF, org_id=1,
                        original_filename="evil.pdf",
                        mime_type="application/pdf")
    assert exc_info.value.status_code == 415


def test_saved_file_is_on_disk(tmp_path, monkeypatch):
    """After a successful save, the file exists at the returned path."""
    import app.config as cfg
    monkeypatch.setattr(cfg, "FILES_ROOT", str(tmp_path))
    from app.services.file_storage import save_attachment, get_attachment_path

    result = save_attachment(MINIMAL_PDF, org_id=42,
                             original_filename="report.pdf",
                             mime_type="application/pdf")

    abs_path = get_attachment_path(result["stored_path"])
    assert abs_path.exists()
    assert abs_path.read_bytes() == MINIMAL_PDF
