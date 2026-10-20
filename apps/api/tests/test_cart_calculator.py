"""Exact unit and property-style tests for cart tax settlement."""

from __future__ import annotations

import random
from uuid import UUID

import pytest
from sensoria.modules.orders.calculator import (
    CartCalculation,
    CartCalculator,
    CartLineInput,
    DeliverySettlement,
    DiscountInput,
)
from sensoria.shared.pricing import split_gross_price
from sensoria.shared.types import VatRate


def _line(identifier: int, unit_price: int, quantity: int, rate: VatRate) -> CartLineInput:
    return CartLineInput(
        item_id=UUID(int=identifier),
        unit_price_snapshot=unit_price,
        quantity=quantity,
        vat_rate_snapshot=rate,
    )


def test_empty_single_item_and_exempt_are_explicit() -> None:
    empty = CartCalculator.calculate([])
    assert empty.items == []
    assert empty.products_gross_grosz == empty.amount_due_grosz == 0
    assert empty.exempt.gross_grosz == 0
    assert [group.vat_rate for group in empty.vat_groups] == [
        VatRate.RATE_23,
        VatRate.RATE_8,
        VatRate.RATE_5,
        VatRate.RATE_0,
    ]

    one = CartCalculator.calculate([_line(1, 100, 1, VatRate.RATE_23)])
    assert (one.items[0].gross_grosz, one.items[0].net_grosz, one.items[0].tax_grosz) == (
        100,
        81,
        19,
    )

    zero_and_exempt = CartCalculator.calculate(
        [_line(2, 1000, 1, VatRate.RATE_0), _line(3, 1000, 1, VatRate.EXEMPT)]
    )
    zero_group = next(
        group for group in zero_and_exempt.vat_groups if group.vat_rate is VatRate.RATE_0
    )
    assert (zero_group.gross_grosz, zero_group.net_grosz, zero_group.tax_grosz) == (
        1000,
        1000,
        0,
    )
    assert zero_and_exempt.exempt.vat_label == "zw."
    assert zero_and_exempt.exempt.gross_grosz == zero_and_exempt.exempt.net_grosz == 1000
    assert zero_and_exempt.exempt.tax_grosz == 0


def test_mockup_cart_exact_breakdown_and_snapshot_round_trip() -> None:
    result = CartCalculator.calculate(
        [
            _line(1, 7900, 1, VatRate.RATE_5),
            _line(2, 25000, 1, VatRate.EXEMPT),
            _line(3, 5900, 2, VatRate.RATE_5),
        ],
        delivery=DeliverySettlement(resolved=True),
    )
    assert [(line.gross_grosz, line.net_grosz, line.tax_grosz) for line in result.items] == [
        (7900, 7524, 376),
        (25000, 25000, 0),
        (11800, 11238, 562),
    ]
    group = next(group for group in result.vat_groups if group.vat_rate is VatRate.RATE_5)
    assert (group.gross_grosz, group.net_grosz, group.tax_grosz) == (19700, 18762, 938)
    assert (result.exempt.gross_grosz, result.exempt.net_grosz, result.exempt.tax_grosz) == (
        25000,
        25000,
        0,
    )
    assert result.products_gross_grosz == result.amount_due_grosz == 44700

    frozen = CartCalculation.model_validate_json(result.model_dump_json())
    assert frozen == result
    assert CartCalculation.model_validate_json(frozen.model_dump_json()) == frozen
    # Catalog changes cannot affect a serialized settlement built from snapshots.
    later_catalog_price = 999999
    assert later_catalog_price != frozen.items[0].unit_price_snapshot


def test_discount_allocation_reconciles_cart_and_vat_after_discount() -> None:
    result = CartCalculator.calculate(
        [
            _line(1, 7900, 1, VatRate.RATE_5),
            _line(2, 25000, 1, VatRate.EXEMPT),
            _line(3, 5900, 2, VatRate.RATE_5),
        ],
        discount=DiscountInput(code="TEN", type="percentage", value=10),
        delivery=DeliverySettlement(resolved=True),
    )
    assert result.products_gross_before_discount_grosz == 44700
    assert result.discount_grosz == 4470
    assert [line.discount_grosz for line in result.items] == [790, 2500, 1180]
    assert result.products_gross_grosz == result.amount_due_grosz == 40230
    assert [line.gross_grosz for line in result.items] == [7110, 22500, 10620]
    assert all(line.net_grosz + line.tax_grosz == line.gross_grosz for line in result.items)
    group = next(group for group in result.vat_groups if group.vat_rate is VatRate.RATE_5)
    assert group.gross_grosz == 17730
    assert result.exempt.vat_rate is VatRate.EXEMPT
    assert result.exempt.gross_grosz == 22500
    assert result.discount_code == "TEN"


def test_fixed_discount_caps_and_deterministic_single_grosz_remainder() -> None:
    lines = [_line(1, 1, 1, VatRate.RATE_0), _line(2, 1, 1, VatRate.EXEMPT)]
    result = CartCalculator.calculate(
        lines, discount=DiscountInput(code="FIX", type="fixed_amount", value=5)
    )
    assert result.discount_grosz == 2
    assert [line.discount_grosz for line in result.items] == [1, 1]
    assert result.products_gross_grosz == 0
    capped = CartCalculator.calculate(
        [_line(3, 100, 1, VatRate.EXEMPT)],
        discount=DiscountInput(code="FIX", type="fixed_amount", value=500),
    )
    assert capped.discount_grosz == 100
    assert capped.exempt.vat_rate is VatRate.EXEMPT
    assert capped.exempt.gross_grosz == capped.exempt.net_grosz == 0


