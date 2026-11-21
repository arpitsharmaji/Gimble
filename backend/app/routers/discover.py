"""Partners swipe through customer profiles. Left = pass. Right = a free, fixed intro message is sent to the customer.

Safety design (deliberate): only APPROVED, AVAILABLE partners can swipe; only admin-approved customers who opted in are shown,
with first name, age, city, bio and photos only; the intro is a server-controlled template (no free text, so no phone numbers
or links can be sent); a daily cap limits spam; the customer can reply, block or report; the partner can't follow up until the
customer replies (see services.chat_state).
"""
import json
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import case, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from ..config import settings
from ..db import get_db
from ..models import User, PartnerProfile, CustomerProfile, Swipe, Message, utcnow
from ..schemas import SwipeIn
from ..security import current_user, rate_limit, age_from
from ..services import blocked_ids, is_blocked, notify, audit
from ..storage import media_url

router = APIRouter(prefix="/api/discover", tags=["discover"])
INTRO_TEXT = "Hi {c}! I'm {p} and I'm interested in being your partner. Hire me and let's explore!"
first = lambda name: (name or "there").split()[0]


def _approved_partner(db: Session, u: User) -> PartnerProfile:
    if u.role != "partner":
        raise HTTPException(403, "Switch to 'Get hired' mode to discover customers")
    p = db.query(PartnerProfile).filter_by(user_id=u.id).first()
    if not p or p.status != "approved":
        raise HTTPException(403, "Your partner profile must be approved before you can discover customers")
    return p


def _intros_used(db: Session, u: User) -> int:
    since = utcnow() - timedelta(hours=24)
    return db.query(Swipe).filter(Swipe.partner_id == u.id, Swipe.direction == "right", Swipe.created_at >= since).count()


def _card(c: CustomerProfile, usr: User) -> dict:
    # Deliberately minimal: no email, no surname, no gender, no exact location.
    return {"id": usr.id, "name": first(usr.name), "age": age_from(usr.dob), "city": usr.city, "bio": c.bio,
            "photos": [media_url(x) for x in json.loads(c.photos_json or "[]")]}


@router.get("/customers")
def customers(limit: int = 20, u: User = Depends(current_user), db: Session = Depends(get_db)):
    _approved_partner(db, u)
    limit = max(1, min(limit, 40))
    swiped = {r[0] for r in db.query(Swipe.customer_id).filter_by(partner_id=u.id)}
    hidden = blocked_ids(db, u.id) | swiped | {u.id}
    rows = (db.query(CustomerProfile, User).join(User, User.id == CustomerProfile.user_id)
            .filter(CustomerProfile.status == "approved", CustomerProfile.discoverable.is_(True), User.active.is_(True),
                    User.role != "admin", ~CustomerProfile.user_id.in_(hidden))
            .order_by(case((func.lower(User.city) == (u.city or "").lower(), 0), else_=1), CustomerProfile.id.desc())
            .limit(limit).all())
    return {"items": [_card(c, usr) for c, usr in rows], "intros_left": max(0, settings.INTRO_DAILY_CAP - _intros_used(db, u)),
            "intro_preview": INTRO_TEXT.format(c="<name>", p=first(u.name))}


@router.post("/swipe", dependencies=[Depends(rate_limit("swipe", 300, 3600))])
def swipe(x: SwipeIn, u: User = Depends(current_user), db: Session = Depends(get_db)):
    p = _approved_partner(db, u)
    if x.direction not in ("left", "right"):
        raise HTTPException(400, "Direction must be left or right")
    if x.customer_id == u.id:
        raise HTTPException(400, "You can't swipe on yourself")
    row = (db.query(CustomerProfile, User).join(User, User.id == CustomerProfile.user_id)
           .filter(CustomerProfile.user_id == x.customer_id, CustomerProfile.status == "approved",
                   CustomerProfile.discoverable.is_(True), User.active.is_(True), User.role != "admin").first())
    if not row or is_blocked(db, u.id, x.customer_id):
        raise HTTPException(404, "This profile is no longer available")
    cust = row[1]
    prior = db.query(Swipe).filter_by(partner_id=u.id, customer_id=x.customer_id).first()
    if prior:
        return {"direction": prior.direction, "sent": False, "already": True, "intros_left": max(0, settings.INTRO_DAILY_CAP - _intros_used(db, u))}
    sent = False
    if x.direction == "right":
        if not p.available:
            raise HTTPException(409, "Turn on availability in your dashboard to send intros")
        if _intros_used(db, u) >= settings.INTRO_DAILY_CAP:
            raise HTTPException(429, "You've reached today's intro limit. Come back tomorrow.")
        db.add(Message(sender_id=u.id, receiver_id=cust.id, body=INTRO_TEXT.format(c=first(cust.name), p=first(u.name))))
        notify(db, cust.id, "message", f"{first(u.name)} is interested in being your partner. See their message.", f"#/messages/{u.id}")
        audit(db, u.id, "intro_sent", f"user:{cust.id}")
        sent = True
    db.add(Swipe(partner_id=u.id, customer_id=x.customer_id, direction=x.direction))
    try:
        db.commit()
    except IntegrityError:   # double-tap / two tabs: the first one won
        db.rollback()
        return {"direction": x.direction, "sent": False, "already": True, "intros_left": max(0, settings.INTRO_DAILY_CAP - _intros_used(db, u))}
    return {"direction": x.direction, "sent": sent, "already": False, "intros_left": max(0, settings.INTRO_DAILY_CAP - _intros_used(db, u))}


@router.delete("/swipes/{customer_id}")
def undo_pass(customer_id: int, u: User = Depends(current_user), db: Session = Depends(get_db)):
    """Undo is only for passes: an intro message that was already sent can't be taken back."""
    _approved_partner(db, u)
    s = db.query(Swipe).filter_by(partner_id=u.id, customer_id=customer_id).first()
    if not s or s.direction != "left":
        raise HTTPException(400, "Only a pass can be undone")
    db.delete(s)
    db.commit()
    return {"undone": True}
