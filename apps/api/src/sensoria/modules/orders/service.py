"""Transactional cart operations; guest secrets are only stored as digests."""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from typing import cast
from uuid import UUID, uuid4

from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from sensoria.modules.catalog.models import (
    Product,
    ProductBook,
    ProductVoucher,
    ProductVoucherVariant,
)
from sensoria.modules.catalog.types import ProductKind, ProductStatus, VoucherVariantKind
from sensoria.modules.vouchers.models import Voucher
from sensoria.shared.audit_log import ActorType, AuditLog
from sensoria.shared.errors import DomainError

from .calculator import DiscountInput
from .delivery import DeliveryMethod, load_delivery_policy
from .models import (
    Cart,
    CartItem,
    CartReorderOperation,
    DiscountCode,
    DiscountRedemption,
    DiscountUseReservation,
    Order,
    OrderItem,
    StockReservation,
)

_TOKEN_BYTES = 32


def _idempotency_digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


async def latest_reorder_report(session: AsyncSession, cart_id: UUID) -> dict[str, object] | None:
    row = await session.scalar(
        select(CartReorderOperation)
        .where(CartReorderOperation.cart_id == cart_id, CartReorderOperation.dismissed_at.is_(None))
        .order_by(CartReorderOperation.created_at.desc(), CartReorderOperation.id.desc())
        .limit(1)
    )
    if row is None:
        return None
    return {**row.report, "operation_id": str(row.id)}


async def dismiss_reorder_report(
    session: AsyncSession, token: str | None, operation_id: UUID
) -> None:
    if token is None:
        raise DomainError("CART_NOT_FOUND", "Nie znaleziono aktywnego koszyka.", 404)
    try:
        digest = _token_digest(token)
    except UnicodeEncodeError:
        raise DomainError("CART_NOT_FOUND", "Nie znaleziono aktywnego koszyka.", 404) from None
    async with session.begin():
        cart = await session.scalar(
            select(Cart)
            .where(Cart.session_token_hash == digest, Cart.customer_id.is_(None))
            .with_for_update()
        )
        if cart is None:
            raise DomainError("CART_NOT_FOUND", "Nie znaleziono aktywnego koszyka.", 404)
        report = await session.scalar(
            select(CartReorderOperation)
            .where(CartReorderOperation.id == operation_id, CartReorderOperation.cart_id == cart.id)
            .with_for_update()
        )
        if report is None:
            raise DomainError("REORDER_REPORT_NOT_FOUND", "Nie znaleziono podsumowania.", 404)
        if report.dismissed_at is None:
            report.dismissed_at = func.now()