def test_group_rounding_is_distributed_by_gross_then_stable_id() -> None:
    result = CartCalculator.calculate(
        [_line(2, 2, 1, VatRate.RATE_23), _line(1, 2, 1, VatRate.RATE_23)]
    )
    first, second = sorted(result.items, key=lambda line: str(line.item_id))
    assert first.rounding_adjustment_grosz == -1
    assert second.rounding_adjustment_grosz == 0
    assert (first.net_grosz, first.tax_grosz) == (1, 1)
    assert (second.net_grosz, second.tax_grosz) == (2, 0)
    assert sum(line.net_grosz for line in result.items) == 3
    assert sum(line.tax_grosz for line in result.items) == 1


def test_one_grosz_positions_and_all_vat_rates() -> None:
    tiny = CartCalculator.calculate(
        [_line(identifier, 1, 1, VatRate.RATE_23) for identifier in (3, 1, 2)]
    )
    assert sorted(line.rounding_adjustment_grosz for line in tiny.items) == [-1, 0, 0]
    assert all(line.net_grosz >= 0 and line.tax_grosz >= 0 for line in tiny.items)
    mixed = CartCalculator.calculate(
        [_line(index + 1, 12345, index + 1, rate) for index, rate in enumerate(VatRate)]
    )
    assert {group.vat_rate for group in mixed.vat_groups} == {
        VatRate.RATE_23,
        VatRate.RATE_8,
        VatRate.RATE_5,
        VatRate.RATE_0,
    }
    exempt_line = next(line for line in mixed.items if line.vat_rate is VatRate.EXEMPT)
    assert exempt_line.gross_grosz == exempt_line.net_grosz and exempt_line.tax_grosz == 0

    distributed = CartCalculator.calculate(
        [_line(identifier, 1, 1, VatRate.RATE_23) for identifier in range(1, 11)]
    )
    assert sum(line.rounding_adjustment_grosz for line in distributed.items) == -2
    assert sum(line.rounding_adjustment_grosz != 0 for line in distributed.items) == 2


def test_quantity_recalculation_is_stateless_and_has_no_rounding_drift() -> None:
    original = _line(1, 2, 2, VatRate.RATE_23)
    expanded = _line(1, 2, 3, VatRate.RATE_23)
    original_result = CartCalculator.calculate([original])
    expanded_result = CartCalculator.calculate([expanded])
    returned_result = CartCalculator.calculate([original])
    assert original_result.items[0].gross_grosz == 4
    assert expanded_result.items[0].gross_grosz == 6
    assert returned_result == original_result


def test_delivery_requires_an_explicit_tax_settlement() -> None:
    with pytest.raises(ValueError, match="Płatna dostawa"):
        CartCalculator.calculate([], delivery=DeliverySettlement(resolved=True, gross_grosz=100))
    delivery_split = split_gross_price(100, VatRate.RATE_8)
    delivery = DeliverySettlement(
        resolved=True,
        gross_grosz=delivery_split.gross_grosz,
        net_grosz=delivery_split.net_grosz,
        tax_grosz=delivery_split.tax_grosz,
        vat_rate=VatRate.RATE_8,
        vat_label=delivery_split.vat_label,
    )
    result = CartCalculator.calculate([_line(1, 1000, 1, VatRate.RATE_5)], delivery=delivery)
    assert result.amount_due_grosz == 1100
    assert result.products_gross_grosz == 1000


def test_thousand_repeatable_random_baskets_preserve_all_invariants() -> None:
    randomizer = random.Random(250314)
    rates = tuple(VatRate)
    for basket_number in range(1000):
        inputs = [
            _line(
                basket_number * 10 + index + 1,
                randomizer.randrange(0, 250_000),
                randomizer.randrange(1, 8),
                randomizer.choice(rates),
            )
            for index in range(randomizer.randrange(0, 10))
        ]
        delivery_gross = randomizer.randrange(0, 100_000)
        delivery_rate = randomizer.choice(rates)
        delivery_split = split_gross_price(delivery_gross, delivery_rate)
        delivery = DeliverySettlement(
            resolved=True,
            gross_grosz=delivery_split.gross_grosz,
            net_grosz=delivery_split.net_grosz,
            tax_grosz=delivery_split.tax_grosz,
            vat_rate=delivery_rate if delivery_gross else None,
            vat_label=delivery_split.vat_label if delivery_gross else None,
        )
        calculated = CartCalculator.calculate(inputs, delivery=delivery)
        assert calculated == CartCalculator.calculate(inputs, delivery=delivery)
        assert calculated.amount_due_grosz == (
            calculated.products_gross_grosz + calculated.delivery.gross_grosz
        )
        assert all(
            min(line.gross_grosz, line.net_grosz, line.tax_grosz) >= 0
            and line.net_grosz + line.tax_grosz == line.gross_grosz
            for line in calculated.items
        )
        for group in calculated.vat_groups:
            group_lines = [line for line in calculated.items if line.vat_rate is group.vat_rate]
            assert group.gross_grosz == sum(line.gross_grosz for line in group_lines)
            assert group.net_grosz == sum(line.net_grosz for line in group_lines)
            assert group.tax_grosz == sum(line.tax_grosz for line in group_lines)
            control = split_gross_price(group.gross_grosz, group.vat_rate)
            assert (group.net_grosz, group.tax_grosz) == (control.net_grosz, control.tax_grosz)
        assert (
            sum(group.gross_grosz for group in calculated.vat_groups)
            + (calculated.exempt.gross_grosz)
            == calculated.products_gross_grosz
        )
        assert calculated.exempt.net_grosz == calculated.exempt.gross_grosz
        assert calculated.exempt.tax_grosz == 0
