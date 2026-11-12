"""Shared helpers used by several routers."""
import json
from datetime import datetime, timedelta
from fastapi import HTTPException
from sqlalchemy import or_, and_
from sqlalchemy.orm import Session
from .config import PLANS
from .models import (User, PartnerProfile, Membership, Booking, Notification, Block,
                     AuditLog, utcnow)
from .security import age_from


def notify(db: Session, user_id: int, kind: str, text: str, link: str = ""):
    db.add(Notification(user_id=user_id, kind=kind, text=text[:300], link=link))


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


def booking_json(b: Booking, db: Session) -> dict:
    c, p = db.get(User, b.customer_id), db.get(User, b.partner_id)
    return {"id": b.id, "customer_id": b.customer_id, "customer_name": c.name if c else "",
            "partner_id": b.partner_id, "partner_name": p.name if p else "",
            "activity": b.activity, "scheduled_at": b.scheduled_at.isoformat() + "Z",
            "duration_minutes": b.duration_minutes, "location": b.location, "price": b.price,
            "note": b.note, "status": b.status, "status_reason": b.status_reason,
            "created_at": b.created_at.isoformat() + "Z"}


def expire_stale(db: Session):
    """Requests whose start time has passed without a response are closed."""
    n = (db.query(Booking).filter(Booking.status == "requested", Booking.scheduled_at < utcnow())
         .update({"status": "expired", "status_reason": "No response before the start time"}))
    if n:
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
