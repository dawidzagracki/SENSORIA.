"""Shared database and application types for money, tax rates, and currency."""

from enum import StrEnum
from typing import Any, cast

from sqlalchemy import BigInteger, String
from sqlalchemy.engine import Dialect
from sqlalchemy.types import TypeDecorator

POSTGRES_BIGINT_MIN = -(2**63)
POSTGRES_BIGINT_MAX = 2**63 - 1


class Money(TypeDecorator[int]):
    """Whole grosz stored as PostgreSQL BIGINT; floats and booleans are rejected."""

    impl = BigInteger
    cache_ok = True

    def process_bind_param(self, value: int | None, dialect: Dialect) -> int | None:
        del dialect
        if value is None:
            return None
        return validate_money(value)

    def process_result_value(self, value: Any, dialect: Dialect) -> int | None:
        del dialect
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError("Wartość Money z bazy nie jest liczbą całkowitą.")
        return cast(int, value)


class VatRate(StrEnum):
    """Application VAT values; exempt is distinct from a zero-percent rate."""

    RATE_23 = "RATE_23"
    RATE_8 = "RATE_8"
    RATE_5 = "RATE_5"
    RATE_0 = "RATE_0"
    EXEMPT = "EXEMPT"


class VatRateType(TypeDecorator[VatRate]):
    """Validated text representation, deliberately not a PostgreSQL ENUM."""

    impl = String(16)
    cache_ok = True

    def process_bind_param(self, value: VatRate | None, dialect: Dialect) -> str | None:
        del dialect
        if value is None:
            return None
        if not isinstance(value, VatRate):
            raise TypeError("Stawka VAT musi być wartością VatRate.")
        return value.value

    def process_result_value(self, value: Any, dialect: Dialect) -> VatRate | None:
        del dialect
        if value is None:
            return None
        try:
            return VatRate(value)
        except ValueError:
            raise ValueError("Nieznana tekstowa wartość stawki VAT.") from None


class Currency(StrEnum):
    """Currencies currently supported by the project."""

    PLN = "PLN"


class CurrencyType(TypeDecorator[Currency]):
    """Validated text representation for the currently supported currency."""

    impl = String(3)
    cache_ok = True

    def process_bind_param(self, value: Currency | None, dialect: Dialect) -> str | None:
        del dialect
        if value is None:
            return None
        if not isinstance(value, Currency):
            raise TypeError("Waluta musi być wartością Currency (PLN).")
        return value.value

    def process_result_value(self, value: Any, dialect: Dialect) -> Currency | None:
        del dialect
        if value is None:
            return None
        try:
            return Currency(value)
        except ValueError:
            raise ValueError("Nieznana wartość waluty.") from None


def format_money(amount_grosz: int) -> str:
    """Format integer grosz as Polish currency without floating-point arithmetic."""

    validate_money(amount_grosz)
    sign = "-" if amount_grosz < 0 else ""
    whole, fraction = divmod(abs(amount_grosz), 100)
    return f"{sign}{whole},{fraction:02d} zł"


def validate_money(value: object) -> int:
    """Validate a whole-grosz integer in PostgreSQL BIGINT range."""

    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("Money musi być całkowitą liczbą groszy typu int.")
    if not POSTGRES_BIGINT_MIN <= value <= POSTGRES_BIGINT_MAX:
        raise ValueError("Money wykracza poza zakres PostgreSQL BIGINT.")
    return value
