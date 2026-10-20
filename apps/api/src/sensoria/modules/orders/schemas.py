"""Typed public contracts for guest cart operations."""

from datetime import datetime
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    field_validator,
    model_validator,
)

from sensoria.modules.catalog.schemas import PublicImage
from sensoria.modules.catalog.types import ProductKind, VoucherVariantKind
from sensoria.shared.types import VatRate

from .calculator import CartCalculation
from .delivery import DeliveryMethod, DeliveryStatus


class CartItemInput(BaseModel):
    """Client may select an item and quantity, never its price or tax."""

    model_config = ConfigDict(extra="forbid")

    product_id: UUID
    variant_id: UUID | None = None
    quantity: StrictInt
    is_gift: StrictBool = False

    @field_validator("quantity")
    @classmethod
    def positive_quantity(cls, value: int) -> int:
        if value < 1:
            raise ValueError("Ilość musi być dodatnią liczbą całkowitą.")
        return value


class CartQuantityInput(BaseModel):
    """Quantity replacement for one owned cart line."""

    model_config = ConfigDict(extra="forbid")

    quantity: StrictInt

    @field_validator("quantity")
    @classmethod
    def positive_quantity(cls, value: int) -> int:
        if value < 1:
            raise ValueError("Ilość musi być dodatnią liczbą całkowitą.")
        return value


class CartGiftInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    is_gift: StrictBool


class CartItemResponse(BaseModel):
    id: UUID
    product_id: UUID
    slug: str
    name: str
    kind: ProductKind
    variant_id: UUID | None
    variant_kind: VoucherVariantKind | None
    quantity: int
    unit_price_snapshot: int
    vat_rate_snapshot: VatRate
    vat_label: str
    line_total_grosz: int
    short_description: str | None
    image: PublicImage | None
    details: str | None
    voucher_validity_months: int | None = None
    is_gift: bool = False


class GiftOrderItemInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cart_item_id: UUID
    recipient_name: str = Field(min_length=1, max_length=160)
    recipient_email: str | None = Field(default=None, max_length=320)
    dedication: str = Field(default="", max_length=300)
    delivery_mode: str
    delivery_date: str | None = Field(default=None, min_length=10, max_length=10)

    @field_validator("recipient_name")
    @classmethod
    def clean_recipient_name(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value or any(ord(char) < 32 for char in value):
            raise ValueError("Podaj imię obdarowanej osoby.")
        return value

    @field_validator("recipient_email")
    @classmethod
    def validate_recipient_email(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        value = value.strip().casefold()
        if (
            value.count("@") != 1
            or "." not in value.rsplit("@", 1)[-1]
            or any(c.isspace() for c in value)
        ):
            raise ValueError("Podaj prawidłowy adres e-mail obdarowanej osoby.")
        return value

    @field_validator("dedication")
    @classmethod
    def clean_dedication(cls, value: str) -> str:
        value = "".join(char for char in value if char in "\n\t" or ord(char) >= 32)
        if len(value) > 300:
            raise ValueError("Dedykacja może mieć maksymalnie 300 znaków.")
        return value

    @model_validator(mode="after")
    def validate_schedule(self) -> "GiftOrderItemInput":
        if self.delivery_mode not in {"immediate", "scheduled"}:
            raise ValueError("Wybierz termin wysyłki prezentu.")
        if self.delivery_mode == "scheduled":
            from datetime import date

            if self.delivery_date is None:
                raise ValueError("Wybierz dzień wysyłki prezentu.")
            try:
                date.fromisoformat(self.delivery_date)
            except ValueError:
                raise ValueError("Podaj prawidłową datę wysyłki z rokiem.") from None
        elif self.delivery_date is not None:
            raise ValueError("Termin można podać tylko dla wybranej daty wysyłki.")
        return self


class PickupPointSnapshot(BaseModel):
    operator: str = "inpost"
    code: str
    name: str
    street: str
    postal_code: str
    city: str
    opening_hours: str | None = None
    point_types: list[str]
    functions: list[str]
    status: str
    verified_at: datetime


class PickupPointQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=2, max_length=100)


class PickupPointCodeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str = Field(min_length=3, max_length=20)


class PickupPointListResponse(BaseModel):
    items: list[PickupPointSnapshot]


class CartResponse(BaseModel):
    items: list[CartItemResponse]
    item_count: int
    expires_at: datetime | None
    calculation: CartCalculation
    delivery: DeliveryStatus
    delivery_point: PickupPointSnapshot | None = None
    discount_code: str | None = None
    discount_notice: str | None = None
    reorder_report: dict[str, object] | None = None


class CartDeliveryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    method: DeliveryMethod


class DiscountCodeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized or len(normalized) > 100:
            raise ValueError("Podaj kod rabatowy o długości od 1 do 100 znaków.")
        return normalized


class CheckoutAddress(BaseModel):
    model_config = ConfigDict(extra="forbid")
    street: str = Field(min_length=1, max_length=180)
    postal_code: str = Field(min_length=1, max_length=20)
    city: str = Field(min_length=1, max_length=100)


class CheckoutInput(BaseModel):
    """Guest order request; monetary amounts and identity are deliberately absent."""

    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=320)
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    phone: str | None = Field(default=None, max_length=40)
    delivery_method: DeliveryMethod | None = None
    shipping_address: CheckoutAddress | None = None
    pickup_point_id: str | None = Field(default=None, max_length=100)
    invoice_kind: str = "private"
    company_name: str | None = Field(default=None, max_length=200)
    nip: str | None = Field(default=None, max_length=20)
    invoice_address: CheckoutAddress | None = None
    invoice_same_as_shipping: StrictBool = False
    payment_method: str
    terms_accepted: StrictBool
    digital_consent: StrictBool = False
    marketing_consent: StrictBool = False
    review_requests_consent: StrictBool = False
    consent_version: str = Field(min_length=1, max_length=40)
    issuance_mode: str = "immediate"
    gifts: list[GiftOrderItemInput] = Field(default_factory=list, max_length=100)

    @field_validator("email")
    @classmethod
    def valid_email(cls, value: str) -> str:
        value = value.strip()
        if (
            value.count("@") != 1
            or any(char.isspace() for char in value)
            or "." not in value.rsplit("@", 1)[-1]
        ):
            raise ValueError("Podaj prawidłowy adres e-mail.")
        return value

    @model_validator(mode="after")
    def validate_business_fields(self) -> "CheckoutInput":
        if self.invoice_kind not in {"private", "company"}:
            raise ValueError("Wybierz osobę prywatną albo firmę.")
        if self.invoice_kind == "company" and (not self.company_name or not self.nip):
            raise ValueError("Dla firmy podaj nazwę i NIP.")
        if self.issuance_mode != "immediate":
            raise ValueError("Wydanie odroczone nie jest obecnie dostępne.")
        if self.payment_method not in {"blik", "card", "wallet"}:
            raise ValueError("Wybierz dostępną metodę płatności.")
        return self


class CheckoutResponse(BaseModel):
    order_id: UUID
    status: str
    amount_due_grosz: int
    payment_integration: str
    payment_url: str | None
    access_token: str
    message: str


class CheckoutConfigResponse(BaseModel):
    consent_version: str
    terms_text: str
    digital_text: str
    marketing_text: str
