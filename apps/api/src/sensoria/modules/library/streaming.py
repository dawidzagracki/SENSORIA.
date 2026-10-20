"""Single-range file streaming for private audio and PDF delivery."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import AsyncIterator
from pathlib import Path
from urllib.parse import quote

from fastapi.responses import StreamingResponse

from sensoria.shared.errors import DomainError

_RANGE = re.compile(r"bytes=(\d*)-(\d*)")


def parse_range(value: str | None, size: int) -> tuple[int, int, bool]:
    """Return (start, end, partial); reject unsatisfiable and multi-range requests."""
    if value is None:
        return 0, size - 1, False
    invalid = DomainError(
        "RANGE_INVALID", "Zakres jest nieprawidłowy.", 416, {"Content-Range": f"bytes */{size}"}
    )
    match = _RANGE.fullmatch(value.strip())
    if match is None:
        raise invalid
    first, last = match.groups()
    if not first and not last:
        raise invalid
    if not first:
        length = int(last)
        if length <= 0:
            raise invalid
        start, end = max(0, size - length), size - 1
    else:
        start = int(first)
        end = min(int(last), size - 1) if last else size - 1
    if start >= size or start > end:
        raise invalid
    return start, end, True


def content_disposition(disposition: str, filename: str) -> str:
    """ASCII fallback plus RFC 5987 UTF-8 name, so Polish titles never break headers."""
    folded = unicodedata.normalize("NFKD", filename).encode("ascii", "ignore").decode()
    fallback = re.sub(r"[^A-Za-z0-9._ -]", "_", folded).strip() or "plik"
    return f"{disposition}; filename=\"{fallback}\"; filename*=UTF-8''{quote(filename)}"


def file_response(
    path: Path,
    *,
    media_type: str,
    filename: str,
    range_header: str | None,
    disposition: str = "attachment",
) -> tuple[StreamingResponse, bool]:
    """Stream a file with Range support; the bool tells whether playback restarts at byte 0."""
    size = path.stat().st_size
    start, end, partial = parse_range(range_header, size)
    stream = path.open("rb")
    stream.seek(start)
    length = end - start + 1

    async def chunks() -> AsyncIterator[bytes]:
        remaining = length
        try:
            while remaining:
                block = stream.read(min(64 * 1024, remaining))
                if not block:
                    break
                remaining -= len(block)
                yield block
        finally:
            stream.close()

    headers = {
        "Accept-Ranges": "bytes",
        "Cache-Control": "private, no-store",
        "Content-Disposition": content_disposition(disposition, filename),
        "Content-Length": str(length),
        "Referrer-Policy": "no-referrer",
        "X-Content-Type-Options": "nosniff",
    }
    if partial:
        headers["Content-Range"] = f"bytes {start}-{end}/{size}"
    response = StreamingResponse(
        chunks(), status_code=206 if partial else 200, headers=headers, media_type=media_type
    )
    return response, start == 0
