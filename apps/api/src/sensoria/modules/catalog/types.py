"""Validated catalog enum values stored as text, not PostgreSQL enums."""

from enum import StrEnum
from typing import Any

from sqlalchemy import String
from sqlalchemy.engine import Dialect
from sqlalchemy.types import TypeDecorator


class ProductKind(StrEnum):
    """The four catalog families; e-books and courses are DIGITAL variants."""

    VOUCHER = "VOUCHER"
    BOOK = "BOOK"
    AUDIOBOOK = "AUDIOBOOK"
    DIGITAL = "DIGITAL"


class ProductStatus(StrEnum):
    """Publication lifecycle for a catalog product."""

    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    WITHDRAWN = "WITHDRAWN"


class VoucherVariantKind(StrEnum):
    """Stable service-voucher delivery variants."""

    IN_PERSON = "IN_PERSON"
    ONLINE = "ONLINE"


class DigitalLabel(StrEnum):
    """Display distinction within the DIGITAL product family."""

    COURSE_PDF = "COURSE_PDF"
    EBOOK_PDF = "EBOOK_PDF"


class _ValidatedTextEnum(TypeDecorator[StrEnum]):
    """Persist a StrEnum as validated VARCHAR while retaining plain text DDL."""

    impl = String
    cache_ok = True
    enum_type: type[StrEnum]
    length: int

    def __init__(self, enum_type: type[StrEnum], length: int) -> None:
        self.enum_type = enum_type
        self.length = length
        super().__init__(length=length)

    def process_bind_param(self, value: StrEnum | None, dialect: Dialect) -> str | None:
        del dialect
        if value is None:
            return None
        if not isinstance(value, self.enum_type):
            raise TypeError(f"Wartość musi należeć do {self.enum_type.__name__}.")
        return value.value

    def process_result_value(self, value: Any, dialect: Dialect) -> StrEnum | None:
        del dialect
        if value is None:
            return None
        try:
            return self.enum_type(value)
        except ValueError:
            raise ValueError(f"Nieznana wartość {self.enum_type.__name__} w bazie.") from None


class ProductKindType(_ValidatedTextEnum):
    """VARCHAR representation of ProductKind."""

    cache_ok = True

    def __init__(self) -> None:
        super().__init__(ProductKind, 16)


class ProductStatusType(_ValidatedTextEnum):
    """VARCHAR representation of ProductStatus."""

    cache_ok = True

    def __init__(self) -> None:
        super().__init__(ProductStatus, 16)


class VoucherVariantKindType(_ValidatedTextEnum):
    """VARCHAR representation of VoucherVariantKind."""

    cache_ok = True

    def __init__(self) -> None:
        super().__init__(VoucherVariantKind, 16)


class DigitalLabelType(_ValidatedTextEnum):
    """VARCHAR representation of DigitalLabel."""

    cache_ok = True

    def __init__(self) -> None:
        super().__init__(DigitalLabel, 16)
