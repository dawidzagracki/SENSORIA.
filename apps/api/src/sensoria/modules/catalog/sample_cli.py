"""Install a separately prepared editorial sample and attach it to a product."""

from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from sensoria.config import get_settings
from sensoria.database import SessionFactory

from .models import Product
from .sample_storage import LocalSampleStorage, SampleKind, SampleStorageError
from .types import ProductKind


async def install_sample(
    slug: str,
    source: str,
    kind: SampleKind,
    metadata_value: int,
) -> str:
    """Install a prepared file under a random key and enable its public sample."""

    async with SessionFactory() as session:
        product = await session.scalar(
            select(Product)
            .where(Product.slug == slug)
            .options(selectinload(Product.digital), selectinload(Product.audiobook))
            .with_for_update()
        )
        if product is None:
            raise ValueError("Nie znaleziono produktu o podanym slugu.")
        if (kind == "pdf" and product.kind is not ProductKind.DIGITAL) or (
            kind == "audio" and product.kind is not ProductKind.AUDIOBOOK
        ):
            raise ValueError("Rodzaj fragmentu nie odpowiada rodzajowi produktu.")

        storage = LocalSampleStorage(get_settings().SAMPLE_STORAGE_ROOT)
        key = storage.install_prepared(source, kind)
        try:
            if kind == "pdf":
                if product.digital is None:
                    raise ValueError("Nie znaleziono szczegółów produktu cyfrowego.")
                product.digital.sample_file_path = key
                product.digital.sample_enabled = True
                product.digital.sample_pages = metadata_value
            else:
                if product.audiobook is None:
                    raise ValueError("Nie znaleziono szczegółów audiobooka.")
                product.audiobook.sample_file_path = key
                product.audiobook.sample_enabled = True
                product.audiobook.sample_duration_seconds = metadata_value
            await session.commit()
            return key
        except BaseException:
            await session.rollback()
            storage.remove(kind, key)
            raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slug", required=True)
    parser.add_argument("--file", required=True, help="Przygotowany fragment, nie pełny plik.")
    parser.add_argument("--kind", choices=("pdf", "audio"), required=True)
    parser.add_argument("--pages", type=int)
    parser.add_argument("--duration-seconds", type=int)
    args = parser.parse_args()
    metadata_value = args.pages if args.kind == "pdf" else args.duration_seconds
    if metadata_value is None or metadata_value <= 0:
        parser.error("Podaj --pages dla PDF albo --duration-seconds dla audio.")
    try:
        key = asyncio.run(install_sample(args.slug, args.file, args.kind, metadata_value))
    except (SampleStorageError, ValueError) as error:
        parser.error(str(error))
    print(f"Zainstalowano osobny fragment pod losowym kluczem: {key}")


if __name__ == "__main__":
    main()
