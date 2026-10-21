"""Payment request and response schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class PaymentSessionResponse(BaseModel):
    payment_id: UUID
    payment_url: str
    status: str
    attempt: int


class OrderItemView(BaseModel):
    name: str | None
    quantity: int
    unit_price_grosz: int
    is_voucher: bool


class OrderStatusResponse(BaseModel):
    order_id: UUID
    public_number: str | None
    status: str
    payment_status: str | None
    payment_method: str
    amount_due_grosz: int
    email_masked: str
    created_at: datetime
    requires_shipping: bool
    delivery_method: str | None
    delivery_summary: str | None = None
    items: list[OrderItemView]
    can_retry_payment: bool
    server_time: datetime
