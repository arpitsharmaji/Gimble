import json
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session
from ..config import settings, MIN_LEAD_MINUTES, ACCEPT_MIN_LEAD_MINUTES
from ..db import get_db
from ..models import User, PartnerProfile, Booking, Review, utcnow
from ..moderation import check_text
from ..schemas import BookingIn, BookingStatusIn, ReviewIn, ReplyIn
from ..security import current_user, rate_limit
from ..services import (active_membership, booking_json, expire_stale, is_blocked, notify, audit,
                        cancel_booking, complete_booking, in_schedule, refund_percent_if_customer_cancels)

router = APIRouter(prefix="/api", tags=["bookings"])
MAX_OPEN_REQUESTS = 10


def _end(b: Booking) -> datetime:
    return b.scheduled_at + timedelta(minutes=b.duration_minutes)


@router.post("/bookings", dependencies=[Depends(rate_limit("booking", 20, 3600))])
def create_booking(x: BookingIn, u: User = Depends(current_user), db: Session = Depends(get_db)):
    if u.role != "customer":
        raise HTTPException(403, "Only customer accounts can request a booking")
    if not x.safety_ack:
        raise HTTPException(400, "Please confirm you'll meet in a public place and follow the safety rules")
    if settings.REQUIRE_VERIFIED_EMAIL and not u.email_verified:
        raise HTTPException(403, "Please verify your email before booking")
    if not active_membership(db, u.id):
        raise HTTPException(402, "An active membership is required before booking")
    p = (db.query(PartnerProfile).join(User, User.id == PartnerProfile.user_id)
         .filter(PartnerProfile.user_id == x.partner_id, PartnerProfile.status == "approved",
                 PartnerProfile.available.is_(True), User.active.is_(True)).first())
    if not p or x.partner_id == u.id or is_blocked(db, u.id, x.partner_id):
        raise HTTPException(404, "This partner is unavailable")
    rates = json.loads(p.rates_json or "{}")
    if x.activity not in rates:
        raise HTTPException(400, "This partner does not offer that activity")
    start = x.scheduled_at
    if start.tzinfo is not None:
        start = start.astimezone(timezone.utc).replace(tzinfo=None)
    now = utcnow()
    if start < now + timedelta(minutes=MIN_LEAD_MINUTES):
        raise HTTPException(400, "Choose a time at least 2 hours from now so there's time to confirm and pay")
    if start > now + timedelta(days=90):
        raise HTTPException(400, "Bookings can be made up to 90 days ahead")
    for field, ctx in ((x.location, "booking"), (x.note, "booking")):
        problem = check_text(field, ctx)
        if problem:
            raise HTTPException(400, problem)
    if not in_schedule(p, start, x.duration_minutes):
        raise HTTPException(400, "This partner isn't available at that time. Check their weekly hours on their profile.")
    open_n = db.query(Booking).filter(Booking.customer_id == u.id, Booking.status == "requested").count()
    if open_n >= MAX_OPEN_REQUESTS:
        raise HTTPException(429, "You have too many pending requests. Wait for responses first.")
    end = start + timedelta(minutes=x.duration_minutes)
    mine = db.query(Booking).filter(Booking.customer_id == u.id, Booking.partner_id == x.partner_id,
                                    Booking.status.in_(("requested", "accepted"))).all()
    if any(o.scheduled_at < end and start < _end(o) for o in mine):
        raise HTTPException(409, "You already have a request with this partner that overlaps that time")
    b = Booking(customer_id=u.id, partner_id=x.partner_id, activity=x.activity, scheduled_at=start,
                duration_minutes=x.duration_minutes, location=x.location.strip(), note=x.note.strip(),
                price=int(rates[x.activity]))  # price always from the partner's rate card
    db.add(b)
    notify(db, x.partner_id, "booking", f"New booking request from {u.name.split()[0]}: {x.activity}", "#/bookings")
    db.commit()
    db.refresh(b)
    return booking_json(b, db)


@router.get("/bookings")
def my_bookings(u: User = Depends(current_user), db: Session = Depends(get_db)):
    expire_stale(db)
    rows = (db.query(Booking).filter(or_(Booking.customer_id == u.id, Booking.partner_id == u.id))
            .order_by(Booking.scheduled_at.desc()).all())
    return [booking_json(b, db) for b in rows]


