import io, secrets
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from PIL import Image, ImageOps
from ..config import settings, KYC_ID_TYPES
from ..db import get_db
from ..models import User, PartnerProfile, KycSubmission, utcnow
from ..schemas import AdminKycIn
from ..security import current_user, admin_user, rate_limit
from ..services import notify, audit

router = APIRouter(prefix="/api", tags=["kyc"])
Image.MAX_IMAGE_PIXELS = 40_000_000


async def _store(file: UploadFile) -> str:
    data = await file.read(settings.MAX_UPLOAD_BYTES + 1)
    if len(data) > settings.MAX_UPLOAD_BYTES:
        raise HTTPException(413, "Each file must be under 5 MB")
    try:
        Image.open(io.BytesIO(data)).verify()
        img = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
    except Exception:
        raise HTTPException(400, "Upload clear JPG, PNG or WebP photos")
    img.thumbnail((2000, 2000))
    settings.PRIVATE_DIR.mkdir(parents=True, exist_ok=True)
    name = f"kyc_{secrets.token_hex(12)}.jpg"
    img.save(settings.PRIVATE_DIR / name, "JPEG", quality=85)
    return name


def _delete_files(sub: KycSubmission):
    for n in (sub.id_file, sub.selfie_file):
        if n:
            (settings.PRIVATE_DIR / n).unlink(missing_ok=True)
    sub.id_file = sub.selfie_file = ""


@router.get("/partner/kyc")
def my_kyc(u: User = Depends(current_user), db: Session = Depends(get_db)):
    if u.role != "partner":
        raise HTTPException(403, "Partner account required")
    p = db.query(PartnerProfile).filter_by(user_id=u.id).first()
    last = db.query(KycSubmission).filter_by(user_id=u.id).order_by(KycSubmission.id.desc()).first()
    return {"verified": bool(p and p.verified), "id_types": KYC_ID_TYPES,
            "latest": {"status": last.status, "reason": last.reason, "id_type": last.id_type,
                       "created_at": last.created_at.isoformat() + "Z"} if last else None}


@router.post("/partner/kyc", dependencies=[Depends(rate_limit("kyc", 5, 3600))])
async def submit_kyc(id_type: str = Form(...), id_file: UploadFile = File(...), selfie_file: UploadFile = File(...),
                     u: User = Depends(current_user), db: Session = Depends(get_db)):
    if u.role != "partner":
        raise HTTPException(403, "Partner account required")
    if id_type not in KYC_ID_TYPES:
        raise HTTPException(400, "Choose a valid ID type")
    if db.query(KycSubmission).filter_by(user_id=u.id, status="pending").first():
        raise HTTPException(409, "Your documents are already under review")
    sub = KycSubmission(user_id=u.id, id_type=id_type, id_file=await _store(id_file), selfie_file=await _store(selfie_file))
    db.add(sub)
    for a in db.query(User).filter_by(role="admin", active=True).all():
        notify(db, a.id, "report", f"New ID verification from {u.name}", "#/admin")
    audit(db, u.id, "kyc_submitted", f"user:{u.id}")
    db.commit()
    return {"message": "Documents received. We review them within 1-2 working days and delete the files afterwards."}


# ---------------- admin ----------------
@router.get("/admin/kyc")
def admin_list(a: User = Depends(admin_user), db: Session = Depends(get_db)):
    rows = db.query(KycSubmission).filter_by(status="pending").order_by(KycSubmission.id).all()
    out = []
    for s in rows:
        u = db.get(User, s.user_id)
        out.append({"id": s.id, "user_id": u.id, "name": u.name, "email": u.email, "id_type": s.id_type,
                    "created_at": s.created_at.isoformat() + "Z"})
    return out


@router.get("/admin/kyc/{sub_id}/file/{which}")
def admin_file(sub_id: int, which: str, a: User = Depends(admin_user), db: Session = Depends(get_db)):
    s = db.get(KycSubmission, sub_id)
    name = (s.id_file if which == "id" else s.selfie_file if which == "selfie" else "") if s else ""
    if not name or not (settings.PRIVATE_DIR / name).is_file():
        raise HTTPException(404, "File not available")
    return FileResponse(settings.PRIVATE_DIR / name, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@router.patch("/admin/kyc/{sub_id}")
def admin_decide(sub_id: int, x: AdminKycIn, a: User = Depends(admin_user), db: Session = Depends(get_db)):
    s = db.get(KycSubmission, sub_id)
    if not s or s.status != "pending":
        raise HTTPException(404, "Submission not found")
    if not x.approved and not x.reason.strip():
        raise HTTPException(400, "Give a reason so the partner can resubmit correctly")
    s.status, s.reason, s.decided_at = ("approved" if x.approved else "rejected"), x.reason.strip(), utcnow()
    _delete_files(s)  # data minimisation: keep only the outcome
    p = db.query(PartnerProfile).filter_by(user_id=s.user_id).first()
    if x.approved and p:
        p.verified = True
    notify(db, s.user_id, "kyc", "Your ID is verified - you now have the ✓ badge and can withdraw earnings." if x.approved
           else f"We couldn't verify your ID: {x.reason.strip()}", "#/verify-id")
    audit(db, a.id, "kyc_approved" if x.approved else "kyc_rejected", f"user:{s.user_id}", x.reason)
    db.commit()
    return {"status": s.status}
