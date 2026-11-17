from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, and_, func
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import (User, PartnerProfile, Favorite, Message, Notification, Block, Report, Booking, utcnow)
from ..moderation import check_text
from ..schemas import MessageIn, ReportIn, SosIn
from ..security import current_user, rate_limit
from ..services import partner_json, can_chat, chat_state, is_blocked, notify, audit, blocked_ids, cancel_booking, first_photo, pair_booking, INQUIRY_CAP

router = APIRouter(prefix="/api", tags=["social"])
REPORT_CATEGORIES = {"harassment", "sexual_solicitation", "scam_or_payment", "fake_profile",
                     "no_show", "unsafe", "underage", "other"}
AUTO_HOLD_THRESHOLD = 3


# ---------- favourites ----------
@router.get("/favorites")
def get_favorites(u: User = Depends(current_user), db: Session = Depends(get_db)):
    hidden = blocked_ids(db, u.id)
    out = []
    for f in db.query(Favorite).filter_by(user_id=u.id).all():
        p = db.query(PartnerProfile).filter_by(user_id=f.partner_id, status="approved").first()
        if p and p.user.active and p.user_id not in hidden:
            out.append(partner_json(p))
    return out


@router.get("/favorites/ids")
def favorite_ids(u: User = Depends(current_user), db: Session = Depends(get_db)):
    return [f.partner_id for f in db.query(Favorite).filter_by(user_id=u.id).all()]


@router.put("/favorites/{partner_id}")
def add_favorite(partner_id: int, u: User = Depends(current_user), db: Session = Depends(get_db)):
    if not db.query(PartnerProfile).filter_by(user_id=partner_id, status="approved").first():
        raise HTTPException(404, "Partner not found")
    if not db.query(Favorite).filter_by(user_id=u.id, partner_id=partner_id).first():
        db.add(Favorite(user_id=u.id, partner_id=partner_id))
        db.commit()
    return {"favorited": True}


@router.delete("/favorites/{partner_id}")
def remove_favorite(partner_id: int, u: User = Depends(current_user), db: Session = Depends(get_db)):
    f = db.query(Favorite).filter_by(user_id=u.id, partner_id=partner_id).first()
    if f:
        db.delete(f)
        db.commit()
    return {"favorited": False}


# ---------- messaging ----------
def _msg(m: Message) -> dict:
    return {"id": m.id, "sender_id": m.sender_id, "receiver_id": m.receiver_id, "body": m.body,
            "read": m.read_at is not None, "created_at": m.created_at.isoformat() + "Z"}


@router.get("/conversations")
def conversations(u: User = Depends(current_user), db: Session = Depends(get_db)):
    pairs = db.query(Booking).filter(or_(Booking.customer_id == u.id, Booking.partner_id == u.id),
                                     Booking.status.in_(("accepted", "completed"))).all()
    others = {(b.partner_id if b.customer_id == u.id else b.customer_id) for b in pairs}
    for m in db.query(Message).filter(or_(Message.sender_id == u.id, Message.receiver_id == u.id)).all():  # inquiries too
        others.add(m.receiver_id if m.sender_id == u.id else m.sender_id)
    out = []
    for oid in others:
        if not chat_state(db, u, oid)["can_read"]:
            continue
        other = db.get(User, oid)
        last = (db.query(Message).filter(or_(and_(Message.sender_id == u.id, Message.receiver_id == oid),
                                             and_(Message.sender_id == oid, Message.receiver_id == u.id)))
                .order_by(Message.id.desc()).first())
        if not last and not pair_booking(db, u.id, oid):
            continue
        unread = db.query(Message).filter_by(sender_id=oid, receiver_id=u.id, read_at=None).count()
        out.append({"user_id": oid, "name": other.name, "photo_url": first_photo(db, oid), "booking": pair_booking(db, u.id, oid),
                    "last_message": last.body if last else "",
                    "last_at": last.created_at.isoformat() + "Z" if last else "", "unread": unread})
    out.sort(key=lambda c: c["last_at"], reverse=True)
    return out


