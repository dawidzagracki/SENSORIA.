"""Public sample endpoints and sample-only storage integration tests."""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sensoria.config import get_settings
from sensoria.database import SessionFactory, get_session
from sensoria.main import app
from sensoria.modules.catalog import samples
from sensoria.modules.catalog.models import (
    Product,
    ProductAudiobook,
    ProductDigital,
    ProductImage,
    SampleAccessSession,
    SampleRateWindow,
)
from sensoria.modules.catalog.price_history import PriceHistory
from sensoria.modules.catalog.sample_storage import LocalSampleStorage, SampleStorageError
from sensoria.modules.catalog.types import ProductKind, ProductStatus
from sensoria.shared.audit_log import AuditLog
from sensoria.shared.types import VatRate
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

API_ROOT = Path(__file__).resolve().parents[1]


@pytest_asyncio.fixture
async def sample_database(
    test_database_url: str,
) -> AsyncIterator[tuple[AsyncSession, AsyncEngine]]:
    """Use only TEST_DATABASE_URL and rollback all fixture data after each test."""

    await asyncio.to_thread(command.upgrade, Config(str(API_ROOT / "alembic.ini")), "head")
    engine = create_async_engine(test_database_url, pool_pre_ping=True)
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            factory = async_sessionmaker(
                bind=connection,
                class_=AsyncSession,
                expire_on_commit=False,
                join_transaction_mode="create_savepoint",
            )
            async with factory() as session:
                yield session, engine
                await session.rollback()
            if transaction.is_active:
                await transaction.rollback()
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def sample_client(
    sample_database: tuple[AsyncSession, AsyncEngine],
) -> AsyncIterator[AsyncClient]:
    session, _engine = sample_database

    async def override_session() -> AsyncIterator[AsyncSession]:
        yield session

    app.dependency_overrides[get_session] = override_session
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://samples-test"
        ) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_session, None)


_FIXTURE_ROOT = Path(__file__).parent / "fixtures"
_PDF_BYTES = (_FIXTURE_ROOT / "sample-fragment-fixture.pdf").read_bytes()
_FULL_PDF_BYTES = b"%PDF-1.7\nFIXTURE ONLY - paid full file\n%%EOF\n"
_AUDIO_BYTES = (_FIXTURE_ROOT / "sample-audio-fixture.mp3").read_bytes()


async def _create_product(
    session: AsyncSession,
    *,
    kind: ProductKind,
    key: str | None,
    slug_suffix: str,
) -> Product:
    slug = f"sample-test-{slug_suffix}-{uuid4().hex[:8]}"
    if kind is ProductKind.DIGITAL:
        details: ProductDigital | None = ProductDigital(
            file_format="PDF",
            sample_file_path=key,
            sample_pages=2 if key else None,
            sample_enabled=key is not None,
        )
        audiobook = None
    else:
        details = None
        audiobook = ProductAudiobook(
            duration_seconds=120,
            narrator="Test",
            file_format="MP3",
            sample_file_path=key,
            sample_duration_seconds=8 if key else None,
            sample_enabled=key is not None,
        )
    product = Product(
        kind=kind,
        name="Produkt testowy próbki",
        slug=slug,
        short_description="Jawne dane fixture testów.",
        price=1000,
        compare_at_price=None,
        vat_rate=VatRate.RATE_23,
        status=ProductStatus.PUBLISHED,
        published_at=datetime.now(UTC) - timedelta(minutes=5),
        digital=details,
        audiobook=audiobook,
        images=[],
        categories=[],
        audience_tags=[],
    )
    session.add(product)
    await session.flush()
    return product