async def _reorder_sources(
    session: AsyncSession,
    *,
    customer_id: UUID,
    cart_token: str | None,
    idempotency_key: str,
    source_kind: str,
    source_id: UUID,
    source_label: str,
    sources: list[tuple[UUID, UUID | None, int, int, str]],
    extra_warnings: list[str] | None = None,
) -> tuple[Cart, str, dict[str, object]]:
    """Add eligible historical lines at live terms in one transaction."""
    if not 8 <= len(idempotency_key) <= 128:
        raise DomainError("REORDER_IDEMPOTENCY_KEY_INVALID", "Nieprawidłowy klucz operacji.", 422)
    key_hash = _idempotency_digest(idempotency_key)
    async with session.begin():
        await session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:key))"),
            {"key": f"reorder:{customer_id}:{key_hash}"},
        )
        previous = await session.scalar(
            select(CartReorderOperation).where(
                CartReorderOperation.customer_id == customer_id,
                CartReorderOperation.idempotency_key_hash == key_hash,
            )
        )
        if previous is not None:
            previous_source_id = previous.order_id or previous.voucher_id
            if previous_source_id != source_id or (previous.order_id is None) != (
                source_kind == "voucher"
            ):
                raise DomainError(
                    "REORDER_IDEMPOTENCY_CONFLICT",
                    "Ten klucz został już użyty do innej operacji.",
                    409,
                )
            cart: Cart | None = None
            if cart_token is not None:
                try:
                    presented_digest = _token_digest(cart_token)
                except UnicodeEncodeError:
                    presented_digest = ""
                if presented_digest:
                    cart = await session.scalar(
                        select(Cart)
                        .where(
                            Cart.session_token_hash == presented_digest,
                            Cart.customer_id.is_(None),
                        )
                        .with_for_update()
                    )
            if cart is not None and cart.id != previous.cart_id:
                raise DomainError(
                    "REORDER_IDEMPOTENCY_CONFLICT", "Ta operacja należy do innego koszyka.", 409
                )
            if cart is None:
                cart = await session.scalar(
                    select(Cart)
                    .where(Cart.id == previous.cart_id, Cart.customer_id.is_(None))
                    .with_for_update()
                )
                if cart is None:
                    raise DomainError(
                        "REORDER_IDEMPOTENCY_CONFLICT", "Koszyk tej operacji jest niedostępny.", 409
                    )
                active_token = new_cart_token()
                cart.session_token_hash = _token_digest(active_token)
                cart.expires_at = func.now() + text("interval '30 days'")
                await session.flush()
                await session.refresh(cart, attribute_names=["expires_at"])
            else:
                active_token = cart_token or new_cart_token()
            return cart, active_token, {**previous.report, "operation_id": str(previous.id)}

        cart, active_token, _created = await _locked_or_new_guest_cart(session, cart_token)

        # Product row locks use a stable order across all multi-line reorders.
        product_ids = sorted({item[0] for item in sources}, key=str)
        products: dict[UUID, Product | None] = {}
        for product_id in product_ids:
            products[product_id] = await session.scalar(
                select(Product)
                .where(Product.id == product_id)
                .options(
                    selectinload(Product.voucher).selectinload(ProductVoucher.variants),
                    selectinload(Product.book),
                )
                .with_for_update()
            )
        cart_items = list(
            (
                await session.scalars(
                    select(CartItem).where(CartItem.cart_id == cart.id).with_for_update()
                )
            ).all()
        )
        db_now = await session.scalar(select(func.now()))
        assert db_now is not None
        digital_product_ids = [
            product_id
            for product_id, product in products.items()
            if product is not None and product.kind in (ProductKind.DIGITAL, ProductKind.AUDIOBOOK)
        ]
        previously_purchased = (
            set(
                (
                    await session.scalars(
                        select(OrderItem.product_id)
                        .join(Order, Order.id == OrderItem.order_id)
                        .where(
                            Order.customer_id == customer_id,
                            Order.status == "paid",
                            OrderItem.product_id.in_(digital_product_ids),
                        )
                        .distinct()
                    )
                ).all()
            )
            if digital_product_ids
            else set()
        )
        lines: list[dict[str, object]] = []
        for product_id, variant_id, requested, old_price, historical_name in sources:
            product = products.get(product_id)
            line: dict[str, object] = {
                "product_id": str(product_id),
                "name": historical_name,
                "variant_id": str(variant_id) if variant_id else None,
                "requested_quantity": requested,
                "added_quantity": 0,
                "status": "skipped",
                "reason": None,
                "old_unit_price_grosz": old_price,
                "new_unit_price_grosz": None,
                "price_changed": False,
                "previous_cart_unit_price_grosz": None,
                "cart_repriced_quantity": 0,
                "warnings": [],
            }
            if requested < 1:
                line["reason"] = "Nieprawidłowa ilość w historii."
                lines.append(line)
                continue
            if (
                product is None
                or product.status is not ProductStatus.PUBLISHED
                or product.published_at is None
            ):
                line["reason"] = "Produkt nie jest już dostępny w sprzedaży."
                lines.append(line)
                continue
            if product.published_at > db_now:
                line["reason"] = "Produkt nie jest jeszcze dostępny w sprzedaży."
                lines.append(line)
                continue
            try:
                price, resolved_variant_id = _resolve_price(product, variant_id)
            except DomainError:
                line["reason"] = "Wybrany wariant nie jest już dostępny."
                lines.append(line)
                continue
            if product.requires_shipping:
                await load_delivery_policy(session)
            line["new_unit_price_grosz"] = price
            line["price_changed"] = price != old_price
            if product.kind is ProductKind.VOUCHER and product.voucher is not None:
                selected_variant = next(
                    (
                        entry
                        for entry in product.voucher.variants
                        if entry.id == resolved_variant_id
                    ),
                    None,
                )
                line["variant"] = (
                    "W gabinecie"
                    if selected_variant is not None
                    and selected_variant.kind is VoucherVariantKind.IN_PERSON
                    else "Online"
                    if selected_variant is not None
                    else ""
                )
            if product.kind is ProductKind.BOOK:
                book = product.book
                if book is None:
                    line["reason"] = "Brak dostępnych egzemplarzy."
                    lines.append(line)
                    continue
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
                existing_quantity = sum(
                    item.quantity
                    for item in cart_items
                    if item.product_id == product.id and item.variant_id is None
                )
                available = max(0, book.stock_quantity - reserved - existing_quantity)
                added = min(requested, available)
                if added == 0:
                    line["reason"] = "Brak wolnych egzemplarzy przy obecnej ilości w koszyku."
                    lines.append(line)
                    continue
                existing = next(
                    (
                        item
                        for item in cart_items
                        if item.product_id == product.id and item.variant_id is None
                    ),
                    None,
                )
                if existing is not None:
                    current_vat_rate = product.vat_rate
                    if current_vat_rate is None:
                        line["reason"] = "Brak poprawnych danych podatkowych produktu."
                        line["status"] = "skipped"
                        lines.append(line)
                        continue
                    line["previous_cart_unit_price_grosz"] = existing.unit_price_snapshot
                    line["cart_repriced_quantity"] = existing.quantity
                    if existing.unit_price_snapshot != price:
                        line["warnings"] = [
                            "Dotychczasowa pozycja książki w koszyku została przeliczona "
                            "według aktualnej ceny."
                        ]
                        existing.unit_price_snapshot = price
                        existing.vat_rate_snapshot = current_vat_rate
                    existing.quantity += added
                else:
                    new_item = CartItem(
                        cart_id=cart.id,
                        product_id=product.id,
                        variant_id=None,
                        line_key=_merge_line_key(product.id, None),
                        quantity=added,
                        unit_price_snapshot=price,
                        vat_rate_snapshot=product.vat_rate,
                        gift_data=None,
                    )
                    session.add(new_item)
                    cart_items.append(new_item)
                line["added_quantity"] = added
                line["status"] = "added" if added == requested else "partial"
                if added < requested:
                    line["reason"] = (
                        f"Dodano {added} z {requested}; ogranicza bieżący stan magazynu."
                    )
            elif product.kind in (ProductKind.DIGITAL, ProductKind.AUDIOBOOK):
                if product.id in previously_purchased:
                    line["warnings"] = ["Masz już ten materiał w bibliotece."]
                existing = next(
                    (
                        item
                        for item in cart_items
                        if item.product_id == product.id and item.variant_id == resolved_variant_id
                    ),
                    None,
                )
                if existing is not None:
                    line["status"] = "already_in_cart"
                    line["reason"] = "Produkt jest już w koszyku; obowiązuje limit jednej sztuki."
                else:
                    session.add(
                        CartItem(
                            cart_id=cart.id,
                            product_id=product.id,
                            variant_id=resolved_variant_id,
                            line_key=_merge_line_key(product.id, resolved_variant_id),
                            quantity=1,
                            unit_price_snapshot=price,
                            vat_rate_snapshot=product.vat_rate,
                            gift_data=None,
                        )
                    )
                    line["added_quantity"] = 1
                    line["status"] = "added" if requested == 1 else "partial"
                    if requested > 1:
                        line["reason"] = (
                            "Produkt cyfrowy można kupić w koszyku w ilości jednej sztuki."
                        )
            elif product.kind is ProductKind.VOUCHER:
                # Each voucher remains an independent one-unit line; gift data is never copied.
                for _ in range(requested):
                    session.add(
                        CartItem(
                            cart_id=cart.id,
                            product_id=product.id,
                            variant_id=resolved_variant_id,
                            line_key=_new_line_key(product.id, resolved_variant_id, product.kind),
                            quantity=1,
                            unit_price_snapshot=price,
                            vat_rate_snapshot=product.vat_rate,
                            gift_data=None,
                        )
                    )
                line["added_quantity"] = requested
                line["status"] = "added"
                line["reason"] = "Dane prezentu wymagają nowego, świadomego wyboru."
            lines.append(line)
        await session.flush()
        discount_removed = await revalidate_cart_discount(session, cart)
        report: dict[str, object] = {
            "source_kind": source_kind,
            "source_id": str(source_id),
            "source_label": source_label,
            "lines": lines,
            "cart_preserved": True,
            "discount_preserved": cart.discount_code_id is not None,
            "discount_revalidation_notice": cart.discount_notice if discount_removed else None,
            "warnings": extra_warnings or [],
            "message": "Dostępne pozycje dodano do koszyka według aktualnej oferty."
            if any(item["added_quantity"] != 0 for item in lines)
            else "Nie dodano produktów. Zobacz powody przy poszczególnych pozycjach.",
        }
        operation = CartReorderOperation(
            id=uuid4(),
            customer_id=customer_id,
            cart_id=cart.id,
            order_id=source_id if source_kind == "order" else None,
            voucher_id=source_id if source_kind == "voucher" else None,
            idempotency_key_hash=key_hash,
            report=report,
        )
        session.add(operation)
        session.add(
            AuditLog(
                actor_type=ActorType.CUSTOMER,
                actor_id=customer_id,
                entity_type="cart",
                entity_id=cart.id,
                action="cart_reorder_completed",
                payload={
                    "operation_id": str(operation.id),
                    "source_kind": source_kind,
                    "source_id": str(source_id),
                    "added_lines": sum(1 for item in lines if item["added_quantity"] != 0),
                    "skipped_lines": sum(1 for item in lines if item["status"] == "skipped"),
                    "line_outcomes": [
                        {
                            "product_id": item["product_id"],
                            "status": item["status"],
                            "requested_quantity": item["requested_quantity"],
                            "added_quantity": item["added_quantity"],
                            "reason": item["reason"],
                        }
                        for item in lines
                    ],
                },
            )
        )
        await session.flush()
    return cart, active_token, {**report, "operation_id": str(operation.id)}


