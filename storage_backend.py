"""Storage interface with a local-development adapter."""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
import os
import shutil
from typing import BinaryIO


class StorageBackend(ABC):
    @abstractmethod
    def put(self, key: str, source: BinaryIO) -> str: ...

    @abstractmethod
    def path(self, key: str) -> Path | None: ...

    @abstractmethod
    def delete_prefix(self, prefix: str) -> None: ...


class LocalStorage(StorageBackend):
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, key: str) -> Path:
        value = (self.root / key.lstrip("/")).resolve()
        if value != self.root and self.root not in value.parents:
            raise ValueError("Storage key không hợp lệ")
        return value

    def put(self, key: str, source: BinaryIO) -> str:
        destination = self._resolve(key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("wb") as output:
            shutil.copyfileobj(source, output, 1024 * 1024)
        return key

    def path(self, key: str) -> Path | None:
        return self._resolve(key)

    def delete_prefix(self, prefix: str) -> None:
        value = self._resolve(prefix)
        if value.is_dir():
            shutil.rmtree(value)
        elif value.exists():
            value.unlink()


def build_storage(default_root: Path) -> StorageBackend:
    backend = os.getenv("STORAGE_BACKEND", "local").strip().lower()
    if backend != "local":
        raise RuntimeError(
            "STORAGE_BACKEND chưa được hỗ trợ trong bản này; hãy cung cấp adapter object storage"
        )
    configured = os.getenv("STORAGE_LOCAL_ROOT", "").strip()
    return LocalStorage(Path(configured).expanduser() if configured else default_root)
