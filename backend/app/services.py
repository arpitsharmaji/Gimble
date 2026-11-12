"""Shared helpers used by several routers."""
import json, logging, threading
from datetime import datetime, timedelta
from fastapi import HTTPException
from sqlalchemy import or_, and_
from sqlalchemy.orm import Session
from .config import PLANS, settings, REFUND_FULL_HOURS, REFUND_HALF_HOURS, PAY_DEADLINE_MINUTES
from .mailer import send_email
from . import payments
from .models import (User, PartnerProfile, Membership, Booking, Notification, Block,
                     AuditLog, LedgerEntry, utcnow)
from .security import age_from


log = logging.getLogger("pairup.services")
EMAIL_KINDS = {"booking", "membership", "payment", "payout", "profile", "kyc", "support"}
IST = timedelta(hours=5, minutes=30)  # India is a single timezone, no DST


def notify(db: Session, user_id: int, kind: str, text: str, link: str = ""):
    """In-app notification; important kinds are also emailed (in a background thread)."""
    db.add(Notification(user_id=user_id, kind=kind, text=text[:300], link=link))
    if kind in EMAIL_KINDS:
        u = db.get(User, user_id)
        if u and u.active and not u.email.endswith("@deleted.invalid"):
            threading.Thread(target=send_email, daemon=True,
                             args=(u.email, "PairUp: " + text[:70], f"{text}\n\n{settings.PUBLIC_URL}/{link}")).start()


def audit(db: Session, actor_id: int | None, action: str, target: str = "", detail: str = ""):
    db.add(AuditLog(actor_id=actor_id, action=action, target=target[:60], detail=detail[:400]))


def user_json(u: User) -> dict:
    return {"id": u.id, "name": u.name, "email": u.email, "age": age_from(u.dob), "city": u.city,
            "gender": u.gender, "role": u.role, "email_verified": u.email_verified}


def partner_json(p: PartnerProfile, own: bool = False) -> dict:
    """Public partner representation. Never includes email."""
    rates = json.loads(p.rates_json or "{}")
    photos = json.loads(p.photos_json or "[]")
    data = {
        "id": p.user_id, "name": p.user.name, "age": age_from(p.user.dob), "city": p.user.city,
        "gender": p.user.gender, "headline": p.headline, "bio": p.bio,
        "photo_url": photos[0] if photos else "", "photos": photos,
        "activities": json.loads(p.activities_json or "[]"), "rates": rates,
        "languages": json.loads(p.languages_json or "[]"),
        "min_rate": min(rates.values()) if rates else 0,
        "available": p.available, "verified": p.verified,
        "rating": round(p.rating or 0, 1), "review_count": p.review_count,
        "member_since": p.user.created_at.strftime("%b %Y"),
        "schedule": json.loads(p.schedule_json or "{}"),
    }
    if own:
        data.update({"status": p.status, "reject_reason": p.reject_reason})
    return data


def active_membership(db: Session, uid: int) -> Membership | None:
    return (db.query(Membership)
            .filter(Membership.user_id == uid, Membership.status == "active", Membership.expires_at > utcnow())
            .order_by(Membership.expires_at.desc()).first())


def grant_membership(db: Session, user_id: int, plan: str, payment_ref: str) -> Membership:
    current = active_membership(db, user_id)
    start = current.expires_at if current else utcnow()
    m = Membership(user_id=user_id, status="active", plan=plan, starts_at=start,
                   expires_at=start + timedelta(days=PLANS[plan]["days"]), payment_ref=payment_ref)
    db.add(m)
    return m


def is_blocked(db: Session, a: int, b: int) -> bool:
    return db.query(Block.id).filter(or_(and_(Block.user_id == a, Block.blocked_id == b),
                                         and_(Block.user_id == b, Block.blocked_id == a))).first() is not None


def blocked_ids(db: Session, uid: int) -> set[int]:
    rows = db.query(Block).filter(or_(Block.user_id == uid, Block.blocked_id == uid)).all()
    return {r.blocked_id if r.user_id == uid else r.user_id for r in rows}


def refund_percent_if_customer_cancels(b: Booking) -> int:
    hours = (b.scheduled_at - utcnow()).total_seconds() / 3600
    return 100 if hours >= REFUND_FULL_HOURS else 50 if hours >= REFUND_HALF_HOURS else 0


def booking_json(b: Booking, db: Session) -> dict:
    c, p = db.get(User, b.customer_id), db.get(User, b.partner_id)
    fee = b.platform_fee or round(b.price * settings.PLATFORM_FEE_PERCENT / 100)
    return {"id": b.id, "customer_id": b.customer_id, "customer_name": c.name if c else "",
            "partner_id": b.partner_id, "partner_name": p.name if p else "",
            "activity": b.activity, "scheduled_at": b.scheduled_at.isoformat() + "Z",
            "duration_minutes": b.duration_minutes, "location": b.location, "price": b.price,
            "note": b.note, "status": b.status, "status_reason": b.status_reason,
            "payment_status": b.payment_status, "paid_amount": b.paid_amount, "refund_amount": b.refund_amount,
            "partner_earning": b.price - fee,
            "pay_deadline": (b.scheduled_at - timedelta(minutes=PAY_DEADLINE_MINUTES)).isoformat() + "Z",
            "payments_on": settings.booking_payments_on,
            "refund_percent_now": refund_percent_if_customer_cancels(b) if b.payment_status == "paid" else None,
            "created_at": b.created_at.isoformat() + "Z"}


