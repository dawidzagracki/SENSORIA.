"""Validated, database-backed delivery pricing for guest carts."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, StrictInt, ValidationError, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sensoria.shared.app_settings import AppSetting
from sensoria.shared.errors import DomainError
from sensoria.shared.pricing import split_gross_price, vat_label
from sensoria.shared.types import VatRate, format_money, validate_money

from .calculator import DeliverySettlement

DELIVERY_SETTING_KEY = "orders.delivery.v1"


class DeliveryMethod(StrEnum):
    PARCEL_LOCKER = "parcel_locker"
    COURIER = "courier"


class DeliveryPolicy(BaseModel):
    """Operator-configured values; all currency fields are integer grosz."""

    # StrictInt fields reject floats/bools; enum JSONB values use their stable string form.
    model_config = ConfigDict(extra="forbid")

    parcel_locker_cost_grosz: StrictInt
    courier_cost_grosz: StrictInt
    free_shipping_threshold_grosz: StrictInt
    incentive_threshold_grosz: StrictInt
    vat_rate: VatRate

    @field_validator(
        "parcel_locker_cost_grosz",
        "courier_cost_grosz",
        "free_shipping_threshold_grosz",
        "incentive_threshold_grosz",
    )
    @classmethod
    def nonnegative_grosz(cls, value: int) -> int:
        validate_money(value)
        if value < 0:
            raise ValueError("Kwoty i progi dostawy nie mogą być ujemne.")
        return value


class DeliveryQuote(BaseModel):
    method: DeliveryMethod
    gross_grosz: int
    net_grosz: int
    tax_grosz: int
    vat_rate: VatRate
    vat_label: str


class DeliveryStatus(BaseModel):
    requires_shipping: bool
    selected_method: DeliveryMethod | None
    available_quotes: list[DeliveryQuote]
    requires_method_selection: bool
    threshold_basis_grosz: int
    free_shipping_threshold_grosz: int | None
    remaining_amount_grosz: int | None
    free_shipping_qualified: bool
    show_incentive: bool
    message: str | None
    settlement: DeliverySettlement


async def load_delivery_policy(session: AsyncSession) -> DeliveryPolicy:
    """Read settings on every request so operator edits take effect immediately."""

    setting = await session.scalar(select(AppSetting).where(AppSetting.key == DELIVERY_SETTING_KEY))
    if setting is None:
        raise DomainError(
            "DELIVERY_SETTINGS_MISSING",
            "Ustawienia kosztów i podatku dostawy nie są skonfigurowane.",
            503,
        )
    try:
        return DeliveryPolicy.model_validate(setting.value)
    except (ValidationError, TypeError, ValueError):
        raise DomainError(
            "DELIVERY_SETTINGS_INVALID",
            "Ustawienia kosztów i podatku dostawy są nieprawidłowe.",
            503,
        ) from None


def _quote(
    method: DeliveryMethod,
    policy: DeliveryPolicy,
    *,
    free: bool,
) -> DeliveryQuote:
    cost = (
        0
        if free
        else (
            policy.parcel_locker_cost_grosz
            if method is DeliveryMethod.PARCEL_LOCKER
            else policy.courier_cost_grosz
        )
    )
    split = split_gross_price(cost, policy.vat_rate)
    return DeliveryQuote(
        method=method,
        gross_grosz=cost,
        net_grosz=split.net_grosz,
        tax_grosz=split.tax_grosz,
        vat_rate=policy.vat_rate,
        vat_label=vat_label(policy.vat_rate),
    )


async def resolve_delivery(
    session: AsyncSession,
    *,
    requires_shipping: bool,
    selected_method: str | None,
    products_gross_after_discount_grosz: int,
) -> tuple[DeliveryStatus, DeliverySettlement]:
    """Resolve quotes and messages using the post-discount product subtotal."""

    validate_money(products_gross_after_discount_grosz)
    if products_gross_after_discount_grosz < 0:
        raise ValueError("Wartość produktów nie może być ujemna.")
    if not requires_shipping:
        return build_delivery_result(
            None,
            requires_shipping=False,
            selected_method=None,
            products_gross_after_discount_grosz=products_gross_after_discount_grosz,
        )
    policy = await load_delivery_policy(session)
    return build_delivery_result(
        policy,
        requires_shipping=True,
        selected_method=selected_method,
        products_gross_after_discount_grosz=products_gross_after_discount_grosz,
    )


def build_delivery_result(
    policy: DeliveryPolicy | None,
    *,
    requires_shipping: bool,
    selected_method: str | None,
    products_gross_after_discount_grosz: int,
) -> tuple[DeliveryStatus, DeliverySettlement]:
    """Pure rule calculation, separated from database setting retrieval."""
    validate_money(products_gross_after_discount_grosz)
    if products_gross_after_discount_grosz < 0:
        raise ValueError("Wartość produktów nie może być ujemna.")
    if not requires_shipping:
        settlement = DeliverySettlement(resolved=True)
        return (
            DeliveryStatus(
                requires_shipping=False,
                selected_method=None,
                available_quotes=[],
                requires_method_selection=False,
                threshold_basis_grosz=products_gross_after_discount_grosz,
                free_shipping_threshold_grosz=None,
                remaining_amount_grosz=None,
                free_shipping_qualified=False,
                show_incentive=False,
                message=None,
                settlement=settlement,
            ),
            settlement,
        )
    if policy is None:
        raise ValueError("Koszyk wymagający przesyłki musi mieć ustawioną politykę dostawy.")
    method: DeliveryMethod | None = None
    if selected_method is not None:
        try:
            method = DeliveryMethod(selected_method)
        except ValueError:
            raise DomainError(
                "DELIVERY_METHOD_INVALID", "Wybierz dostępną metodę dostawy.", 422
            ) from None
    qualifies = products_gross_after_discount_grosz >= policy.free_shipping_threshold_grosz
    remaining = max(0, policy.free_shipping_threshold_grosz - products_gross_after_discount_grosz)
    quotes = [_quote(candidate, policy, free=qualifies) for candidate in DeliveryMethod]
    selected_quote = next((quote for quote in quotes if quote.method is method), None)
    settlement = (
        DeliverySettlement(
            resolved=True,
            gross_grosz=selected_quote.gross_grosz,
            net_grosz=selected_quote.net_grosz,
            tax_grosz=selected_quote.tax_grosz,
            vat_rate=selected_quote.vat_rate,
            vat_label=selected_quote.vat_label,
        )
        if selected_quote is not None
        else DeliverySettlement()
    )
    threshold_text = format_money(policy.free_shipping_threshold_grosz)
    message: str | None = None
    show_incentive = False
    if qualifies:
        wording = (
            "przekroczyło"
            if products_gross_after_discount_grosz > policy.free_shipping_threshold_grosz
            else "osiągnęło próg"
        )
        message = f"Darmowa dostawa — Twoje zamówienie {wording} {threshold_text}"
    elif remaining > 0 and remaining < policy.incentive_threshold_grosz:
        show_incentive = True
        message = f"Do darmowej dostawy brakuje Ci {format_money(remaining)}"

    status = DeliveryStatus(
        requires_shipping=True,
        selected_method=method,
        available_quotes=quotes,
        requires_method_selection=method is None,
        threshold_basis_grosz=products_gross_after_discount_grosz,
        free_shipping_threshold_grosz=policy.free_shipping_threshold_grosz,
        remaining_amount_grosz=remaining,
        free_shipping_qualified=qualifies,
        show_incentive=show_incentive,
        message=message,
        settlement=settlement,
    )
    return status, settlement
