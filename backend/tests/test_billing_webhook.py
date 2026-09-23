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
