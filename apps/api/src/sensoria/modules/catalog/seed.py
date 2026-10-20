"""Idempotent, explicitly fictional catalog examples for local development."""

import asyncio

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from sensoria.database import SessionFactory
from sensoria.shared.app_settings import AppSetting
from sensoria.shared.types import VatRate

from .models import (
    AudienceTag,
    Category,
    Product,
    ProductAudiobook,
    ProductAudiobookChapter,
    ProductBook,
    ProductDigital,
    ProductImage,
    ProductVoucher,
    ProductVoucherVariant,
)
from .service import create_and_publish_product
from .types import DigitalLabel, ProductKind, ProductStatus, VoucherVariantKind

_DEMO_DESCRIPTION = "Dane demonstracyjne — nie stanowią produkcyjnej oferty Sensoria."
_DEMO_CATEGORIES = (
    ("Vouchery na wizyty", "vouchery-na-wizyty"),
    ("Książki papierowe", "ksiazki-papierowe"),
    ("Audiobooki", "audiobooki"),
    ("Kursy PDF", "kursy-pdf"),
)
_DEMO_AUDIENCES = (("Rodzice", "rodzice"), ("Dorośli", "dorosli"), ("Specjaliści", "specjalisci"))
_DEMO_ASSIGNMENTS = {
    "konsultacja-z-psychologiem": ("vouchery-na-wizyty", ("dorosli", "rodzice")),
    "integracja-sensoryczna-w-codziennosci": ("ksiazki-papierowe", ("rodzice", "specjalisci")),
    "kiedy-zmysly-mowia-glosniej": ("audiobooki", ("dorosli",)),
    "swiadoma-seksualnosc": ("kursy-pdf", ("dorosli",)),
}


def demo_products() -> tuple[Product, ...]:
    """Build four local examples; invented catalog attributes are labeled as demo data."""

    return (
        Product(
            kind=ProductKind.VOUCHER,
            name="Konsultacja z psychologiem",
            slug="konsultacja-z-psychologiem",
            short_description=_DEMO_DESCRIPTION,
            description=_DEMO_DESCRIPTION,
            price=22000,
            vat_rate=VatRate.EXEMPT,
            images=[
                ProductImage(
                    url="https://example.invalid/demo/voucher.webp",
                    alt="Demonstracyjny obraz vouchera",
                    position=0,
                )
            ],
            voucher=ProductVoucher(
                service_name="Konsultacja demonstracyjna",
                variants=[
                    ProductVoucherVariant(kind=VoucherVariantKind.IN_PERSON, price=25000),
                    ProductVoucherVariant(kind=VoucherVariantKind.ONLINE, price=22000),
                ],
            ),
        ),
        Product(
            kind=ProductKind.BOOK,
            name="Integracja sensoryczna w codzienności",
            slug="integracja-sensoryczna-w-codziennosci",
            short_description=_DEMO_DESCRIPTION,
            price=0,
            vat_rate=VatRate.EXEMPT,
            images=[
                ProductImage(
                    url="https://example.invalid/demo/book.webp",
                    alt="Demonstracyjny obraz książki",
                    position=0,
                )
            ],
            book=ProductBook(stock_quantity=1),
        ),
        Product(
            kind=ProductKind.AUDIOBOOK,
            name="Kiedy zmysły mówią głośniej",
            slug="kiedy-zmysly-mowia-glosniej",
            short_description=_DEMO_DESCRIPTION,
            price=0,
            vat_rate=VatRate.EXEMPT,
            images=[
                ProductImage(
                    url="https://example.invalid/demo/audiobook.webp",
                    alt="Demonstracyjny obraz audiobooka",
                    position=0,
                )
            ],
            audiobook=ProductAudiobook(
                duration_seconds=60,
                narrator="Lektor demonstracyjny",
                chapters=[
                    ProductAudiobookChapter(
                        title="Rozdział demonstracyjny",
                        length_seconds=60,
                        position=0,
                    )
                ],
            ),
        ),
        Product(
            kind=ProductKind.DIGITAL,
            name="Świadoma seksualność",
            slug="swiadoma-seksualnosc",
            short_description=_DEMO_DESCRIPTION,
            price=0,
            vat_rate=VatRate.EXEMPT,
            images=[
                ProductImage(
                    url="https://example.invalid/demo/ebook.webp",
                    alt="Demonstracyjny obraz e-booka PDF",
                    position=0,
                )
            ],
            digital=ProductDigital(file_format="PDF", label=DigitalLabel.EBOOK_PDF),
        ),
    )


async def seed_products() -> int:
    """Insert demo catalog defaults, assigning taxonomy only to newly inserted products."""

    inserted = 0
    async with SessionFactory.begin() as session:
        for name, slug in _DEMO_CATEGORIES:
            if await session.scalar(select(Category.id).where(Category.slug == slug)) is None:
                session.add(Category(name=name, slug=slug))
        for name, slug in _DEMO_AUDIENCES:
            if await session.scalar(select(AudienceTag.id).where(AudienceTag.slug == slug)) is None:
                session.add(AudienceTag(name=name, slug=slug))
        await session.flush()
        for product in demo_products():
            existing = await session.scalar(select(Product.id).where(Product.slug == product.slug))
            if existing is not None:
                continue
            await create_and_publish_product(session, product)
            inserted += 1

        for slug, (category_slug, audience_slugs) in _DEMO_ASSIGNMENTS.items():
            marker_key = f"catalog.demo_taxonomy_seed_v1.{slug}"
            marker = await session.scalar(select(AppSetting.id).where(AppSetting.key == marker_key))
            if marker is not None:
                continue
            seeded_product = await session.scalar(
                select(Product)
                .where(Product.slug == slug)
                .options(selectinload(Product.categories), selectinload(Product.audience_tags))
            )
            category = await session.scalar(select(Category).where(Category.slug == category_slug))
            tags = (
                await session.scalars(
                    select(AudienceTag).where(AudienceTag.slug.in_(audience_slugs))
                )
            ).all()
            if (
                seeded_product is not None
                and seeded_product.status is ProductStatus.PUBLISHED
                and category is not None
                and not seeded_product.categories
                and not seeded_product.audience_tags
            ):
                seeded_product.categories.append(category)
                seeded_product.audience_tags.extend(tags)
            if seeded_product is not None:
                session.add(
                    AppSetting(
                        key=marker_key,
                        value={"seeded": True},
                        description="Znacznik inicjalizacji demonstracyjnych przypisań katalogu.",
                    )
                )
    return inserted


async def _main() -> None:
    inserted = await seed_products()
    print(f"Dodano {inserted} nowych produktów demonstracyjnych i uzupełniono słowniki.")


if __name__ == "__main__":
    asyncio.run(_main())
