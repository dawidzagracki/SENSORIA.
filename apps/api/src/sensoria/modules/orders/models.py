"""Persistent guest and customer cart models."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from sensoria.database import Base, TimestampMixin, UUIDMixin
from sensoria.shared.types import Money, VatRate, VatRateType, validate_money


class Cart(UUIDMixin, TimestampMixin, Base):
    """One persistent basket; customer_id stays an unbound UUID until accounts exist."""

    __tablename__ = "carts"
    __allow_unmapped__ = True
    __table_args__ = (
        UniqueConstraint("session_token_hash"),
        Index(
            "ix_carts_guest_expiry",
            "expires_at",
            postgresql_where=text("customer_id IS NULL"),
        ),
        Index(
            "uq_carts_customer_id",
            "customer_id",
            unique=True,
            postgresql_where=text("customer_id IS NOT NULL"),
        ),
        CheckConstraint(
            "(customer_id IS NULL AND session_token_hash IS NOT NULL AND expires_at IS NOT NULL) "
            "OR (customer_id IS NOT NULL AND session_token_hash IS NULL)",
            name="guest_or_customer_identity",
        ),
        CheckConstraint(
            "delivery_method IS NULL OR delivery_method IN ('parcel_locker', 'courier')",
            name="valid_delivery_method",
        ),
    )

    session_token_hash: Mapped[str | None] = mapped_column(String(64))
    # The accounts module has no customer model yet; this nullable UUID is a future FK point.
    customer_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    discount_code_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("discount_codes.id", ondelete="RESTRICT")
    )
    delivery_method: Mapped[str | None] = mapped_column(String(24))
    delivery_point_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    items: Mapped[list[CartItem]] = relationship(
        back_populates="cart", cascade="all, delete-orphan", lazy="raise"
    )
    discount_code: Mapped[DiscountCode | None] = relationship(lazy="raise")
    discount_notice: str | None = None


class DiscountCode(UUIDMixin, TimestampMixin, Base):
    """Discount definition; code casing is retained while lookup is normalized."""

    __tablename__ = "discount_codes"
    __table_args__ = (
        CheckConstraint("type IN ('percentage', 'fixed_amount')", name="valid_type"),
        CheckConstraint(
            "(type = 'percentage' AND value BETWEEN 1 AND 100) OR "
            "(type = 'fixed_amount' AND value > 0)",
            name="valid_value",
        ),
        CheckConstraint("min_order_value >= 0", name="nonnegative_minimum"),
        CheckConstraint("used_count >= 0", name="nonnegative_used_count"),
        CheckConstraint("max_uses IS NULL OR max_uses > 0", name="positive_max_uses"),
        CheckConstraint(
            "valid_to IS NULL OR valid_from IS NULL OR valid_to > valid_from", name="valid_dates"
        ),
        CheckConstraint("length(btrim(code)) > 0", name="nonempty_code"),
        Index(
            "uq_discount_codes_normalized_code", func.lower(func.btrim(text("code"))), unique=True
        ),
    )

    code: Mapped[str] = mapped_column(String(100), nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    value: Mapped[int] = mapped_column(BigInteger, nullable=False)
    min_order_value: Mapped[int] = mapped_column(
        Money(), nullable=False, default=0, server_default="0"
    )
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    max_uses: Mapped[int | None] = mapped_column(Integer)
    used_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    is_active: Mapped[bool] = mapped_column(
        nullable=False, default=True, server_default=text("true")
    )

    @validates("code")
    def trim_code(self, _key: str, value: str) -> str:
        """Trim edge whitespace while retaining administrator casing."""
        return value.strip()

    @validates("value")
    def validate_value(self, _key: str, value: int) -> int:
        """Reject bool/float and enforce the current type's value range."""
        validate_money(value)
        if getattr(self, "type", None) == "percentage" and not 1 <= value <= 100:
            raise ValueError("Rabat procentowy musi mieścić się w zakresie 1–100.")
        if getattr(self, "type", None) == "fixed_amount" and value <= 0:
            raise ValueError("Kwota rabatu musi być dodatnią liczbą groszy.")
        return value

    @validates("type")
    def validate_type(self, _key: str, value: str) -> str:
        if value not in {"percentage", "fixed_amount"}:
            raise ValueError("Rodzaj kodu musi być percentage albo fixed_amount.")
        current_value = getattr(self, "value", None)
        if current_value is not None:
            if value == "percentage" and not 1 <= current_value <= 100:
                raise ValueError("Rabat procentowy musi mieścić się w zakresie 1–100.")
            if value == "fixed_amount" and current_value <= 0:
                raise ValueError("Kwota rabatu musi być dodatnią liczbą groszy.")
        return value

    @validates("min_order_value")
    def validate_minimum(self, _key: str, value: int) -> int:
        validate_money(value)
        if value < 0:
            raise ValueError("Minimalna wartość zamówienia nie może być ujemna.")
        return value

    @validates("max_uses")
    def validate_max_uses(self, _key: str, value: int | None) -> int | None:
        if value is not None and (
            isinstance(value, bool) or not isinstance(value, int) or value < 1
        ):
            raise ValueError("Limit użyć musi być dodatnią liczbą całkowitą albo None.")
        return value

    @validates("used_count")
    def validate_used_count(self, _key: str, value: int) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError("Licznik użyć musi być nieujemną liczbą całkowitą.")
        return value

    @validates("valid_from", "valid_to")
    def normalize_validity_time(self, _key: str, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Daty kodu rabatowego muszą mieć strefę czasową.")
        return value.astimezone(UTC)


class DiscountRedemption(UUIDMixin, Base):
    """Idempotency record written only after trusted payment confirmation."""

    __tablename__ = "discount_redemptions"
    __table_args__ = (UniqueConstraint("discount_code_id", "order_id"),)

    discount_code_id: Mapped[UUID] = mapped_column(
        ForeignKey("discount_codes.id", ondelete="RESTRICT"), nullable=False
    )
    order_id: Mapped[UUID] = mapped_column(
        ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False
    )


class Order(UUIDMixin, TimestampMixin, Base):
    """Guest checkout snapshot awaiting payment; no customer account is implied."""

    __tablename__ = "orders"
    __table_args__ = (
        UniqueConstraint("cart_id"),
        UniqueConstraint("public_number"),
        CheckConstraint(
            "status IN ('pending_payment', 'paid', 'cancelled', 'expired')", name="valid_status"
        ),
        CheckConstraint("length(btrim(email)) > 0", name="nonempty_email"),
        CheckConstraint("amount_due_grosz >= 0", name="nonnegative_amount_due"),
        CheckConstraint(
            "fulfillment_status IN ('awaiting_fulfillment', 'shipped', 'delivered', "
            "'ready_for_pickup', 'picked_up', 'cancelled')",
            name="valid_fulfillment_status",
        ),
        Index("ix_orders_status_created_at", "status", "created_at"),
    )

    cart_id: Mapped[UUID] = mapped_column(
        ForeignKey("carts.id", ondelete="RESTRICT"), nullable=False
    )
    # Stable human-readable reference; nullable only for rows created before [57].
    public_number: Mapped[str | None] = mapped_column(String(32))
    # Account ownership is assigned only after the order's buyer email is verified.
    customer_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("customers.id", ondelete="SET NULL"), index=True
    )
    idempotency_key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    payment_method: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, server_default="pending_payment"
    )
    invoice_data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    shipping_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    delivery_point_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    calculation_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    amount_due_grosz: Mapped[int] = mapped_column(Money(), nullable=False)
    discount_code_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("discount_codes.id", ondelete="RESTRICT")
    )
    # Fulfillment is deliberately separate from payment ``status``.
    fulfillment_status: Mapped[str] = mapped_column(
        String(24), nullable=False, server_default="awaiting_fulfillment"
    )
    fulfillment_ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    pickup_ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    pickup_ready_by: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    picked_up_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    picked_up_by: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    reservations: Mapped[list[StockReservation]] = relationship(
        back_populates="order", cascade="all, delete-orphan", lazy="raise"
    )


