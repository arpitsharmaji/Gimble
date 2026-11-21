"""The 'hire' side of an account (photos + bio, no rates) and switching between Hire and Get hired."""
import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import User, PartnerProfile, CustomerProfile, utcnow
from ..moderation import check_text
from ..schemas import CustomerProfileIn, SwitchModeIn
from ..security import current_user, rate_limit
from ..services import user_json, audit, customer_complete, CUSTOMER_BIO_MIN
from ..storage import canonical_photo, media_url

router = APIRouter(prefix="/api", tags=["profiles"])


def own_customer_profile(db: Session, u: User) -> CustomerProfile:
    c = db.query(CustomerProfile).filter_by(user_id=u.id).first()
    if not c:
        c = CustomerProfile(user_id=u.id)
        db.add(c)
        db.flush()
    return c


def customer_json(c: CustomerProfile) -> dict:
    return {"bio": c.bio, "photos": [media_url(x) for x in json.loads(c.photos_json or "[]")], "discoverable": c.discoverable,
            "status": c.status, "reject_reason": c.reject_reason, "complete": customer_complete(c), "bio_min": CUSTOMER_BIO_MIN}


@router.get("/me/customer-profile")
def get_customer_profile(u: User = Depends(current_user), db: Session = Depends(get_db)):
    if u.role == "admin":
        raise HTTPException(400, "Admin accounts have no customer profile")
    c = own_customer_profile(db, u)
    db.commit()
    return customer_json(c)


@router.put("/me/customer-profile", dependencies=[Depends(rate_limit("custprofile", 60, 3600))])
def save_customer_profile(x: CustomerProfileIn, u: User = Depends(current_user), db: Session = Depends(get_db)):
    if u.role == "admin":
        raise HTTPException(400, "Admin accounts have no customer profile")
    bio = x.bio.strip()
    problem = check_text(bio, "profile")
    if problem:
        raise HTTPException(400, problem)
    photos = []
    for url in x.photos:
        canon = canonical_photo(url, u.id)
        if not canon:
            raise HTTPException(400, "Photos must be uploaded through Gimble")
        if canon not in photos:
            photos.append(canon)
    c = own_customer_profile(db, u)
    changed = (c.bio, c.photos_json) != (bio, json.dumps(photos))
    c.bio, c.photos_json, c.discoverable = bio, json.dumps(photos), x.discoverable
    ready = len(bio) >= CUSTOMER_BIO_MIN and bool(photos)
    if not ready:
        c.status = "draft"
        message = f"Add at least one photo and a bio of {CUSTOMER_BIO_MIN}+ characters to finish your profile."
    elif c.status in ("draft", "rejected") or (c.status == "approved" and changed):
        c.status, c.reject_reason, c.submitted_at = "pending", "", utcnow()
        message = "Profile saved. Our team reviews it before partners can see it. You can hire companions right away."
        audit(db, u.id, "customer_profile_submitted", f"user:{u.id}")
    else:
        message = "Profile saved."
    db.commit()
    return {"message": message, **customer_json(c)}


@router.post("/auth/switch-mode", dependencies=[Depends(rate_limit("switchmode", 40, 3600))])
def switch_mode(x: SwitchModeIn, u: User = Depends(current_user), db: Session = Depends(get_db)):
    """hire = find a companion (customer side), hired = become a partner. One account, two sides."""
    if u.role == "admin":
        raise HTTPException(400, "Admin accounts can't switch modes")
    if x.mode not in ("hire", "hired"):
        raise HTTPException(400, "Mode must be 'hire' or 'hired'")
    if x.mode == "hired":
        u.role = "partner"
        if not db.query(PartnerProfile).filter_by(user_id=u.id).first():
            db.add(PartnerProfile(user_id=u.id))
    else:
        u.role = "customer"
        own_customer_profile(db, u)
    db.commit()
    db.refresh(u)
    return {"user": user_json(u)}
