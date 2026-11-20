"""Manual UPI QR payments, for when no payment gateway is available.

Flow: customer scans the static UPI QR, types the amount themselves, pays, then submits the UTR + a screenshot.
The submission lands in Admin -> Payments tagged "Membership" or "Companion booking". An admin compares it with the
bank/UPI app and approves (membership activates / booking is confirmed) or rejects with a reason.

The amount is ALWAYS set by the server (plan price / booking price); the customer never chooses what they "owe".
"""
import hashlib, io, re, secrets
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import Response
from pydantic import BaseModel, Field
from PIL import Image, ImageOps
from sqlalchemy.orm import Session
from ..config import settings, PLANS
from ..db import get_db
from ..models import User, Booking, ManualPayment, utcnow
from ..security import current_user, admin_user, rate_limit
from ..services import grant_membership, mark_booking_paid, notify, audit
from ..storage import get_storage
from .payments import _payable

router = APIRouter(prefix="/api", tags=["manual-payments"])
Image.MAX_IMAGE_PIXELS = 40_000_000
UTR_RE = re.compile(r"^[A-Z0-9]{8,35}$")   # bank UTRs are 12 digits; PhonePe/Paytm ids are longer alphanumerics
TAG = {"membership": "Membership", "booking": "Companion booking"}


class DecisionIn(BaseModel):
    approved: bool
    reason: str = Field(default="", max_length=300)


class RefundDoneIn(BaseModel):
    reference: str = Field(default="", max_length=80)


def _require_on():
    if not settings.manual_upi_enabled:
        raise HTTPException(503, "UPI payments are not switched on yet")


async def _store_proof(file: UploadFile) -> tuple[str, str]:
    data = await file.read(settings.MAX_UPLOAD_BYTES + 1)
    if len(data) > settings.MAX_UPLOAD_BYTES:
        raise HTTPException(413, "The screenshot must be under 5 MB")
    try:
        Image.open(io.BytesIO(data)).verify()
        img = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
    except Exception:
        raise HTTPException(400, "Upload a clear JPG, PNG or WebP screenshot of the payment")
    img.thumbnail((2000, 2000))
    buf = io.BytesIO(); img.save(buf, "JPEG", quality=85)
    jpg = buf.getvalue()
    return jpg, hashlib.sha256(jpg).hexdigest()


# ---------------- customer ----------------
@router.get("/payments/manual/info")
def info(u: User = Depends(current_user)):
    _require_on()
    return {"upi_id": settings.UPI_ID, "payee_name": settings.UPI_PAYEE_NAME, "qr_url": settings.UPI_QR_URL}


