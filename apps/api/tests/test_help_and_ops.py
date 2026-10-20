"""Help center search, cookie register, security headers, deep health and audit viewer."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sensoria.modules.mail.models import MailOutbox

from . import test_cart
from .admin_helpers import admin_headers, create_admin
from .test_cart import CartEnvironment

cart_environment = test_cart.cart_environment
__all__ = ["cart_environment"]


@pytest.mark.asyncio
async def test_faq_admin_crud_and_public_search(cart_environment: CartEnvironment) -> None:
    client, factory = cart_environment
    await create_admin(factory, "owner@example.com", "owner")
    await create_admin(factory, "staff@example.com", "staff")
    owner = await admin_headers(client, "owner@example.com")
    staff = await admin_headers(client, "staff@example.com")
    entries = [
        ("Zamówienia", "Jak odebrać zakupiony e-book?", "Pobierz go z biblioteki.", True),
        ("Zamówienia", "Ile trwa dostawa?", "Zwykle 2 dni robocze.", True),
        ("Vouchery", "Jak zrealizować voucher?", "Podaj kod w gabinecie.", True),
        ("Vouchery", "Szkic wewnętrzny", "Nie publikować.", False),
    ]
    ids = []
    for category, question, answer, published in entries:
        body = {
            "category": category,
            "question": question,
            "answer": answer,
            "published": published,
        }
        assert (await client.post("/admin/faq", json=body, headers=staff)).status_code == 403
        created = await client.post("/admin/faq", json=body, headers=owner)
        assert created.status_code == 201
        ids.append(created.json()["id"])
    everything = (await client.get("/help")).json()
    assert everything["total"] == 3 and [c["name"] for c in everything["categories"]] == [
        "Vouchery",
        "Zamówienia",
    ]
    found = (await client.get("/help?q=VOUCHER")).json()
    assert found["total"] == 1 and "szkic" not in str(found).lower()
    assert (await client.get("/help?q=100%25")).json()["total"] == 0  # LIKE wildcards are escaped
    assert (await client.get("/help?q=" + "x" * 101)).status_code == 422
    updated = await client.put(
        f"/admin/faq/{ids[3]}",
        json={
            "category": "Vouchery",
            "question": "Szkic wewnętrzny",
            "answer": "Dziękujemy",
            "published": True,
        },
        headers=owner,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["published"] is True
    assert (await client.get("/help")).json()["total"] == 4
    assert (await client.delete(f"/admin/faq/{ids[3]}", headers=owner)).status_code == 204


@pytest.mark.asyncio
async def test_cookie_consent_register_is_append_only(cart_environment: CartEnvironment) -> None:
    client, factory = cart_environment
    first = await client.post("/consents/cookies", json={"analytics": True, "marketing": False})
    assert first.status_code == 201
    subject = first.json()["subject_id"]
    again = await client.post(
        "/consents/cookies", json={"analytics": False, "marketing": False, "subject_id": subject}
    )
    assert again.json()["subject_id"] == subject
    assert (await client.post("/consents/cookies", json={"analytics": "yes"})).status_code == 422
    assert (await client.post("/consents/cookies", json={"admin": True})).status_code == 422
    await create_admin(factory, "owner@example.com", "owner")
    owner = await admin_headers(client, "owner@example.com")
    register = (await client.get("/admin/cookie-consents", headers=owner)).json()
    assert register["total"] == 2
    assert sorted(r["analytics"] for r in register["items"]) == [False, True]


@pytest.mark.asyncio
async def test_security_headers_deep_health_and_audit_view(
    cart_environment: CartEnvironment,
) -> None:
    client, factory = cart_environment
    response = await client.get("/health")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert "camera=()" in response.headers["permissions-policy"]

    deep = await client.get("/health/deep")
    assert deep.status_code == 200 and deep.json()["status"] == "ok"
    async with factory() as session:
        session.add(
            MailOutbox(
                idempotency_key=f"k-{uuid4()}",
                template_key="pickup_ready",
                recipient="x@example.com",
                subject="s",
                html_body="h",
                text_body="t",
                status="failed",
            )
        )
        await session.commit()
    degraded = await client.get("/health/deep")
    assert degraded.status_code == 503
    assert degraded.json()["error"]["code"] == "HEALTH_DEGRADED"

    await create_admin(factory, "owner@example.com", "owner")
    await create_admin(factory, "staff@example.com", "staff")
    owner = await admin_headers(client, "owner@example.com")
    staff = await admin_headers(client, "staff@example.com")
    assert (await client.get("/admin/audit", headers=staff)).status_code == 403
    audit = (await client.get("/admin/audit?action=admin.login", headers=owner)).json()
    assert audit["total"] >= 2 and all(
        i["action"].startswith("admin.login") for i in audit["items"]
    )
