import json, logging
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from ..config import settings, PLANS
from ..db import get_db
from ..models import User, PaymentOrder
from ..schemas import CheckoutIn, VerifyPaymentIn
from ..security import current_user
from .. import payments
from ..services import active_membership, grant_membership, notify

router = APIRouter(prefix="/api", tags=["membership"])
log = logging.getLogger("pairup.pay")


def _require_customer(u: User):
    if u.role != "customer":
        raise HTTPException(403, "Memberships are for customer accounts")


@router.get("/membership/plans")
def plans():
    return {"plans": [{"id": k, **v} for k, v in PLANS.items()],
            "mode": "razorpay" if settings.razorpay_enabled else ("demo" if settings.DEMO_PAYMENTS_ENABLED else "unavailable")}


@router.get("/membership/status")
def status(u: User = Depends(current_user), db: Session = Depends(get_db)):
    m = active_membership(db, u.id)
    return {"active": bool(m), "plan": m.plan if m else None, "expires_at": m.expires_at.isoformat() + "Z" if m else None}


@router.post("/membership/checkout")
def checkout(x: CheckoutIn, u: User = Depends(current_user), db: Session = Depends(get_db)):
    """Server-side order creation. The amount comes from PLANS, never from the browser."""
    _require_customer(u)
    if x.plan not in PLANS:
        raise HTTPException(400, "Invalid plan")
    amount_paise = PLANS[x.plan]["amount"] * 100
    if settings.razorpay_enabled:
        try:
            order = payments.create_order(amount_paise, f"pairup-{u.id}-{x.plan}", {"user_id": str(u.id), "plan": x.plan})
        except Exception:
            log.exception("Razorpay order creation failed")
            raise HTTPException(502, "Payment provider is unavailable. Please try again shortly.")
        db.add(PaymentOrder(user_id=u.id, plan=x.plan, amount_paise=amount_paise, provider_order_id=order["id"]))
        db.commit()
        return {"mode": "razorpay", "key_id": settings.RAZORPAY_KEY_ID, "order_id": order["id"],
                "amount": amount_paise, "currency": "INR", "name": "PairUp", "description": f"{PLANS[x.plan]['label']} membership",
                "prefill": {"name": u.name, "email": u.email}}
    if settings.DEMO_PAYMENTS_ENABLED:
        return {"mode": "demo", "amount": amount_paise}
    raise HTTPException(503, "Payments are not configured yet")


def _activate_paid_order(db: Session, order: PaymentOrder, payment_id: str):
    if order.status == "paid":  # idempotent: browser verify and webhook may both arrive
        return
    order.status, order.payment_id = "paid", payment_id
    grant_membership(db, order.user_id, order.plan, f"razorpay:{payment_id}")
    notify(db, order.user_id, "membership", "Your PairUp membership is active. You can now send booking requests.", "#/")


@router.post("/membership/verify")
def verify(x: VerifyPaymentIn, u: User = Depends(current_user), db: Session = Depends(get_db)):
    if not settings.razorpay_enabled:
        raise HTTPException(503, "Payments are not configured")
    order = db.query(PaymentOrder).filter_by(provider_order_id=x.razorpay_order_id, user_id=u.id).first()
    if not order:
        raise HTTPException(404, "Order not found")
    if not payments.verify_payment_signature(x.razorpay_order_id, x.razorpay_payment_id, x.razorpay_signature):
        order.status = "failed"
        db.commit()
        raise HTTPException(400, "Payment signature could not be verified")
    _activate_paid_order(db, order, x.razorpay_payment_id)
    db.commit()
    return {"message": "Membership activated"}


@router.post("/webhooks/razorpay")
async def razorpay_webhook(request: Request, db: Session = Depends(get_db)):
    body = await request.body()
    if not payments.verify_webhook_signature(body, request.headers.get("x-razorpay-signature", "")):
        raise HTTPException(400, "Invalid signature")
    event = json.loads(body or b"{}")
    if event.get("event") in ("payment.captured", "order.paid"):
        pay = event.get("payload", {}).get("payment", {}).get("entity", {})
        order = db.query(PaymentOrder).filter_by(provider_order_id=pay.get("order_id", "")).first()
        if order and pay.get("amount") == order.amount_paise:
            _activate_paid_order(db, order, pay.get("id", ""))
            db.commit()
    return {"ok": True}


@router.post("/membership/demo-activate")
def demo_activate(x: CheckoutIn, u: User = Depends(current_user), db: Session = Depends(get_db)):
    """Development-only entitlement switch. Collects NO money. Disabled in production."""
    _require_customer(u)
    if not settings.DEMO_PAYMENTS_ENABLED or settings.razorpay_enabled and settings.is_production:
        raise HTTPException(404, "Demo membership is disabled")
    if x.plan not in PLANS:
        raise HTTPException(400, "Invalid plan")
    m = grant_membership(db, u.id, x.plan, "DEMO-NO-MONEY-COLLECTED")
    db.commit()
    return {"message": "Demo membership activated without payment. Not valid for a real launch.",
            "expires_at": m.expires_at.isoformat() + "Z", "demo": True}