@router.get("/payments/manual/mine")
def mine(u: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.query(ManualPayment).filter_by(user_id=u.id).order_by(ManualPayment.id.desc()).limit(30).all()
    return [{"id": m.id, "kind": m.kind, "plan": m.plan, "booking_id": m.booking_id, "amount": m.amount, "utr": m.utr,
             "status": m.status, "reason": m.reason, "created_at": m.created_at.isoformat() + "Z"} for m in rows]


@router.post("/payments/manual", dependencies=[Depends(rate_limit("manualpay", 10, 3600))])
async def submit(kind: str = Form(...), utr: str = Form(...), plan: str = Form(""), booking_id: int | None = Form(None),
                 proof: UploadFile = File(...), u: User = Depends(current_user), db: Session = Depends(get_db)):
    _require_on()
    utr = re.sub(r"\s+", "", utr).upper()
    if not UTR_RE.match(utr):
        raise HTTPException(400, "Enter the UTR / transaction ID exactly as shown in your UPI app (8-35 letters and digits)")
    if kind == "membership":
        if u.role != "customer":
            raise HTTPException(403, "Memberships are for customer accounts")
        if plan not in PLANS:
            raise HTTPException(400, "Choose a plan")
        amount, bid = PLANS[plan]["amount"], None
    elif kind == "booking":
        b = _payable(db, booking_id or 0, u)      # same rules as card payments: yours, accepted, unpaid, before the deadline
        amount, bid, plan = b.price, b.id, "booking"
    else:
        raise HTTPException(400, "Invalid payment type")
    if db.query(ManualPayment).filter_by(user_id=u.id, kind=kind, booking_id=bid, status="pending").first():
        raise HTTPException(409, "Your payment proof is already under review. We'll notify you as soon as it's checked.")
    if db.query(ManualPayment).filter(ManualPayment.utr == utr, ManualPayment.status.in_(("pending", "approved"))).first():
        raise HTTPException(409, "This transaction ID has already been submitted")
    jpg, digest = await _store_proof(proof)
    if db.query(ManualPayment).filter(ManualPayment.proof_hash == digest, ManualPayment.status.in_(("pending", "approved"))).first():
        raise HTTPException(409, "This screenshot has already been submitted. Upload the screenshot of this payment.")
    name = f"pay_{secrets.token_hex(12)}.jpg"
    try:
        get_storage().put_private(name, jpg)
    except Exception:
        raise HTTPException(503, "Storage is unavailable right now. Please try again shortly.")
    m = ManualPayment(user_id=u.id, kind=kind, plan=plan if kind == "membership" else "", booking_id=bid, amount=amount,
                      utr=utr, proof_file=name, proof_hash=digest)
    db.add(m); db.flush()
    for a in db.query(User).filter_by(role="admin", active=True).all():
        notify(db, a.id, "report", f"Payment to verify: ₹{amount} ({TAG[kind]}) from {u.name}", "#/admin")
    audit(db, u.id, "manual_payment_submitted", f"payment:{m.id}", f"{kind} ₹{amount} utr={utr}")
    db.commit()
    return {"message": "Payment proof received. We'll verify it and confirm shortly - usually within a few hours.", "id": m.id}


# ---------------- admin ----------------
def _row(m: ManualPayment, db: Session) -> dict:
    u = db.get(User, m.user_id)
    d = {"id": m.id, "kind": m.kind, "tag": TAG[m.kind], "amount": m.amount, "utr": m.utr, "status": m.status, "reason": m.reason,
         "name": u.name if u else "", "email": u.email if u else "", "plan": m.plan,
         "plan_label": PLANS[m.plan]["label"] if m.plan in PLANS else "",
         "has_proof": bool(m.proof_file), "created_at": m.created_at.isoformat() + "Z",
         "decided_at": m.decided_at.isoformat() + "Z" if m.decided_at else None}
    if m.kind == "booking":
        b = db.get(Booking, m.booking_id)
        p = db.get(User, b.partner_id) if b else None
        d.update({"booking_id": m.booking_id, "partner_name": p.name if p else "", "activity": b.activity if b else "",
                  "scheduled_at": b.scheduled_at.isoformat() + "Z" if b else None, "booking_status": b.status if b else "missing"})
    return d


@router.get("/admin/manual-payments")
def admin_list(a: User = Depends(admin_user), db: Session = Depends(get_db)):
    pending = db.query(ManualPayment).filter_by(status="pending").order_by(ManualPayment.id).all()
    recent = (db.query(ManualPayment).filter(ManualPayment.status != "pending")
              .order_by(ManualPayment.decided_at.desc()).limit(25).all())
    return {"pending": [_row(m, db) for m in pending], "recent": [_row(m, db) for m in recent]}


@router.get("/admin/manual-payments/{pid}/proof")
def admin_proof(pid: int, a: User = Depends(admin_user), db: Session = Depends(get_db)):
    m = db.get(ManualPayment, pid)
    data = get_storage().get_private(m.proof_file) if m and m.proof_file else None
    if not data:
        raise HTTPException(404, "Screenshot not available")
    return Response(data, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@router.patch("/admin/manual-payments/{pid}")
def admin_decide(pid: int, x: DecisionIn, a: User = Depends(admin_user), db: Session = Depends(get_db)):
    m = db.get(ManualPayment, pid)
    if not m or m.status != "pending":
        raise HTTPException(404, "Payment not found or already decided")
    reason = x.reason.strip()
    if not x.approved and not reason:
        raise HTTPException(400, "Give a reason so the customer knows what to fix")
    if x.approved:
        if m.kind == "membership":
            grant_membership(db, m.user_id, m.plan, f"upi:{m.utr}")
            notify(db, m.user_id, "membership", "Payment verified - your Gimble membership is active. You can now send booking requests.", "#/browse")
        else:
            b = db.get(Booking, m.booking_id)
            if not b or b.status != "accepted" or b.payment_status != "unpaid":
                raise HTTPException(409, f"This booking is {b.status if b else 'missing'} and can't be confirmed any more. "
                                         "Reject this payment (with a reason) and refund the customer by UPI.")
            mark_booking_paid(db, b, f"UPI:{m.utr}")
    else:
        notify(db, m.user_id, "payment", f"We couldn't verify your payment of ₹{m.amount}: {reason}", "#/bookings" if m.kind == "booking" else "#/browse")
    m.status, m.reason, m.decided_by, m.decided_at = ("approved" if x.approved else "rejected"), reason, a.id, utcnow()
    audit(db, a.id, "manual_payment_approved" if x.approved else "manual_payment_rejected", f"payment:{m.id}", f"{m.kind} ₹{m.amount} utr={m.utr} {reason}")
    db.commit()
    return {"status": m.status}


@router.post("/admin/bookings/{booking_id}/mark-refunded")
def mark_refunded(booking_id: int, x: RefundDoneIn, a: User = Depends(admin_user), db: Session = Depends(get_db)):
    """After staff sent a refund for a manual-UPI booking, record it (the customer is told)."""
    b = db.get(Booking, booking_id)
    if not b or b.payment_status != "refund_pending" or not b.payment_id.startswith("UPI:"):
        raise HTTPException(400, "This booking has no manual UPI refund pending")
    ref = x.reference.strip()
    if not ref:
        raise HTTPException(400, "Enter the UTR of the refund you sent")
    b.payment_status = "refunded" if b.refund_amount >= b.paid_amount else "partially_refunded"
    notify(db, b.customer_id, "payment", f"Your refund of ₹{b.refund_amount} has been sent by UPI (ref {ref}). It should reach you shortly.", "#/bookings")
    audit(db, a.id, "manual_refund_sent", f"booking:{b.id}", f"₹{b.refund_amount} ref={ref}")
    db.commit()
    return {"payment_status": b.payment_status}
