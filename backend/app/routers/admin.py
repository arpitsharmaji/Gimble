from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, or_
from sqlalchemy.orm import Session
from ..db import get_db
from ..config import settings
from ..models import (User, PartnerProfile, Booking, Membership, Report, AuditLog, Review, PayoutRequest,
                      KycSubmission, SupportTicket, LedgerEntry, utcnow)
from ..schemas import (AdminPartnerDecisionIn, AdminVerifyIn, AdminSuspendIn, AdminResolveIn, AdminPayoutIn, AdminAdjustIn)
from ..security import admin_user
from ..services import (partner_json, booking_json, notify, audit, cancel_booking, credit, _do_refund)

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/overview")
def overview(a: User = Depends(admin_user), db: Session = Depends(get_db)):
    q = db.query
    return {
        "users": q(User).count(),
        "customers": q(User).filter_by(role="customer").count(),
        "partners": q(PartnerProfile).count(),
        "pending_partners": q(PartnerProfile).filter_by(status="pending").count(),
        "live_partners": q(PartnerProfile).filter_by(status="approved").count(),
        "bookings": q(Booking).count(),
        "completed_bookings": q(Booking).filter_by(status="completed").count(),
        "gross_completed_inr": q(func.coalesce(func.sum(Booking.price), 0)).filter(Booking.status == "completed").scalar(),
        "active_memberships": q(Membership).filter(Membership.status == "active", Membership.expires_at > utcnow()).count(),
        "paid_in_inr": q(func.coalesce(func.sum(Booking.paid_amount - Booking.refund_amount), 0)).filter(Booking.payment_status.in_(("paid", "partially_refunded"))).scalar(),
        "platform_fees_inr": q(func.coalesce(func.sum(Booking.platform_fee), 0)).filter(Booking.status == "completed", Booking.payment_status == "paid").scalar(),
        "pending_payouts": q(PayoutRequest).filter_by(status="requested").count(),
        "pending_payout_inr": q(func.coalesce(func.sum(PayoutRequest.amount), 0)).filter(PayoutRequest.status == "requested").scalar(),
        "pending_kyc": q(KycSubmission).filter_by(status="pending").count(),
        "open_tickets": q(SupportTicket).filter_by(status="open").count(),
        "refund_pending": q(Booking).filter_by(payment_status="refund_pending").count(),
        "open_reports": q(Report).filter_by(status="open").count(),
        "critical_reports": q(Report).filter_by(status="open", severity="critical").count(),
    }


@router.get("/partners")
def partners(status: str = "pending", a: User = Depends(admin_user), db: Session = Depends(get_db)):
    qs = db.query(PartnerProfile)
    if status != "all":
        qs = qs.filter_by(status=status)
    return [{**partner_json(p, own=True), "email": p.user.email, "active": p.user.active,
             "submitted_at": p.submitted_at.isoformat() + "Z" if p.submitted_at else None}
            for p in qs.order_by(PartnerProfile.submitted_at.asc()).limit(200).all()]


@router.patch("/partners/{partner_id}")
def review_partner(partner_id: int, x: AdminPartnerDecisionIn, a: User = Depends(admin_user), db: Session = Depends(get_db)):
    p = db.query(PartnerProfile).filter_by(user_id=partner_id).first()
    if not p:
        raise HTTPException(404, "Partner profile not found")
    if not x.approved and not x.reason.strip():
        raise HTTPException(400, "Give a reason so the partner can fix their profile")
    p.status = "approved" if x.approved else "rejected"
    p.reject_reason = "" if x.approved else x.reason.strip()
    notify(db, partner_id, "profile",
           "Your profile is approved and now live." if x.approved else f"Your profile needs changes: {x.reason.strip()}", "#/dashboard")
    audit(db, a.id, "partner_approved" if x.approved else "partner_rejected", f"user:{partner_id}", x.reason)
    db.commit()
    return {"status": p.status}


