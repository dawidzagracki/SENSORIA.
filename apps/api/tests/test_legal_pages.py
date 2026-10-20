"""Shipped page drafts: structurally valid, idempotent and honest about unknown facts."""

from __future__ import annotations

import pytest
from sensoria.modules.admin.routes_products import ChapterBlock
from sensoria.modules.content import legal_pages
from sensoria.modules.content.models import ContentPage
from sqlalchemy import select

from . import test_cart
from .test_cart import CartEnvironment

cart_environment = test_cart.cart_environment
__all__ = ["cart_environment"]


def test_blocks_match_the_editor_schema_and_flag_unknown_facts() -> None:
    assert set(legal_pages.PAGES) == {
        "regulamin",
        "polityka-prywatnosci",
        "polityka-cookies",
        "dostawa-i-platnosci",
        "o-autorce",
    }
    for slug, page in legal_pages.PAGES.items():
        for block in page["blocks"]:
            ChapterBlock.model_validate(block)
        assert page["title"] and page["summary"], slug
    text = str(legal_pages.PAGES["regulamin"]["blocks"])
    assert "[UZUPEŁNIJ" in text  # tax id and e-mail are never invented
    for needed in ("14 dni", "odstąpienia", "Stripe", "InPost", "najniższą cenę z 30 dni"):
        assert needed in text or needed in str(legal_pages.PAGES)


@pytest.mark.asyncio
async def test_install_is_idempotent_and_never_overwrites(
    cart_environment: CartEnvironment, monkeypatch: pytest.MonkeyPatch
) -> None:
    _client, factory = cart_environment
    monkeypatch.setattr(legal_pages, "SessionFactory", factory)
    first = await legal_pages.install()
    assert set(first.values()) == {"created"}
    async with factory() as session:
        page = await session.scalar(select(ContentPage).where(ContentPage.slug == "regulamin"))
        assert page is not None and page.status == "draft"
        page.title = "Zmieniony przez właścicielkę"
        await session.commit()
    second = await legal_pages.install(publish=True)
    assert set(second.values()) == {"exists"}
    async with factory() as session:
        page = await session.scalar(select(ContentPage).where(ContentPage.slug == "regulamin"))
        assert page is not None and page.title == "Zmieniony przez właścicielkę"