async def reorder_order(
    session: AsyncSession,
    *,
    customer_id: UUID,
    order_id: UUID,
    cart_token: str | None,
    idempotency_key: str,
) -> tuple[Cart, str, dict[str, object]]:
    order = await session.scalar(
        select(Order).where(
            Order.id == order_id, Order.customer_id == customer_id, Order.status == "paid"
        )
    )
    if order is None:
        raise DomainError("ORDER_NOT_FOUND", "Nie znaleziono zamówienia.", 404)
    source_label = f"Zamówienie {order.public_number or str(order.id)}"
    has_historical_discount = order.discount_code_id is not None
    rows = list(
        (
            await session.execute(
                select(
                    OrderItem.product_id,
                    OrderItem.variant_id,
                    OrderItem.quantity,
                    OrderItem.unit_price_snapshot,
                    OrderItem.product_name_snapshot,
                )
                .where(OrderItem.order_id == order_id)
                .order_by(OrderItem.product_id, OrderItem.id)
            )
        ).all()
    )
    await session.rollback()
    sources = [
        (pid, vid, quantity, price, name or "Produkt z wcześniejszego zamówienia")
        for pid, vid, quantity, price, name in rows
    ]
    return await _reorder_sources(
        session,
        customer_id=customer_id,
        cart_token=cart_token,
        idempotency_key=idempotency_key,
        source_kind="order",
        source_id=order_id,
        source_label=source_label,
        sources=sources,
        extra_warnings=(
            ["Kod rabatowy z wcześniejszego zamówienia nie został przeniesiony."]
            if has_historical_discount
            else []
        ),
    )


async def preview_reorder_order(
    session: AsyncSession,
    *,
    customer_id: UUID,
    order_id: UUID,
    cart_token: str | None,
) -> dict[str, object]:
    order = await session.scalar(
        select(Order).where(
            Order.id == order_id, Order.customer_id == customer_id, Order.status == "paid"
        )
    )
    if order is None:
        raise DomainError("ORDER_NOT_FOUND", "Nie znaleziono zamówienia.", 404)
    result = await session.execute(
        select(OrderItem.product_id, OrderItem.variant_id, OrderItem.quantity)
        .where(OrderItem.order_id == order_id)
        .order_by(OrderItem.product_id, OrderItem.id)
    )
    rows = [(row.product_id, row.variant_id, row.quantity) for row in result]
    return await _preview_reorder_items(session, cart_token, rows)


async def preview_reorder_voucher(
    session: AsyncSession,
    *,
    customer_id: UUID,
    voucher_id: UUID,
    cart_token: str | None,
) -> dict[str, object]:
    row = await session.execute(
        select(Voucher, Order, OrderItem)
        .join(OrderItem, OrderItem.id == Voucher.order_item_id)
        .join(Order, Order.id == OrderItem.order_id)
        .where(Voucher.id == voucher_id, Order.customer_id == customer_id, Order.status == "paid")
    )
    result = row.first()
    if result is None:
        raise DomainError("VOUCHER_NOT_FOUND", "Nie znaleziono vouchera.", 404)
    voucher, _order, item = result
    if item.variant_id is None:
        return {"can_add": False, "message": "Nie można ustalić zakupionego wariantu."}
    return await _preview_reorder_items(
        session, cart_token, [(voucher.product_id, item.variant_id, 1)]
    )


