"""Transactional manual shipment operations and tracking URL policy."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote, urlsplit
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from sensoria.modules.catalog.models import Product
from sensoria.modules.catalog.types import ProductKind
from sensoria.shared.app_settings import AppSetting
from sensoria.shared.audit_log import ActorType, AuditLog
from sensoria.shared.errors import DomainError

from .models import Order, OrderItem, Shipment, ShipmentHistory, ShipmentNotificationJob

TRACKING_SETTING_KEY = "orders.shipment_tracking.v1"
_CONTROL_CHARACTERS = re.compile(r"[\x00-\x1f\x7f]")
_INPOST_24_DIGITS = re.compile(r"\d{24}")


class CarrierTrackingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str = Field(min_length=1, max_length=40)
    template: str = Field(min_length=1, max_length=500)
    host: str = Field(min_length=1, max_length=253)


class TrackingPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")
    carriers: dict[str, CarrierTrackingConfig]


@dataclass(frozen=True, slots=True)
class TrackingLink:
    url: str | None
    warning: str | None


def validate_tracking_number(value: str) -> tuple[str, str | None]:
    """Preserve the carrier's identifier while rejecting empty/control data."""
    number = value.strip()
    if not number:
        raise DomainError("SHIPMENT_TRACKING_REQUIRED", "Wpisz numer nadania.", 422)
    if len(number) > 160 or _CONTROL_CHARACTERS.search(number):
        raise DomainError(
            "SHIPMENT_TRACKING_INVALID", "Numer nadania ma nieprawidłowy format.", 422
        )
    warning = None
    if not _INPOST_24_DIGITS.fullmatch(number):
        warning = "Numer odbiega od typowego 24-cyfrowego numeru InPost. Sprawdź go przed zapisem."
    return number, warning


async def load_tracking_policy(session: AsyncSession) -> TrackingPolicy:
    setting = await session.scalar(select(AppSetting).where(AppSetting.key == TRACKING_SETTING_KEY))
    if setting is None:
        raise DomainError(
            "TRACKING_SETTINGS_MISSING", "Śledzenie przesyłek nie jest skonfigurowane.", 503
        )
    try:
        policy = TrackingPolicy.model_validate(setting.value)
    except (ValidationError, TypeError, ValueError):
        raise DomainError(
            "TRACKING_SETTINGS_INVALID", "Konfiguracja śledzenia jest nieprawidłowa.", 503
        ) from None
    for key, carrier in policy.carriers.items():
        parsed = urlsplit(carrier.template.replace("{tracking_number}", "PLACEHOLDER"))
        if (
            not re.fullmatch(r"[a-z0-9_-]{1,40}", key)
            or parsed.scheme != "https"
            or parsed.hostname is None
            or parsed.hostname.casefold() != carrier.host.casefold()
            or "{tracking_number}" not in carrier.template
            or carrier.template.count("{tracking_number}") != 1
            or parsed.username is not None
            or parsed.password is not None
        ):
            raise DomainError(
                "TRACKING_SETTINGS_INVALID", "Konfiguracja śledzenia jest nieprawidłowa.", 503
            )
    return policy


def build_tracking_url(policy: TrackingPolicy, carrier_key: str, number: str) -> str:
    config = policy.carriers.get(carrier_key)
    if config is None:
        raise DomainError("SHIPMENT_CARRIER_INVALID", "Wybierz skonfigurowanego przewoźnika.", 422)
    url = config.template.replace("{tracking_number}", quote(number, safe=""))
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname is None
        or parsed.hostname.casefold() != config.host.casefold()
    ):
        raise DomainError(
            "TRACKING_SETTINGS_INVALID", "Nie można bezpiecznie zbudować adresu śledzenia.", 503
        )
    return url


def build_shipment_tracking_url(policy: TrackingPolicy, carrier: str, number: str) -> str | None:
    """Resolve a stored carrier label through the trusted policy, never a stored URL."""
    matches = [key for key, config in policy.carriers.items() if config.label == carrier]
    if len(matches) != 1:
        return None
    try:
        return build_tracking_url(policy, matches[0], number)
    except DomainError:
        return None


async def _lock_order(session: AsyncSession, order_id: UUID) -> Order:
    order = await session.scalar(select(Order).where(Order.id == order_id).with_for_update())
    if order is None:
        raise DomainError("ORDER_NOT_FOUND", "Nie znaleziono zamówienia.", 404)
    return order


async def _has_books(session: AsyncSession, order_id: UUID) -> bool:
    return bool(
        await session.scalar(
            select(OrderItem.id)
            .join(Product, Product.id == OrderItem.product_id)
            .where(OrderItem.order_id == order_id, Product.kind == ProductKind.BOOK)
            .limit(1)
        )
    )


