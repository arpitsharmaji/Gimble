import re
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..config import settings
from ..db import get_db
from ..models import User, PartnerProfile, LedgerEntry, PayoutRequest, utcnow
from ..schemas import PayoutDetailsIn, PayoutIn
from ..security import current_user, rate_limit
from ..services import wallet_totals, credit, notify, audit
from ..moderation import check_text

router = APIRouter(prefix="/api/wallet", tags=["wallet"])
_UPI = re.compile(r"^[a-zA-Z0-9.\-_]{2,}@[a-zA-Z]{2,}$")


def _partner(u: User, db: Session) -> PartnerProfile:
    p = db.query(PartnerProfile).filter_by(user_id=u.id).first() if u.role == "partner" else None
    if not p:
        raise HTTPException(403, "Partner account required")
    return p


@router.get("")
def wallet(u: User = Depends(current_user), db: Session = Depends(get_db)):
    p = _partner(u, db)
    ledger = db.query(LedgerEntry).filter_by(user_id=u.id).order_by(LedgerEntry.id.desc()).limit(60).all()
    payouts = db.query(PayoutRequest).filter_by(user_id=u.id).order_by(PayoutRequest.id.desc()).limit(30).all()
    return {**wallet_totals(db, u.id), "fee_percent": settings.PLATFORM_FEE_PERCENT, "min_payout": settings.MIN_PAYOUT_INR,
            "hold_hours": settings.PAYOUT_HOLD_HOURS, "verified": p.verified,
            "payout_details": {"upi": p.payout_upi, "name": p.payout_name},
            "ledger": [{"id": e.id, "kind": e.kind, "amount": e.amount, "note": e.note, "booking_id": e.booking_id,
                        "available_at": e.available_at.isoformat() + "Z", "created_at": e.created_at.isoformat() + "Z"} for e in ledger],
            "payouts": [{"id": r.id, "amount": r.amount, "upi": r.upi, "status": r.status, "reference": r.reference,
                         "reason": r.reason, "created_at": r.created_at.isoformat() + "Z"} for r in payouts]}


@router.put("/payout-details")
def set_details(x: PayoutDetailsIn, u: User = Depends(current_user), db: Session = Depends(get_db)):
    p = _partner(u, db)
    upi = x.upi.strip()
    if not _UPI.match(upi):
        raise HTTPException(400, "Enter a valid UPI ID, e.g. name@okaxis")
    p.payout_upi, p.payout_name = upi, x.name.strip()
    audit(db, u.id, "payout_details_changed", f"user:{u.id}")
    db.commit()
    return {"message": "Payout details saved"}


@router.post("/payouts", dependencies=[Depends(rate_limit("payout", 10, 3600))])
def request_payout(x: PayoutIn, u: User = Depends(current_user), db: Session = Depends(get_db)):
    p = _partner(u, db)
    if not p.verified:
        raise HTTPException(403, "Complete ID verification before withdrawing earnings")
    if not p.payout_upi:
        raise HTTPException(400, "Add your UPI ID first")
    if x.amount < settings.MIN_PAYOUT_INR:
        raise HTTPException(400, f"Minimum payout is ₹{settings.MIN_PAYOUT_INR}")
    if x.amount > wallet_totals(db, u.id)["available"]:
        raise HTTPException(400, "That's more than your available balance")
    if db.query(PayoutRequest).filter_by(user_id=u.id, status="requested").count() >= 3:
        raise HTTPException(429, "You already have 3 payouts in progress")
    r = PayoutRequest(user_id=u.id, amount=x.amount, upi=p.payout_upi, account_name=p.payout_name)
    db.add(r)
    db.flush()
    credit(db, u.id, -x.amount, "payout", None, f"Payout request #{r.id}", hold=False)
    for a in db.query(User).filter_by(role="admin", active=True).all():
        notify(db, a.id, "report", f"Payout request of ₹{x.amount} from {u.name}", "#/admin")
    audit(db, u.id, "payout_requested", f"payout:{r.id}", str(x.amount))
    db.commit()
    return {"message": "Payout requested. We process payouts within 2 working days.", "id": r.id}
