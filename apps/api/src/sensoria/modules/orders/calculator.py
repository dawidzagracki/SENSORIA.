"""Deterministic cart settlement from immutable item price and VAT snapshots."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import cast
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StrictInt, field_validator

from sensoria.shared.pricing import split_gross_price, vat_label
from sensoria.shared.types import VatRate, validate_money

CALCULATION_VERSION = "1"
_PERCENT_RATES = (VatRate.RATE_23, VatRate.RATE_8, VatRate.RATE_5, VatRate.RATE_0)


@dataclass(frozen=True, slots=True)
class CartLineInput:
    """The only monetary inputs accepted by the calculator are cart snapshots."""

    item_id: UUID
    unit_price_snapshot: int
    quantity: int
    vat_rate_snapshot: VatRate


@dataclass(frozen=True, slots=True)
class DiscountInput:
    """Validated server-side discount terms; percentage value 10 means ten percent."""

    code: str
    type: str
    value: int


class CartLineSettlement(BaseModel):
    item_id: UUID
    unit_price_snapshot: int
    quantity: int
    vat_rate: VatRate
    vat_label: str
    gross_grosz: int
    discount_grosz: int = 0
    gross_before_discount_grosz: int = 0
    net_grosz: int
    tax_grosz: int
    # Signed grosz added to preliminary net; tax receives the opposite adjustment.
    rounding_adjustment_grosz: int


class VatGroupSettlement(BaseModel):
    vat_rate: VatRate
    vat_label: str
    gross_grosz: int
    net_grosz: int
    tax_grosz: int


class ExemptSettlement(BaseModel):
    vat_rate: VatRate = VatRate.EXEMPT
    vat_label: str = "zw."
    gross_grosz: int
    net_grosz: int
    tax_grosz: int


class DeliverySettlement(BaseModel):
    """Explicit result supplied by a future delivery integration [27]."""

    model_config = ConfigDict(extra="forbid")

    resolved: bool = False
    gross_grosz: StrictInt = 0
    net_grosz: StrictInt = 0
    tax_grosz: StrictInt = 0
    vat_rate: VatRate | None = None
    vat_label: str | None = None

    @field_validator("gross_grosz", "net_grosz", "tax_grosz")
    @classmethod
    def valid_amount(cls, value: int) -> int:
        validate_money(value)
        if value < 0:
            raise ValueError("Kwoty dostawy nie mogą być ujemne.")
        return value

    def validate_settlement(self) -> None:
        if not self.resolved:
            if (
                self.gross_grosz
                or self.net_grosz
                or self.tax_grosz
                or self.vat_rate
                or self.vat_label
            ):
                raise ValueError("Nierozliczona dostawa nie może zawierać kwot ani stawki VAT.")
            return
        if self.gross_grosz > 0 and self.vat_rate is None:
            raise ValueError("Płatna dostawa wymaga jawnego rozliczenia VAT z etapu [27].")
        if self.gross_grosz != self.net_grosz + self.tax_grosz:
            raise ValueError("Rozliczenie dostawy musi sumować się co do grosza.")
        if self.gross_grosz == 0:
            if self.net_grosz or self.tax_grosz:
                raise ValueError("Zerowa dostawa nie może mieć kwot netto ani podatku.")
            return
        if self.vat_rate is None or self.vat_label != vat_label(self.vat_rate):
            raise ValueError("Płatna dostawa wymaga jawnego rozliczenia VAT z etapu [27].")
        expected = split_gross_price(self.gross_grosz, self.vat_rate)
        if (self.net_grosz, self.tax_grosz) != (expected.net_grosz, expected.tax_grosz):
            raise ValueError("Rozliczenie VAT dostawy jest niespójne.")


class CartCalculation(BaseModel):
    """JSON-serializable settlement contract and future order snapshot [29]."""

    calculation_version: str = CALCULATION_VERSION
    items: list[CartLineSettlement]
    vat_groups: list[VatGroupSettlement]
    exempt: ExemptSettlement
    products_gross_grosz: int
    products_gross_before_discount_grosz: int = 0
    discount_grosz: int = 0
    discount_code: str | None = None
    delivery: DeliverySettlement
    amount_due_grosz: int
    amount_due_is_final: bool


class CartCalculator:
    """Calculate positions, reconcile each percentage VAT group, then totals."""

    @staticmethod
    def calculate(
        items: Iterable[CartLineInput],
        *,
        delivery: DeliverySettlement | None = None,
        discount: DiscountInput | None = None,
    ) -> CartCalculation:
        delivery_result = delivery or DeliverySettlement()
        delivery_result.validate_settlement()
        raw_lines: list[dict[str, int | UUID | VatRate | str]] = []
        seen_item_ids: set[UUID] = set()
        for item in items:
            if not isinstance(item.item_id, UUID):
                raise TypeError("Identyfikator pozycji musi być UUID.")
            if item.item_id in seen_item_ids:
                raise ValueError("Identyfikatory pozycji koszyka muszą być unikalne.")
            seen_item_ids.add(item.item_id)
            validate_money(item.unit_price_snapshot)
            if item.unit_price_snapshot < 0:
                raise ValueError("Cena snapshotu nie może być ujemna.")
            if isinstance(item.quantity, bool) or not isinstance(item.quantity, int):
                raise TypeError("Ilość musi być liczbą całkowitą.")
            if item.quantity < 1:
                raise ValueError("Ilość musi być dodatnia.")
            if not isinstance(item.vat_rate_snapshot, VatRate):
                raise TypeError("Stawka VAT snapshotu musi być wartością VatRate.")
            gross = item.unit_price_snapshot * item.quantity
            validate_money(gross)
            preliminary = split_gross_price(gross, item.vat_rate_snapshot)
            raw_lines.append(
                {
                    "item_id": item.item_id,
                    "unit_price_snapshot": item.unit_price_snapshot,
                    "quantity": item.quantity,
                    "vat_rate": item.vat_rate_snapshot,
                    "vat_label": preliminary.vat_label,
                    "gross_grosz": gross,
                    "net_grosz": preliminary.net_grosz,
                    "tax_grosz": preliminary.tax_grosz,
                    "rounding_adjustment_grosz": 0,
                }
            )

        gross_before_discount = sum(int(line["gross_grosz"]) for line in raw_lines)
        validate_money(gross_before_discount)
        discount_total = 0
        if discount is not None:
            if discount.type == "percentage":
                if not 1 <= discount.value <= 100:
                    raise ValueError("Nieprawidłowa wartość procentowa kodu rabatowego.")
                discount_total = (gross_before_discount * discount.value + 50) // 100
            elif discount.type == "fixed_amount":
                if discount.value <= 0:
                    raise ValueError("Kwota rabatu musi być dodatnia.")
                discount_total = min(discount.value, gross_before_discount)
            else:
                raise ValueError("Nieznany rodzaj kodu rabatowego.")
            validate_money(discount_total)
            if gross_before_discount:
                allocations = [
                    discount_total * int(line["gross_grosz"]) // gross_before_discount
                    for line in raw_lines
                ]
                remaining = discount_total - sum(allocations)
                ordered = sorted(
                    range(len(raw_lines)),
                    key=lambda index: (
                        -int(raw_lines[index]["gross_grosz"]),
                        str(raw_lines[index]["item_id"]),
                    ),
                )
                for index in ordered:
                    if remaining == 0:
                        break
                    capacity = int(raw_lines[index]["gross_grosz"]) - allocations[index]
                    applied = min(capacity, remaining)
                    allocations[index] += applied
                    remaining -= applied
                if remaining:
                    raise ArithmeticError("Nie można rozdzielić rabatu na pozycje koszyka.")
                for index, line in enumerate(raw_lines):
                    before = int(line["gross_grosz"])
                    line["gross_before_discount_grosz"] = before
                    line["discount_grosz"] = allocations[index]
                    line["gross_grosz"] = before - allocations[index]
                    split = split_gross_price(
                        int(line["gross_grosz"]),
                        cast(VatRate, line["vat_rate"]),
                    )
                    line["net_grosz"] = split.net_grosz
                    line["tax_grosz"] = split.tax_grosz
            else:
                for line in raw_lines:
                    line["gross_before_discount_grosz"] = int(line["gross_grosz"])
                    line["discount_grosz"] = 0
        else:
            for line in raw_lines:
                line["gross_before_discount_grosz"] = int(line["gross_grosz"])
                line["discount_grosz"] = 0

        if sum(int(line["discount_grosz"]) for line in raw_lines) != discount_total:
            raise ArithmeticError("Alokacja pozycji nie sumuje się do rabatu całkowitego.")
        if sum(
            int(line["gross_before_discount_grosz"]) for line in raw_lines
        ) - discount_total != sum(int(line["gross_grosz"]) for line in raw_lines):
            raise ArithmeticError("Rabat nie zgadza się z kwotami brutto pozycji.")

        groups: list[VatGroupSettlement] = []
        for rate in _PERCENT_RATES:
            line_indexes = [
                index for index, line in enumerate(raw_lines) if line["vat_rate"] is rate
            ]
            group_gross = sum(int(raw_lines[index]["gross_grosz"]) for index in line_indexes)
            validate_money(group_gross)
            control = split_gross_price(group_gross, rate)
            preliminary_net = sum(int(raw_lines[index]["net_grosz"]) for index in line_indexes)
            adjustment_left = control.net_grosz - preliminary_net
            ordered_indexes = sorted(
                line_indexes,
                key=lambda index: (
                    -int(raw_lines[index]["gross_grosz"]),
                    str(raw_lines[index]["item_id"]),
                ),
            )
            for index in ordered_indexes:
                if adjustment_left == 0:
                    break
                line = raw_lines[index]
                net = int(line["net_grosz"])
                tax = int(line["tax_grosz"])
                gross = int(line["gross_grosz"])
                capacity = gross - net if adjustment_left > 0 else net
                applied = min(abs(adjustment_left), capacity)
                if adjustment_left < 0:
                    applied = -applied
                line["net_grosz"] = net + applied
                line["tax_grosz"] = tax - applied
                line["rounding_adjustment_grosz"] = applied
                adjustment_left -= applied
            if adjustment_left != 0:
                raise ArithmeticError("Nie można rozdzielić korekty zaokrąglenia VAT.")

            group_lines = [raw_lines[index] for index in line_indexes]
            corrected_net = sum(int(line["net_grosz"]) for line in group_lines)
            corrected_tax = sum(int(line["tax_grosz"]) for line in group_lines)
            if corrected_net != control.net_grosz or corrected_tax != control.tax_grosz:
                raise ArithmeticError("Pozycje po korekcie nie zgadzają się z grupą VAT.")
            groups.append(
                VatGroupSettlement(
                    vat_rate=rate,
                    vat_label=vat_label(rate),
                    gross_grosz=group_gross,
                    net_grosz=control.net_grosz,
                    tax_grosz=control.tax_grosz,
                )
            )

        exempt_lines = [line for line in raw_lines if line["vat_rate"] is VatRate.EXEMPT]
        exempt_gross = sum(int(line["gross_grosz"]) for line in exempt_lines)
        exempt = ExemptSettlement(
            gross_grosz=exempt_gross,
            net_grosz=exempt_gross,
            tax_grosz=0,
        )
        settled_lines = [CartLineSettlement.model_validate(line) for line in raw_lines]
        for settled_line in settled_lines:
            if settled_line.net_grosz + settled_line.tax_grosz != settled_line.gross_grosz:
                raise ArithmeticError("Netto i podatek pozycji nie sumują się do brutto.")

        products_gross = sum(line.gross_grosz for line in settled_lines)
        validate_money(products_gross)
        if sum(group.gross_grosz for group in groups) + exempt.gross_grosz != products_gross:
            raise ArithmeticError("Grupy VAT nie sumują się do brutto produktów.")
        due = products_gross + delivery_result.gross_grosz
        validate_money(due)
        return CartCalculation(
            items=settled_lines,
            vat_groups=groups,
            exempt=exempt,
            products_gross_grosz=products_gross,
            products_gross_before_discount_grosz=gross_before_discount,
            discount_grosz=discount_total,
            discount_code=discount.code if discount is not None else None,
            delivery=delivery_result,
            amount_due_grosz=due,
            amount_due_is_final=delivery_result.resolved,
        )