@pytest.mark.asyncio
async def test_public_pdf_is_sample_only_and_counted_once(
    sample_database: tuple[AsyncSession, AsyncEngine],
    sample_client: AsyncClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    catalog_session, _engine = sample_database
    storage = LocalSampleStorage(tmp_path / "samples")
    pdf_source = tmp_path / "prepared-fixture.pdf"
    pdf_source.write_bytes(_PDF_BYTES)
    pdf_key = storage.install_prepared(pdf_source, "pdf")
    monkeypatch.setattr(samples, "_storage", lambda: storage)
    settings = get_settings()
    monkeypatch.setattr(settings, "SAMPLE_OPEN_LIMIT", 10)
    private_file = tmp_path / "private" / "paid-full.pdf"
    private_file.parent.mkdir()
    private_file.write_bytes(_FULL_PDF_BYTES)

    pdf_product = await _create_product(
        catalog_session, kind=ProductKind.DIGITAL, key=pdf_key, slug_suffix="pdf"
    )
    assert samples._sample_details(pdf_product) is not None
    assert storage.exists("pdf", pdf_key)
    published_pdf = await samples._published_product(catalog_session, pdf_product.slug)
    assert published_pdf is not None
    assert samples._sample_details(published_pdf) is not None
    open_id = str(uuid4())
    opened = await sample_client.post(
        f"/products/{pdf_product.slug}/sample/open",
        headers={"X-Sample-Open-Id": open_id},
    )
    assert opened.status_code == 200, opened.text
    assert opened.json()["content_type"] == "application/pdf"
    assert opened.json()["pages"] == 2
    assert "paid-full.pdf" not in opened.text
    assert str(private_file) not in opened.text

    retry = await sample_client.post(
        f"/products/{pdf_product.slug}/sample/open",
        headers={"X-Sample-Open-Id": open_id},
    )
    assert retry.status_code == 200
    assert retry.json()["sample_url"] == opened.json()["sample_url"]
    assert (
        await catalog_session.scalar(
            select(Product.sample_open_count).where(Product.id == pdf_product.id)
        )
        == 1
    )

    sample_url = opened.json()["sample_url"]
    full_sample = await sample_client.get(sample_url)
    assert full_sample.status_code == 200
    assert full_sample.content == _PDF_BYTES
    assert full_sample.content != _FULL_PDF_BYTES
    assert full_sample.headers["content-type"].startswith("application/pdf")
    assert full_sample.headers["content-disposition"].startswith("inline;")
    assert str(tmp_path) not in full_sample.text


@pytest.mark.asyncio
async def test_audio_sample_supports_range_and_rate_limit(
    sample_database: tuple[AsyncSession, AsyncEngine],
    sample_client: AsyncClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    catalog_session, _engine = sample_database
    storage = LocalSampleStorage(tmp_path / "samples")
    audio_source = tmp_path / "prepared-fixture.mp3"
    audio_source.write_bytes(_AUDIO_BYTES)
    audio_key = storage.install_prepared(audio_source, "audio")
    monkeypatch.setattr(samples, "_storage", lambda: storage)
    settings = get_settings()
    monkeypatch.setattr(settings, "SAMPLE_OPEN_LIMIT", 1)
    audio_product = await _create_product(
        catalog_session, kind=ProductKind.AUDIOBOOK, key=audio_key, slug_suffix="audio"
    )
    audio_opened = await sample_client.post(
        f"/products/{audio_product.slug}/sample/open",
        headers={"X-Sample-Open-Id": str(uuid4())},
    )
    assert audio_opened.status_code == 200, audio_opened.text
    assert audio_opened.json()["content_type"] == "audio/mpeg"
    audio_response = await sample_client.get(
        audio_opened.json()["sample_url"], headers={"Range": "bytes=0-7"}
    )
    assert audio_response.status_code == 206
    assert audio_response.content == _AUDIO_BYTES[:8]
    assert audio_response.headers["content-range"] == f"bytes 0-7/{len(_AUDIO_BYTES)}"
    assert audio_response.headers["accept-ranges"] == "bytes"
    assert (
        await catalog_session.scalar(
            select(Product.sample_open_count).where(Product.id == audio_product.id)
        )
        == 1
    )
    assert (
        await catalog_session.scalar(
            select(SampleAccessSession.request_count).where(
                SampleAccessSession.product_id == audio_product.id
            )
        )
        == 1
    )
    limited_retry = await sample_client.post(
        f"/products/{audio_product.slug}/sample/open",
        headers={"X-Sample-Open-Id": str(uuid4())},
    )
    assert limited_retry.status_code == 429
    assert int(limited_retry.headers["retry-after"]) >= 1


@pytest.mark.asyncio
async def test_parallel_sample_opens_increment_counter_without_lost_updates(
    test_database_url: str,
    api_client: AsyncClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del test_database_url  # conftest verifies this is the dedicated `_test` database.
    storage = LocalSampleStorage(tmp_path / "samples")
    pdf_source = tmp_path / "parallel-fixture.pdf"
    pdf_source.write_bytes(_PDF_BYTES)
    sample_key = storage.install_prepared(pdf_source, "pdf")
    monkeypatch.setattr(samples, "_storage", lambda: storage)
    monkeypatch.setattr(get_settings(), "TRUSTED_PROXY_CIDRS", "127.0.0.1/32")
    product_id = uuid4()
    slug = f"sample-parallel-{product_id.hex}"
    async with SessionFactory() as session:
        product = Product(
            id=product_id,
            kind=ProductKind.DIGITAL,
            name="Fixture równoległych otwarć",
            slug=slug,
            short_description="Dane testowe.",
            price=1000,
            vat_rate=VatRate.RATE_23,
            status=ProductStatus.PUBLISHED,
            published_at=datetime.now(UTC) - timedelta(minutes=5),
            digital=ProductDigital(
                file_format="PDF",
                sample_file_path=sample_key,
                sample_pages=2,
                sample_enabled=True,
            ),
            images=[ProductImage(url="https://example.invalid/sample.jpg", alt="Fixture")],
            categories=[],
            audience_tags=[],
        )
        session.add(product)
        await session.commit()

    try:
        responses = await asyncio.gather(
            *(
                api_client.post(
                    f"/products/{slug}/sample/open",
                    headers={
                        "X-Sample-Open-Id": str(uuid4()),
                        "X-Forwarded-For": f"198.18.{product_id.int % 255}.{index + 1}",
                    },
                )
                for index in range(8)
            )
        )
        assert all(response.status_code == 200 for response in responses)
        async with SessionFactory() as session:
            assert await session.scalar(
                select(Product.sample_open_count).where(Product.id == product_id)
            ) == len(responses)
    finally:
        async with SessionFactory() as session:
            # This is an isolated `_test` database: bypass append-only cleanup
            # only for this generated fixture, then restore the trigger in the
            # same transaction before returning to the test suite.
            await session.execute(
                text("ALTER TABLE price_history DISABLE TRIGGER trg_price_history_append_only")
            )
            await session.execute(delete(PriceHistory).where(PriceHistory.product_id == product_id))
            await session.execute(
                text("ALTER TABLE price_history ENABLE TRIGGER trg_price_history_append_only")
            )
            await session.execute(delete(AuditLog).where(AuditLog.entity_id == product_id))
            await session.execute(delete(Product).where(Product.id == product_id))
            await session.execute(delete(SampleRateWindow))
            await session.commit()


@pytest.mark.asyncio
async def test_unavailable_samples_and_unpublished_products_are_indistinguishable(
    sample_database: tuple[AsyncSession, AsyncEngine],
    sample_client: AsyncClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    catalog_session, _engine = sample_database
    storage = LocalSampleStorage(tmp_path / "samples")
    monkeypatch.setattr(samples, "_storage", lambda: storage)
    unavailable = await _create_product(
        catalog_session, kind=ProductKind.DIGITAL, key=None, slug_suffix="disabled"
    )
    disabled = await sample_client.post(
        f"/products/{unavailable.slug}/sample/open",
        headers={"X-Sample-Open-Id": str(uuid4())},
    )
    assert disabled.status_code == 404
    assert "path" not in disabled.text.lower()
    assert (
        await catalog_session.scalar(
            select(Product.sample_open_count).where(Product.id == unavailable.id)
        )
        == 0
    )

    missing_file_key = f"{uuid4()}.pdf"
    product = await _create_product(
        catalog_session,
        kind=ProductKind.DIGITAL,
        key=missing_file_key,
        slug_suffix="missing",
    )
    missing = await sample_client.post(
        f"/products/{product.slug}/sample/open",
        headers={"X-Sample-Open-Id": str(uuid4())},
    )
    assert missing.status_code == 404
    assert str(tmp_path) not in missing.text

    product.status = ProductStatus.WITHDRAWN
    await catalog_session.flush()
    hidden = await sample_client.post(
        f"/products/{product.slug}/sample/open",
        headers={"X-Sample-Open-Id": str(uuid4())},
    )
    assert hidden.status_code == 404


def test_sample_storage_rejects_path_traversal_and_wrong_file_kind(tmp_path: Path) -> None:
    storage = LocalSampleStorage(tmp_path / "samples")
    storage.ensure_directories()
    with pytest.raises(SampleStorageError):
        storage.open("pdf", "..%2fprivate.pdf")
    with pytest.raises(SampleStorageError):
        storage.open("pdf", f"{uuid4()}.mp3")


def test_sample_storage_rejects_symlinked_file_and_root(tmp_path: Path) -> None:
    storage = LocalSampleStorage(tmp_path / "samples")
    storage.ensure_directories()
    external = tmp_path / "private-full.pdf"
    external.write_bytes(_FULL_PDF_BYTES)
    sample_link = storage.root / "pdf" / f"{uuid4()}.pdf"
    try:
        os.symlink(external, sample_link)
    except (OSError, NotImplementedError):
        pytest.skip("System nie pozwala tworzyć symlinków w tym środowisku.")
    assert not storage.exists("pdf", sample_link.name)
    with pytest.raises(SampleStorageError):
        storage.open("pdf", sample_link.name)

    linked_root = tmp_path / "linked-samples"
    os.symlink(storage.root, linked_root, target_is_directory=True)
    linked_storage = LocalSampleStorage(linked_root)
    with pytest.raises(SampleStorageError):
        linked_storage.ensure_directories()


def test_forwarded_ip_is_used_only_for_trusted_proxy(monkeypatch: pytest.MonkeyPatch) -> None:
    from starlette.requests import Request

    settings = get_settings()
    monkeypatch.setattr(settings, "TRUSTED_PROXY_CIDRS", "172.18.0.0/16")

    def request(peer: str) -> Request:
        return Request(
            {
                "type": "http",
                "method": "GET",
                "path": "/",
                "headers": [(b"x-forwarded-for", b"198.51.100.23, 172.18.0.12")],
                "client": (peer, 1234),
                "server": ("test", 80),
                "scheme": "http",
                "query_string": b"",
            }
        )

    assert samples._client_ip(request("172.18.0.8")) == "198.51.100.23"
    assert samples._client_ip(request("203.0.113.8")) == "203.0.113.8"
