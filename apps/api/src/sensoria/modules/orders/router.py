"""Public guest-cart endpoints; account identity is never client-selectable."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Cookie, Depends, Header, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from sensoria.database import get_session
from sensoria.modules.catalog.schemas import PublicImage
from sensoria.modules.catalog.types import ProductKind
from sensoria.shared.errors import DomainError
from sensoria.shared.pricing import vat_label

from .calculator import CartCalculator, CartLineInput
from .checkout import checkout_consent_config, create_guest_order
from .delivery import resolve_delivery
from .pickup_points import choose_cart_point, get_point, list_cart_points
from .schemas import (
    CartDeliveryInput,
    CartGiftInput,
    CartItemInput,
    CartItemResponse,
    CartQuantityInput,
    CartResponse,
    CheckoutConfigResponse,
    CheckoutInput,
    CheckoutResponse,
    DiscountCodeInput,
    PickupPointCodeInput,
    PickupPointListResponse,
    PickupPointSnapshot,
)
from .service import (
    add_item,
    clear_cart,
    delete_item,
    discount_calculation_input,
    dismiss_reorder_report,
    get_cart_rows,
    latest_reorder_report,
    remove_cart_discount,
    set_cart_delivery_method,
    set_cart_discount,
    set_item_gift,
    update_item,
)

router = APIRouter(prefix="/cart", tags=["cart"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]
_COOKIE_NAME = "cart_token"
_COOKIE_PATH = "/api/cart"


async def _response(
    session: AsyncSession, token: str | None, *, discount_notice: str | None = None
) -> CartResponse:
    cart, rows = await get_cart_rows(session, token)
    lines = [
        CartLineInput(
            item_id=item.id,
            unit_price_snapshot=item.unit_price_snapshot,
            quantity=item.quantity,
            vat_rate_snapshot=item.vat_rate_snapshot,
        )
        for item, _product, _variant_kind in rows
    ]
    discount = discount_calculation_input(cart.discount_code if cart else None)
    preliminary = CartCalculator.calculate(lines, discount=discount)
    requires_shipping = any(product.requires_shipping for _item, product, _kind in rows)
    delivery_status, delivery_settlement = await resolve_delivery(
        session,
        requires_shipping=requires_shipping,
        selected_method=cart.delivery_method if cart else None,
        products_gross_after_discount_grosz=preliminary.products_gross_grosz,
    )
    calculation = CartCalculator.calculate(lines, discount=discount, delivery=delivery_settlement)
    settlements = {line.item_id: line for line in calculation.items}
    items = []
    for item, product, variant_kind in rows:
        if product.kind is ProductKind.BOOK and product.book is not None:
            details = "Książka papierowa"
            if product.book.shipping_method:
                details += f" · wysyłka: {product.book.shipping_method}"
            if product.book.shipping_business_days:
                details += f" · {product.book.shipping_business_days} dni roboczych"
        elif product.kind is ProductKind.DIGITAL and product.digital is not None:
            label = product.digital.label.value.replace("_", " ")
            details = f"{label} · {product.digital.file_format.upper()}"
            if product.digital.page_count:
                details += f" · {product.digital.page_count} stron"
        elif product.kind is ProductKind.AUDIOBOOK and product.audiobook is not None:
            details = "Audiobook"
            if product.audiobook.duration_seconds:
                seconds = product.audiobook.duration_seconds
                hours, remainder = divmod(seconds, 3600)
                minutes, rest_seconds = divmod(remainder, 60)
                parts = ([f"{hours} godz."] if hours else []) + (
                    [f"{minutes} min"] if minutes else []
                )
                if rest_seconds and not parts:
                    parts.append(f"{rest_seconds} sek.")
                if parts:
                    details += " · " + " ".join(parts)
        elif product.kind is ProductKind.VOUCHER:
            details = "Voucher"
            if variant_kind is not None:
                details += " · " + ("gabinet" if variant_kind.value == "IN_PERSON" else "online")
        else:
            details = None
        image = product.images[0] if product.images else None
        settled_line = settlements[item.id]
        items.append(
            CartItemResponse(
                id=item.id,
                product_id=item.product_id,
                slug=product.slug,
                name=product.name,
                kind=product.kind,
                variant_id=item.variant_id,
                variant_kind=variant_kind,
                quantity=item.quantity,
                unit_price_snapshot=item.unit_price_snapshot,
                vat_rate_snapshot=item.vat_rate_snapshot,
                vat_label=vat_label(item.vat_rate_snapshot),
                line_total_grosz=settled_line.gross_grosz,
                short_description=product.short_description,
                image=(PublicImage(url=image.url, alt=image.alt) if image is not None else None),
                details=details,
                voucher_validity_months=(
                    product.voucher.validity_months if product.voucher is not None else None
                ),
                is_gift=item.gift_data is not None,
            )
        )
    return CartResponse(
        items=items,
        item_count=sum(item.quantity for item, _product, _kind in rows),
        expires_at=cart.expires_at if cart else None,
        calculation=calculation,
        delivery=delivery_status,
        delivery_point=(
            PickupPointSnapshot.model_validate(cart.delivery_point_snapshot)
            if cart is not None and cart.delivery_point_snapshot is not None
            else None
        ),
        discount_code=cart.discount_code.code if cart and cart.discount_code else None,
        discount_notice=discount_notice,
        reorder_report=(
            await latest_reorder_report(session, cart.id) if cart is not None else None
        ),
    )


def _set_cart_cookie(response: Response, token: str, expires_at: datetime) -> None:
    response.set_cookie(
        key=_COOKIE_NAME,
        value=token,
        expires=expires_at,
        path=_COOKIE_PATH,
        secure=True,
        httponly=True,
        samesite="lax",
    )


@router.get("", response_model=CartResponse)
async def read_cart(
    session: SessionDependency,
    response: Response,
    cart_token: Annotated[str | None, Cookie()] = None,
) -> CartResponse:
    """Read a basket; an absent or expired cookie does not create a database row."""

    result = await _response(session, cart_token)
    if cart_token is not None and result.expires_at is not None:
        _set_cart_cookie(response, cart_token, result.expires_at)
        response.delete_cookie(
            _COOKIE_NAME, path="/api", secure=True, httponly=True, samesite="lax"
        )
    response.headers.update(
        {"Cache-Control": "private, no-store", "Referrer-Policy": "no-referrer"}
    )
    if cart_token is not None and result.expires_at is None:
        response.delete_cookie(
            _COOKIE_NAME, path="/api", secure=True, httponly=True, samesite="lax"
        )
    return result


@router.post("/items", response_model=CartResponse, status_code=200)
async def add_cart_item(
    payload: CartItemInput,
    session: SessionDependency,
    response: Response,
    cart_token: Annotated[str | None, Cookie()] = None,
) -> CartResponse:
    """Add a product using server price/VAT, then issue the persistent cookie."""

    cart, token = await add_item(
        session,
        cart_token,
        product_id=payload.product_id,
        variant_id=payload.variant_id,
        quantity=payload.quantity,
        is_gift=payload.is_gift,
    )
    if cart.expires_at is None:
        raise DomainError("CART_EXPIRY_INVALID", "Nie można zapisać czasu ważności koszyka.", 500)
    _set_cart_cookie(response, token, cart.expires_at)
    return await _response(session, token, discount_notice=cart.discount_notice)


@router.patch("/items/{item_id}", response_model=CartResponse)
async def change_cart_item(
    item_id: UUID,
    payload: CartQuantityInput,
    session: SessionDependency,
    cart_token: Annotated[str | None, Cookie()] = None,
) -> CartResponse:
    """Replace quantity for an item owned by the current guest basket."""

    if cart_token is None:
        raise DomainError("CART_ITEM_NOT_FOUND", "Nie znaleziono pozycji koszyka.", 404)
    cart = await update_item(session, cart_token, item_id, payload.quantity)
    return await _response(session, cart_token, discount_notice=cart.discount_notice)


@router.patch("/items/{item_id}/gift", response_model=CartResponse)
async def change_cart_item_gift(
    item_id: UUID,
    payload: CartGiftInput,
    session: SessionDependency,
    cart_token: Annotated[str | None, Cookie()] = None,
) -> CartResponse:
    """Toggle gift intent on a voucher owned by the current cart cookie."""
    if cart_token is None:
        raise DomainError("CART_ITEM_NOT_FOUND", "Nie znaleziono pozycji koszyka.", 404)
    cart = await set_item_gift(session, cart_token, item_id, payload.is_gift)
    return await _response(session, cart_token, discount_notice=cart.discount_notice)


@router.delete("/items/{item_id}", response_model=CartResponse)
async def remove_cart_item(
    item_id: UUID,
    session: SessionDependency,
    cart_token: Annotated[str | None, Cookie()] = None,
) -> CartResponse:
    """Remove only an item belonging to the current guest basket."""

    if cart_token is None:
        raise DomainError("CART_ITEM_NOT_FOUND", "Nie znaleziono pozycji koszyka.", 404)
    cart = await delete_item(session, cart_token, item_id)
    return await _response(session, cart_token, discount_notice=cart.discount_notice)


@router.delete("", response_model=CartResponse)
async def empty_cart(
    session: SessionDependency,
    cart_token: Annotated[str | None, Cookie()] = None,
) -> CartResponse:
    """Clear all lines while retaining the guest basket and its fixed expiry."""

    cart = await clear_cart(session, cart_token)
    return await _response(
        session,
        cart_token,
        discount_notice=cart.discount_notice if cart else None,
    )


@router.post("/discount", response_model=CartResponse)
async def apply_cart_discount(
    payload: DiscountCodeInput,
    session: SessionDependency,
    cart_token: Annotated[str | None, Cookie()] = None,
) -> CartResponse:
    """Validate and apply a code; all monetary values are calculated on the server."""
    await set_cart_discount(session, cart_token, payload.code)
    return await _response(session, cart_token)


@router.delete("/discount", response_model=CartResponse)
async def clear_cart_discount(
    session: SessionDependency,
    cart_token: Annotated[str | None, Cookie()] = None,
) -> CartResponse:
    await remove_cart_discount(session, cart_token)
    return await _response(session, cart_token)


@router.post("/reorder-report/{operation_id}/dismiss", status_code=204)
async def dismiss_reorder_summary(
    operation_id: UUID,
    session: SessionDependency,
    response: Response,
    cart_token: Annotated[str | None, Cookie()] = None,
) -> Response:
    """Dismiss only the report belonging to the current opaque cart cookie."""
    await dismiss_reorder_report(session, cart_token, operation_id)
    response.status_code = 204
    response.headers.update(
        {"Cache-Control": "private, no-store", "Referrer-Policy": "no-referrer"}
    )
    return response


@router.patch("/delivery", response_model=CartResponse)
async def choose_cart_delivery(
    payload: CartDeliveryInput,
    session: SessionDependency,
    cart_token: Annotated[str | None, Cookie()] = None,
) -> CartResponse:
    """Choose a delivery method; server-side settings determine the price."""
    await set_cart_delivery_method(session, cart_token, payload.method.value)
    return await _response(session, cart_token)


@router.get("/pickup-points", response_model=PickupPointListResponse)
async def search_cart_pickup_points(
    query: Annotated[str, Query(min_length=2, max_length=100)],
    session: SessionDependency,
    cart_token: Annotated[str | None, Cookie()] = None,
) -> PickupPointListResponse:
    """Search only operating InPost parcel lockers for the current shipping cart."""
    return await list_cart_points(session, cart_token, query)


@router.post("/pickup-point", response_model=CartResponse)
async def select_cart_pickup_point(
    payload: PickupPointCodeInput,
    session: SessionDependency,
    cart_token: Annotated[str | None, Cookie()] = None,
) -> CartResponse:
    """Resolve the operator record and persist its server-verified cart snapshot."""
    await choose_cart_point(session, cart_token, payload.code)
    return await _response(session, cart_token)


@router.post("/checkout", response_model=CheckoutResponse, status_code=201)
async def submit_checkout(
    payload: CheckoutInput,
    request: Request,
    session: SessionDependency,
    cart_token: Annotated[str | None, Cookie()] = None,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")] = "",
) -> CheckoutResponse:
    """Persist an idempotent pending-payment order; this does not initiate payment."""
    cart, _rows = await get_cart_rows(session, cart_token)
    verified_point: PickupPointSnapshot | None = None
    if cart is not None and cart.delivery_method == "parcel_locker":
        if cart.delivery_point_snapshot is None:
            await session.rollback()
            raise DomainError(
                "CHECKOUT_PICKUP_REQUIRED", "Wybierz i potwierdź Paczkomat InPost.", 422
            )
        code = cart.delivery_point_snapshot.get("code")
        await session.rollback()
        verified_point = await get_point(str(code))
    elif cart is not None:
        await session.rollback()
    from sensoria.modules.accounts.privacy import hashed_client_ip

    return await create_guest_order(
        session,
        cart_token,
        idempotency_key,
        payload,
        verified_pickup_point=verified_point,
        consent_ip_hash=hashed_client_ip(request),
    )


@router.get("/checkout-config", response_model=CheckoutConfigResponse)
async def read_checkout_config(session: SessionDependency) -> CheckoutConfigResponse:
    """Expose only the currently displayed checkout consent strings and version."""
    return CheckoutConfigResponse(**await checkout_consent_config(session))