@router.patch("/bookings/{booking_id}")
def update_booking(booking_id: int, x: BookingStatusIn, u: User = Depends(current_user), db: Session = Depends(get_db)):
    expire_stale(db)
    b = db.get(Booking, booking_id)
    if not b or u.id not in (b.customer_id, b.partner_id):
        raise HTTPException(404, "Booking not found")
    new, reason = x.status, x.reason.strip()
    is_partner = u.id == b.partner_id
    other = b.customer_id if is_partner else b.partner_id
    if b.status in ("completed", "cancelled", "rejected", "expired"):
        raise HTTPException(409, "This booking is already closed")

    if b.status == "requested":
        if new in ("accepted", "rejected"):
            if not is_partner:
                raise HTTPException(403, "Only the partner can accept or decline a request")
        elif new == "cancelled":
            pass
        else:
            raise HTTPException(400, "A request can only be accepted, declined or cancelled")
    elif b.status == "accepted":
        if new == "cancelled":
            if not reason:
                raise HTTPException(400, "Please give a short reason for cancelling")
        elif new == "completed":
            if utcnow() < b.scheduled_at:
                raise HTTPException(400, "You can mark this completed once the plan has started")
            if settings.booking_payments_on and b.payment_status != "paid":
                raise HTTPException(400, "This booking hasn't been paid, so it can't be completed")
        else:
            raise HTTPException(400, "An accepted booking can only be cancelled or completed")

    if new == "accepted":
        if settings.booking_payments_on and b.scheduled_at < utcnow() + timedelta(minutes=ACCEPT_MIN_LEAD_MINUTES):
            raise HTTPException(409, "This is too close to the start time to confirm - the customer wouldn't have time to pay. Please decline.")
        clash = db.query(Booking).filter(Booking.partner_id == b.partner_id, Booking.status == "accepted",
                                         Booking.id != b.id).all()
        if any(o.scheduled_at < _end(b) and b.scheduled_at < _end(o) for o in clash):
            raise HTTPException(409, "You already have an accepted booking that overlaps this time")

    if new == "cancelled":
        pct = 100 if is_partner or b.status == "requested" else refund_percent_if_customer_cancels(b)
        cancel_booking(db, b, reason, pct)
    elif new == "completed":
        complete_booking(db, b)
        b.status_reason = reason
    else:
        b.status, b.status_reason = new, reason
    labels = {"accepted": "accepted your request - pay now to confirm", "rejected": "declined your request",
              "cancelled": "cancelled the booking", "completed": "marked the booking completed"}
    notify(db, other, "booking", f"{u.name.split()[0]} {labels[new]} ({b.activity})", "#/bookings")
    audit(db, u.id, f"booking_{new}", f"booking:{b.id}")
    db.commit()
    return booking_json(b, db)


@router.post("/bookings/{booking_id}/reviews")
def create_review(booking_id: int, x: ReviewIn, u: User = Depends(current_user), db: Session = Depends(get_db)):
    b = db.get(Booking, booking_id)
    if not b or b.customer_id != u.id or b.status != "completed":
        raise HTTPException(400, "A review requires your completed booking")
    if db.query(Review).filter_by(booking_id=booking_id).first():
        raise HTTPException(409, "This booking has already been reviewed")
    comment = x.comment.strip()
    problem = check_text(comment, "message")
    if problem:
        raise HTTPException(400, problem)
    db.add(Review(booking_id=booking_id, customer_id=u.id, partner_id=b.partner_id, rating=x.rating, comment=comment))
    db.flush()
    p = db.query(PartnerProfile).filter_by(user_id=b.partner_id).first()
    reviews = db.query(Review).filter_by(partner_id=b.partner_id).all()
    if p:
        p.review_count = len(reviews)
        p.rating = sum(r.rating for r in reviews) / len(reviews)
    notify(db, b.partner_id, "review", f"You received a {x.rating}★ review", "#/dashboard")
    db.commit()
    return {"message": "Verified review saved"}


@router.post("/reviews/{booking_id}/reply")
def reply_to_review(booking_id: int, x: ReplyIn, u: User = Depends(current_user), db: Session = Depends(get_db)):
    r = db.query(Review).filter_by(booking_id=booking_id, partner_id=u.id).first()
    if not r:
        raise HTTPException(404, "Review not found")
    reply = x.reply.strip()
    problem = check_text(reply, "message")
    if problem:
        raise HTTPException(400, problem)
    r.partner_reply = reply
    db.commit()
    return {"message": "Reply posted"}
