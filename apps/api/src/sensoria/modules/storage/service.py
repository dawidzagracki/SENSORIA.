"""Private, no-overwrite storage operations for generated voucher PDFs."""

from __future__ import annotations

import hashlib
import os
import secrets
import tempfile
from contextlib import suppress
from pathlib import Path
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from sensoria.config import get_settings
from sensoria.shared.errors import DomainError

from .models import StoredFile


class StorageService:
    """Store voucher PDFs outside any static web root."""

    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root or get_settings().UPLOADS_ROOT).expanduser().resolve()

    def _voucher_directory(self, year: int) -> Path:
        if not 2000 <= year <= 9999:
            raise ValueError("Nieprawidłowy rok magazynu.")
        root = self.root
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        if root.is_symlink():
            raise DomainError("VOUCHER_STORAGE_UNAVAILABLE", "Nie można zapisać pliku.", 503)
        with suppress(OSError):
            os.chmod(root, 0o700)
        category_directory = root / "vouchers"
        category_directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        if category_directory.is_symlink() or not category_directory.resolve().is_relative_to(root):
            raise DomainError("VOUCHER_STORAGE_UNAVAILABLE", "Nie można zapisać pliku.", 503)
        with suppress(OSError):
            os.chmod(category_directory, 0o700)
        directory = category_directory / str(year)
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        resolved = directory.resolve()
        if directory.is_symlink() or not resolved.is_relative_to(root):
            raise DomainError("VOUCHER_STORAGE_UNAVAILABLE", "Nie można zapisać pliku.", 503)
        with suppress(OSError):
            os.chmod(directory, 0o700)
        return directory

    async def store_voucher_pdf(
        self,
        session: AsyncSession,
        *,
        voucher_id: UUID,
        year: int,
        content: bytes,
    ) -> StoredFile:
        """Atomically publish a private PDF and add its metadata to the transaction."""
        if not content.startswith(b"%PDF-") or not content:
            raise DomainError("VOUCHER_PDF_INVALID", "Nie udało się przygotować pliku.", 500)
        directory = self._voucher_directory(year)
        stored_name = secrets.token_hex(32)
        target = directory / stored_name
        descriptor, temporary_name = tempfile.mkstemp(prefix=".pending-", dir=directory)
        temporary = Path(temporary_name)
        try:
            with suppress(OSError):
                os.chmod(temporary, 0o600)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            # link() is atomic and fails instead of replacing an existing destination.
            os.link(temporary, target)
            temporary.unlink()
            record = StoredFile(
                category="vouchers",
                original_name="voucher.pdf",
                stored_name=stored_name,
                mime_type="application/pdf",
                size_bytes=len(content),
                checksum=hashlib.sha256(content).hexdigest(),
                scope_id=voucher_id,
                storage_year=year,
            )
            session.add(record)
            await session.flush()
            return record
        except BaseException:
            if temporary.exists():
                temporary.unlink(missing_ok=True)
            if target.exists():
                target.unlink(missing_ok=True)
            raise

    def read_voucher_pdf(self, stored_file: StoredFile) -> Path:
        """Resolve only a validated metadata record to a private file path."""
        if (
            stored_file.category != "vouchers"
            or not stored_file.stored_name.isascii()
            or len(stored_file.stored_name) != 64
            or any(character not in "0123456789abcdef" for character in stored_file.stored_name)
            or not 2000 <= stored_file.storage_year <= 9999
        ):
            raise DomainError("VOUCHER_PDF_NOT_FOUND", "Plik vouchera jest niedostępny.", 404)
        directory = self._voucher_directory(stored_file.storage_year)
        path = directory / stored_file.stored_name
        if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(self.root):
            raise DomainError("VOUCHER_PDF_NOT_FOUND", "Plik vouchera jest niedostępny.", 404)
        return path
