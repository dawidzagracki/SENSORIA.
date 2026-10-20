"""Adapter from voucher reminders to the account consent event log."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from sensoria.modules.accounts.auth import normalize_email
from sensoria.modules.accounts.models import Customer
from sensoria.modules.accounts.privacy import has_current_consent
from sensoria.modules.orders.models import Order


class AccountVoucherReminderConsentReader:
    """Require the explicit voucher-reminder purpose for the account or guest email."""

    async def has_current_consent(
        self, session: AsyncSession, *, order_id: UUID, email: str
    ) -> bool | None:
        order = await session.get(Order, order_id)
        if order is None or normalize_email(order.email) != normalize_email(email):
            return False
        customer = await session.get(Customer, order.customer_id) if order.customer_id else None
        if customer is not None and customer.deleted_at is not None:
            return False
        customer_id = customer.id if customer is not None else None
        return await has_current_consent(
            session,
            "voucher_reminders",
            customer_id=customer_id,
            email=email,
        )
