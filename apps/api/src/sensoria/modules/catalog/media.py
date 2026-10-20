"""Public product images stored under a random name and served read-only by the API."""

from __future__ import annotations

import os
import re
import secrets
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

from sensoria.config import get_settings
from sensoria.shared.errors import DomainError

router = APIRouter(prefix="/media", tags=["media"])
NAME_RE = re.compile(r"^[0-9a-f]{32}\.(png|jpg|webp)$")
MAX_IMAGE_BYTES = 5 * 1024 * 1024
TYPES = {"png": "image/png", "jpg": "image/jpeg", "webp": "image/webp"}


def media_root() -> Path:
    root = Path(get_settings().UPLOADS_ROOT).expanduser().resolve() / "media"
    root.mkdir(parents=True, exist_ok=True, mode=0o755)
    return root


def sniff_image(content: bytes) -> str | None:
    """Detect the real type from magic bytes; the client-supplied type is never trusted."""
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if content.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "webp"
    return None


def store_image(content: bytes) -> str:
    if not content or len(content) > MAX_IMAGE_BYTES:
        raise DomainError("MEDIA_SIZE_INVALID", "Obraz musi mieć od 1 B do 5 MB.", 422)
    extension = sniff_image(content)
    if extension is None:
        raise DomainError("MEDIA_TYPE_INVALID", "Dozwolone formaty: PNG, JPEG, WebP.", 422)
    name = f"{secrets.token_hex(16)}.{extension}"
    target = media_root() / name
    with open(os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644), "wb") as stream:
        stream.write(content)
    return name


@router.get("/{name}")
async def read_media(name: str) -> FileResponse:
    if NAME_RE.fullmatch(name) is None:
        raise DomainError("MEDIA_NOT_FOUND", "Nie znaleziono pliku.", 404)
    path = media_root() / name
    if path.is_symlink() or not path.is_file():
        raise DomainError("MEDIA_NOT_FOUND", "Nie znaleziono pliku.", 404)
    return FileResponse(
        path,
        media_type=TYPES[name.rsplit(".", 1)[1]],
        headers={
            "Cache-Control": "public, max-age=31536000, immutable",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; img-src 'self'",
        },
    )