class OrderItem(UUIDMixin, Base):
    """Immutable product and price snapshot stored with an order."""

    __tablename__ = "order_items"
    __table_args__ = (CheckConstraint("quantity > 0", name="positive_quantity"),)

    order_id: Mapped[UUID] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[UUID] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), nullable=False
    )
    variant_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price_snapshot: Mapped[int] = mapped_column(Money(), nullable=False)
    vat_rate_snapshot: Mapped[VatRate] = mapped_column(VatRateType(), nullable=False)
    item_settlement: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    product_name_snapshot: Mapped[str | None] = mapped_column(String(200))
    voucher_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    gift_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    shipping_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB)


class OrderConsent(UUIDMixin, Base):
    """Versioned record of checkout declarations and their displayed copy."""

    __tablename__ = "order_consents"
    __table_args__ = (UniqueConstraint("order_id", "kind"),)

    order_id: Mapped[UUID] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    granted: Mapped[bool] = mapped_column(nullable=False)
    version: Mapped[str] = mapped_column(String(40), nullable=False)
    displayed_text: Mapped[str] = mapped_column(Text, nullable=False)
    scope: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    issuance_mode: Mapped[str | None] = mapped_column(String(24))
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class StockReservation(UUIDMixin, Base):
    """Temporary book-stock hold, released by the periodic cleanup job."""

    __tablename__ = "stock_reservations"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="positive_quantity"),
        Index("ix_stock_reservations_expiry", "expires_at"),
        Index("ix_stock_reservations_product_expiry", "product_id", "expires_at"),
    )

    order_id: Mapped[UUID] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[UUID] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), nullable=False
    )
    order_item_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("order_items.id", ondelete="RESTRICT")
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    order: Mapped[Order] = relationship(back_populates="reservations", lazy="raise")