def _state_json(st: dict) -> dict:
    return {"can_send": st["can_send"], "reason": st["reason"], "needs_membership": st["needs_membership"], "remaining": st["remaining"]}


@router.get("/messages/{other_id}")
def get_messages(other_id: int, after: int = 0, u: User = Depends(current_user), db: Session = Depends(get_db)):
    st = chat_state(db, u, other_id)
    if not st["can_read"]:
        raise HTTPException(403, st["reason"])
    now = utcnow()
    db.query(Message).filter_by(sender_id=other_id, receiver_id=u.id, read_at=None).update({"read_at": now})
    db.commit()
    rows = (db.query(Message).filter(Message.id > after, or_(
        and_(Message.sender_id == u.id, Message.receiver_id == other_id),
        and_(Message.sender_id == other_id, Message.receiver_id == u.id)))
        .order_by(Message.id.asc()).limit(300).all())
    other = db.get(User, other_id)
    return {"other": {"id": other.id, "name": other.name, "photo_url": first_photo(db, other_id), "booking": pair_booking(db, u.id, other_id)},
            "state": _state_json(st), "messages": [_msg(m) for m in rows]}


@router.post("/messages", dependencies=[Depends(rate_limit("message", 60, 60))])
def send_message(x: MessageIn, u: User = Depends(current_user), db: Session = Depends(get_db)):
    st = chat_state(db, u, x.receiver_id)
    if not st["can_send"]:
        raise HTTPException(402 if st["needs_membership"] else 403, st["reason"])
    # Before a booking is accepted, keep contact details / links off-platform-proof; after it, coordination is allowed.
    problem = check_text(x.body, "message" if st["booking_chat"] else "profile")
    if problem:
        raise HTTPException(400, problem)
    first = db.query(Message.id).filter(or_(and_(Message.sender_id == u.id, Message.receiver_id == x.receiver_id),
                                            and_(Message.sender_id == x.receiver_id, Message.receiver_id == u.id))).first() is None
    m = Message(sender_id=u.id, receiver_id=x.receiver_id, body=x.body)
    db.add(m)
    if first:
        notify(db, x.receiver_id, "message", f"{u.name.split()[0]} sent you a message", f"#/messages/{u.id}")
    db.commit()
    out = _msg(m)
    out["remaining"] = None if st["booking_chat"] or st["remaining"] is None else max(0, st["remaining"] - 1)
    return out


