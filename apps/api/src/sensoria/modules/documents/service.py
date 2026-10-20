"""Issue and render numbered sales documents from immutable order snapshots."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sensoria.modules.orders.models import Order, OrderItem
from sensoria.modules.storage.models import StoredFile
from sensoria.modules.storage.service import StorageService
from sensoria.shared.app_settings import AppSetting
from sensoria.shared.audit_log import ActorType, AuditLog
from sensoria.shared.errors import DomainError

from .models import DocumentCounter, SalesDocument
from .pdf import render_document

SELLER_SETTING_KEY = "company.seller.v1"
METHOD_LABELS = {"blik": "BLIK", "card": "Karta płatnicza", "wallet": "Portfel mobilny"}


class SellerSettings(BaseModel):
    """Seller identity is owner-supplied configuration; nothing is invented by the app."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=2, max_length=200)
    street: str = Field(min_length=2, max_length=200)
    postal_code: str = Field(min_length=3, max_length=12)
    city: str = Field(min_length=2, max_length=100)
    nip: str | None = Field(default=None, max_length=20)
    vat_exempt_note: str | None = Field(default=None, max_length=300)

    def lines(self) -> list[str]:
        result = [self.name, self.street, f"{self.postal_code} {self.city}"]
        if self.nip:
            result.append(f"NIP: {self.nip}")
        if self.vat_exempt_note:
            result.append(self.vat_exempt_note)
        return result


async def load_seller(session: AsyncSession) -> SellerSettings:
    setting = await session.scalar(select(AppSetting).where(AppSetting.key == SELLER_SETTING_KEY))
    if setting is None:
        raise DomainError(
            "SELLER_NOT_CONFIGURED", "Brak skonfigurowanych danych sprzedawcy dla dokumentów.", 503
        )
    try:
        return SellerSettings.model_validate(setting.value)
    except ValidationError:
        raise DomainError(
            "SELLER_NOT_CONFIGURED", "Dane sprzedawcy dla dokumentów są nieprawidłowe.", 503
        ) from None


def _buyer_lines(order: Order) -> list[str]:
    invoice = order.invoice_data
    snapshot = invoice.get("buyer_snapshot") or {}
    name = " ".join(filter(None, [snapshot.get("first_name"), snapshot.get("last_name")]))
    address = invoice.get("address") or {}
    lines: list[str] = []
    if invoice.get("kind") == "company":
        lines.append(str(invoice.get("company_name") or ""))
        if invoice.get("nip"):
            lines.append(f"NIP: {invoice['nip']}")
    elif name:
        lines.append(name)
    street = " ".join(filter(None, [address.get("street"), address.get("building_number")]))
    if address.get("apartment_number"):
        street += f"/{address['apartment_number']}"
    if street:
        lines.append(street)
    city = " ".join(filter(None, [address.get("postal_code"), address.get("city")]))
    if city:
        lines.append(city)
    lines.append(order.email)
    return [line for line in lines if line]


async def _next_number(session: AsyncSession, kind: str, year: int) -> str:
    counter = await session.scalar(
        select(DocumentCounter)
        .where(DocumentCounter.kind == kind, DocumentCounter.year == year)
        .with_for_update()
    )
    if counter is None:
        counter = DocumentCounter(kind=kind, year=year, last_number=0)
        session.add(counter)
        await session.flush()
    counter.last_number += 1
    await session.flush()
    prefix = "FV" if kind == "invoice" else "PAR"
    return f"{prefix}/{year}/{counter.last_number:05d}"


