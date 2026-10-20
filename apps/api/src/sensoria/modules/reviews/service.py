"""Review submission rules, public summaries, moderation and the request scheduler."""

from __future__ import annotations

import asyncio
import logging
import re
import unicodedata
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from sensoria.config import get_settings
from sensoria.database import SessionFactory
from sensoria.modules.accounts.auth import normalize_email
from sensoria.modules.accounts.models import Customer
from sensoria.modules.accounts.privacy import has_current_consent
from sensoria.modules.catalog.models import Product
from sensoria.modules.catalog.types import ProductStatus
from sensoria.modules.mail.outbox import enqueue_mail
from sensoria.modules.orders.models import Order, OrderItem
from sensoria.modules.payments.tokens import order_access_token
from sensoria.shared.app_settings import AppSetting
from sensoria.shared.audit_log import ActorType, AuditLog
from sensoria.shared.errors import DomainError

from .models import Review, ReviewRequest

logger = logging.getLogger("sensoria.reviews")
SETTINGS_KEY = "reviews.requests.v1"
DEFAULT_DELAY_DAYS = 7
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def clean_text(value: str, *, multiline: bool) -> str:
    """Normalize Unicode, drop control characters and collapse whitespace."""
    text = unicodedata.normalize("NFC", value)
    text = _CONTROL.sub("", text)
    if multiline:
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
    else:
        text = re.sub(r"\s+", " ", text)
    return text.strip()


def display_name(first_name: str | None, email: str) -> str:
    """Public author label: first name plus initial or a neutral fallback; never the email."""
    if first_name and first_name.strip():
        return first_name.strip()[:60]
    return "Klientka"


async def submit_review(
    session: AsyncSession,
    *,
    order: Order,
    order_item_id: UUID,
    rating: int,
    title: str | None,
    body: str,
    customer: Customer | None,
) -> Review:
    """Create a pending review for a paid purchase; one review per purchased item."""
    if order.status != "paid":
        raise DomainError(
            "REVIEW_ORDER_NOT_PAID", "Opinię można dodać po opłaceniu zamówienia.", 409
        )
    item = await session.scalar(
        select(OrderItem).where(OrderItem.id == order_item_id, OrderItem.order_id == order.id)
    )
    if item is None:
        raise DomainError("REVIEW_ITEM_NOT_FOUND", "Nie znaleziono produktu w zamówieniu.", 404)
    clean_body = clean_text(body, multiline=True)
    if len(clean_body) < 10:
        raise DomainError("REVIEW_TOO_SHORT", "Opinia musi mieć co najmniej 10 znaków.", 422)
    if len(clean_body) > 2000:
        raise DomainError("REVIEW_TOO_LONG", "Opinia może mieć najwyżej 2000 znaków.", 422)
    first_name = (
        customer.first_name
        if customer
        else (order.invoice_data.get("buyer_snapshot") or {}).get("first_name")
    )
    review = Review(
        product_id=item.product_id,
        order_item_id=item.id,
        order_id=order.id,
        customer_id=customer.id if customer else order.customer_id,
        author_name=display_name(first_name, order.email),
        rating=rating,
        title=clean_text(title, multiline=False)[:120] if title and title.strip() else None,
        body=clean_body,
    )
    try:
        async with session.begin_nested():
            session.add(review)
            await session.flush()
    except IntegrityError:
        raise DomainError(
            "REVIEW_ALREADY_EXISTS", "Opinia o tym produkcie została już dodana.", 409
        ) from None
    session.add(
        AuditLog(
            actor_type=ActorType.CUSTOMER if customer else ActorType.SYSTEM,
            actor_id=customer.id if customer else None,
            entity_type="review",
            entity_id=review.id,
            action="review.submitted",
            payload={"order_id": str(order.id)},
        )
    )
    await session.flush()
    return review


async def product_summary(session: AsyncSession, product_id: UUID) -> dict[str, Any]:
    rows = (
        await session.execute(
            select(Review.rating, func.count())
            .where(Review.product_id == product_id, Review.status == "approved")
            .group_by(Review.rating)
        )
    ).all()
    distribution = {str(star): 0 for star in range(1, 6)}
    for rating, count in rows:
        distribution[str(rating)] = int(count)
    total = sum(distribution.values())
    average = (
        round(sum(int(star) * n for star, n in distribution.items()) / total, 2) if total else None
    )
    return {"count": total, "average": average, "distribution": distribution}