@router.patch("/partners/{partner_id}/verified")
def set_verified(partner_id: int, x: AdminVerifyIn, a: User = Depends(admin_user), db: Session = Depends(get_db)):
    """'Verified' means identity (ID) checked off-platform by staff - separate from content approval."""
    p = db.query(PartnerProfile).filter_by(user_id=partner_id).first()
    if not p:
        raise HTTPException(404, "Partner profile not found")
    p.verified = x.verified
    audit(db, a.id, "kyc_verified" if x.verified else "kyc_removed", f"user:{partner_id}")
    db.commit()
    return {"verified": p.verified}


@router.get("/users")
def users(q: str = "", a: User = Depends(admin_user), db: Session = Depends(get_db)):
    qs = db.query(User)
    if q:
        like = f"%{q.lower()}%"
        qs = qs.filter(or_(func.lower(User.name).like(like), func.lower(User.email).like(like)))
    return [{"id": u.id, "name": u.name, "email": u.email, "role": u.role, "city": u.city, "active": u.active,
             "suspended_reason": u.suspended_reason, "email_verified": u.email_verified,
             "created_at": u.created_at.isoformat() + "Z"} for u in qs.order_by(User.id.desc()).limit(100).all()]


@router.patch("/users/{user_id}/suspend")
def suspend(user_id: int, x: AdminSuspendIn, a: User = Depends(admin_user), db: Session = Depends(get_db)):
    u = db.get(User, user_id)
    if not u or u.role == "admin":
        raise HTTPException(400, "This user can't be suspended")
    if x.suspended and not x.reason.strip():
        raise HTTPException(400, "A reason is required")
    u.active = not x.suspended
    u.suspended_reason = x.reason.strip() if x.suspended else ""
    if x.suspended:
        for b in db.query(Booking).filter(or_(Booking.customer_id == u.id, Booking.partner_id == u.id),
                                          Booking.status.in_(("requested", "accepted"))).all():
            cancel_booking(db, b, "Cancelled by PairUp safety team", 100)
    audit(db, a.id, "user_suspended" if x.suspended else "user_reinstated", f"user:{user_id}", x.reason)
    db.commit()
    return {"active": u.active}


@router.get("/reports")
def reports(status: str = "open", a: User = Depends(admin_user), db: Session = Depends(get_db)):
    qs = db.query(Report)
    if status != "all":
        qs = qs.filter_by(status=status)
    rows = qs.order_by(Report.severity.desc(), Report.id.desc()).limit(200).all()  # 'normal' > 'critical' alphabetically
    rows.sort(key=lambda r: (r.severity != "critical", -r.id))
    out = []
    for r in rows:
        rep, tgt = db.get(User, r.reporter_id), db.get(User, r.target_id) if r.target_id else None
        out.append({"id": r.id, "category": r.category, "severity": r.severity, "details": r.details, "status": r.status,
                    "resolution": r.resolution, "booking_id": r.booking_id,
                    "reporter": {"id": rep.id, "name": rep.name} if rep else None,
                    "target": {"id": tgt.id, "name": tgt.name, "active": tgt.active} if tgt else None,
                    "created_at": r.created_at.isoformat() + "Z"})
    return out


@router.patch("/reports/{report_id}")
def resolve_report(report_id: int, x: AdminResolveIn, a: User = Depends(admin_user), db: Session = Depends(get_db)):
    r = db.get(Report, report_id)
    if not r:
        raise HTTPException(404, "Report not found")
    r.status, r.resolution, r.resolved_by = "resolved", x.resolution.strip(), a.id
    if x.suspend_target and r.target_id:
        t = db.get(User, r.target_id)
        if t and t.role != "admin":
            t.active, t.suspended_reason = False, f"Suspended after report #{r.id}"
            for b in db.query(Booking).filter(or_(Booking.customer_id == t.id, Booking.partner_id == t.id),
                                              Booking.status.in_(("requested", "accepted"))).all():
                cancel_booking(db, b, "Cancelled by PairUp safety team", 100)
            audit(db, a.id, "user_suspended", f"user:{t.id}", f"report #{r.id}")
    notify(db, r.reporter_id, "report", "We've reviewed your report and taken action where needed. Thank you for helping keep PairUp safe.", "")
    audit(db, a.id, "report_resolved", f"report:{r.id}", x.resolution)
    db.commit()
    return {"status": r.status}