async def _preview_reorder_items(
    session: AsyncSession,
    cart_token: str | None,
    sources: list[tuple[UUID, UUID | None, int]],
) -> dict[str, object]:
    now = await session.scalar(select(func.now()))
    if now is None:
        raise DomainError(
            "REORDER_PREVIEW_UNAVAILABLE", "Nie udało się sprawdzić dostępności.", 503
        )
    product_ids = sorted({product_id for product_id, _variant_id, _qty in sources}, key=str)
    products = {
        product.id: product
        for product in (
            await session.scalars(
                select(Product)
                .where(Product.id.in_(product_ids))
                .options(
                    selectinload(Product.voucher).selectinload(ProductVoucher.variants),
                    selectinload(Product.book),
                )
            )
        ).all()
    }
    cart, cart_rows = await get_cart_rows(session, cart_token)
    cart_items = [item for item, _product, _variant in cart_rows]
    book_ids = [
        product_id for product_id, product in products.items() if product.kind is ProductKind.BOOK
    ]
    reserved = (
        {
            product_id: int(quantity or 0)
            for product_id, quantity in (
                await session.execute(
                    select(StockReservation.product_id, func.sum(StockReservation.quantity))
                    .join(Order, Order.id == StockReservation.order_id)
                    .where(
                        StockReservation.product_id.in_(book_ids),
                        StockReservation.released_at.is_(None),
                        StockReservation.expires_at > now,
                        Order.status == "pending_payment",
                    )
                    .group_by(StockReservation.product_id)
                )
            ).all()
        }
        if book_ids
        else {}
    )
    for product_id, variant_id, _requested in sources:
        product = products.get(product_id)
        if (
            product is None
            or product.status is not ProductStatus.PUBLISHED
            or product.published_at is None
            or product.published_at > now
        ):
            continue
        try:
            _price, selected_variant = _resolve_price(product, variant_id)
        except DomainError:
            continue
        if product.kind is ProductKind.BOOK:
            book = product.book
            existing_quantity = sum(
                item.quantity
                for item in cart_items
                if item.product_id == product.id and item.variant_id is None
            )
            if (
                book is not None
                and book.stock_quantity - reserved.get(product.id, 0) - existing_quantity > 0
            ):
                return {"can_add": True, "message": None}
        elif product.kind in (ProductKind.DIGITAL, ProductKind.AUDIOBOOK):
            if not any(
                item.product_id == product.id and item.variant_id == selected_variant
                for item in cart_items
            ):
                return {"can_add": True, "message": None}
        elif product.kind is ProductKind.VOUCHER:
            return {"can_add": True, "message": None}
    return {
        "can_add": False,
        "message": "Żadnej pozycji nie można teraz dodać. Sprawdź dostępność i zawartość koszyka.",
    }


async def reorder_voucher(
    session: AsyncSession,
    *,
    customer_id: UUID,
    voucher_id: UUID,
    cart_token: str | None,
    idempotency_key: str,
) -> tuple[Cart, str, dict[str, object]]:
    row = await session.execute(
        select(Voucher, Order, OrderItem)
        .join(OrderItem, OrderItem.id == Voucher.order_item_id)
        .join(Order, Order.id == OrderItem.order_id)
        .where(Voucher.id == voucher_id, Order.customer_id == customer_id, Order.status == "paid")
    )
    result = row.first()
    if result is None:
        raise DomainError("VOUCHER_NOT_FOUND", "Nie znaleziono vouchera.", 404)
    voucher, order, item = result
    variant_id = item.variant_id
    product_id = voucher.product_id
    price_snapshot = item.unit_price_snapshot
    name = str(voucher.issue_snapshot.get("product_name") or "Voucher na wizytę")
    source_label = f"Voucher z zamówienia {order.public_number or str(order.id)}"
    # Release the read transaction; the owner is immutable once linked and the
    # purchased item snapshot is append-only. The write path locks cart/products.
    await session.rollback()
    if variant_id is None:
        raise DomainError(
            "REORDER_VARIANT_UNAVAILABLE", "Nie można ustalić zakupionego wariantu.", 409
        )
    return await _reorder_sources(
        session,
        customer_id=customer_id,
        cart_token=cart_token,
        idempotency_key=idempotency_key,
        source_kind="voucher",
        source_id=voucher_id,
        source_label=source_label,
        sources=[(product_id, variant_id, 1, price_snapshot, name)],
    )


def new_cart_token() -> str:
    """Return a high-entropy opaque cookie value."""

    return secrets.token_urlsafe(_TOKEN_BYTES)


def _token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("ascii", errors="strict")).hexdigest()


def _merge_line_key(product_id: UUID, variant_id: UUID | None) -> str:
    return f"{product_id}:{variant_id or 'none'}"


def _new_line_key(product_id: UUID, variant_id: UUID | None, kind: ProductKind) -> str:
    if kind is ProductKind.VOUCHER:
        return f"voucher:{uuid4()}"
    return _merge_line_key(product_id, variant_id)


async def find_guest_cart(session: AsyncSession, token: str | None) -> Cart | None:
    """Return only an unexpired guest basket for the presented opaque token."""

    if token is None or not 40 <= len(token) <= 128:
        return None
    try:
        digest = _token_digest(token)
    except UnicodeEncodeError:
        return None
    return cast(
        Cart | None,
        await session.scalar(
            select(Cart)
            .where(
                Cart.session_token_hash == digest,
                Cart.customer_id.is_(None),
                Cart.expires_at > func.now(),
            )
            .options(selectinload(Cart.items), selectinload(Cart.discount_code))
        ),
    )


async def _locked_or_new_guest_cart(
    session: AsyncSession, token: str | None
) -> tuple[Cart, str, bool]:
    if token is not None and 40 <= len(token) <= 128:
        try:
            digest = _token_digest(token)
        except UnicodeEncodeError:
            digest = ""
        if digest:
            cart = await session.scalar(
                select(Cart)
                .where(
                    Cart.session_token_hash == digest,
                    Cart.customer_id.is_(None),
                    Cart.expires_at > func.now(),
                )
                .with_for_update()
            )
            if cart is not None:
                return cart, token, False

    fresh_token = new_cart_token()
    cart = Cart(
        session_token_hash=_token_digest(fresh_token),
        expires_at=func.now() + text("interval '30 days'"),
    )
    session.add(cart)
    await session.flush()
    await session.refresh(cart, attribute_names=["expires_at"])
    return cart, fresh_token, True


