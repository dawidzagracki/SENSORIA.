"""Pure tests for database-configured delivery pricing rules."""

from __future__ import annotations

import pytest
from sensoria.modules.orders.delivery import (
    DeliveryMethod,
    DeliveryPolicy,
    build_delivery_result,
)
from sensoria.shared.types import VatRate


@pytest.fixture
def policy() -> DeliveryPolicy:
    return DeliveryPolicy(
        parcel_locker_cost_grosz=1200,
        courier_cost_grosz=1800,
        free_shipping_threshold_grosz=15000,
        incentive_threshold_grosz=5000,
        vat_rate=VatRate.RATE_23,
    )


def test_digital_or_empty_basket_never_gets_shipping_messages(policy: DeliveryPolicy) -> None:
    status, settlement = build_delivery_result(
        policy,
        requires_shipping=False,
        selected_method=None,
        products_gross_after_discount_grosz=0,
    )
    assert not status.requires_shipping
    assert status.available_quotes == []
    assert status.message is None
    assert status.remaining_amount_grosz is None
    assert settlement.resolved and settlement.gross_grosz == 0


@pytest.mark.parametrize(
    ("amount", "free", "remaining", "message_part"),
    [
        (14999, False, 1, "brakuje Ci 0,01 zł"),
        (15000, True, 0, "osiągnęło próg 150,00 zł"),
        (15001, True, 0, "przekroczyło 150,00 zł"),
    ],
)
def test_free_shipping_boundary_is_inclusive(
    policy: DeliveryPolicy, amount: int, free: bool, remaining: int, message_part: str
) -> None:
    status, settlement = build_delivery_result(
        policy,
        requires_shipping=True,
        selected_method=DeliveryMethod.PARCEL_LOCKER.value,
        products_gross_after_discount_grosz=amount,
    )
    assert status.free_shipping_qualified is free
    assert status.remaining_amount_grosz == remaining
    assert status.message is not None and message_part in status.message
    assert settlement.gross_grosz == (0 if free else 1200)
    assert settlement.vat_rate is VatRate.RATE_23


def test_incentive_uses_strict_configured_limit_and_shipping_vat(policy: DeliveryPolicy) -> None:
    at_limit, _ = build_delivery_result(
        policy,
        requires_shipping=True,
        selected_method=None,
        products_gross_after_discount_grosz=10000,
    )
    below_limit, settlement = build_delivery_result(
        policy,
        requires_shipping=True,
        selected_method=DeliveryMethod.COURIER.value,
        products_gross_after_discount_grosz=10001,
    )
    assert not at_limit.show_incentive
    assert at_limit.message is None
    assert below_limit.show_incentive
    assert below_limit.remaining_amount_grosz == 4999
    assert below_limit.message == "Do darmowej dostawy brakuje Ci 49,99 zł"
    assert (settlement.gross_grosz, settlement.net_grosz, settlement.tax_grosz) == (
        1800,
        1463,
        337,
    )
    assert settlement.vat_rate is VatRate.RATE_23


def test_policy_rejects_float_negative_and_invalid_vat() -> None:
    base = {
        "parcel_locker_cost_grosz": 1200,
        "courier_cost_grosz": 1800,
        "free_shipping_threshold_grosz": 15000,
        "incentive_threshold_grosz": 5000,
        "vat_rate": "RATE_23",
    }
    with pytest.raises(ValueError):
        DeliveryPolicy.model_validate({**base, "courier_cost_grosz": 18.0})
    with pytest.raises(ValueError):
        DeliveryPolicy.model_validate({**base, "parcel_locker_cost_grosz": -1})
    with pytest.raises(ValueError):
        DeliveryPolicy.model_validate({**base, "vat_rate": "INVALID"})