async def mark_fulfillment_ready_after_payment(
    session: AsyncSession, *, order_id: UUID, paid_at: datetime
) -> datetime | None:
    """[33] hook: set the shipment waiting-age origin inside the payment transaction.

    Caller owns the transaction and has already verified payment. This function does
    not commit and never touches inventory or digital fulfillment.
    """
    if paid_at.tzinfo is None or paid_at.utcoffset() is None:
        raise ValueError("Czas potwierdzenia płatności musi zawierać strefę.")
    order = await session.scalar(select(Order).where(Order.id == order_id).with_for_update())
    if order is None:
        raise DomainError("ORDER_NOT_FOUND", "Nie znaleziono zamówienia.", 404)
    if order.status != "paid":
        raise DomainError(
            "ORDER_NOT_PAID", "Gotowość realizacji wymaga potwierdzonej płatności.", 409
        )
    if not await _has_books(session, order.id):
        return None
    if order.fulfillment_ready_at is None:
        order.fulfillment_ready_at = paid_at.astimezone(UTC)
        await session.flush()
    return order.fulfillment_ready_at


async def ship_order(
    session: AsyncSession,
    *,
    order_id: UUID,
    carrier: str,
    tracking_number: str,
    actor_id: UUID,
    now: datetime | None = None,
) -> Shipment:
    """Create a shipment atomically with fulfillment, audit, and durable notice intent."""
    if now is not None and (now.tzinfo is None or now.utcoffset() is None):
        raise ValueError("Czas nadania musi zawierać strefę czasową.")
    number, _warning = validate_tracking_number(tracking_number)
    async with session.begin():
        order = await _lock_order(session, order_id)
        if order.status != "paid":
            raise DomainError(
                "SHIPMENT_ORDER_NOT_PAID", "Można nadać wyłącznie opłacone zamówienie.", 409
            )
        if not await _has_books(session, order_id):
            raise DomainError(
                "SHIPMENT_NO_PHYSICAL_ITEMS",
                "Zamówienie nie zawiera produktów wymagających wysyłki.",
                409,
            )
        shipping = order.shipping_data or {}
        if shipping.get("method") not in {"parcel_locker", "courier"}:
            raise DomainError(
                "SHIPMENT_METHOD_INVALID", "Metoda dostawy nie wymaga nadania przesyłki.", 409
            )
        policy = await load_tracking_policy(session)
        carrier_config = policy.carriers.get(carrier)
        if carrier_config is None:
            raise DomainError(
                "SHIPMENT_CARRIER_INVALID", "Wybierz skonfigurowanego przewoźnika.", 422
            )
        existing = await session.scalar(
            select(Shipment).where(Shipment.order_id == order_id).with_for_update()
        )
        if existing is not None:
            if existing.carrier == carrier_config.label and existing.tracking_number == number:
                return existing
            raise DomainError(
                "SHIPMENT_ALREADY_EXISTS", "Przesyłka już istnieje. Użyj korekty numeru.", 409
            )
        if order.fulfillment_status in {
            "cancelled",
            "shipped",
            "delivered",
            "ready_for_pickup",
            "picked_up",
        }:
            raise DomainError("SHIPMENT_STATE_CONFLICT", "Zamówienie nie oczekuje na nadanie.", 409)
        timestamp = (now or datetime.now(UTC)).astimezone(UTC)
        shipment = Shipment(
            order_id=order.id,
            carrier=carrier_config.label,
            tracking_number=number,
            shipped_at=timestamp,
            status="shipped",
            created_by=actor_id,
        )
        session.add(shipment)
        await session.flush()
        session.add(
            ShipmentHistory(
                shipment_id=shipment.id,
                new_carrier=shipment.carrier,
                new_tracking_number=number,
                changed_at=timestamp,
                performed_by=actor_id,
                operation="created",
            )
        )
        order.fulfillment_status = "shipped"
        session.add(
            AuditLog(
                actor_type=ActorType.ADMINISTRATOR,
                actor_id=actor_id,
                entity_type="shipment",
                entity_id=shipment.id,
                action="shipment.created",
                payload={
                    "order_id": str(order.id),
                    "carrier": carrier,
                    "fulfillment_status": "shipped",
                },
            )
        )
        session.add(
            ShipmentNotificationJob(
                order_id=order.id,
                shipment_id=shipment.id,
                kind="shipped",
                idempotency_key=f"shipment:{shipment.id}:shipped",
                status="pending",
            )
        )
        await session.flush()
    return shipment