async def get_cart_rows(
    session: AsyncSession, token: str | None
) -> tuple[Cart | None, list[tuple[CartItem, Product, VoucherVariantKind | None]]]:
    """Load a cart snapshot without creating rows for an empty GET."""

    cart = await find_guest_cart(session, token)
    if cart is None:
        return None, []
    rows = (
        await session.execute(
            select(CartItem, Product, ProductVoucherVariant.kind)
            .join(Product, Product.id == CartItem.product_id)
            .outerjoin(ProductVoucherVariant, ProductVoucherVariant.id == CartItem.variant_id)
            .options(
                selectinload(Product.images),
                selectinload(Product.book),
                selectinload(Product.digital),
                selectinload(Product.audiobook),
                selectinload(Product.voucher),
            )
            .where(CartItem.cart_id == cart.id)
            .order_by(CartItem.id)
        )
    ).all()
    return cart, [(row[0], row[1], row[2]) for row in rows]


async def _published_product(session: AsyncSession, product_id: UUID) -> Product:
    product = await session.scalar(
        select(Product)
        .where(
            Product.id == product_id,
            Product.status == ProductStatus.PUBLISHED,
            Product.published_at.is_not(None),
            Product.published_at <= func.now(),
        )
        .options(
            selectinload(Product.voucher).selectinload(ProductVoucher.variants),
            selectinload(Product.book),
        )
        .with_for_update()
    )
    if product is None:
        raise DomainError("CART_PRODUCT_UNAVAILABLE", "Produkt jest niedostępny.", 409)
    return product


def _resolve_price(product: Product, variant_id: UUID | None) -> tuple[int, UUID | None]:
    if product.vat_rate is None:
        raise DomainError("CART_PRODUCT_UNAVAILABLE", "Produkt jest niedostępny.", 409)
    if product.kind is ProductKind.VOUCHER:
        if variant_id is None or product.voucher is None:
            raise DomainError("CART_VARIANT_REQUIRED", "Wybierz wariant vouchera.", 422)
        variant = next((item for item in product.voucher.variants if item.id == variant_id), None)
        if variant is None:
            raise DomainError(
                "CART_VARIANT_INVALID", "Wybrany wariant nie należy do produktu.", 422
            )
        return variant.price, variant.id
    if variant_id is not None:
        raise DomainError("CART_VARIANT_INVALID", "Ten produkt nie ma wariantów do wyboru.", 422)
    if product.price is None or product.vat_rate is None:
        raise DomainError("CART_PRODUCT_UNAVAILABLE", "Produkt jest niedostępny.", 409)
    return product.price, None


def _validate_quantity(product: Product, quantity: int) -> None:
    if product.kind is ProductKind.VOUCHER and quantity != 1:
        raise DomainError(
            "CART_VOUCHER_QUANTITY", "Każdy voucher dodawaj jako osobną pozycję.", 422
        )
    if product.kind in (ProductKind.DIGITAL, ProductKind.AUDIOBOOK) and quantity != 1:
        raise DomainError(
            "CART_DIGITAL_QUANTITY", "Produkt cyfrowy można dodać tylko w ilości 1.", 422
        )


async def _check_book_stock(
    session: AsyncSession,
    product: Product,
    cart_id: UUID,
    quantity: int,
    variant_id: UUID | None,
    existing_item: CartItem | None,
) -> None:
    if product.kind is not ProductKind.BOOK:
        return
    book = await session.scalar(
        select(ProductBook).where(ProductBook.product_id == product.id).with_for_update()
    )
    if book is None:
        raise DomainError("CART_PRODUCT_UNAVAILABLE", "Produkt jest niedostępny.", 409)
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
    available = max(0, book.stock_quantity - reserved)
    current = 0
    if existing_item is not None:
        current = existing_item.quantity
    else:
        current = int(
            await session.scalar(
                select(func.coalesce(func.sum(CartItem.quantity), 0)).where(
                    CartItem.cart_id == cart_id,
                    CartItem.product_id == product.id,
                    CartItem.variant_id.is_(None),
                )
            )
            or 0
        )
    if current + quantity > available:
        raise DomainError(
            "CART_STOCK_LIMIT",
            f"Dostępnych egzemplarzy: {max(0, available - current)}.",
            409,
        )


async def add_item(
    session: AsyncSession,
    token: str | None,
    *,
    product_id: UUID,
    variant_id: UUID | None,
    quantity: int,
    is_gift: bool = False,
) -> tuple[Cart, str]:
    """Add an item using server-side catalog price and tax snapshots."""

    async with session.begin():
        cart, active_token, _created = await _locked_or_new_guest_cart(session, token)
        product = await _published_product(session, product_id)
        if product.requires_shipping:
            await load_delivery_policy(session)
        _validate_quantity(product, quantity)
        if is_gift and product.kind is not ProductKind.VOUCHER:
            raise DomainError("CART_GIFT_NOT_VOUCHER", "Prezent dotyczy wyłącznie vouchera.", 422)
        price, resolved_variant_id = _resolve_price(product, variant_id)
        line_key = _new_line_key(product.id, resolved_variant_id, product.kind)
        existing = None
        if product.kind is not ProductKind.VOUCHER:
            existing = await session.scalar(
                select(CartItem)
                .where(CartItem.cart_id == cart.id, CartItem.line_key == line_key)
                .with_for_update()
            )
        await _check_book_stock(session, product, cart.id, quantity, resolved_variant_id, existing)
        if existing is not None:
            if product.kind in (ProductKind.DIGITAL, ProductKind.AUDIOBOOK):
                return cart, active_token
            existing.quantity += quantity
        else:
            session.add(
                CartItem(
                    cart_id=cart.id,
                    product_id=product.id,
                    variant_id=resolved_variant_id,
                    line_key=line_key,
                    quantity=quantity,
                    unit_price_snapshot=price,
                    vat_rate_snapshot=product.vat_rate,
                    gift_data={} if is_gift else None,
                )
            )
        await session.flush()
        await revalidate_cart_discount(session, cart)
    return cart, active_token