class StockFulfillmentConflict(UUIDMixin, Base):
    """Paid physical order item that could not be secured after its hold expired."""

    __tablename__ = "stock_fulfillment_conflicts"
    __table_args__ = (
        UniqueConstraint("order_item_id"),
        CheckConstraint("requested_quantity > 0", name="positive_requested_quantity"),
        CheckConstraint("status IN ('open', 'resolved')", name="valid_status"),
    )

    order_id: Mapped[UUID] = mapped_column(
        ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False
    )
    order_item_id: Mapped[UUID] = mapped_column(
        ForeignKey("order_items.id", ondelete="RESTRICT"), nullable=False
    )
    product_id: Mapped[UUID] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), nullable=False
    )
    requested_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="open")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class DiscountUseReservation(UUIDMixin, Base):
    """Temporary exclusive capacity hold for a discount code pending payment."""

    __tablename__ = "discount_use_reservations"
    __table_args__ = (
        UniqueConstraint("order_id"),
        Index("ix_discount_use_reservations_code_expiry", "discount_code_id", "expires_at"),
    )

    discount_code_id: Mapped[UUID] = mapped_column(
        ForeignKey("discount_codes.id", ondelete="RESTRICT"), nullable=False
    )
    order_id: Mapped[UUID] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CartItem(UUIDMixin, Base):
    """A price and VAT snapshot captured when an item enters the cart."""

    __tablename__ = "cart_items"
    __table_args__ = (
        UniqueConstraint("cart_id", "line_key", name="uq_cart_items_cart_line_key"),
        CheckConstraint("quantity > 0", name="positive_quantity"),
        CheckConstraint("length(btrim(line_key)) > 0", name="nonempty_line_key"),
        CheckConstraint("unit_price_snapshot >= 0", name="nonnegative_price_snapshot"),
        CheckConstraint(
            "vat_rate_snapshot IN ('RATE_23', 'RATE_8', 'RATE_5', 'RATE_0', 'EXEMPT')",
            name="valid_vat_rate_snapshot",
        ),
        Index("ix_cart_items_product_id", "product_id"),
    )

    cart_id: Mapped[UUID] = mapped_column(
        ForeignKey("carts.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[UUID] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), nullable=False
    )
    variant_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("product_voucher_variants.id", ondelete="SET NULL")
    )
    # Deterministic for mergeable lines, random for each independently purchased voucher.
    line_key: Mapped[str] = mapped_column(String(100), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price_snapshot: Mapped[int] = mapped_column(Money(), nullable=False)
    vat_rate_snapshot: Mapped[VatRate] = mapped_column(VatRateType(), nullable=False)
    gift_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    cart: Mapped[Cart] = relationship(back_populates="items", lazy="raise")


class CartReorderOperation(UUIDMixin, TimestampMixin, Base):
    """Durable, customer/cart-scoped result of one idempotent reorder request."""

    __tablename__ = "cart_reorder_operations"
    __table_args__ = (
        UniqueConstraint("customer_id", "idempotency_key_hash"),
        Index("ix_cart_reorder_operations_cart_created", "cart_id", "created_at"),
    )

    customer_id: Mapped[UUID] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"), nullable=False
    )
    cart_id: Mapped[UUID] = mapped_column(
        ForeignKey("carts.id", ondelete="CASCADE"), nullable=False
    )
    order_id: Mapped[UUID | None] = mapped_column(ForeignKey("orders.id", ondelete="RESTRICT"))
    voucher_id: Mapped[UUID | None] = mapped_column(ForeignKey("vouchers.id", ondelete="RESTRICT"))
    idempotency_key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    report: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Shipment(UUIDMixin, Base):
    """One shipment per physical order; partial and multi-parcel shipping is unsupported."""

    __tablename__ = "shipments"
    __table_args__ = (
        UniqueConstraint("order_id"),
        Index("ix_shipments_shipped_at", "shipped_at"),
        CheckConstraint("status IN ('shipped', 'delivered')", name="valid_status"),
        CheckConstraint("length(btrim(carrier)) > 0", name="nonempty_carrier"),
        CheckConstraint("length(btrim(tracking_number)) > 0", name="nonempty_tracking_number"),
    )

    order_id: Mapped[UUID] = mapped_column(
        ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False
    )
    carrier: Mapped[str] = mapped_column(String(40), nullable=False)
    tracking_number: Mapped[str] = mapped_column(String(160), nullable=False)
    shipped_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="shipped")
    created_by: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)