@router.get("/bookings")
def bookings(a: User = Depends(admin_user), db: Session = Depends(get_db)):
    return [booking_json(b, db) for b in db.query(Booking).order_by(Booking.id.desc()).limit(200).all()]


@router.get("/audit")
def audit_log(a: User = Depends(admin_user), db: Session = Depends(get_db)):
    return [{"id": e.id, "actor_id": e.actor_id, "action": e.action, "target": e.target, "detail": e.detail,
             "created_at": e.created_at.isoformat() + "Z"} for e in db.query(AuditLog).order_by(AuditLog.id.desc()).limit(150).all()]


# ---------------- finance ----------------
@router.get("/payouts")
def payouts(status: str = "requested", a: User = Depends(admin_user), db: Session = Depends(get_db)):
    qs = db.query(PayoutRequest)
    if status != "all":
        qs = qs.filter_by(status=status)
    out = []
    for r in qs.order_by(PayoutRequest.id.asc()).limit(200).all():
        u = db.get(User, r.user_id)
        out.append({"id": r.id, "user_id": r.user_id, "name": u.name, "amount": r.amount, "upi": r.upi, "account_name": r.account_name,
                    "status": r.status, "reference": r.reference, "reason": r.reason, "created_at": r.created_at.isoformat() + "Z"})
    return out


@router.patch("/payouts/{payout_id}")
def decide_payout(payout_id: int, x: AdminPayoutIn, a: User = Depends(admin_user), db: Session = Depends(get_db)):
    """Money is sent manually (UPI) by staff; here they record the UTR, or reject and return the funds."""
    r = db.get(PayoutRequest, payout_id)
    if not r or r.status != "requested":
        raise HTTPException(404, "Payout not found or already processed")
    if x.paid:
        if len(x.reference.strip()) < 4:
            raise HTTPException(400, "Enter the UPI/bank transaction reference (UTR)")
        r.status, r.reference = "paid", x.reference.strip()
        notify(db, r.user_id, "payout", f"Your payout of ₹{r.amount} was sent (ref {r.reference}).", "#/earnings")
    else:
        if not x.reason.strip():
            raise HTTPException(400, "Give a reason")
        r.status, r.reason = "rejected", x.reason.strip()
        credit(db, r.user_id, r.amount, "payout_reversal", None, f"Payout #{r.id} returned", hold=False)
        notify(db, r.user_id, "payout", f"Your payout request was declined: {r.reason}. The amount is back in your wallet.", "#/earnings")
    r.processed_at = utcnow()
    audit(db, a.id, "payout_paid" if x.paid else "payout_rejected", f"payout:{r.id}", x.reference or x.reason)
    db.commit()
    return {"status": r.status}


@router.post("/bookings/{booking_id}/retry-refund")
def retry_refund(booking_id: int, a: User = Depends(admin_user), db: Session = Depends(get_db)):
    b = db.get(Booking, booking_id)
    if not b or b.payment_status != "refund_pending":
        raise HTTPException(400, "This booking has no pending refund")
    amount = b.refund_amount
    b.payment_status = "paid"
    _do_refund(db, b, amount)
    audit(db, a.id, "refund_retried", f"booking:{b.id}", b.payment_status)
    db.commit()
    return {"payment_status": b.payment_status}


@router.post("/ledger/adjust")
def adjust(x: AdminAdjustIn, a: User = Depends(admin_user), db: Session = Depends(get_db)):
    """Manual correction (e.g. a disputed completion). Negative amounts deduct."""
    if not db.get(User, x.user_id) or x.amount == 0:
        raise HTTPException(400, "Invalid adjustment")
    credit(db, x.user_id, x.amount, "adjustment", None, x.note, hold=False)
    audit(db, a.id, "ledger_adjust", f"user:{x.user_id}", f"{x.amount}: {x.note}")
    db.commit()
    return {"ok": True}
