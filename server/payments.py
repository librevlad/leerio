"""
server/payments.py — Paddle payment integration.

Handles webhook events from Paddle to update user subscription status.
Frontend uses Paddle.js checkout overlay (no server-side session creation needed).
"""

import hashlib
import hmac
import logging
import os

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from . import db

logger = logging.getLogger("leerio.payments")

router = APIRouter(prefix="/api/payments", tags=["payments"])

PADDLE_WEBHOOK_SECRET = os.environ.get("PADDLE_WEBHOOK_SECRET", "")


def _verify_signature(raw_body: bytes, signature: str) -> bool:
    """Verify Paddle webhook signature."""
    if not PADDLE_WEBHOOK_SECRET:
        logger.error("PADDLE_WEBHOOK_SECRET not set, rejecting webhook")
        return False

    # Paddle sends: ts=timestamp;h1=hash
    parts = dict(p.split("=", 1) for p in signature.split(";") if "=" in p)
    ts = parts.get("ts", "")
    h1 = parts.get("h1", "")

    if not ts or not h1:
        return False

    signed_payload = f"{ts}:{raw_body.decode()}"
    expected = hmac.new(PADDLE_WEBHOOK_SECRET.encode(), signed_payload.encode(), hashlib.sha256).hexdigest()

    return hmac.compare_digest(expected, h1)


@router.post("/paddle-webhook")
async def paddle_webhook(request: Request):
    """Handle Paddle webhook events."""
    raw_body = await request.body()
    signature = request.headers.get("paddle-signature", "")

    if PADDLE_WEBHOOK_SECRET and not _verify_signature(raw_body, signature):
        raise HTTPException(403, "Invalid signature")

    import json

    try:
        data = json.loads(raw_body)
    except json.JSONDecodeError:
        raise HTTPException(400, "Invalid JSON")

    event_type = data.get("event_type", "")
    event_data = data.get("data", {})

    logger.info("Paddle event: %s", event_type)

    # Extract customer email from event
    customer = event_data.get("customer", {})
    email = customer.get("email", "")
    paddle_customer_id = customer.get("id", "")

    if not email:
        # Try custom_data passthrough
        custom = event_data.get("custom_data", {})
        email = custom.get("email", "")

    if event_type == "subscription.activated":
        _activate_premium(email, paddle_customer_id)
    elif event_type == "subscription.updated":
        status = event_data.get("status", "")
        if status == "active":
            _activate_premium(email, paddle_customer_id)
        elif status in ("canceled", "past_due", "paused"):
            _deactivate_premium(email)
    elif event_type == "subscription.canceled":
        _deactivate_premium(email)

    return JSONResponse({"ok": True})


def _activate_premium(email: str, paddle_customer_id: str = ""):
    """Set user plan to premium."""
    if not email:
        logger.warning("Cannot activate: no email")
        return
    conn = db._get_conn()
    cursor = conn.execute(
        "UPDATE users SET plan = 'premium', paddle_customer_id = ? WHERE email = ?",
        (paddle_customer_id, email),
    )
    conn.commit()
    if cursor.rowcount == 0:
        logger.warning("Premium activation: no user found for email %s", email)
    else:
        logger.info("Premium activated for %s", email)


def _deactivate_premium(email: str):
    """Set user plan back to free."""
    if not email:
        return
    conn = db._get_conn()
    conn.execute("UPDATE users SET plan = 'free' WHERE email = ?", (email,))
    conn.commit()
    logger.info("Premium deactivated for %s", email)


@router.get("/plan")
async def get_plan(request: Request):
    """Public endpoint to get Paddle price ID, client token, and limits for checkout."""
    price_id = os.environ.get("PADDLE_PRICE_ID", "")
    client_token = os.environ.get("PADDLE_CLIENT_TOKEN", "")
    from .constants import FREE_BOOK_LIMIT

    free_limit = FREE_BOOK_LIMIT
    return {"price_id": price_id, "client_token": client_token, "free_limit": free_limit}