# ---------- notifications ----------
@router.get("/notifications")
def notifications(u: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.query(Notification).filter_by(user_id=u.id).order_by(Notification.id.desc()).limit(40).all()
    unread_msgs = db.query(Message).filter_by(receiver_id=u.id, read_at=None).count()
    return {"items": [{"id": n.id, "kind": n.kind, "text": n.text, "link": n.link, "read": n.read,
                       "created_at": n.created_at.isoformat() + "Z"} for n in rows],
            "unread": sum(1 for n in rows if not n.read), "unread_messages": unread_msgs}


@router.post("/notifications/read")
def mark_read(u: User = Depends(current_user), db: Session = Depends(get_db)):
    db.query(Notification).filter_by(user_id=u.id, read=False).update({"read": True})
    db.commit()
    return {"ok": True}


# ---------- blocking & reporting ----------
@router.get("/blocks")
def list_blocks(u: User = Depends(current_user), db: Session = Depends(get_db)):
    return [{"user_id": b.blocked_id, "name": db.get(User, b.blocked_id).name}
            for b in db.query(Block).filter_by(user_id=u.id).all()]


@router.put("/blocks/{target_id}")
def block(target_id: int, u: User = Depends(current_user), db: Session = Depends(get_db)):
    t = db.get(User, target_id)
    if not t or t.id == u.id or t.role == "admin":
        raise HTTPException(400, "You can't block this user")
    if not db.query(Block).filter_by(user_id=u.id, blocked_id=target_id).first():
        db.add(Block(user_id=u.id, blocked_id=target_id))
    pair = or_(and_(Booking.customer_id == u.id, Booking.partner_id == target_id),
               and_(Booking.customer_id == target_id, Booking.partner_id == u.id))
    for b in db.query(Booking).filter(pair, Booking.status.in_(("requested", "accepted"))).all():
        cancel_booking(db, b, "Cancelled because a user was blocked", 100)
    db.query(Favorite).filter(or_(and_(Favorite.user_id == u.id, Favorite.partner_id == target_id),
                                  and_(Favorite.user_id == target_id, Favorite.partner_id == u.id))).delete()
    db.commit()
    return {"blocked": True}


@router.delete("/blocks/{target_id}")
def unblock(target_id: int, u: User = Depends(current_user), db: Session = Depends(get_db)):
    db.query(Block).filter_by(user_id=u.id, blocked_id=target_id).delete()
    db.commit()
    return {"blocked": False}


def _notify_admins(db: Session, text: str):
    for a in db.query(User).filter_by(role="admin", active=True).all():
        notify(db, a.id, "report", text, "#/admin")


@router.post("/reports", dependencies=[Depends(rate_limit("report", 20, 3600))])
def create_report(x: ReportIn, u: User = Depends(current_user), db: Session = Depends(get_db)):
    if x.category not in REPORT_CATEGORIES:
        raise HTTPException(400, "Choose a valid report category")
    target = db.get(User, x.target_id)
    if not target or target.id == u.id:
        raise HTTPException(400, "Invalid report target")
    if x.booking_id:
        b = db.get(Booking, x.booking_id)
        if not b or u.id not in (b.customer_id, b.partner_id):
            raise HTTPException(400, "Invalid booking reference")
    db.add(Report(reporter_id=u.id, target_id=target.id, booking_id=x.booking_id, category=x.category,
                  details=x.details.strip(), severity="critical" if x.category in ("unsafe", "underage") else "normal"))
    db.flush()
    # Auto-hold: several independent open reports pull a live profile back into review.
    distinct = (db.query(func.count(func.distinct(Report.reporter_id)))
                .filter(Report.target_id == target.id, Report.status == "open").scalar())
    p = db.query(PartnerProfile).filter_by(user_id=target.id).first()
    if p and p.status == "approved" and distinct >= AUTO_HOLD_THRESHOLD:
        p.status = "pending"
        audit(db, None, "auto_hold", f"user:{target.id}", f"{distinct} open reports")
    _notify_admins(db, f"New {x.category.replace('_', ' ')} report against {target.name}")
    db.commit()
    return {"message": "Thanks - our safety team will review this report."}


@router.post("/safety/sos", dependencies=[Depends(rate_limit("sos", 10, 3600))])
def sos(x: SosIn, u: User = Depends(current_user), db: Session = Depends(get_db)):
    """Records a critical safety alert for the admin team. It is NOT a substitute for calling 112."""
    target_id, booking = None, None
    if x.booking_id:
        booking = db.get(Booking, x.booking_id)
        if not booking or u.id not in (booking.customer_id, booking.partner_id):
            raise HTTPException(400, "Invalid booking reference")
        target_id = booking.partner_id if u.id == booking.customer_id else booking.customer_id
    db.add(Report(reporter_id=u.id, target_id=target_id, booking_id=x.booking_id, category="sos",
                  details=x.note.strip(), severity="critical"))
    _notify_admins(db, f"SOS alert from {u.name}" + (f" (booking #{x.booking_id})" if x.booking_id else ""))
    audit(db, u.id, "sos", f"booking:{x.booking_id}")
    db.commit()
    return {"message": "Alert sent to the Gimble safety team. If you are in danger, call 112 now."}