class ShipmentHistory(UUIDMixin, Base):
    """Append-only carrier/tracking changes; initial shipment is also recorded."""

    __tablename__ = "shipment_history"
    __table_args__ = (
        UniqueConstraint(
            "shipment_id",
            "operation_key",
            name="uq_shipment_history_shipment_operation_key",
        ),
        CheckConstraint(
            "operation IN ('created', 'corrected', 'delivered')", name="valid_operation"
        ),
        Index("ix_shipment_history_shipment_changed", "shipment_id", "changed_at"),
    )

    shipment_id: Mapped[UUID] = mapped_column(
        ForeignKey("shipments.id", ondelete="RESTRICT"), nullable=False
    )
    previous_carrier: Mapped[str | None] = mapped_column(String(40))
    new_carrier: Mapped[str | None] = mapped_column(String(40))
    previous_tracking_number: Mapped[str | None] = mapped_column(String(160))
    new_tracking_number: Mapped[str | None] = mapped_column(String(160))
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    performed_by: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    operation: Mapped[str] = mapped_column(String(16), nullable=False)
    operation_key: Mapped[str | None] = mapped_column(String(120))
    reason: Mapped[str | None] = mapped_column(Text)


class ShipmentNotificationJob(UUIDMixin, Base):
    """Durable notification intent; no delivery is claimed without [63] worker."""

    __tablename__ = "shipment_notification_jobs"
    __table_args__ = (
        UniqueConstraint("idempotency_key"),
        CheckConstraint("kind IN ('shipped', 'pickup_ready', 'manual_resend')", name="valid_kind"),
        CheckConstraint(
            "status IN ('pending', 'sending', 'sent', 'failed', 'cancelled')",
            name="valid_status",
        ),
        CheckConstraint("attempts >= 0", name="nonnegative_attempts"),
        Index("ix_shipment_notification_jobs_pending", "status", "created_at"),
    )

    order_id: Mapped[UUID] = mapped_column(
        ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False
    )
    shipment_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("shipments.id", ondelete="RESTRICT")
    )
    kind: Mapped[str] = mapped_column(String(24), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(180), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="pending")
    queued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    failure_code: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
