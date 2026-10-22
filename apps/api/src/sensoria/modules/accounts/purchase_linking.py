"""Verified-email reconciliation of previously guest-owned purchases.

The caller owns the transaction. This service never commits and only attaches
unowned, paid orders whose normalized checkout email matches a verified account.
Dependent vouchers and future entitlements remain attached through order items.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from sensoria.modules.orders.checkout import normalize_nip
from sensoria.modules.orders.models import Cart, Order, OrderConsent, OrderItem
from sensoria.modules.vouchers.models import Voucher, VoucherExtensionRequest
from sensoria.shared.audit_log import ActorType, AuditLog
from sensoria.shared.errors import DomainError

from .address_fingerprint import address_fingerprint
from .models import (
    ConsentGuestImport,
    Customer,
    CustomerAddress,
    CustomerBillingProfile,
    CustomerConsent,
)

ReconciliationSource = Literal[
    "registration",
    "email_verification",
    "password_login",
    "login_link",
    "manual",
    "payment",
    "oauth",
    "email_code",
]


@dataclass(frozen=True, slots=True)
class PurchaseLinkingResult:
    orders_linked: int = 0
    vouchers_linked: int = 0
    entitlements_linked: int = 0
    addresses_added: int = 0
    billing_profiles_added: int = 0
    conflicts: int = 0
    skipped: int = 0

    def as_dict(self) -> dict[str, int]:
        return asdict(self)


def _safe_address(raw: Any) -> dict[str, str] | None:
    if not isinstance(raw, dict):
        return None
    street = raw.get("street")
    postal_code = raw.get("postal_code")
    city = raw.get("city")
    if not all(isinstance(value, str) and value.strip() for value in (street, postal_code, city)):
        return None
    assert isinstance(street, str)
    assert isinstance(postal_code, str)
    assert isinstance(city, str)
    return {
        "street": " ".join(street.split()),
        "postal_code": " ".join(postal_code.split()),
        "city": " ".join(city.split()),
    }


async def _import_order_data(
    session: AsyncSession, customer: Customer, order: Order
) -> tuple[int, int]:
    addresses_added = 0
    billing_added = 0
    shipping = order.shipping_data if isinstance(order.shipping_data, dict) else {}
    # Pickup locations and home addresses are saved as separate typed destinations.
    address_type: str | None = None
    address: dict[str, str] | None = None
    if shipping.get("method") == "courier":
        address = _safe_address(shipping.get("address"))
        address_type = "address"
    elif shipping.get("method") == "parcel_locker":
        point = order.delivery_point_snapshot
        if isinstance(point, dict) and all(
            isinstance(point.get(key), str) and point[key].strip()
            for key in ("code", "name", "street", "postal_code", "city")
        ):
            address = {
                key: str(point[key]).strip()
                for key in ("code", "name", "street", "postal_code", "city")
            }
            address_type = "parcel_locker"
    if address is not None and address_type is not None:
        fingerprint = address_fingerprint(address_type, address)
        saved_addresses = list(
            (
                await session.scalars(
                    select(CustomerAddress).where(CustomerAddress.customer_id == customer.id)
                )
            ).all()
        )
        already_saved = any(
            row.address_type == address_type
            and address_fingerprint(address_type, row.address_snapshot) == fingerprint
            for row in saved_addresses
        )
        if not already_saved:
            has_default = any(row.is_default for row in saved_addresses)
            session.add(
                CustomerAddress(
                    customer_id=customer.id,
                    source_order_id=order.id,
                    label="Paczkomat z zamówienia"
                    if address_type == "parcel_locker"
                    else "Adres z zamówienia",
                    address_type=address_type,
                    is_default=not has_default,
                    fingerprint=fingerprint,
                    address_snapshot=address,
                )
            )
            addresses_added += 1

    invoice = order.invoice_data if isinstance(order.invoice_data, dict) else {}
    kind = invoice.get("kind")
    if kind not in {"private", "company"}:
        return addresses_added, billing_added
    existing_profile = await session.scalar(
        select(CustomerBillingProfile.id).where(
            CustomerBillingProfile.customer_id == customer.id,
            CustomerBillingProfile.kind == kind,
        )
    )
    if existing_profile is None:
        # Keep only the first historic profile for each buyer kind. Checkout snapshots
        # are never edited, and existing account settings are never overwritten.
        address = _safe_address(invoice.get("address"))
        buyer = invoice.get("buyer_snapshot")
        buyer = buyer if isinstance(buyer, dict) else {}
        first_name = str(buyer.get("first_name", "")).strip() or None
        last_name = str(buyer.get("last_name", "")).strip() or None
        company_name = str(invoice.get("company_name", "")).strip() or None
        normalized_nip: str | None = None
        if kind == "company" and isinstance(invoice.get("nip"), str):
            try:
                normalized_nip = normalize_nip(invoice["nip"])
            except DomainError:  # Invalid old billing snapshot must not poison other imports.
                normalized_nip = None
        has_identity = (kind == "company" and company_name and normalized_nip) or (
            kind == "private" and first_name and last_name
        )
        if has_identity or address is not None:
            session.add(
                CustomerBillingProfile(
                    customer_id=customer.id,
                    source_order_id=order.id,
                    kind=kind,
                    first_name=first_name if kind == "private" else None,
                    last_name=last_name if kind == "private" else None,
                    company_name=company_name if kind == "company" else None,
                    nip=normalized_nip if kind == "company" else None,
                    address_snapshot=address,
                )
            )
            billing_added += 1
    return addresses_added, billing_added


async def reconcile_guest_purchases(
    session: AsyncSession,
    customer_id: UUID,
    *,
    source: ReconciliationSource,
    at: datetime,
    dry_run: bool = False,
) -> PurchaseLinkingResult:
    """Attach eligible purchases atomically; never commit or transfer owned records.

    ``at`` is supplied by the trusted caller's clock. The account row and matching
    orders are locked to serialize logins and concurrent reconciliation attempts.
    """

    if source not in {
        "registration",
        "email_verification",
        "password_login",
        "login_link",
        "manual",
        "payment",
        "oauth",
        "email_code",
    }:
        raise ValueError("Unsupported purchase-linking source")
    if at.tzinfo is None or at.utcoffset() is None:
        raise ValueError("Purchase reconciliation requires a timezone-aware timestamp")
    customer = await session.scalar(
        select(Customer).where(Customer.id == customer_id).with_for_update()
    )
    if customer is None or customer.deleted_at is not None or customer.email_verified_at is None:
        return PurchaseLinkingResult()
    # Lock order is always customer row, then advisory key, then guest orders.
    # Auth routes already hold the customer row while consuming their token.
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:key))"),
        {"key": f"purchase-link:{customer_id}"},
    )

    email_match = func.lower(func.btrim(Order.email)) == customer.email
    candidate_rows = (
        await session.execute(
            select(Order, Cart)
            .join(Cart, Cart.id == Order.cart_id)
            .where(
                email_match,
                Order.status == "paid",
                Order.customer_id.is_(None),
                or_(Cart.customer_id.is_(None), Cart.customer_id == customer.id),
            )
            .order_by(Order.id)
            .with_for_update(of=[Order, Cart])
        )
    ).all()
    conflicts = int(
        await session.scalar(
            select(func.count())
            .select_from(Order)
            .join(Cart, Cart.id == Order.cart_id)
            .where(
                email_match,
                Order.status == "paid",
                Order.customer_id.is_(None),
                Cart.customer_id.is_not(None),
                Cart.customer_id != customer.id,
            )
        )
        or 0
    )
    candidate_ids = [order.id for order, _cart in candidate_rows]
    conflicting_voucher_orders: set[UUID] = set()
    if candidate_ids:
        conflicting_voucher_orders = set(
            (
                await session.scalars(
                    select(OrderItem.order_id)
                    .join(Voucher, Voucher.order_item_id == OrderItem.id)
                    .join(
                        VoucherExtensionRequest,
                        VoucherExtensionRequest.voucher_id == Voucher.id,
                    )
                    .where(
                        OrderItem.order_id.in_(candidate_ids),
                        VoucherExtensionRequest.customer_id != customer.id,
                    )
                    .distinct()
                )
            ).all()
        )
        conflicts += len(conflicting_voucher_orders)
    if dry_run:
        return PurchaseLinkingResult(
            orders_linked=len(candidate_rows) - len(conflicting_voucher_orders),
            conflicts=conflicts,
        )

    address_count = 0
    billing_count = 0
    for order, cart in candidate_rows:
        # Recheck after row lock; Cart identity may have changed independently.
        if order.customer_id is not None or cart.customer_id not in {None, customer.id}:
            conflicts += 1
            continue
        if order.id in conflicting_voucher_orders:
            continue
        order.customer_id = customer.id
        new_addresses, new_profiles = await _import_order_data(session, customer, order)
        address_count += new_addresses
        billing_count += new_profiles
        checkout_consents = list(
            (
                await session.scalars(select(OrderConsent).where(OrderConsent.order_id == order.id))
            ).all()
        )
        for checkout_consent in checkout_consents:
            event = await session.scalar(
                select(CustomerConsent)
                .where(CustomerConsent.order_consent_id == checkout_consent.id)
                .with_for_update()
            )
            if event is None or event.customer_id is not None:
                continue
            event.customer_id = customer.id
            event.email = None
            session.add(
                ConsentGuestImport(
                    order_consent_id=checkout_consent.id,
                    customer_id=customer.id,
                    consent_event_id=event.id,
                )
            )

    await session.flush()
    linked = sum(1 for order, _cart in candidate_rows if order.customer_id == customer.id)
    linked_order_ids = [
        order.id for order, _cart in candidate_rows if order.customer_id == customer.id
    ]
    voucher_count = 0
    if linked_order_ids:
        voucher_count = int(
            await session.scalar(
                select(func.count())
                .select_from(Voucher)
                .join(OrderItem, OrderItem.id == Voucher.order_item_id)
                .where(OrderItem.order_id.in_(linked_order_ids))
            )
            or 0
        )
    result = PurchaseLinkingResult(
        orders_linked=linked,
        # No entitlements table exists in the current checkout/payment implementation;
        # the orders and order_items are the ownership chain for all attached purchases.
        vouchers_linked=voucher_count,
        entitlements_linked=0,
        addresses_added=address_count,
        billing_profiles_added=billing_count,
        conflicts=conflicts,
        skipped=max(0, len(candidate_rows) - linked),
    )
    if any(result.as_dict().values()):
        session.add(
            AuditLog(
                actor_type=ActorType.CUSTOMER if source != "manual" else ActorType.SYSTEM,
                actor_id=customer.id if source != "manual" else None,
                entity_type="customer",
                entity_id=customer.id,
                action="guest_purchases_reconciled",
                payload={"source": source, **result.as_dict()},
            )
        )
    return result