def _snapshot(order: Order, items: list[OrderItem], seller: SellerSettings) -> dict[str, Any]:
    calc = order.calculation_snapshot
    settlements = {entry["item_id"]: entry for entry in calc["items"]}
    lines: list[dict[str, Any]] = []
    for item in items:
        settlement = settlements.get(str(item.id)) or item.item_settlement
        lines.append(
            {
                "name": item.product_name_snapshot or "Produkt",
                "quantity": item.quantity,
                "unit_gross_grosz": item.unit_price_snapshot,
                "vat_label": settlement["vat_label"],
                "net_grosz": settlement["net_grosz"],
                "tax_grosz": settlement["tax_grosz"],
                "gross_grosz": settlement["gross_grosz"],
            }
        )
    delivery = calc.get("delivery") or {}
    if delivery.get("resolved") and delivery.get("gross_grosz", 0) > 0:
        lines.append(
            {
                "name": "Dostawa",
                "quantity": 1,
                "unit_gross_grosz": delivery["gross_grosz"],
                "vat_label": delivery["vat_label"],
                "net_grosz": delivery["net_grosz"],
                "tax_grosz": delivery["tax_grosz"],
                "gross_grosz": delivery["gross_grosz"],
            }
        )
    groups = [dict(group) for group in calc["vat_groups"]]
    exempt = calc.get("exempt") or {}
    if exempt.get("gross_grosz"):
        groups.append(dict(exempt))
    return {
        "order_number": order.public_number,
        "seller": {"lines": seller.lines()},
        "buyer": {"lines": _buyer_lines(order)},
        "lines": lines,
        "vat_groups": groups,
        "discount_grosz": calc.get("discount_grosz", 0),
        "total_grosz": order.amount_due_grosz,
        "payment_method": METHOD_LABELS.get(order.payment_method, order.payment_method),
    }


async def issue_document_for_order(
    session: AsyncSession, order_id: UUID, *, now: datetime | None = None
) -> SalesDocument:
    """Idempotently allocate a number and freeze the snapshot; caller owns the transaction."""
    order = await session.scalar(select(Order).where(Order.id == order_id).with_for_update())
    if order is None or order.status != "paid":
        raise DomainError("DOCUMENT_ORDER_NOT_PAID", "Dokument wymaga opłaconego zamówienia.", 409)
    kind = "invoice" if order.invoice_data.get("kind") == "company" else "receipt"
    existing = await session.scalar(
        select(SalesDocument).where(SalesDocument.order_id == order_id, SalesDocument.kind == kind)
    )
    if existing is not None:
        return existing
    seller = await load_seller(session)
    items = list(
        (
            await session.scalars(
                select(OrderItem).where(OrderItem.order_id == order_id).order_by(OrderItem.id)
            )
        ).all()
    )
    issued_at = (now or datetime.now(UTC)).astimezone(UTC)
    document = SalesDocument(
        order_id=order_id,
        kind=kind,
        number=await _next_number(session, kind, issued_at.year),
        issued_at=issued_at,
        data=_snapshot(order, items, seller),
    )
    session.add(document)
    await session.flush()
    session.add(
        AuditLog(
            actor_type=ActorType.SYSTEM,
            actor_id=None,
            entity_type="sales_document",
            entity_id=document.id,
            action="document.issued",
            payload={"order_id": str(order_id), "kind": kind, "number": document.number},
        )
    )
    await session.flush()
    return document


async def issue_after_payment(session: AsyncSession, order_id: UUID) -> SalesDocument | None:
    """Payment must never fail because documents are unconfigured; record and move on."""
    try:
        async with session.begin_nested():
            return await issue_document_for_order(session, order_id)
    except DomainError as error:
        session.add(
            AuditLog(
                actor_type=ActorType.SYSTEM,
                actor_id=None,
                entity_type="order",
                entity_id=order_id,
                action="document.issue_deferred",
                payload={"code": error.code},
            )
        )
        await session.flush()
        return None


async def document_pdf_path(session: AsyncSession, document: SalesDocument) -> tuple[Any, str]:
    """Render once, store privately, return (path, download name)."""
    storage = StorageService()
    title = "Faktura VAT" if document.kind == "invoice" else "Potwierdzenie sprzedaży (paragon)"
    name = f"{document.number.replace('/', '-')}.pdf"
    if document.stored_file_id is None:
        content = await asyncio.to_thread(
            render_document,
            document.data,
            title=title,
            number=document.number,
            issued=document.issued_at.astimezone(UTC).strftime("%Y-%m-%d"),
        )
        stored = await storage.store_file(
            session,
            category="documents",
            scope_id=document.id,
            year=document.issued_at.year,
            content=content,
            original_name=name,
            mime_type="application/pdf",
        )
        document.stored_file_id = stored.id
        await session.flush()
    stored_file = await session.get(StoredFile, document.stored_file_id)
    assert stored_file is not None
    return storage.resolve_file(stored_file), name
