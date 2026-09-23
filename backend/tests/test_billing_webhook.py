"""Webhook signature verification: fails closed, rejects forgery, credits only on valid HMAC."""

import hashlib
import hmac
import json
import uuid

import httpx
import pytest


def _sign(secret: str, raw_body: bytes) -> str:
    return hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()


async def _register_and_org_id(client: httpx.AsyncClient) -> dict:
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"wh-{uuid.uuid4().hex[:8]}@example.com",
            "full_name": "Webhook Tester",
            "password": "Testpass123!",
            "org_name": f"WhOrg-{uuid.uuid4().hex[:6]}",
        },
    )
    assert resp.status_code == 201, resp.text
    headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}
    me = await client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200
    return {"headers": headers, "org_id": me.json()["org_id"]}


@pytest.mark.asyncio
async def test_webhook_fails_closed_when_secret_unset(client: httpx.AsyncClient, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "PAYMENT_WEBHOOK_SECRET", "")
    ctx = await _register_and_org_id(client)
    payload = json.dumps(
        {
            "event": "payment.captured",
            "order_id": "order_x",
            "org_id": ctx["org_id"],
            "credits": 200,
        }
    ).encode()
    resp = await client.post(
        "/api/v1/billing/webhook",
        content=payload,
        headers={"X-Payment-Signature": _sign("whatever", payload)},
    )
    assert resp.status_code == 503
    assert "PAYMENT_WEBHOOK_SECRET" in resp.json()["error"]["message"]


@pytest.mark.asyncio
async def test_webhook_rejects_forged_signature(client: httpx.AsyncClient, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "PAYMENT_WEBHOOK_SECRET", "s3cret")
    ctx = await _register_and_org_id(client)
    payload = json.dumps(
        {
            "event": "payment.captured",
            "order_id": "order_x",
            "org_id": ctx["org_id"],
            "credits": 99999,
        }
    ).encode()
    resp = await client.post(
        "/api/v1/billing/webhook",
        content=payload,
        headers={"X-Payment-Signature": _sign("wrong-secret", payload)},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_webhook_credits_org_on_valid_signature(client: httpx.AsyncClient, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "PAYMENT_WEBHOOK_SECRET", "s3cret")
    ctx = await _register_and_org_id(client)
    balance_resp = await client.get("/api/v1/billing/usage", headers=ctx["headers"])
    assert balance_resp.status_code == 200
    initial = balance_resp.json()["current_balance"]

    added = 200
    payload = json.dumps(
        {
            "event": "payment.captured",
            "order_id": "order_valid",
            "org_id": ctx["org_id"],
            "credits": added,
        }
    ).encode()
    resp = await client.post(
        "/api/v1/billing/webhook",
        content=payload,
        headers={"X-Payment-Signature": _sign("s3cret", payload)},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "credited"
    assert body["added"] == added
    assert body["new_balance"] == initial + added


@pytest.mark.asyncio
async def test_webhook_native_razorpay_payload_credits_stored_order(
    client: httpx.AsyncClient, monkeypatch
):
    from app.core.config import settings

    monkeypatch.setattr(settings, "PAYMENT_WEBHOOK_SECRET", "s3cret")
    ctx = await _register_and_org_id(client)

    checkout = await client.post(
        "/api/v1/billing/checkout",
        json={"pack_credits": 100, "gateway": "razorpay", "currency": "INR"},
        headers=ctx["headers"],
    )
    assert checkout.status_code == 200, checkout.text
    order_id = checkout.json()["order_id"]

    payload = json.dumps(
        {
            "event": "payment.captured",
            "entity": {
                "order_id": order_id,
                "id": "pay_native123",
                "amount": 39900,
                "currency": "INR",
            },
        }
    ).encode()
    resp = await client.post(
        "/api/v1/billing/webhook",
        content=payload,
        headers={"X-Razorpay-Signature": _sign("s3cret", payload)},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "credited"
    assert body["added"] == 100
    assert body["order_id"] == order_id

    duplicate = await client.post(
        "/api/v1/billing/webhook",
        content=payload,
        headers={"X-Razorpay-Signature": _sign("s3cret", payload)},
    )
    assert duplicate.status_code == 200
    assert duplicate.json()["duplicate"] is True


@pytest.mark.asyncio
async def test_webhook_native_payload_unknown_order_404(client: httpx.AsyncClient, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "PAYMENT_WEBHOOK_SECRET", "s3cret")
    ctx = await _register_and_org_id(client)
    payload = json.dumps(
        {
            "event": "payment.captured",
            "entity": {"order_id": "order_does_not_exist", "id": "pay_x"},
        }
    ).encode()
    resp = await client.post(
        "/api/v1/billing/webhook",
        content=payload,
        headers={"X-Razorpay-Signature": _sign("s3cret", payload)},
    )
    assert resp.status_code == 404

    usage = await client.get("/api/v1/billing/usage", headers=ctx["headers"])
    assert usage.status_code == 200


@pytest.mark.asyncio
async def test_checkout_persists_payment_order(client: httpx.AsyncClient):
    ctx = await _register_and_org_id(client)
    resp = await client.post(
        "/api/v1/billing/checkout",
        json={"pack_credits": 100, "gateway": "razorpay", "currency": "INR"},
        headers=ctx["headers"],
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["gateway"] == "razorpay"
    assert data["amount"] == 399
    assert data["credits"] == 100
    assert data["order_id"].startswith("order_")


@pytest.mark.asyncio
async def test_webhook_accepts_stripe_timestamped_signature(client: httpx.AsyncClient, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "PAYMENT_WEBHOOK_SECRET", "s3cret")
    ctx = await _register_and_org_id(client)
    payload = json.dumps(
        {
            "event": "checkout.session.completed",
            "order_id": "order_stripe",
            "org_id": ctx["org_id"],
            "credits": 100,
        }
    ).encode()
    ts = "1700000000"
    expected = hmac.new(b"s3cret", f"{ts}.{payload.decode()}".encode(), hashlib.sha256).hexdigest()
    resp = await client.post(
        "/api/v1/billing/webhook",
        content=payload,
        headers={"Stripe-Signature": f"t={ts},v1={expected}"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["added"] == 100