# ---------------- wallet / ledger ----------------
def credit(db: Session, user_id: int, amount: int, kind: str, booking_id: int | None = None, note: str = "", hold: bool = True):
    when = utcnow() + (timedelta(hours=settings.PAYOUT_HOLD_HOURS) if hold else timedelta())
    db.add(LedgerEntry(user_id=user_id, booking_id=booking_id, kind=kind, amount=amount, available_at=when, note=note[:200]))


def wallet_totals(db: Session, user_id: int) -> dict:
    now = utcnow()
    rows = db.query(LedgerEntry).filter_by(user_id=user_id).all()
    total = sum(r.amount for r in rows)
    available = sum(r.amount for r in rows if r.amount < 0 or r.available_at <= now)
    return {"balance": total, "available": max(0, available), "pending": total - max(0, available)}


def mark_booking_paid(db: Session, b: Booking, payment_id: str):
    if b.payment_status != "unpaid":
        return  # idempotent (browser verify and webhook can both arrive)
    b.payment_status, b.paid_amount, b.payment_id = "paid", b.price, payment_id
    b.platform_fee = round(b.price * settings.PLATFORM_FEE_PERCENT / 100)
    notify(db, b.partner_id, "payment", f"Payment received for your {b.activity} booking. It's confirmed!", "#/bookings")
    notify(db, b.customer_id, "payment", f"Payment confirmed for your {b.activity} booking.", "#/bookings")


def _do_refund(db: Session, b: Booking, amount: int):
    if amount <= 0:
        return
    b.refund_amount = amount
    full = amount >= b.paid_amount
    if b.payment_id and not b.payment_id.startswith("DEMO") and settings.razorpay_enabled:
        try:
            payments.refund(b.payment_id, amount * 100)
        except Exception:
            log.exception("Refund API failed for booking %s", b.id)
            b.payment_status = "refund_pending"  # an admin can retry from the console
            notify(db, b.customer_id, "payment", "Your refund is being processed and will be completed shortly.", "#/bookings")
            return
    b.payment_status = "refunded" if full else "partially_refunded"
    notify(db, b.customer_id, "payment", f"Refund of ₹{amount} initiated for your cancelled booking. It usually reaches you in 5-7 working days.", "#/bookings")


def cancel_booking(db: Session, b: Booking, reason: str, refund_percent: int = 100):
    """Cancel and settle money: refund `refund_percent` of what was paid; the retained part goes to the partner."""
    b.status, b.status_reason = "cancelled", reason
    if b.payment_status == "paid":
        refund = round(b.paid_amount * refund_percent / 100)
        retained = b.paid_amount - refund
        _do_refund(db, b, refund)
        if refund == 0:
            b.payment_status = "paid"  # nothing returned
        if retained > 0:
            fee = round(retained * settings.PLATFORM_FEE_PERCENT / 100)
            credit(db, b.partner_id, retained - fee, "cancel_compensation", b.id, f"Late cancellation of booking #{b.id}")


def complete_booking(db: Session, b: Booking):
    b.status = "completed"
    if b.payment_status == "paid":
        credit(db, b.partner_id, b.paid_amount - b.platform_fee, "earning", b.id, f"{b.activity} (booking #{b.id})")


def in_schedule(p: PartnerProfile, start_utc: datetime, minutes: int) -> bool:
    """True if [start, start+minutes] fits inside the partner's weekly hours (IST). Empty schedule = any time."""
    sched = json.loads(p.schedule_json or "{}")
    if not sched:
        return True
    local = start_utc + IST
    win = sched.get(["mon", "tue", "wed", "thu", "fri", "sat", "sun"][local.weekday()])
    if not win:
        return False
    s_h, s_m = map(int, win[0].split(":")); e_h, e_m = map(int, win[1].split(":"))
    start_min, end_min = local.hour * 60 + local.minute, local.hour * 60 + local.minute + minutes
    return s_h * 60 + s_m <= start_min and end_min <= e_h * 60 + e_m


def expire_stale(db: Session):
    """Housekeeping: close unanswered requests and cancel accepted-but-unpaid bookings."""
    now = utcnow()
    changed = (db.query(Booking).filter(Booking.status == "requested", Booking.scheduled_at < now)
               .update({"status": "expired", "status_reason": "No response before the start time"}))
    if settings.booking_payments_on:
        due = db.query(Booking).filter(Booking.status == "accepted", Booking.payment_status == "unpaid",
                                       Booking.scheduled_at < now + timedelta(minutes=PAY_DEADLINE_MINUTES)).all()
        for b in due:
            cancel_booking(db, b, "Payment was not completed in time")
            notify(db, b.customer_id, "booking", f"Your {b.activity} booking was cancelled because payment wasn't completed in time.", "#/bookings")
            notify(db, b.partner_id, "booking", f"Your {b.activity} booking was cancelled - the customer didn't pay in time.", "#/bookings")
        changed += len(due)
    if changed:
        db.commit()


def can_chat(db: Session, a: int, b: int) -> bool:
    if a == b or is_blocked(db, a, b):
        return False
    cutoff = utcnow() - timedelta(hours=48)
    pair = or_(and_(Booking.customer_id == a, Booking.partner_id == b),
               and_(Booking.customer_id == b, Booking.partner_id == a))
    return db.query(Booking.id).filter(pair, or_(
        Booking.status == "accepted",
        and_(Booking.status == "completed", Booking.updated_at >= cutoff))).first() is not None


def require_adult_active(u: User):
    if age_from(u.dob) < 18:
        raise HTTPException(403, "Members must be 18 or older")
