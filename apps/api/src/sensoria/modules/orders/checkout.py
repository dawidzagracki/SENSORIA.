"""Guest checkout order creation and its temporary stock reservations."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date, timedelta
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from sensoria.config import get_settings
from sensoria.modules.accounts.models import ConsentTextVersion, CustomerConsent
from sensoria.modules.accounts.privacy import CONSENT_COPY
from sensoria.modules.catalog.models import Product, ProductBook, ProductVoucher
from sensoria.modules.catalog.types import ProductKind, ProductStatus
from sensoria.modules.payments.stripe_client import stripe_configured
from sensoria.modules.payments.tokens import order_access_token
from sensoria.modules.vouchers.gifts import load_gift_settings, scheduled_delivery_at
from sensoria.shared.app_settings import AppSetting
from sensoria.shared.errors import DomainError

from .calculator import CartCalculator, CartLineInput
from .delivery import resolve_delivery
from .models import (
    Cart,
    CartItem,
    DiscountCode,
    DiscountUseReservation,
    Order,
    OrderConsent,
    OrderItem,
    StockReservation,
)
from .schemas import CheckoutInput, CheckoutResponse, PickupPointSnapshot
from .service import _token_digest, discount_calculation_input

CONSENT_SETTING_KEY = "orders.checkout.consents.v1"
CONSENT_COPY_KEYS = ("terms", "digital", "marketing")
RESERVATION_MINUTES = 24 * 60
_NIP_WEIGHTS = (6, 5, 7, 2, 3, 4, 5, 6, 7)


def normalize_nip(value: str) -> str:
    """Normalize permitted separators and verify the Polish NIP checksum."""
    digits = re.sub(r"[\s-]", "", value)
    if not re.fullmatch(r"\d{10}", digits):
        raise DomainError("CHECKOUT_NIP_INVALID", "Podaj prawidłowy, 10-cyfrowy NIP.", 422)
    checksum = (
        sum(int(digit) * weight for digit, weight in zip(digits[:9], _NIP_WEIGHTS, strict=True))
        % 11
    )
    if checksum == 10 or checksum != int(digits[9]):
        raise DomainError(
            "CHECKOUT_NIP_INVALID", "Podany NIP ma nieprawidłową sumę kontrolną.", 422
        )
    return digits


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _request_hash(payload: CheckoutInput) -> str:
    data = payload.model_dump(mode="json")
    return _hash(json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


async def checkout_consent_config(session: AsyncSession) -> dict[str, str]:
    """Return only the public, versioned consent text needed by the checkout form."""
    setting = await session.scalar(select(AppSetting).where(AppSetting.key == CONSENT_SETTING_KEY))
    if setting is None or not isinstance(setting.value, dict):
        raise DomainError(
            "CHECKOUT_CONSENTS_UNAVAILABLE", "Konfiguracja zgód nie jest dostępna.", 503
        )
    value = setting.value
    if not isinstance(value.get("version"), str) or any(
        not isinstance(value.get(key), str) for key in CONSENT_COPY_KEYS
    ):
        raise DomainError(
            "CHECKOUT_CONSENTS_UNAVAILABLE", "Konfiguracja zgód jest nieprawidłowa.", 503
        )
    return {
        "consent_version": value["version"],
        "terms_text": value["terms"],
        "digital_text": value["digital"],
        "marketing_text": value["marketing"],
    }


def _invoice(payload: CheckoutInput) -> dict[str, Any]:
    address = (
        payload.shipping_address if payload.invoice_same_as_shipping else payload.invoice_address
    )
    return {
        "kind": payload.invoice_kind,
        "buyer_snapshot": {
            "first_name": payload.first_name.strip() if payload.first_name else None,
            "last_name": payload.last_name.strip() if payload.last_name else None,
        },
        "company_name": payload.company_name,
        "nip": normalize_nip(payload.nip)
        if payload.invoice_kind == "company" and payload.nip
        else None,
        "address": address.model_dump() if address else None,
        "same_as_shipping": payload.invoice_same_as_shipping
        and payload.shipping_address is not None,
    }


def _payment_integration() -> str:
    return "stripe" if stripe_configured(get_settings()) else "not_configured"


async def create_guest_order(
    session: AsyncSession,
    token: str | None,
    idempotency_key: str,
    payload: CheckoutInput,
    *,
    verified_pickup_point: PickupPointSnapshot | None = None,
    consent_ip_hash: str | None = None,
) -> CheckoutResponse:
    """Create a pending-payment order in one transaction; never claim a payment succeeded."""
    if token is None or not 40 <= len(token) <= 128:
        raise DomainError("CHECKOUT_CART_NOT_FOUND", "Nie znaleziono aktywnego koszyka.", 404)
    try:
        digest = _token_digest(token)
    except UnicodeEncodeError:
        raise DomainError(
            "CHECKOUT_CART_NOT_FOUND", "Nie znaleziono aktywnego koszyka.", 404
        ) from None
    if not idempotency_key or len(idempotency_key) > 200:
        raise DomainError("CHECKOUT_IDEMPOTENCY_REQUIRED", "Nieprawidłowy klucz ponowienia.", 422)
    key_hash = _hash(idempotency_key)
    body_hash = _request_hash(payload)

    async with session.begin():
        public_policy = await checkout_consent_config(session)
        policy = {
            "version": public_policy["consent_version"],
            "terms": public_policy["terms_text"],
            "digital": public_policy["digital_text"],
            "marketing": public_policy["marketing_text"],
            "review_requests": CONSENT_COPY["review_requests"][1],
        }
        cart = await session.scalar(
            select(Cart)
            .where(
                Cart.session_token_hash == digest,
                Cart.customer_id.is_(None),
                Cart.expires_at > func.now(),
            )
            .with_for_update()
        )
        if cart is None:
            raise DomainError("CHECKOUT_CART_NOT_FOUND", "Koszyk wygasł lub nie istnieje.", 404)
        prior = await session.scalar(
            select(Order).where(Order.cart_id == cart.id).with_for_update()
        )
        if prior is not None:
            if prior.idempotency_key_hash != key_hash or prior.request_hash != body_hash:
                raise DomainError(
                    "CHECKOUT_ALREADY_CREATED",
                    "Dla tego koszyka zapisano już zamówienie. "
                    "Rozpocznij nowy koszyk, aby złożyć kolejne.",
                    409,
                )
            return CheckoutResponse(
                order_id=prior.id,
                status=prior.status,
                amount_due_grosz=prior.amount_due_grosz,
                payment_integration=_payment_integration(),
                payment_url=None,
                access_token=order_access_token(prior.id),
                message=(
                    "Zamówienie oczekuje na płatność. Rozpocznij ją przez endpoint sesji płatności."
                ),
            )

        rows = list(
            (
                await session.execute(
                    select(CartItem, Product)
                    .join(Product, Product.id == CartItem.product_id)
                    .where(CartItem.cart_id == cart.id)
                    .order_by(Product.id, CartItem.id)
                    .options(
                        selectinload(Product.book),
                        selectinload(Product.voucher).selectinload(ProductVoucher.variants),
                    )
                    .with_for_update(of=Product)
                )
            ).all()
        )
        if not rows:
            raise DomainError("CHECKOUT_CART_EMPTY", "Koszyk jest pusty.", 409)
        checkout_now = await session.scalar(select(func.now()))
        if checkout_now is None:
            raise DomainError(
                "CHECKOUT_CLOCK_UNAVAILABLE", "Nie można ustalić czasu zamówienia.", 503
            )

        gift_inputs = {entry.cart_item_id: entry for entry in payload.gifts}
        if len(gift_inputs) != len(payload.gifts):
            raise DomainError("CHECKOUT_GIFT_DUPLICATE", "Dane prezentu powtórzono.", 422)
        voucher_cart_ids = {
            item.id for item, product in rows if product.kind is ProductKind.VOUCHER
        }
        gift_cart_ids = {item.id for item, _product in rows if item.gift_data is not None}
        if set(gift_inputs) != gift_cart_ids or not set(gift_inputs).issubset(voucher_cart_ids):
            raise DomainError(
                "CHECKOUT_GIFT_MISMATCH",
                "Odśwież koszyk i uzupełnij dane dla każdej pozycji prezentowej.",
                422,
            )
        gift_settings = await load_gift_settings(session)
        gift_snapshots: dict[Any, dict[str, Any]] = {}
        for cart_item_id, gift in gift_inputs.items():
            if gift.delivery_mode == "immediate":
                deliver_at = checkout_now
            else:
                try:
                    selected_date = date.fromisoformat(gift.delivery_date or "")
                except ValueError:
                    raise DomainError(
                        "GIFT_DATE_INVALID", "Podaj prawidłową datę wysyłki.", 422
                    ) from None
                deliver_at = scheduled_delivery_at(
                    selected_date,
                    now=checkout_now,
                    local_time=gift_settings["local_send_time"],
                    timezone=ZoneInfo(gift_settings["timezone"]),
                )
            gift_snapshots[cart_item_id] = {
                "version": 1,
                "is_gift": True,
                "recipient_name": gift.recipient_name,
                "recipient_email": gift.recipient_email,
                "dedication": gift.dedication,
                "delivery_mode": gift.delivery_mode,
                "delivery_date": gift.delivery_date,
                "gift_delivery_at": deliver_at.isoformat(),
                "local_send_time": gift_settings["local_send_time"],
                "timezone": gift_settings["timezone"],
            }

        needs_shipping = any(product.requires_shipping for _item, product in rows)
        if needs_shipping:
            for _item, product in rows:
                if product.requires_shipping and (
                    product.book is None
                    or product.book.weight_grams is None
                    or product.book.length_mm is None
                    or product.book.width_mm is None
                    or product.book.height_mm is None
                ):
                    raise DomainError(
                        "CHECKOUT_BOOK_SHIPPING_DATA_MISSING",
                        f"Brakuje wagi lub wymiarów książki „{product.name}”. "
                        "Skontaktuj się ze sklepem.",
                        409,
                    )
            if not (
                payload.first_name
                and payload.last_name
                and payload.phone
                and payload.delivery_method
            ):
                raise DomainError(
                    "CHECKOUT_SHIPPING_REQUIRED",
                    "Uzupełnij dane i metodę dostawy dla książki.",
                    422,
                )
            if (
                cart.delivery_method is not None
                and cart.delivery_method != payload.delivery_method.value
            ):
                raise DomainError(
                    "CHECKOUT_DELIVERY_CHANGED",
                    "Metoda dostawy zmieniła się. Odśwież podsumowanie i wybierz ją ponownie.",
                    409,
                )
            if payload.delivery_method.value == "parcel_locker":
                saved_point = cart.delivery_point_snapshot
                if (
                    saved_point is None
                    or verified_pickup_point is None
                    or saved_point.get("code") != verified_pickup_point.code
                    or payload.pickup_point_id not in (None, verified_pickup_point.code)
                ):
                    raise DomainError(
                        "CHECKOUT_PICKUP_REQUIRED",
                        "Punkt Paczkomat nie jest wybrany albo wymaga ponownego potwierdzenia.",
                        422,
                    )
            elif payload.delivery_method.value == "courier" and payload.shipping_address is None:
                raise DomainError(
                    "CHECKOUT_SHIPPING_REQUIRED", "Podaj adres dostawy kurierskiej.", 422
                )
        digital_products = [product for _item, product in rows if product.is_digital]
        if not payload.terms_accepted:
            raise DomainError(
                "CHECKOUT_TERMS_REQUIRED", "Zaakceptuj regulamin i politykę prywatności.", 422
            )
        if digital_products and not payload.digital_consent:
            raise DomainError(
                "CHECKOUT_DIGITAL_CONSENT_REQUIRED",
                "Zgoda na natychmiastowe udostępnienie treści cyfrowej jest wymagana.",
                422,
            )
        if payload.consent_version != policy["version"]:
            raise DomainError(
                "CHECKOUT_CONSENT_VERSION_CHANGED",
                "Treść zgód zmieniła się. Odśwież formularz i zapoznaj się z aktualną wersją.",
                409,
            )
        if payload.invoice_kind == "company":
            can_reuse_shipping = (
                payload.invoice_same_as_shipping
                and payload.delivery_method is not None
                and payload.delivery_method.value == "courier"
                and payload.shipping_address is not None
            )
            if not payload.invoice_address and not can_reuse_shipping:
                raise DomainError(
                    "CHECKOUT_INVOICE_ADDRESS_REQUIRED", "Podaj adres do faktury.", 422
                )
        if payload.invoice_same_as_shipping and (
            payload.delivery_method is None
            or payload.delivery_method.value != "courier"
            or payload.shipping_address is None
        ):
            raise DomainError(
                "CHECKOUT_INVOICE_ADDRESS_INVALID",
                "Adres Paczkomatu nie może być adresem do faktury.",
                422,
            )

        line_inputs: list[CartLineInput] = []
        order_items_by_product: dict[Any, OrderItem] = {}
        for item, product in rows:
            if (
                product.status is not ProductStatus.PUBLISHED
                or product.published_at is None
                or product.published_at > checkout_now
            ):
                raise DomainError(
                    "CHECKOUT_PRODUCT_UNAVAILABLE",
                    f"Produkt „{product.name}” nie jest już dostępny.",
                    409,
                )
            if product.kind is ProductKind.VOUCHER:
                variant = (
                    next((v for v in product.voucher.variants if v.id == item.variant_id), None)
                    if product.voucher
                    else None
                )
                current_price = variant.price if variant else None
            else:
                current_price = product.price
            if current_price is None or product.vat_rate is None:
                raise DomainError(
                    "CHECKOUT_PRODUCT_UNAVAILABLE",
                    f"Produkt „{product.name}” nie jest dostępny.",
                    409,
                )
            if (
                current_price != item.unit_price_snapshot
                or product.vat_rate != item.vat_rate_snapshot
            ):
                raise DomainError(
                    "CHECKOUT_PRICE_CHANGED",
                    f"Cena lub VAT produktu „{product.name}” zmieniły się. "
                    "Wróć do koszyka i zatwierdź aktualne warunki.",
                    409,
                )
            line_inputs.append(
                CartLineInput(
                    item.id, item.unit_price_snapshot, item.quantity, item.vat_rate_snapshot
                )
            )

        discount = None
        if cart.discount_code_id is not None:
            code = await session.scalar(
                select(DiscountCode)
                .where(DiscountCode.id == cart.discount_code_id)
                .with_for_update()
            )
            now = checkout_now
            if (
                code is None
                or not code.is_active
                or (code.valid_from and code.valid_from > now)
                or (code.valid_to and code.valid_to <= now)
                or (code.max_uses is not None and code.used_count >= code.max_uses)
            ):
                raise DomainError(
                    "CHECKOUT_DISCOUNT_INVALID",
                    "Kod rabatowy utracił ważność. Wróć do koszyka.",
                    409,
                )
            cart_gross_before_discount = int(
                await session.scalar(
                    select(
                        func.coalesce(func.sum(CartItem.unit_price_snapshot * CartItem.quantity), 0)
                    ).where(CartItem.cart_id == cart.id)
                )
                or 0
            )
            if cart_gross_before_discount < code.min_order_value:
                raise DomainError(
                    "CHECKOUT_DISCOUNT_MINIMUM",
                    "Koszyk nie spełnia już minimalnej wartości kodu rabatowego.",
                    409,
                )
            if code.max_uses is not None:
                active_holds = int(
                    await session.scalar(
                        select(func.count(DiscountUseReservation.id)).where(
                            DiscountUseReservation.discount_code_id == code.id,
                            DiscountUseReservation.expires_at > func.now(),
                        )
                    )
                    or 0
                )
                if code.used_count + active_holds >= code.max_uses:
                    raise DomainError(
                        "CHECKOUT_DISCOUNT_EXHAUSTED",
                        "Limit użyć kodu został zarezerwowany przez inne zamówienie.",
                        409,
                    )
            discount = discount_calculation_input(code)
        preliminary = CartCalculator.calculate(line_inputs, discount=discount)
        if needs_shipping:
            delivery_status, delivery = await resolve_delivery(
                session,
                requires_shipping=True,
                selected_method=payload.delivery_method.value if payload.delivery_method else None,
                products_gross_after_discount_grosz=preliminary.products_gross_grosz,
            )
        else:
            delivery_status, delivery = await resolve_delivery(
                session,
                requires_shipping=False,
                selected_method=None,
                products_gross_after_discount_grosz=preliminary.products_gross_grosz,
            )
        if delivery_status.requires_method_selection:
            raise DomainError("CHECKOUT_DELIVERY_REQUIRED", "Wybierz metodę dostawy.", 422)
        calculation = CartCalculator.calculate(line_inputs, discount=discount, delivery=delivery)

        # Lock book detail rows and account for other unexpired reservations before inserting holds.
        reservations: list[StockReservation] = []
        for item, product in rows:
            if not product.requires_shipping:
                continue
            book = await session.scalar(
                select(ProductBook).where(ProductBook.product_id == product.id).with_for_update()
            )
            reserved = int(
                await session.scalar(
                    select(func.coalesce(func.sum(StockReservation.quantity), 0))
                    .join(Order, Order.id == StockReservation.order_id)
                    .where(
                        StockReservation.product_id == product.id,
                        StockReservation.released_at.is_(None),
                        StockReservation.expires_at > func.now(),
                        Order.status == "pending_payment",
                    )
                )
                or 0
            )
            if book is None or book.stock_quantity - reserved < item.quantity:
                raise DomainError(
                    "CHECKOUT_STOCK_UNAVAILABLE",
                    f"Brak wystarczającej liczby egzemplarzy produktu „{product.name}”.",
                    409,
                )
            reservations.append(
                StockReservation(
                    product_id=product.id,
                    quantity=item.quantity,
                    expires_at=checkout_now + timedelta(minutes=RESERVATION_MINUTES),
                )
            )

        order = Order(
            cart_id=cart.id,
            public_number=f"SEN-{checkout_now.year}-{uuid4().hex[:16].upper()}",
            idempotency_key_hash=key_hash,
            request_hash=body_hash,
            email=payload.email,
            payment_method=payload.payment_method,
            status="pending_payment",
            invoice_data=_invoice(payload),
            shipping_data=(
                {
                    "first_name": payload.first_name,
                    "last_name": payload.last_name,
                    "phone": payload.phone,
                    "method": payload.delivery_method.value if payload.delivery_method else None,
                    "address": payload.shipping_address.model_dump()
                    if payload.shipping_address
                    else None,
                }
                if needs_shipping
                else None
            ),
            delivery_point_snapshot=(
                verified_pickup_point.model_dump(mode="json")
                if needs_shipping
                and payload.delivery_method is not None
                and payload.delivery_method.value == "parcel_locker"
                and verified_pickup_point is not None
                else None
            ),
            calculation_snapshot=calculation.model_dump(mode="json"),
            amount_due_grosz=calculation.amount_due_grosz,
            discount_code_id=cart.discount_code_id,
        )
        session.add(order)
        await session.flush()
        item_settlements = {entry.item_id: entry for entry in calculation.items}
        for item, product in rows:
            voucher_snapshot = None
            if product.kind is ProductKind.VOUCHER and product.voucher is not None:
                variant = next(
                    (entry for entry in product.voucher.variants if entry.id == item.variant_id),
                    None,
                )
                if variant is None:
                    raise DomainError(
                        "CHECKOUT_VARIANT_REQUIRED", "Wybierz dostępny wariant vouchera.", 409
                    )
                voucher_snapshot = {
                    "kind": ProductKind.VOUCHER.value,
                    "service_name": product.voucher.service_name,
                    "validity_months": product.voucher.validity_months,
                    "variant_kind": variant.kind.value,
                }
            gift_snapshot = gift_snapshots.get(item.id)
            order_item = OrderItem(
                order_id=order.id,
                product_id=product.id,
                variant_id=item.variant_id,
                quantity=item.quantity,
                unit_price_snapshot=item.unit_price_snapshot,
                vat_rate_snapshot=item.vat_rate_snapshot,
                item_settlement=item_settlements[item.id].model_dump(mode="json"),
                product_name_snapshot=product.name,
                voucher_snapshot=voucher_snapshot,
                gift_snapshot=gift_snapshot,
                shipping_snapshot=(
                    {
                        "weight_grams": product.book.weight_grams,
                        "length_mm": product.book.length_mm,
                        "width_mm": product.book.width_mm,
                        "height_mm": product.book.height_mm,
                        "quantity": item.quantity,
                    }
                    if product.requires_shipping and product.book is not None
                    else None
                ),
            )
            session.add(order_item)
            order_items_by_product[product.id] = order_item
        await session.flush()
        for reservation in reservations:
            reservation.order_id = order.id
            reservation.order_item_id = order_items_by_product[reservation.product_id].id
            session.add(reservation)
        if cart.discount_code_id is not None:
            session.add(
                DiscountUseReservation(
                    discount_code_id=cart.discount_code_id,
                    order_id=order.id,
                    expires_at=checkout_now + timedelta(minutes=RESERVATION_MINUTES),
                )
            )
        scopes = [str(product.id) for _item, product in rows]
        consent_rows = [
            ("terms", payload.terms_accepted),
            ("digital", payload.digital_consent),
            ("marketing", payload.marketing_consent),
        ]
        if payload.review_requests_consent:
            consent_rows.append(("review_requests", True))
        for kind, granted in consent_rows:
            if kind == "digital" and not digital_products:
                continue
            kind_version = (
                CONSENT_COPY["review_requests"][0]
                if kind == "review_requests"
                else policy["version"]
            )
            order_consent = OrderConsent(
                order_id=order.id,
                kind=kind,
                granted=granted,
                version=kind_version,
                displayed_text=policy[kind],
                scope=scopes,
                issuance_mode="immediate" if kind == "digital" else None,
            )
            session.add(order_consent)
            await session.flush()
            consent_type = {
                "terms": "checkout_terms",
                "digital": "checkout_digital",
                "marketing": "checkout_marketing",
                "review_requests": "review_requests",
            }[kind]
            text_version = await session.scalar(
                select(ConsentTextVersion).where(
                    ConsentTextVersion.consent_type == consent_type,
                    ConsentTextVersion.version == kind_version,
                )
            )
            if text_version is None:
                text_version = ConsentTextVersion(
                    consent_type=consent_type,
                    version=kind_version,
                    text=policy[kind],
                )
                session.add(text_version)
                await session.flush()
            elif text_version.text != policy[kind]:
                raise DomainError(
                    "CHECKOUT_CONSENT_VERSION_CONFLICT",
                    "Wersja treści zgody ma już inną zapisaną treść.",
                    409,
                )
            from sensoria.modules.accounts.auth import normalize_email
            from sensoria.modules.accounts.privacy import consent_subject_digest

            session.add(
                CustomerConsent(
                    email=normalize_email(payload.email),
                    subject_digest=consent_subject_digest(payload.email),
                    consent_type=consent_type,
                    granted=granted,
                    occurred_at=checkout_now,
                    source="checkout",
                    consent_text_id=text_version.id,
                    ip_hash=consent_ip_hash,
                    order_consent_id=order_consent.id,
                )
            )
        # Keep the cart for idempotent retries; its guest TTL remains authoritative.
        return CheckoutResponse(
            order_id=order.id,
            status=order.status,
            amount_due_grosz=order.amount_due_grosz,
            payment_integration=_payment_integration(),
            payment_url=None,
            access_token=order_access_token(order.id),
            message=(
                "Zamówienie zapisano jako oczekujące na płatność. "
                "Rozpocznij płatność przez endpoint sesji płatności."
            ),
        )
