"""Runs inside the api container: showcase categories and audiences, assigned to demo products."""

import asyncio

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from sensoria.database import SessionFactory
from sensoria.modules.catalog.models import (
    AudienceTag,
    Category,
    Product,
    product_audience_tags,
    product_categories,
)

CATEGORIES = {
    "vouchery": ("Vouchery na wizyty", ["konsultacja-psychologiczna", "diagnoza-integracji-sensorycznej"]),
    "ksiazki": ("Książki papierowe", ["integracja-sensoryczna-w-codziennosci"]),
    "audiobooki": ("Audiobooki", ["kiedy-zmysly-mowia-glosniej"]),
    "e-booki": ("E-booki", ["zmysly-w-domu"]),
    "kursy-pdf": ("Kursy PDF", ["regulacja-emocji-u-dziecka-kurs-pdf"]),
}
EVERY = [
    "konsultacja-psychologiczna", "diagnoza-integracji-sensorycznej", "integracja-sensoryczna-w-codziennosci",
    "kiedy-zmysly-mowia-glosniej", "zmysly-w-domu", "regulacja-emocji-u-dziecka-kurs-pdf",
]
AUDIENCES = {
    "rodzice": ("Rodzice", EVERY),
    "terapeuci": ("Terapeuci", ["integracja-sensoryczna-w-codziennosci", "zmysly-w-domu", "regulacja-emocji-u-dziecka-kurs-pdf"]),
    "nauczyciele": ("Nauczyciele", ["integracja-sensoryczna-w-codziennosci", "regulacja-emocji-u-dziecka-kurs-pdf"]),
    "dorośli": ("Dorośli", ["konsultacja-psychologiczna", "diagnoza-integracji-sensorycznej"]),
}


async def main() -> None:
    async with SessionFactory() as session, session.begin():
        products = {p.slug: p.id for p in (await session.scalars(select(Product))).all()}
        for position, (slug, (name, members)) in enumerate(CATEGORIES.items()):
            category = await session.scalar(select(Category).where(Category.slug == slug))
            if category is None:
                category = Category(name=name, slug=slug, position=position)
                session.add(category)
                await session.flush()
            for member in members:
                if member in products:
                    await session.execute(
                        insert(product_categories).values(product_id=products[member], category_id=category.id).on_conflict_do_nothing()
                    )
        for slug, (name, members) in AUDIENCES.items():
            slug = slug.replace("ś", "s")
            tag = await session.scalar(select(AudienceTag).where(AudienceTag.slug == slug))
            if tag is None:
                tag = AudienceTag(name=name, slug=slug)
                session.add(tag)
                await session.flush()
            for member in members:
                if member in products:
                    await session.execute(
                        insert(product_audience_tags).values(product_id=products[member], audience_tag_id=tag.id).on_conflict_do_nothing()
                    )



async def search_settings() -> None:
    from sensoria.modules.catalog.search_presentation import SEARCH_PRESENTATION_SETTING_KEY
    from sensoria.shared.app_settings import AppSetting

    async with SessionFactory() as session, session.begin():
        if await session.scalar(select(AppSetting).where(AppSetting.key == SEARCH_PRESENTATION_SETTING_KEY)) is None:
            session.add(
                AppSetting(
                    key=SEARCH_PRESENTATION_SETTING_KEY,
                    value={
                        "suggested_queries": ["integracja sensoryczna", "voucher", "audiobook", "e-book"],
                        "contact_email": "kontakt@sensoria.demo",
                        "contact_phone": "+48 600 100 200",
                    },
                    description="Podpowiedzi i kontakt przy braku wyników wyszukiwania",
                )
            )


async def run_all() -> None:
    await main()
    await search_settings()


asyncio.run(run_all())
