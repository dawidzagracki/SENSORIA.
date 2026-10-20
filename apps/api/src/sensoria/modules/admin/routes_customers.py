"""Read-only customer directory for support; every detail view is audited."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Query
from sqlalchemy import func, or_, select

from sensoria.modules.accounts.models import Customer
from sensoria.modules.orders.models import Order
from sensoria.shared.audit_log import ActorType, AuditLog
from sensoria.shared.errors import DomainError

from .common import Page, PageSize, SessionDependency, Staff

router = APIRouter(prefix="/customers", tags=["admin-customers"])


def _view(c: Customer) -> dict[str, Any]:
    return {
        "id": str(c.id),
        "email": c.email,
        "first_name": c.first_name,
        "last_name": c.last_name,
        "phone": c.phone,
        "email_verified": c.email_verified_at is not None,
        "created_at": c.created_at.isoformat(),
        "last_login_at": c.last_login_at.isoformat() if c.last_login_at else None,
    }


@router.get("")
async def list_customers(
    session: SessionDependency,
    _admin: Staff,
    q: Annotated[str | None, Query(max_length=100)] = None,
    page: Page = 1,
    page_size: PageSize = 25,
) -> dict[str, Any]:
    statement = select(Customer).where(Customer.deleted_at.is_(None))
    if q:
        needle = f"%{q.strip().lower()}%"
        statement = statement.where(
            or_(
                func.lower(Customer.email).like(needle),
                func.lower(Customer.first_name).like(needle),
                func.lower(Customer.last_name).like(needle),
            )
        )
    total = int(await session.scalar(select(func.count()).select_from(statement.subquery())) or 0)
    rows = list(
        (
            await session.scalars(
                statement.order_by(Customer.created_at.desc(), Customer.id)
                .limit(page_size)
                .offset((page - 1) * page_size)
            )
        ).all()
    )
    return {"total": total, "page": page, "items": [_view(c) for c in rows]}


@router.get("/{customer_id}")
async def customer_detail(
    customer_id: UUID, session: SessionDependency, admin: Staff
) -> dict[str, Any]:
    customer = await session.get(Customer, customer_id)
    if customer is None or customer.deleted_at is not None:
        raise DomainError("CUSTOMER_NOT_FOUND", "Nie znaleziono klientki.", 404)
    orders = list(
        (
            await session.scalars(
                select(Order)
                .where(Order.customer_id == customer_id)
                .order_by(Order.created_at.desc())
                .limit(100)
            )
        ).all()
    )
    session.add(
        AuditLog(
            actor_type=ActorType.ADMINISTRATOR,
            actor_id=admin.id,
            entity_type="customer",
            entity_id=customer_id,
            action="customer.viewed",
            payload={},
        )
    )
    await session.commit()
    paid = [o for o in orders if o.status == "paid"]
    return {
        **_view(customer),
        "orders_count": len(orders),
        "paid_total_grosz": sum(o.amount_due_grosz for o in paid),
        "orders": [
            {
                "id": str(o.id),
                "number": o.public_number,
                "status": o.status,
                "amount_due_grosz": o.amount_due_grosz,
                "created_at": o.created_at.isoformat(),
            }
            for o in orders
        ],
    }