async def set_item_gift(
    session: AsyncSession, token: str | None, item_id: UUID, is_gift: bool
) -> Cart:
    """Toggle gift intent on one owned voucher cart line and clear data when disabled."""
    async with session.begin():
        cart, _active_token, _created = await _locked_or_new_guest_cart(session, token)
        item = await session.scalar(
            select(CartItem)
            .where(CartItem.id == item_id, CartItem.cart_id == cart.id)
            .with_for_update()
        )
        if item is None:
            raise DomainError("CART_ITEM_NOT_FOUND", "Nie znaleziono pozycji koszyka.", 404)
        product = await _published_product(session, item.product_id)
        if product.kind is not ProductKind.VOUCHER:
            raise DomainError("CART_GIFT_NOT_VOUCHER", "Prezent dotyczy wyłącznie vouchera.", 422)
        item.gift_data = {} if is_gift else None
        await session.flush()
        await revalidate_cart_discount(session, cart)
    return cart


async def update_item(
    session: AsyncSession, token: str | None, item_id: UUID, quantity: int
) -> Cart:
    async with session.begin():
        cart, _active_token, _created = await _locked_or_new_guest_cart(session, token)
        item = await session.scalar(
            select(CartItem)
            .where(CartItem.id == item_id, CartItem.cart_id == cart.id)
            .with_for_update()
        )
        if item is None:
            raise DomainError("CART_ITEM_NOT_FOUND", "Nie znaleziono pozycji koszyka.", 404)
        product = await _published_product(session, item.product_id)
        _validate_quantity(product, quantity)
        _resolve_price(product, item.variant_id)
        await _check_book_stock(
            session, product, cart.id, quantity - item.quantity, item.variant_id, item
        )
        item.quantity = quantity
        await session.flush()
        await revalidate_cart_discount(session, cart)
    return cart


async def delete_item(session: AsyncSession, token: str | None, item_id: UUID) -> Cart:
    async with session.begin():
        cart, _active_token, _created = await _locked_or_new_guest_cart(session, token)
        item = await session.scalar(
            select(CartItem)
            .where(CartItem.id == item_id, CartItem.cart_id == cart.id)
            .with_for_update()
        )
        if item is None:
            raise DomainError("CART_ITEM_NOT_FOUND", "Nie znaleziono pozycji koszyka.", 404)
        await session.delete(item)
        await session.flush()
        if not await _cart_has_physical_product(session, cart.id):
            cart.delivery_method = None
        await revalidate_cart_discount(session, cart)
    return cart


async def clear_cart(session: AsyncSession, token: str | None) -> Cart | None:
    async with session.begin():
        if token is None:
            return None
        cart = await find_guest_cart(session, token)
        if cart is None:
            return None
        cart = cast(
            Cart | None,
            await session.scalar(select(Cart).where(Cart.id == cart.id).with_for_update()),
        )
        if cart is None:
            return None
        await session.execute(delete(CartItem).where(CartItem.cart_id == cart.id))
        cart.delivery_method = None
        await revalidate_cart_discount(session, cart)
    return cart


async def _cart_has_physical_product(session: AsyncSession, cart_id: UUID) -> bool:
    """Use the catalog kind property contract: BOOK is the sole shippable kind."""
    return bool(
        await session.scalar(
            select(CartItem.id)
            .join(Product, Product.id == CartItem.product_id)
            .where(CartItem.cart_id == cart_id, Product.kind == ProductKind.BOOK)
            .limit(1)
        )
    )


async def set_cart_delivery_method(session: AsyncSession, token: str | None, method: str) -> Cart:
    """Persist an allowed delivery method for a cart that contains a physical product."""
    if method not in {item.value for item in DeliveryMethod}:
        raise DomainError("DELIVERY_METHOD_INVALID", "Wybierz dostępną metodę dostawy.", 422)
    if token is None:
        raise DomainError("CART_NOT_FOUND", "Nie znaleziono aktywnego koszyka.", 404)
    try:
        digest = _token_digest(token)
    except UnicodeEncodeError:
        raise DomainError("CART_NOT_FOUND", "Nie znaleziono aktywnego koszyka.", 404) from None
    async with session.begin():
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
            raise DomainError("CART_NOT_FOUND", "Nie znaleziono aktywnego koszyka.", 404)
        if not await _cart_has_physical_product(session, cart.id):
            raise DomainError("DELIVERY_NOT_REQUIRED", "Ten koszyk nie wymaga dostawy.", 409)
        await load_delivery_policy(session)
        cart.delivery_method = method
        if method != DeliveryMethod.PARCEL_LOCKER.value:
            cart.delivery_point_snapshot = None
        await session.flush()
    return cart


def discount_calculation_input(code: DiscountCode | None) -> DiscountInput | None:
    """Translate a stored code into the calculator's server-only input."""
    if code is None:
        return None
    return DiscountInput(code=code.code, type=code.type, value=code.value)


async def _cart_total_gross(session: AsyncSession, cart_id: UUID) -> int:
    return int(
        await session.scalar(
            select(
                func.coalesce(func.sum(CartItem.unit_price_snapshot * CartItem.quantity), 0)
            ).where(CartItem.cart_id == cart_id)
        )
        or 0
    )