async def eligible_items(session: AsyncSession, order: Order) -> list[dict[str, Any]]:
    if order.status != "paid":
        return []
    rows = (
        await session.execute(
            select(OrderItem, Review.id)
            .outerjoin(Review, Review.order_item_id == OrderItem.id)
            .where(OrderItem.order_id == order.id)
            .order_by(OrderItem.id)
        )
    ).all()
    return [
        {
            "order_item_id": str(item.id),
            "product_id": str(item.product_id),
            "name": item.product_name_snapshot,
            "reviewed": review_id is not None,
        }
        for item, review_id in rows
    ]


async def decide(
    session: AsyncSession, review_id: UUID, *, admin_id: UUID, approve: bool, note: str | None
) -> Review:
    review = await session.scalar(select(Review).where(Review.id == review_id).with_for_update())
    if review is None:
        raise DomainError("REVIEW_NOT_FOUND", "Nie znaleziono opinii.", 404)
    review.status = "approved" if approve else "rejected"
    review.moderated_at = datetime.now(UTC)
    review.moderated_by = admin_id
    review.moderation_note = (note or "").strip()[:500] or None
    session.add(
        AuditLog(
            actor_type=ActorType.ADMINISTRATOR,
            actor_id=admin_id,
            entity_type="review",
            entity_id=review.id,
            action="review.approved" if approve else "review.rejected",
            payload={},
        )
    )
    await session.flush()
    return review


async def _delay_days(session: AsyncSession) -> int:
    setting = await session.scalar(select(AppSetting).where(AppSetting.key == SETTINGS_KEY))
    value = setting.value.get("delay_days") if setting and isinstance(setting.value, dict) else None
    if isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= 90:
        return value
    return DEFAULT_DELAY_DAYS


async def queue_review_requests(
    session_factory: async_sessionmaker[AsyncSession] = SessionFactory,
    *,
    batch_size: int = 100,
    now: datetime | None = None,
) -> int:
    """Mail a review request once per purchased item, only with a current consent.

    Physical items wait for delivery/pickup; digital and voucher items qualify after the delay.
    """
    moment = now or datetime.now(UTC)
    origin = get_settings().SITE_URL or ""
    queued = 0
    async with session_factory() as session, session.begin():
        delay = await _delay_days(session)
        cutoff = moment - timedelta(days=delay)
        rows = (
            await session.execute(
                select(OrderItem, Order, Product)
                .join(Order, Order.id == OrderItem.order_id)
                .join(Product, Product.id == OrderItem.product_id)
                .where(
                    Order.status == "paid",
                    Order.created_at <= cutoff,
                    Product.status != ProductStatus.DRAFT,
                    ~select(ReviewRequest.id)
                    .where(ReviewRequest.order_item_id == OrderItem.id)
                    .exists(),
                    ~select(Review.id).where(Review.order_item_id == OrderItem.id).exists(),
                )
                .order_by(Order.created_at)
                .limit(batch_size)
            )
        ).all()
        for item, order, _product in rows:
            if order.shipping_data is not None and order.fulfillment_status not in {
                "delivered",
                "picked_up",
            }:
                continue
            customer = await session.get(Customer, order.customer_id) if order.customer_id else None
            consent = await has_current_consent(
                session,
                "review_requests",
                customer_id=customer.id if customer else None,
                email=normalize_email(order.email),
            )
            if consent is not True or (customer is not None and customer.deleted_at is not None):
                continue
            token = order_access_token(order.id)
            await enqueue_mail(
                session,
                template_key="review_request",
                recipient=order.email,
                variables={
                    "product_name": item.product_name_snapshot or "Twój zakup",
                    "review_url": (
                        f"{origin}/opinie/nowa?order={order.id}&item={item.id}&token={token}"
                    ),
                    "unsubscribe_url": f"{origin}/konto/dane",
                },
                idempotency_key=f"review-request:{item.id}",
                order_id=order.id,
            )
            session.add(ReviewRequest(order_item_id=item.id, order_id=order.id))
            queued += 1
    return queued


async def review_request_scheduler(interval_seconds: int = 3600) -> None:
    while True:
        await asyncio.sleep(interval_seconds)
        try:
            await queue_review_requests()
        except asyncio.CancelledError:
            raise
        except Exception as error:
            logger.error("Planowanie próśb o opinię nie powiodło się [%s].", type(error).__name__)
