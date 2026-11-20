"""Money in: membership + booking payments (Razorpay or demo), verification and webhook."""
import json, logging
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from ..config import settings, PLANS, PAY_DEADLINE_MINUTES
from ..db import get_db
from ..models import User, Booking, PaymentOrder, ManualPayment, utcnow
from ..schemas import VerifyPaymentIn
from ..security import current_user, rate_limit
from .. import payments
from ..services import grant_membership, mark_booking_paid, notify, _do_refund, audit

router = APIRouter(prefix="/api", tags=["payments"])
log = logging.getLogger("gimble.pay")


def activate_order(db: Session, order: PaymentOrder, payment_id: str):
    """Idempotent: both the browser callback and the webhook may call this."""
    if order.status == "paid":
        return
    order.status, order.payment_id = "paid", payment_id
    if order.kind == "membership":
        grant_membership(db, order.user_id, order.plan, f"razorpay:{payment_id}")
        notify(db, order.user_id, "membership", "Your Gimble membership is active. You can now send booking requests.", "#/browse")
        return
    b = db.get(Booking, order.booking_id)
    if b and b.status == "accepted":
        mark_booking_paid(db, b, payment_id)
    elif b and b.payment_status == "unpaid":  # booking was cancelled while the customer was paying: give it back
        b.payment_status, b.paid_amount, b.payment_id = "paid", b.price, payment_id
        _do_refund(db, b, b.price)
        audit(db, None, "late_payment_refunded", f"booking:{b.id}")


@router.post("/payments/verify", dependencies=[Depends(rate_limit("payverify", 30, 600))])
@router.post("/membership/verify", include_in_schema=False)  # kept for v2 clients
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
    activate_order(db, order, x.razorpay_payment_id)
    db.commit()
    return {"message": "Payment confirmed"}


@router.get("/payments/orders/{provider_order_id}", dependencies=[Depends(rate_limit("payorder", 90, 600))])
def order_status(provider_order_id: str, u: User = Depends(current_user), db: Session = Depends(get_db)):
    """Polled by the browser after checkout. If we have not heard from Razorpay yet (UPI app-switch),
    ask Razorpay directly, so a paid order is never left dangling. Only a captured payment whose amount
    matches the order we created activates it."""
    order = db.query(PaymentOrder).filter_by(provider_order_id=provider_order_id, user_id=u.id).first()
    if not order:
        raise HTTPException(404, "Order not found")
    if order.status == "created" and settings.razorpay_enabled:
        try:
            for pay in payments.order_payments(provider_order_id):
                if pay.get("status") == "captured" and pay.get("amount") == order.amount_paise:
                    activate_order(db, order, pay.get("id", ""))
                    db.commit()
                    break
        except Exception:
            log.warning("Order reconcile failed for %s", provider_order_id, exc_info=True)
    return {"status": order.status}


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
            activate_order(db, order, pay.get("id", ""))
            db.commit()
    elif event.get("event") == "payment.failed":
        # UPI attempts fail often (declined, timed out, wrong PIN) and the customer can retry on the same
        # order, so this is informational: never downgrade an order that is already paid.
        pay = event.get("payload", {}).get("payment", {}).get("entity", {})
        log.info("Razorpay payment failed: order=%s reason=%s", pay.get("order_id"), pay.get("error_description"))
    elif event.get("event") == "refund.failed":
        ref = event.get("payload", {}).get("refund", {}).get("entity", {})
        b = db.query(Booking).filter_by(payment_id=ref.get("payment_id", "")).first()
        if b:
            b.payment_status = "refund_pending"  # surfaces in the admin console for a manual retry
            audit(db, None, "refund_failed", f"booking:{b.id}", ref.get("id", ""))
            db.commit()
    return {"ok": True}


# ---------------- booking payment ----------------
def _payable(db: Session, booking_id: int, u: User) -> Booking:
    b = db.get(Booking, booking_id)
    if not b or b.customer_id != u.id:
        raise HTTPException(404, "Booking not found")
    if b.status != "accepted":
        raise HTTPException(409, "You can pay once the partner has accepted your request")
    if b.payment_status != "unpaid":
        raise HTTPException(409, "This booking is already paid")
    if settings.booking_payments_on and utcnow() > b.scheduled_at - timedelta(minutes=PAY_DEADLINE_MINUTES):
        raise HTTPException(409, f"Payment must be made at least {PAY_DEADLINE_MINUTES} minutes before the start")
    return b


@router.post("/bookings/{booking_id}/pay", dependencies=[Depends(rate_limit("bookpay", 20, 600))])
def pay_booking(booking_id: int, u: User = Depends(current_user), db: Session = Depends(get_db)):
    b = _payable(db, booking_id, u)
    amount = b.price * 100
    if settings.razorpay_enabled:
        try:
            order = payments.create_order(amount, f"booking-{b.id}", {"booking_id": str(b.id), "user_id": str(u.id)})
        except Exception:
            log.exception("Razorpay order creation failed")
            raise HTTPException(502, "Payment provider is unavailable. Please try again shortly.")
        db.add(PaymentOrder(user_id=u.id, plan="booking", kind="booking", booking_id=b.id, amount_paise=amount,
                            provider_order_id=order["id"]))
        db.commit()
        return {"mode": "razorpay", "key_id": settings.RAZORPAY_KEY_ID, "order_id": order["id"], "amount": amount,
                "currency": "INR", "name": "Gimble", "description": f"{b.activity} booking #{b.id}",
                "prefill": {"name": u.name, "email": u.email}}
    if settings.manual_upi_enabled:
        if db.query(ManualPayment).filter_by(user_id=u.id, kind="booking", booking_id=b.id, status="pending").first():
            raise HTTPException(409, "Your payment proof is already under review. We'll notify you as soon as it's checked.")
        return {"mode": "manual", "amount": amount, "booking_id": b.id}
    if settings.DEMO_PAYMENTS_ENABLED:
        return {"mode": "demo", "amount": amount}
    raise HTTPException(503, "Payments are not configured yet")


@router.post("/bookings/{booking_id}/demo-pay")
def demo_pay(booking_id: int, u: User = Depends(current_user), db: Session = Depends(get_db)):
    """Development only: marks a booking paid WITHOUT collecting money."""
    if not settings.DEMO_PAYMENTS_ENABLED or settings.razorpay_enabled or settings.manual_upi_enabled:
        raise HTTPException(404, "Demo payments are disabled")
    b = _payable(db, booking_id, u)
    mark_booking_paid(db, b, "DEMO-NO-MONEY")
    db.commit()
    return {"message": "Demo payment recorded (no money collected)"}