async def correct_shipment(
    session: AsyncSession,
    *,
    order_id: UUID,
    carrier: str,
    tracking_number: str,
    actor_id: UUID,
    reason: str,
    resend_notification: bool = False,
    operation_key: str,
) -> Shipment:
    number, _warning = validate_tracking_number(tracking_number)
    reason = " ".join(reason.split())
    if not reason or len(reason) > 500:
        raise DomainError("SHIPMENT_CORRECTION_REASON_REQUIRED", "Podaj powód korekty numeru.", 422)
    if not operation_key or len(operation_key) > 120:
        raise DomainError(
            "SHIPMENT_IDEMPOTENCY_REQUIRED", "Nie można bezpiecznie ponowić korekty.", 422
        )
    async with session.begin():
        order = await _lock_order(session, order_id)
        shipment = await session.scalar(
            select(Shipment).where(Shipment.order_id == order_id).with_for_update()
        )
        if shipment is None:
            raise DomainError("SHIPMENT_NOT_FOUND", "Nie znaleziono przesyłki.", 404)
        if shipment.status != "shipped":
            raise DomainError(
                "SHIPMENT_STATE_CONFLICT", "Nie można poprawić zakończonej przesyłki.", 409
            )
        policy = await load_tracking_policy(session)
        config = policy.carriers.get(carrier)
        if config is None:
            raise DomainError(
                "SHIPMENT_CARRIER_INVALID", "Wybierz skonfigurowanego przewoźnika.", 422
            )
        key = f"shipment-correction:{shipment.id}:{operation_key}"
        prior = await session.scalar(
            select(ShipmentHistory).where(
                ShipmentHistory.shipment_id == shipment.id,
                ShipmentHistory.operation == "corrected",
                ShipmentHistory.operation_key == operation_key,
            )
        )
        if prior is not None:
            prior_resend = await session.scalar(
                select(ShipmentNotificationJob.id).where(
                    ShipmentNotificationJob.idempotency_key == key
                )
            )
            if (
                prior.new_carrier != config.label
                or prior.new_tracking_number != number
                or prior.reason != reason
                or (prior_resend is not None) != resend_notification
            ):
                raise DomainError(
                    "SHIPMENT_IDEMPOTENCY_CONFLICT",
                    "Klucz ponowienia został już użyty dla innych danych korekty.",
                    409,
                )
            return shipment
        in_flight = await session.scalar(
            select(ShipmentNotificationJob.id)
            .where(
                ShipmentNotificationJob.shipment_id == shipment.id,
                ShipmentNotificationJob.status == "sending",
            )
            .limit(1)
        )
        if in_flight is not None:
            raise DomainError(
                "SHIPMENT_NOTIFICATION_IN_FLIGHT",
                "Powiadomienie jest właśnie przekazywane. Spróbuj ponownie za chwilę.",
                409,
            )
        previous_carrier, previous_number = shipment.carrier, shipment.tracking_number
        shipment.carrier, shipment.tracking_number = config.label, number
        session.add(
            ShipmentHistory(
                shipment_id=shipment.id,
                previous_carrier=previous_carrier,
                new_carrier=config.label,
                previous_tracking_number=previous_number,
                new_tracking_number=number,
                performed_by=actor_id,
                operation="corrected",
                operation_key=operation_key,
                reason=reason,
            )
        )
        session.add(
            AuditLog(
                actor_type=ActorType.ADMINISTRATOR,
                actor_id=actor_id,
                entity_type="shipment",
                entity_id=shipment.id,
                action="shipment.corrected",
                payload={"order_id": str(order.id), "resend_notification": resend_notification},
            )
        )
        if resend_notification:
            session.add(
                ShipmentNotificationJob(
                    order_id=order.id,
                    shipment_id=shipment.id,
                    kind="manual_resend",
                    idempotency_key=key,
                    status="pending",
                )
            )
        await session.flush()
    return shipment


