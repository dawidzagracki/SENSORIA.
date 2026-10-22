"""Course view of a purchased PDF: chapters from the PDF outline and server-rendered pages.

Pages are rendered to images so the reader works the same on every device and never exposes
the file itself; the downloadable copy stays the buyer-stamped PDF.
"""

from __future__ import annotations

import io
import math
import threading
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import pypdfium2 as pdfium  # type: ignore[import-untyped]
from pypdf import PdfReader

from sensoria.shared.errors import DomainError

# PDFium is not thread-safe: page renders (run in worker threads) must never overlap.
_RENDER_LOCK = threading.Lock()
MAX_WIDTH = 1600
DEFAULT_WIDTH = 1000


@dataclass(frozen=True)
class PdfChapter:
    position: int
    title: str
    start: int  # zero-based first page
    end: int  # zero-based last page, inclusive

    @property
    def page_count(self) -> int:
        return self.end - self.start + 1


def _chunks(total: int) -> list[PdfChapter]:
    size = 10 if total > 30 else 5
    chapters: list[PdfChapter] = []
    for position, start in enumerate(range(0, total, size)):
        end = min(start + size, total) - 1
        title = f"Strona {start + 1}" if start == end else f"Strony {start + 1}–{end + 1}"
        chapters.append(PdfChapter(position, title, start, end))
    return chapters


@lru_cache(maxsize=64)
def _chapters_cached(path: str, mtime_ns: int) -> tuple[int, tuple[PdfChapter, ...]]:
    reader = PdfReader(path)
    total = len(reader.pages)
    if total == 0:
        return 0, ()
    starts: list[tuple[int, str]] = []
    try:
        for item in reader.outline:
            if isinstance(item, list):
                continue  # nested entries stay inside their parent chapter
            title = str(getattr(item, "title", "") or "").strip()
            page = reader.get_destination_page_number(item)
            if title and page is not None and 0 <= page < total:
                starts.append((page, title[:200]))
    except Exception:  # noqa: BLE001 - a broken outline falls back to page ranges
        starts = []
    unique: dict[int, str] = {}
    for page, title in sorted(starts):
        unique.setdefault(page, title)
    if len(unique) < 2:
        return total, tuple(_chunks(total))
    pages = sorted(unique)
    if pages[0] != 0:
        unique[0] = "Początek"
        pages = sorted(unique)
    chapters = [
        PdfChapter(
            position,
            unique[start],
            start,
            (pages[position + 1] - 1) if position + 1 < len(pages) else total - 1,
        )
        for position, start in enumerate(pages)
    ]
    return total, tuple(chapters)


def build_chapters(path: Path) -> tuple[int, list[PdfChapter]]:
    stat = path.stat()
    total, chapters = _chapters_cached(str(path), stat.st_mtime_ns)
    return total, list(chapters)


@lru_cache(maxsize=128)
def _render_cached(path: str, mtime_ns: int, page_number: int, width: int) -> bytes:
    with _RENDER_LOCK:
        document = pdfium.PdfDocument(path)
        try:
            if not 1 <= page_number <= len(document):
                raise DomainError("PAGE_NOT_FOUND", "Nie znaleziono strony.", 404)
            page = document[page_number - 1]
            scale = width / max(1.0, float(page.get_width()))
            bitmap = page.render(scale=math.ceil(scale * 100) / 100)
            buffer = io.BytesIO()
            bitmap.to_pil().save(buffer, format="PNG")
            return buffer.getvalue()
        finally:
            document.close()


def render_page(path: Path, page_number: int, width: int = DEFAULT_WIDTH) -> bytes:
    """Render one 1-based page to PNG at the requested width (cached per file version)."""
    width = max(320, min(width, MAX_WIDTH))
    return _render_cached(str(path), path.stat().st_mtime_ns, page_number, width)
