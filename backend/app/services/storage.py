"""Storage backend abstraction for attachment bytes."""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from fastapi import HTTPException

from app import config


class StorageBackend(ABC):
    @abstractmethod
    def write_bytes(self, relative_path: str, data: bytes) -> None:
        """Persist data under relative_path."""

    @abstractmethod
    def resolve_path(self, relative_path: str) -> Path:
        """Return a safe absolute path for a stored object."""

    @abstractmethod
    def delete(self, relative_path: str) -> bool:
        """Delete a stored object if it exists."""


class LocalStorageBackend(StorageBackend):
    def __init__(self, root: str | Path | None = None):
        self.root = Path(root or config.FILES_ROOT).resolve()

    def resolve_path(self, relative_path: str) -> Path:
        raw = Path(relative_path)
        if raw.is_absolute():
            raise HTTPException(status_code=400, detail="Invalid attachment path")
        target = (self.root / raw).resolve()
        try:
            target.relative_to(self.root)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid attachment path")
        return target

    def write_bytes(self, relative_path: str, data: bytes) -> None:
        target = self.resolve_path(relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

    def delete(self, relative_path: str) -> bool:
        target = self.resolve_path(relative_path)
        try:
            target.unlink()
            return True
        except FileNotFoundError:
            return False


def get_storage_backend() -> StorageBackend:
    """Return the configured storage backend (only 'local' is supported)."""
    if config.STORAGE_BACKEND != "local":
        raise RuntimeError(f"Unsupported STORAGE_BACKEND: {config.STORAGE_BACKEND}")
    return LocalStorageBackend()
