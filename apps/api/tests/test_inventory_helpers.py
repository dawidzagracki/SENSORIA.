"""Pure inventory invariants that do not require a database fixture."""

import pytest
from sensoria.modules.catalog.inventory import (
    available_quantity,
    calculate_shipment_weight,
    is_low_stock_crossing,
)


@pytest.mark.parametrize(
    ("stock", "reserved", "available"),
    [(8, 0, 8), (8, 3, 5), (0, 0, 0)],
)
def test_available_quantity_separates_physical_stock_from_holds(
    stock: int, reserved: int, available: int
) -> None:
    assert available_quantity(stock, reserved) == available


@pytest.mark.parametrize(("stock", "reserved"), [(2, 3), (-1, 0), (True, 0)])
def test_available_quantity_rejects_impossible_or_non_integer_states(
    stock: int, reserved: int
) -> None:
    with pytest.raises(ValueError):
        available_quantity(stock, reserved)


def test_shipment_weight_uses_grams_and_only_the_passed_physical_lines() -> None:
    assert calculate_shipment_weight([(320, 2), (410, 1)]) == 1050
    assert calculate_shipment_weight([]) == 0


@pytest.mark.parametrize(("lines",), [([(0, 1)],), ([(100, 0)],), ([(True, 1)],)])
def test_shipment_weight_rejects_invalid_values(lines: list[tuple[int, int]]) -> None:
    with pytest.raises(ValueError):
        calculate_shipment_weight(lines)


@pytest.mark.parametrize(
    ("previous", "current", "threshold", "expected"),
    [
        (10, 9, 10, True),
        (9, 8, 10, False),
        (10, 10, 10, False),
        (4, 3, 0, False),
        (11, 9, 10, True),
    ],
)
def test_low_stock_alert_is_only_a_downward_physical_threshold_crossing(
    previous: int, current: int, threshold: int, expected: bool
) -> None:
    assert is_low_stock_crossing(previous, current, threshold) is expected
