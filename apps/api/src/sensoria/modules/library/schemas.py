"""Library request and response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class LibraryItem(BaseModel):
    id: UUID
    kind: str
    title: str
    order_number: str | None
    granted_at: datetime
    has_reader: bool
    chapters_total: int
    chapters_completed: int


class LibraryResponse(BaseModel):
    items: list[LibraryItem]


class FileInfo(BaseModel):
    id: UUID
    kind: str
    label: str
    chapter_id: UUID | None


class ReaderChapterInfo(BaseModel):
    position: int
    title: str
    page_count: int | None


class AudioChapterInfo(BaseModel):
    position: int
    title: str
    length_seconds: int
    file_id: UUID | None


class Progress(BaseModel):
    position: int
    offset_seconds: int
    completed: list[int]
    font_scale: int


class EntitlementDetail(BaseModel):
    id: UUID
    kind: str
    product_id: UUID
    title: str
    author: str | None
    cover_url: str | None = None
    order_number: str | None
    buyer_email: str
    granted_at: datetime
    files: list[FileInfo]
    reader_chapters: list[ReaderChapterInfo]
    audio_chapters: list[AudioChapterInfo]
    total_pages: int | None
    progress: Progress


class DownloadLinkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_id: UUID


class DownloadLinkResponse(BaseModel):
    url: str
    expires_at: datetime
    uses_left: int


class ChapterResponse(BaseModel):
    position: int
    title: str
    blocks: list[dict[str, Any]]
    total_chapters: int
    footer: str


class ProgressInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    position: int = Field(ge=0, le=10_000)
    offset_seconds: int = Field(default=0, ge=0, le=86_400)
    completed_position: int | None = Field(default=None, ge=0, le=10_000)
    font_scale: int | None = Field(default=None, ge=80, le=200)