async def mark_shipment_delivered(
    session: AsyncSession, *, order_id: UUID, actor_id: UUID, now: datetime | None = None
) -> Shipment:
    timestamp = (now or datetime.now(UTC)).astimezone(UTC)
    async with session.begin():
        order = await _lock_order(session, order_id)
        if order.status != "paid":
            raise DomainError(
                "SHIPMENT_ORDER_NOT_PAID",
                "Nie można oznaczyć nieopłaconego zamówienia jako dostarczonego.",
                409,
            )
        shipment = await session.scalar(
            select(Shipment).where(Shipment.order_id == order_id).with_for_update()
        )
        if shipment is not None and shipment.status == "delivered":
            return shipment
        if shipment is None or shipment.status != "shipped":
            raise DomainError(
                "SHIPMENT_STATE_CONFLICT",
                "Przesyłka nie oczekuje na potwierdzenie dostarczenia.",
                409,
            )
        shipment.status, shipment.delivered_at = "delivered", timestamp
        # Keep mixed digital order independent: only physical fulfillment changes.
        order.fulfillment_status = "delivered"
        session.add(
            ShipmentHistory(
                shipment_id=shipment.id,
                previous_carrier=shipment.carrier,
                new_carrier=shipment.carrier,
                previous_tracking_number=shipment.tracking_number,
                new_tracking_number=shipment.tracking_number,
                changed_at=timestamp,
                performed_by=actor_id,
                operation="delivered",
            )
        )
        session.add(
            AuditLog(
                actor_type=ActorType.ADMINISTRATOR,
                actor_id=actor_id,
                entity_type="shipment",
                entity_id=shipment.id,
                action="shipment.delivered",
                payload={"order_id": str(order.id)},
            )
        )
    return shipment


async def mark_pickup_ready(
    session: AsyncSession, *, order_id: UUID, actor_id: UUID, now: datetime | None = None
) -> Order:
    timestamp = (now or datetime.now(UTC)).astimezone(UTC)
    async with session.begin():
        order = await _lock_order(session, order_id)
        if (
            order.status != "paid"
            or (order.shipping_data or {}).get("method") != "pickup_in_person"
        ):
            raise DomainError(
                "PICKUP_ORDER_INVALID",
                "To zamówienie nie kwalifikuje się do odbioru osobistego.",
                409,
            )
        if not await _has_books(session, order.id):
            raise DomainError(
                "PICKUP_NO_PHYSICAL_ITEMS", "Zamówienie nie zawiera książek do odbioru.", 409
            )
        if order.fulfillment_status != "awaiting_fulfillment":
            if order.fulfillment_status == "ready_for_pickup":
                return order
            raise DomainError(
                "PICKUP_STATE_CONFLICT", "Zamówienie nie oczekuje na przygotowanie odbioru.", 409
            )
        order.fulfillment_status = "ready_for_pickup"
        order.pickup_ready_at, order.pickup_ready_by = timestamp, actor_id
        session.add(
            AuditLog(
                actor_type=ActorType.ADMINISTRATOR,
                actor_id=actor_id,
                entity_type="order",
                entity_id=order.id,
                action="order.pickup_ready",
                payload={"fulfillment_status": "ready_for_pickup"},
            )
        )
        session.add(
            ShipmentNotificationJob(
                order_id=order.id,
                kind="pickup_ready",
                idempotency_key=f"order:{order.id}:pickup-ready",
            )
        )
    return order


async def mark_picked_up(
    session: AsyncSession, *, order_id: UUID, actor_id: UUID, now: datetime | None = None
) -> Order:
    timestamp = (now or datetime.now(UTC)).astimezone(UTC)
    async with session.begin():
        order = await _lock_order(session, order_id)
        if order.status != "paid" or order.fulfillment_status != "ready_for_pickup":
            if order.status == "paid" and order.fulfillment_status == "picked_up":
                return order
            raise DomainError(
                "PICKUP_STATE_CONFLICT", "Zamówienie nie jest gotowe do odbioru.", 409
            )
        order.fulfillment_status = "picked_up"
        order.picked_up_at, order.picked_up_by = timestamp, actor_id
        session.add(
            AuditLog(
                actor_type=ActorType.ADMINISTRATOR,
                actor_id=actor_id,
                entity_type="order",
                entity_id=order.id,
                action="order.picked_up",
                payload={"fulfillment_status": "picked_up"},
            )
        )
    return order


async def shipping_dashboard(
    session: AsyncSession, *, at: datetime | None = None
) -> dict[str, Any]:
    """Count paid, physical parcel orders; age starts at trusted paid-ready time."""
    now = at or datetime.now(UTC)
    eligible = (
        select(Order.id, Order.fulfillment_ready_at)
        .join(OrderItem, OrderItem.order_id == Order.id)
        .join(Product, Product.id == OrderItem.product_id)
        .where(
            Order.status == "paid",
            Order.fulfillment_status == "awaiting_fulfillment",
            Order.fulfillment_ready_at.is_not(None),
            Product.kind == ProductKind.BOOK,
            Order.shipping_data["method"].astext.in_(["parcel_locker", "courier"]),
        )
        .distinct()
    ).subquery()
    count, oldest = await session.execute(
        select(func.count(eligible.c.id), func.min(eligible.c.fulfillment_ready_at))
    )
    return {
        "count": int(count),
        "oldest_ready_at": oldest,
        "oldest_age_seconds": max(0, int((now - oldest).total_seconds())) if oldest else None,
    }
