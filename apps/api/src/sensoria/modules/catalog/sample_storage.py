"""Isolated local storage adapter for editorially prepared public samples.

TODO [38]: replace this adapter with the private/public object-storage service.
Full paid files belong under a separate private storage root and are never read
or resolved by this module.
"""

from __future__ import annotations

import os
import re
import shutil
import stat
from pathlib import Path
from typing import BinaryIO, Literal
from uuid import uuid4

SampleKind = Literal["pdf", "audio"]
SampleContentType = Literal["application/pdf", "audio/mpeg"]
MAX_SAMPLE_BYTES = 50 * 1024 * 1024
_SAMPLE_KEY = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\.(pdf|mp3)$"
)


class SampleStorageError(Exception):
    """Safe storage failure; callers must not include OS paths in responses."""


class LocalSampleStorage:
    """Resolve only random UUID filenames inside kind-specific sample folders."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).expanduser().absolute()

    def ensure_directories(self) -> None:
        """Create private sample directories with owner-only permissions."""

        if self.root.is_symlink():
            raise SampleStorageError("Unsafe sample storage root.")
        for directory in (self.root, self.root / "pdf", self.root / "audio"):
            directory.mkdir(mode=0o700, parents=True, exist_ok=True)
            if directory.is_symlink():
                raise SampleStorageError("Unsafe sample storage directory.")
            try:
                directory.chmod(0o700)
            except OSError:
                # Windows test hosts do not implement POSIX mode bits.
                if os.name != "nt":
                    raise SampleStorageError("Unable to secure sample storage directory.") from None

    @staticmethod
    def content_type(kind: SampleKind) -> SampleContentType:
        return "application/pdf" if kind == "pdf" else "audio/mpeg"

    def _path(self, kind: SampleKind, key: str) -> Path:
        match = _SAMPLE_KEY.fullmatch(key)
        expected_extension = "pdf" if kind == "pdf" else "mp3"
        if match is None or match.group(1) != expected_extension:
            raise SampleStorageError("Invalid sample key.")
        directory = self.root / kind
        if self.root.is_symlink() or directory.is_symlink():
            raise SampleStorageError("Unsafe sample storage directory.")
        candidate = directory / key
        try:
            resolved_directory = directory.resolve(strict=True)
            resolved_candidate = candidate.resolve(strict=True)
        except OSError:
            raise SampleStorageError("Sample is missing.") from None
        if candidate.is_symlink() or resolved_candidate.parent != resolved_directory:
            raise SampleStorageError("Unsafe sample file.")
        return candidate

    def exists(self, kind: SampleKind, key: str | None) -> bool:
        if not key or _SAMPLE_KEY.fullmatch(key) is None:
            return False
        try:
            path = self._path(kind, key)
            info = path.stat()
            return stat.S_ISREG(info.st_mode) and 0 < info.st_size <= MAX_SAMPLE_BYTES
        except (OSError, SampleStorageError):
            return False

    def open(self, kind: SampleKind, key: str) -> tuple[BinaryIO, int]:
        """Open a sample without following symlinks and reject non-regular files."""

        path = self._path(kind, key)
        nofollow = getattr(os, "O_NOFOLLOW", 0)
        flags = os.O_RDONLY | nofollow
        try:
            descriptor = os.open(path, flags)
            info = os.fstat(descriptor)
            if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= MAX_SAMPLE_BYTES:
                os.close(descriptor)
                raise SampleStorageError("Invalid sample file.")
            return os.fdopen(descriptor, "rb"), info.st_size
        except SampleStorageError:
            raise
        except OSError:
            raise SampleStorageError("Sample cannot be opened.") from None

    def install_prepared(self, source: str | Path, kind: SampleKind) -> str:
        """Copy a redaction-ready sample to a newly generated random key."""

        source_path = Path(source).expanduser()
        extension = ".pdf" if kind == "pdf" else ".mp3"
        if source_path.suffix.casefold() != extension:
            raise SampleStorageError("Sample file has the wrong media extension.")
        try:
            source_info = source_path.stat()
            if (
                not stat.S_ISREG(source_info.st_mode)
                or not 0 < source_info.st_size <= MAX_SAMPLE_BYTES
            ):
                raise SampleStorageError("Invalid sample file size or type.")
            with source_path.open("rb") as source_file:
                signature = source_file.read(8)
            if kind == "pdf" and not signature.startswith(b"%PDF-"):
                raise SampleStorageError("Prepared fragment is not a PDF.")
            if kind == "audio" and not (signature.startswith(b"ID3") or signature[0:1] == b"\xff"):
                raise SampleStorageError("Prepared audio fragment is not an MP3 file.")
        except SampleStorageError:
            raise
        except OSError:
            raise SampleStorageError("Prepared sample cannot be read.") from None

        self.ensure_directories()
        key = f"{uuid4()}{extension}"
        destination = self.root / kind / key
        try:
            with source_path.open("rb") as source_file, destination.open("xb") as target:
                shutil.copyfileobj(source_file, target, length=1024 * 1024)
            try:
                destination.chmod(0o600)
            except OSError:
                if os.name != "nt":
                    raise
            return key
        except OSError:
            destination.unlink(missing_ok=True)
            raise SampleStorageError("Prepared sample cannot be installed.") from None

    def remove(self, kind: SampleKind, key: str) -> None:
        """Remove only a generated sample key after a failed metadata transaction."""

        try:
            self._path(kind, key).unlink(missing_ok=True)
        except OSError:
            raise SampleStorageError("Unattached sample cannot be removed safely.") from None
