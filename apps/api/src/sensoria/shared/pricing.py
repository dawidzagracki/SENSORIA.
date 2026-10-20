"""Exact gross-to-net VAT calculations in whole grosz."""

from dataclasses import dataclass

from sensoria.shared.types import VatRate, validate_money

_VAT_PERCENT: dict[VatRate, int] = {
    VatRate.RATE_23: 23,
    VatRate.RATE_8: 8,
    VatRate.RATE_5: 5,
    VatRate.RATE_0: 0,
    VatRate.EXEMPT: 0,
}


@dataclass(frozen=True, slots=True)
class PriceBreakdown:
    """Amounts in grosz and the display label that preserves VAT exemption."""

    gross_grosz: int
    net_grosz: int
    tax_grosz: int
    vat_rate: VatRate
    vat_label: str


def vat_label(vat_rate: VatRate) -> str:
    """Return a stable Polish VAT label; exemption is not a zero rate."""

    _require_vat_rate(vat_rate)
    return "zw." if vat_rate is VatRate.EXEMPT else f"{_VAT_PERCENT[vat_rate]}%"


def split_gross_price(gross_grosz: int, vat_rate: VatRate) -> PriceBreakdown:
    """Split gross into net and tax, rounding net HALF_UP to one grosz.

    For percentage rates, net = gross / (1 + rate). The integer formula
    implements ROUND_HALF_UP exactly; tax is always gross minus rounded net.
    """

    validate_money(gross_grosz)
    if gross_grosz < 0:
        raise ValueError("Cena brutto nie może być ujemna.")
    _require_vat_rate(vat_rate)
    percent = _VAT_PERCENT[vat_rate]
    if vat_rate in (VatRate.RATE_0, VatRate.EXEMPT):
        net = gross_grosz
    else:
        denominator = 100 + percent
        # Exact nearest-integer division with ties rounded away from zero.
        net = (2 * gross_grosz * 100 + denominator) // (2 * denominator)
    tax = gross_grosz - net
    return PriceBreakdown(gross_grosz, net, tax, vat_rate, vat_label(vat_rate))


def _require_vat_rate(vat_rate: VatRate) -> None:
    if not isinstance(vat_rate, VatRate):
        raise TypeError("Stawka VAT musi być wartością VatRate.")
