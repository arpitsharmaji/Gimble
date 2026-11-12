"""Razorpay helpers: server-side order creation + signature verification.

NOTE: written against Razorpay's documented API but not exercised against a live account
in this build. Test fully in Razorpay *test mode* before enabling live keys.
"""
import hashlib, hmac
import httpx
from .config import settings

API = "https://api.razorpay.com/v1"


def create_order(amount_paise: int, receipt: str, notes: dict) -> dict:
    r = httpx.post(
        f"{API}/orders",
        auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET),
        json={"amount": amount_paise, "currency": "INR", "receipt": receipt, "notes": notes},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


def verify_payment_signature(order_id: str, payment_id: str, signature: str) -> bool:
    expected = hmac.new(settings.RAZORPAY_KEY_SECRET.encode(), f"{order_id}|{payment_id}".encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature or "")


def verify_webhook_signature(body: bytes, signature: str) -> bool:
    if not settings.RAZORPAY_WEBHOOK_SECRET:
        return False
    expected = hmac.new(settings.RAZORPAY_WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature or "")
