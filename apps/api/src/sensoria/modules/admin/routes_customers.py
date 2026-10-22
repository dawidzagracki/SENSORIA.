"""Read-only customer directory for support; every detail view is audited."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Query
from sqlalchemy import BigInteger, and_, cast, func, or_, select

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


def _order_name(order: Order | None) -> str | None:
    """Best-effort buyer name from the order itself (guests have no account profile)."""
    if order is None:
        return None
    shipping = order.shipping_data if isinstance(order.shipping_data, dict) else {}
    parts = [str(shipping.get("first_name") or ""), str(shipping.get("last_name") or "")]
    name = " ".join(part for part in parts if part).strip()
    if name:
        return name
    invoice = order.invoice_data if isinstance(order.invoice_data, dict) else {}
    company = invoice.get("company_name") or invoice.get("name")
    return str(company) if company else None


@router.get("")
async def list_customers(
    session: SessionDependency,
    _admin: Staff,
    q: Annotated[str | None, Query(max_length=100)] = None,
    page: Page = 1,
    page_size: PageSize = 25,
) -> dict[str, Any]:
    """Every buyer (paid order by e-mail, with or without an account) plus empty accounts."""
    buyers = (
        select(
            func.lower(Order.email).label("email"),
            func.count().label("orders_count"),
            func.coalesce(cast(func.sum(Order.amount_due_grosz), BigInteger), 0).label(
                "paid_total"
            ),
            func.max(Order.created_at).label("last_order_at"),
        )
        .where(Order.status == "paid")
        .group_by(func.lower(Order.email))
        .subquery()
    )
    email = func.coalesce(buyers.c.email, Customer.email).label("email")
    statement = (
        select(
            email,
            func.coalesce(buyers.c.orders_count, 0).label("orders_count"),
            func.coalesce(buyers.c.paid_total, 0).label("paid_total"),
            buyers.c.last_order_at,
            Customer.id.label("customer_id"),
            Customer.first_name,
            Customer.last_name,
            Customer.created_at.label("account_created_at"),
            Customer.last_login_at,
        )
        .select_from(
            buyers.join(
                Customer,
                and_(Customer.email == buyers.c.email, Customer.deleted_at.is_(None)),
                isouter=True,
                full=True,
            )
        )
        .where(or_(Customer.id.is_(None), Customer.deleted_at.is_(None)))
    )
    if q:
        needle = f"%{q.strip().lower()}%"
        statement = statement.where(
            or_(
                email.like(needle),
                func.lower(func.coalesce(Customer.first_name, "")).like(needle),
                func.lower(func.coalesce(Customer.last_name, "")).like(needle),
            )
        )
    total = int(await session.scalar(select(func.count()).select_from(statement.subquery())) or 0)
    rows = (
        await session.execute(
            statement.order_by(
                func.coalesce(buyers.c.last_order_at, Customer.created_at).desc(), email
            )
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
    ).all()
    items: list[dict[str, Any]] = []
    for row in rows:
        last_order = await session.scalar(
            select(Order)
            .where(func.lower(Order.email) == row.email)
            .order_by(Order.created_at.desc())
            .limit(1)
        )
        name = " ".join(x for x in (row.first_name, row.last_name) if x).strip()
        items.append(
            {
                "email": row.email,
                "name": name or _order_name(last_order) or None,
                "has_account": row.customer_id is not None,
                "customer_id": str(row.customer_id) if row.customer_id else None,
                "orders_count": int(row.orders_count),
                "paid_total_grosz": int(row.paid_total),
                "last_order_at": row.last_order_at.isoformat() if row.last_order_at else None,
                "account_created_at": row.account_created_at.isoformat()
                if row.account_created_at
                else None,
                "last_login_at": row.last_login_at.isoformat() if row.last_login_at else None,
            }
        )
    return {"total": total, "page": page, "items": items}


@router.get("/detail")
async def buyer_detail(
    session: SessionDependency,
    admin: Staff,
    email: Annotated[str, Query(min_length=3, max_length=320)],
) -> dict[str, Any]:
    """A buyer is identified by e-mail; the account (if any) is optional."""
    key = email.strip().lower()
    orders = list(
        (
            await session.scalars(
                select(Order)
                .where(func.lower(Order.email) == key)
                .order_by(Order.created_at.desc())
                .limit(100)
            )
        ).all()
    )
    customer = await session.scalar(
        select(Customer).where(Customer.email == key, Customer.deleted_at.is_(None))
    )
    if not orders and customer is None:
        raise DomainError("CUSTOMER_NOT_FOUND", "Nie znaleziono klienta.", 404)
    session.add(
        AuditLog(
            actor_type=ActorType.ADMINISTRATOR,
            actor_id=admin.id,
            entity_type="customer",
            entity_id=customer.id if customer else uuid4(),
            action="customer.viewed",
            payload={"has_account": customer is not None},
        )
    )
    await session.commit()
    paid = [o for o in orders if o.status == "paid"]
    shipping = next((o.shipping_data for o in orders if isinstance(o.shipping_data, dict)), {})
    name = (
        f"{customer.first_name} {customer.last_name}".strip()
        if customer
        else _order_name(orders[0] if orders else None)
    )
    return {
        "email": key,
        "name": name or None,
        "phone": (customer.phone if customer else None) or (shipping or {}).get("phone"),
        "has_account": customer is not None,
        "email_verified": bool(customer and customer.email_verified_at),
        "account_created_at": customer.created_at.isoformat() if customer else None,
        "last_login_at": customer.last_login_at.isoformat()
        if customer and customer.last_login_at
        else None,
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