async def _validate_discount(session: AsyncSession, code: DiscountCode, cart_id: UUID) -> None:
    if not code.is_active:
        raise DomainError("DISCOUNT_INVALID", "Ten kod rabatowy jest nieaktywny.", 400)
    currently_valid = await session.scalar(
        select(
            (DiscountCode.valid_from.is_(None) | (DiscountCode.valid_from <= func.now()))
            & (DiscountCode.valid_to.is_(None) | (DiscountCode.valid_to > func.now()))
        ).where(DiscountCode.id == code.id)
    )
    if not currently_valid:
        raise DomainError("DISCOUNT_INVALID", "Kod rabatowy nie jest teraz ważny.", 400)
    if code.max_uses is not None and code.used_count >= code.max_uses:
        raise DomainError("DISCOUNT_INVALID", "Limit użyć tego kodu został wyczerpany.", 400)
    if await _cart_total_gross(session, cart_id) < code.min_order_value:
        raise DomainError(
            "DISCOUNT_MINIMUM",
            "Wartość produktów nie osiąga minimalnego progu dla tego kodu.",
            400,
        )


async def set_cart_discount(session: AsyncSession, token: str | None, code_value: str) -> Cart:
    """Validate a candidate before replacing any code currently assigned to a cart."""
    if token is None:
        raise DomainError("DISCOUNT_CART_EMPTY", "Dodaj produkty przed użyciem kodu.", 400)
    try:
        digest = _token_digest(token)
    except UnicodeEncodeError:
        raise DomainError("DISCOUNT_CART_EMPTY", "Nie znaleziono aktywnego koszyka.", 400) from None
    async with session.begin():
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
            raise DomainError("DISCOUNT_CART_EMPTY", "Nie znaleziono aktywnego koszyka.", 400)
        code = await session.scalar(
            select(DiscountCode)
            .where(func.lower(func.btrim(DiscountCode.code)) == code_value.lower())
            .with_for_update()
        )
        if code is None:
            raise DomainError("DISCOUNT_INVALID", "Kod rabatowy jest nieprawidłowy.", 400)
        await _validate_discount(session, code, cart.id)
        cart.discount_code_id = code.id
        await session.flush()
    return cart


async def remove_cart_discount(session: AsyncSession, token: str | None) -> None:
    if token is None:
        return
    try:
        digest = _token_digest(token)
    except UnicodeEncodeError:
        return
    async with session.begin():
        cart = await session.scalar(
            select(Cart)
            .where(
                Cart.session_token_hash == digest,
                Cart.customer_id.is_(None),
                Cart.expires_at > func.now(),
            )
            .with_for_update()
        )
        if cart is not None:
            cart.discount_code_id = None
            await session.flush()


async def revalidate_cart_discount(session: AsyncSession, cart: Cart) -> bool:
    """Remove an ineligible code after a cart content change; return whether removed."""
    if cart.discount_code_id is None:
        return False
    code = await session.get(DiscountCode, cart.discount_code_id)
    if code is None:
        cart.discount_code_id = None
        cart.discount_notice = "Kod rabatowy został usunięty, ponieważ nie jest już dostępny."
        await session.flush()
        return True
    try:
        await _validate_discount(session, code, cart.id)
    except DomainError:
        cart.discount_code_id = None
        cart.discount_notice = (
            "Kod rabatowy został usunięty, ponieważ koszyk nie spełnia już jego warunków."
        )
        await session.flush()
        return True
    return False


async def record_paid_discount_use(
    session: AsyncSession, *, discount_code_id: UUID, order_id: UUID
) -> bool:
    """Record a trusted payment use inside the caller's payment transaction."""
    existing = await session.scalar(
        select(DiscountRedemption.id).where(
            DiscountRedemption.discount_code_id == discount_code_id,
            DiscountRedemption.order_id == order_id,
        )
    )
    if existing is not None:
        return False
    code = await session.scalar(
        select(DiscountCode).where(DiscountCode.id == discount_code_id).with_for_update()
    )
    if code is None:
        raise DomainError("DISCOUNT_NOT_FOUND", "Nie znaleziono kodu rabatowego.", 404)
    # A concurrent retry may have inserted this redemption while we waited for the row lock.
    existing = await session.scalar(
        select(DiscountRedemption.id).where(
            DiscountRedemption.discount_code_id == discount_code_id,
            DiscountRedemption.order_id == order_id,
        )
    )
    if existing is not None:
        return False
    if code.max_uses is not None and code.used_count >= code.max_uses:
        raise DomainError("DISCOUNT_EXHAUSTED", "Limit użyć kodu został wyczerpany.", 409)
    code.used_count += 1
    session.add(DiscountRedemption(discount_code_id=code.id, order_id=order_id))
    reservation = await session.scalar(
        select(DiscountUseReservation)
        .where(DiscountUseReservation.order_id == order_id)
        .with_for_update()
    )
    if reservation is not None:
        await session.delete(reservation)
    await session.flush()
    return True


@dataclass(frozen=True, slots=True)
class CartMergeConflict:
    product_id: UUID
    reason: str
    guest_quantity: int
    account_quantity: int
    available_quantity: int | None


@dataclass(frozen=True, slots=True)
class CartMergeResult:
    merged: bool
    conflicts: tuple[CartMergeConflict, ...] = ()
    conditions_changed: tuple[CartMergeConditionChange, ...] = ()


@dataclass(frozen=True, slots=True)
class CartMergeConditionChange:
    product_id: UUID
    account_price_snapshot: int
    guest_price_snapshot: int
    account_vat_snapshot: str
    guest_vat_snapshot: str


class _MergeAborted(Exception):
    def __init__(self, conflicts: tuple[CartMergeConflict, ...]) -> None:
        self.conflicts = conflicts


