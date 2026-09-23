"""Razorpay Orders API integration.

Creates real gateway orders from checkout sessions. Uses the Razorpay REST API
(``https://api.razorpay.com/v1/orders``) with basic auth from
``RAZORPAY_KEY_ID`` / ``RAZORPAY_KEY_SECRET``. Amounts are in the smallest
currency unit (paise) as required by Razorpay.
"""

from __future__ import annotations

import base64
import json
from typing import Any, cast

import httpx

RAZORPAY_API_BASE = "https://api.razorpay.com/v1"


class RazorpayError(RuntimeError):
    """Raised when Razorpay rejects an order request."""


def razorpay_configured(*, key_id: str, key_secret: str) -> bool:
    return bool(key_id and key_secret)


def _auth_header(key_id: str, key_secret: str) -> dict[str, str]:
    token = base64.b64encode(f"{key_id}:{key_secret}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


async def create_order(
    *,
    key_id: str,
    key_secret: str,
    amount: int,
    currency: str = "INR",
    receipt: str,
    notes: dict[str, Any] | None = None,
    timeout: float = 15.0,
) -> dict[str, Any]:
    """Create a Razorpay order and return its issuance payload.

    ``amount`` is in the smallest currency unit (e.g. paise). Raises
    :class:`RazorpayError` on upstream failure.
    """
    params: dict[str, Any] = {
        "amount": amount,
        "currency": currency.upper(),
        "receipt": receipt,
    }
    if notes:
        params["notes"] = notes

    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(
            f"{RAZORPAY_API_BASE}/orders",
            headers=_auth_header(key_id, key_secret),
            json=params,
        )
    if resp.status_code not in (200, 201):
        raise RazorpayError(
            f"Razorpay order creation failed: HTTP {resp.status_code} {resp.text[:500]}"
        )
    data = resp.json()
    order_id = data.get("id")
    if not order_id:
        raise RazorpayError(f"Razorpay returned no order id: {json.dumps(data)[:500]}")
    return cast(dict[str, Any], data)
