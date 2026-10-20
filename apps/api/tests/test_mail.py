"""Mail outbox: templates, retries, attachments, secret scrubbing and bridges."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sensoria.config import Settings
from sensoria.modules.accounts.models import AuthEmailJob, Customer
from sensoria.modules.accounts.router import _encrypt_payload
from sensoria.modules.catalog.types import ProductKind
from sensoria.modules.mail.bridge import dispatch_legacy_jobs
from sensoria.modules.mail.models import MailOutbox
from sensoria.modules.mail.outbox import enqueue_mail
from sensoria.modules.mail.templates import TEMPLATES, render_template
from sensoria.modules.mail.transport import (
    OutgoingMail,
    PermanentMailError,
    TransientMailError,
)
from sensoria.modules.mail.worker import process_outbox
from sensoria.modules.vouchers.pdf_worker import process_voucher_pdf_jobs
from sensoria.shared.errors import DomainError
from sqlalchemy import select

from . import test_cart
from .test_cart import CartEnvironment
from .test_library import _pay, uploads
from .test_payments import _checkout, stripe_settings

cart_environment = test_cart.cart_environment
__all__ = ["cart_environment", "stripe_settings", "uploads"]


class FakeTransport:
    def __init__(self, *errors: Exception) -> None:
        self.sent: list[OutgoingMail] = []
        self.errors = list(errors)

    async def send(self, mail: OutgoingMail) -> str:
        if self.errors:
            raise self.errors.pop(0)
        self.sent.append(mail)
        return mail.message_id


def test_templates_escape_untrusted_values_and_all_keys_render() -> None:
    subject, html, text = render_template(
        "voucher_gift",
        {
            "recipient_name": "<script>alert(1)</script>",
            "buyer_hint": "Ona",
            "service_name": "Wizyta",
            "code": "ABC-123",
            "valid_until": "01.01.2027",
            "dedication": '"><img src=x onerror=alert(1)>',
        },
    )
    assert "<script>" not in html and "<img" not in html
    assert "&lt;script&gt;" in html and subject
    assert "alert(1)" in text  # plain text is never interpreted
    assert set(TEMPLATES) >= {
        "order_confirmation",
        "payment_failed",
        "digital_access",
        "voucher_delivery",
        "voucher_gift",
        "shipment_sent",
        "pickup_ready",
        "voucher_expiry_reminder",
    }
    with pytest.raises(DomainError):
        render_template("order_confirmation", {})
    with pytest.raises(DomainError):
        render_template("nope", {})


@pytest.mark.asyncio
async def test_retry_backoff_permanent_failure_and_unconfigured_noop(
    cart_environment: CartEnvironment,
) -> None:
    _client, factory = cart_environment
    async with factory() as session, session.begin():
        for name in ("a", "b", "c"):
            await enqueue_mail(
                session,
                template_key="pickup_ready",
                recipient=f"{name}@example.com",
                variables={"order_number": f"SEN-{name}"},
                idempotency_key=f"t-{name}",
            )
        duplicate = await enqueue_mail(
            session,
            template_key="pickup_ready",
            recipient="a@example.com",
            variables={"order_number": "x"},
            idempotency_key="t-a",
        )
        assert duplicate.subject.endswith("SEN-a czeka na odbiór")

    assert (await process_outbox(factory))["skipped_unconfigured"] == 1

    transport = FakeTransport(TransientMailError("timeout"), PermanentMailError("smtp_550"))
    now = datetime.now(UTC)
    counts = await process_outbox(factory, transport=transport, now=now)
    assert counts["sent"] == 1 and counts["retry"] == 1 and counts["failed"] == 1
    async with factory() as session:
        rows = list((await session.scalars(select(MailOutbox))).all())
        by_status = {r.status: r for r in rows}
        assert set(by_status) == {"retry", "failed", "sent"}
        assert by_status["retry"].attempts == 1 and by_status["retry"].next_attempt_at > now
        assert by_status["failed"].last_error == "smtp_550"
        assert by_status["sent"].sent_at is not None
    again = await process_outbox(factory, transport=transport, now=now)
    assert again["sent"] == 0  # backoff has not elapsed (db now() < next attempt)


@pytest.mark.asyncio
async def test_paid_voucher_order_sends_confirmation_and_voucher_pdf(
    cart_environment: CartEnvironment, stripe_settings: Settings
) -> None:
    client, factory = cart_environment
    checkout = await _checkout(client, ProductKind.VOUCHER, factory)
    await _pay(client, checkout, factory)
    await process_voucher_pdf_jobs(factory)
    counts = await dispatch_legacy_jobs(factory)
    assert counts["vouchers"] == 1
    assert (await dispatch_legacy_jobs(factory))["vouchers"] == 0  # exactly once

    transport = FakeTransport()
    await process_outbox(factory, transport=transport)
    by_subject = {m.subject: m for m in transport.sent}
    assert any(s.startswith("Dziękujemy za zamówienie SEN-") for s in by_subject)
    voucher_mail = next(m for s, m in by_subject.items() if s.startswith("Twój voucher"))
    assert voucher_mail.to == "buyer@example.com"
    assert len(voucher_mail.attachments) == 1
    name, content, mime = voucher_mail.attachments[0]
    assert name == "voucher.pdf" and content.startswith(b"%PDF-") and mime == "application/pdf"


@pytest.mark.asyncio
async def test_auth_job_becomes_link_mail_and_secret_is_scrubbed_after_send(
    cart_environment: CartEnvironment, monkeypatch: pytest.MonkeyPatch
) -> None:
    from sensoria.config import get_settings

    _client, factory = cart_environment
    monkeypatch.setattr(get_settings(), "SITE_URL", "https://sklep.example")
    async with factory() as session, session.begin():
        customer = Customer(
            email="klientka@example.com",
            password_hash="x",
            first_name="Anna",
            last_name="Test",
        )
        session.add(customer)
        await session.flush()
        session.add(
            AuthEmailJob(
                customer_id=customer.id,
                purpose="password_reset",
                payload_ciphertext=_encrypt_payload(
                    {"to": "klientka@example.com", "token": "sel.secret"}
                ),
                idempotency_key="password_reset:sel",
            )
        )
    assert (await dispatch_legacy_jobs(factory))["auth"] == 1
    async with factory() as session:
        row = await session.scalar(select(MailOutbox))
        assert (
            row is not None
            and "https://sklep.example/konto/ustaw-haslo/sel.secret" in row.text_body
        )
    transport = FakeTransport()
    await process_outbox(factory, transport=transport)
    assert "ustaw-haslo/sel.secret" in transport.sent[0].text
    await dispatch_legacy_jobs(factory)  # sync step
    async with factory() as session:
        row = await session.scalar(select(MailOutbox))
        job = await session.scalar(select(AuthEmailJob))
        assert row is not None and job is not None
        assert "secret" not in row.html_body and "secret" not in row.text_body
        assert job.status == "sent" and job.payload_ciphertext == ""


@pytest.mark.asyncio
async def test_gift_mail_is_two_phase_and_validity_starts_at_provider_acceptance(
    cart_environment: CartEnvironment, stripe_settings: Settings
) -> None:
    from sensoria.modules.vouchers.models import Voucher

    from .test_cart import _cookie, _product, _publish

    client, factory = cart_environment
    voucher = await _publish(factory, _product(ProductKind.VOUCHER, price=7900))
    assert voucher.voucher is not None
    added = await client.post(
        "/cart/items",
        json={
            "product_id": str(voucher.id),
            "quantity": 1,
            "variant_id": str(voucher.voucher.variants[0].id),
        },
    )
    item_id = added.json()["items"][0]["id"]
    cookie = _cookie(added)
    toggled = await client.patch(
        f"/cart/items/{item_id}/gift",
        json={"is_gift": True},
        headers={"Cookie": f"cart_token={cookie}"},
    )
    assert toggled.status_code == 200, toggled.text
    config = (await client.get("/cart/checkout-config")).json()
    response = await client.post(
        "/cart/checkout",
        json={
            "email": "buyer@example.com",
            "invoice_kind": "private",
            "payment_method": "blik",
            "terms_accepted": True,
            "consent_version": config["consent_version"],
            "gifts": [
                {
                    "cart_item_id": item_id,
                    "recipient_name": "Żaneta",
                    "recipient_email": "zaneta@example.com",
                    "dedication": "Sto lat!",
                    "delivery_mode": "immediate",
                }
            ],
        },
        headers={"Idempotency-Key": "gift-key", "Cookie": f"cart_token={cookie}"},
    )
    assert response.status_code == 201, response.text
    await _pay(client, response.json(), factory)

    counts = await dispatch_legacy_jobs(factory)
    assert counts["gifts"] == 1
    async with factory() as session:
        stored = await session.scalar(select(Voucher))
        assert stored is not None and stored.gift_delivery_status != "sent"
    transport = FakeTransport()
    await process_outbox(factory, transport=transport)
    gift_mail = next(m for m in transport.sent if m.to == "zaneta@example.com")
    assert gift_mail.attachments[0][1].startswith(b"%PDF-")
    assert "Sto lat!" in gift_mail.text or "Sto lat!" in gift_mail.html

    await dispatch_legacy_jobs(factory)
    async with factory() as session:
        done = await session.scalar(select(Voucher))
        assert done is not None
        assert done.gift_delivery_status == "sent" and done.gift_sent_at is not None