async def merge_guest_cart_after_login(
    session: AsyncSession, *, guest_token: str, authenticated_customer_id: UUID
) -> CartMergeResult:
    """Merge only when called by a trusted successful-login integration.

    Authentication is not implemented in the current accounts module. The caller must
    obtain ``authenticated_customer_id`` from its verified principal, never request data.
    A guest digest is consumed by deleting the guest row after a successful transaction.
    """

    if not 40 <= len(guest_token) <= 128:
        return CartMergeResult(merged=False)
    try:
        digest = _token_digest(guest_token)
    except UnicodeEncodeError:
        return CartMergeResult(merged=False)
    try:
        async with session.begin():
            guest = await session.scalar(
                select(Cart)
                .where(
                    Cart.session_token_hash == digest,
                    Cart.customer_id.is_(None),
                    Cart.expires_at > func.now(),
                )
                .with_for_update()
            )
            if guest is None:
                return CartMergeResult(merged=False)
            lock_id = int.from_bytes(
                hashlib.sha256(authenticated_customer_id.bytes).digest()[:8],
                byteorder="big",
                signed=True,
            )
            await session.execute(
                text("SELECT pg_advisory_xact_lock(:lock_id)"), {"lock_id": lock_id}
            )
            account = await session.scalar(
                select(Cart).where(Cart.customer_id == authenticated_customer_id).with_for_update()
            )
            if account is None:
                account = Cart(customer_id=authenticated_customer_id, expires_at=None)
                session.add(account)
                await session.flush()
                await session.refresh(account)
            guest_items = list(
                (
                    await session.scalars(
                        select(CartItem)
                        .where(CartItem.cart_id == guest.id)
                        .order_by(CartItem.product_id, CartItem.id)
                        .with_for_update()
                    )
                ).all()
            )
            account_items = list(
                (
                    await session.scalars(
                        select(CartItem)
                        .where(CartItem.cart_id == account.id)
                        .order_by(CartItem.product_id, CartItem.id)
                        .with_for_update()
                    )
                ).all()
            )
            account_by_key = {item.line_key: item for item in account_items}
            conflicts: list[CartMergeConflict] = []
            changed_conditions: dict[UUID, CartMergeConditionChange] = {}
            products: dict[UUID, Product | None] = {}
            for item in guest_items:
                product = await session.scalar(
                    select(Product)
                    .where(
                        Product.id == item.product_id,
                        Product.published_at.is_not(None),
                        Product.published_at <= func.now(),
                    )
                    .options(
                        selectinload(Product.voucher).selectinload(ProductVoucher.variants),
                        selectinload(Product.book),
                    )
                    .with_for_update()
                )
                products[item.product_id] = product
                if (
                    product is None
                    or product.status is not ProductStatus.PUBLISHED
                    or product.published_at is None
                ):
                    conflicts.append(
                        CartMergeConflict(item.product_id, "unavailable", item.quantity, 0, None)
                    )
                    continue
                if product.kind is ProductKind.VOUCHER and item.variant_id is None:
                    conflicts.append(
                        CartMergeConflict(
                            item.product_id, "variant_unavailable", item.quantity, 0, None
                        )
                    )
                    continue
                if item.variant_id is not None:
                    variant = next(
                        (
                            value
                            for value in (product.voucher.variants if product.voucher else [])
                            if value.id == item.variant_id
                        ),
                        None,
                    )
                    if variant is None:
                        conflicts.append(
                            CartMergeConflict(
                                item.product_id, "variant_unavailable", item.quantity, 0, None
                            )
                        )
                        continue
                existing = account_by_key.get(item.line_key)
                if existing is not None and (
                    existing.unit_price_snapshot != item.unit_price_snapshot
                    or existing.vat_rate_snapshot is not item.vat_rate_snapshot
                ):
                    changed_conditions[item.product_id] = CartMergeConditionChange(
                        product_id=item.product_id,
                        account_price_snapshot=existing.unit_price_snapshot,
                        guest_price_snapshot=item.unit_price_snapshot,
                        account_vat_snapshot=existing.vat_rate_snapshot.value,
                        guest_vat_snapshot=item.vat_rate_snapshot.value,
                    )
                if product.kind is ProductKind.BOOK:
                    book = await session.scalar(
                        select(ProductBook)
                        .where(ProductBook.product_id == product.id)
                        .with_for_update()
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
                    stock = max(0, (book.stock_quantity if book else 0) - reserved)
                    account_quantity = existing.quantity if existing else 0
                    if account_quantity + item.quantity > stock:
                        conflicts.append(
                            CartMergeConflict(
                                item.product_id,
                                "stock_limit",
                                item.quantity,
                                account_quantity,
                                max(0, stock - account_quantity),
                            )
                        )
            if conflicts:
                raise _MergeAborted(tuple(conflicts))

            for item in guest_items:
                product = products[item.product_id]
                assert product is not None
                if product.kind is ProductKind.VOUCHER:
                    session.add(
                        CartItem(
                            cart_id=account.id,
                            product_id=item.product_id,
                            variant_id=item.variant_id,
                            line_key=f"voucher:{uuid4()}",
                            quantity=1,
                            unit_price_snapshot=item.unit_price_snapshot,
                            vat_rate_snapshot=item.vat_rate_snapshot,
                            gift_data=item.gift_data,
                        )
                    )
                    continue
                existing = account_by_key.get(item.line_key)
                if existing is not None:
                    if product.kind is ProductKind.BOOK:
                        existing.quantity += item.quantity
                    # Digital/audio duplicates retain the account snapshot and quantity.
                    continue
                copied = CartItem(
                    cart_id=account.id,
                    product_id=item.product_id,
                    variant_id=item.variant_id,
                    line_key=item.line_key,
                    quantity=item.quantity,
                    unit_price_snapshot=item.unit_price_snapshot,
                    vat_rate_snapshot=item.vat_rate_snapshot,
                    gift_data=item.gift_data,
                )
                session.add(copied)
                account_by_key[item.line_key] = copied
            if account.delivery_method is None:
                account.delivery_method = guest.delivery_method
            await session.delete(guest)
            await session.flush()
        return CartMergeResult(
            merged=True,
            conditions_changed=tuple(
                changed_conditions[key] for key in sorted(changed_conditions, key=str)
            ),
        )
    except _MergeAborted as aborted:
        return CartMergeResult(merged=False, conflicts=aborted.conflicts)
