import io, json, re, secrets
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy import func
from sqlalchemy.orm import Session
from PIL import Image, ImageOps
from ..config import settings, ACTIVITY_SUGGESTIONS
from ..db import get_db
from ..models import User, PartnerProfile, Review, utcnow
from ..moderation import check_text
from ..schemas import ProfileIn, AvailabilityIn
from ..security import current_user, optional_user
from ..services import partner_json, blocked_ids, audit, notify

router = APIRouter(prefix="/api", tags=["partners"])
Image.MAX_IMAGE_PIXELS = 40_000_000
MIN_RATE, MAX_RATE = 50, 50_000


def _partner_user(u: User) -> User:
    if u.role != "partner":
        raise HTTPException(403, "Partner account required")
    return u


def _own_profile(db: Session, u: User) -> PartnerProfile:
    p = db.query(PartnerProfile).filter_by(user_id=u.id).first()
    if not p:
        p = PartnerProfile(user_id=u.id)
        db.add(p)
        db.flush()
    return p


@router.get("/meta")
def meta():
    return {"activity_suggestions": ACTIVITY_SUGGESTIONS, "min_rate": MIN_RATE, "max_rate": MAX_RATE,
            "razorpay": settings.razorpay_enabled, "demo_payments": settings.DEMO_PAYMENTS_ENABLED,
            "demo_accounts": settings.SEED_DEMO}


@router.get("/cities")
def cities(db: Session = Depends(get_db)):
    rows = (db.query(User.city).join(PartnerProfile, PartnerProfile.user_id == User.id)
            .filter(PartnerProfile.status == "approved", User.active.is_(True)).distinct().all())
    return sorted({r[0] for r in rows if r[0]})


@router.get("/partners")
def list_partners(city: str | None = None, activity: str | None = None, q: str | None = None,
                  gender: str | None = None, min_price: int | None = None, max_price: int | None = None,
                  min_rating: float | None = None, available: bool | None = None,
                  sort: str = "relevance", limit: int = 24, offset: int = 0,
                  viewer: User | None = Depends(optional_user), db: Session = Depends(get_db)):
    limit = max(1, min(limit, 60))
    qs = (db.query(PartnerProfile).join(User, User.id == PartnerProfile.user_id)
          .filter(PartnerProfile.status == "approved", User.active.is_(True)))
    if city:
        qs = qs.filter(func.lower(User.city).contains(city.strip().lower(), autoescape=True))
    if gender:
        qs = qs.filter(User.gender == gender)
    if available is not None:
        qs = qs.filter(PartnerProfile.available.is_(available))
    if min_rating:
        qs = qs.filter(PartnerProfile.rating >= min_rating)
    hidden = blocked_ids(db, viewer.id) if viewer else set()
    items = []
    for p in qs.all():
        if p.user_id in hidden or (viewer and p.user_id == viewer.id):
            continue
        d = partner_json(p)
        if activity and activity.lower() not in [a.lower() for a in d["activities"]]:
            continue
        if min_price is not None and d["min_rate"] < min_price:
            continue
        if max_price is not None and d["min_rate"] > max_price:
            continue
        if q:
            hay = f'{d["name"]} {d["headline"]} {d["bio"]} {" ".join(d["activities"])}'.lower()
            if q.strip().lower() not in hay:
                continue
        items.append(d)
    home = (viewer.city.lower() if viewer and viewer.city else "")
    if sort == "rating":
        items.sort(key=lambda d: (-d["rating"], -d["review_count"]))
    elif sort == "price_low":
        items.sort(key=lambda d: d["min_rate"])
    elif sort == "price_high":
        items.sort(key=lambda d: -d["min_rate"])
    elif sort == "newest":
        items.sort(key=lambda d: -d["id"])
    else:  # relevance: viewer's city first, then available, then best rated
        items.sort(key=lambda d: (d["city"].lower() != home, not d["available"], -d["rating"], -d["review_count"]))
    return {"items": items[offset:offset + limit], "total": len(items)}


@router.get("/partners/{partner_id}")
def get_partner(partner_id: int, viewer: User | None = Depends(optional_user), db: Session = Depends(get_db)):
    p = (db.query(PartnerProfile).join(User, User.id == PartnerProfile.user_id)
         .filter(User.id == partner_id, PartnerProfile.status == "approved", User.active.is_(True)).first())
    if not p or (viewer and partner_id in blocked_ids(db, viewer.id)):
        raise HTTPException(404, "Partner not found")
    return partner_json(p)


@router.get("/partners/{partner_id}/reviews")
def partner_reviews(partner_id: int, db: Session = Depends(get_db)):
    rows = db.query(Review).filter_by(partner_id=partner_id).order_by(Review.created_at.desc()).limit(30).all()
    out = []
    for r in rows:
        c = db.get(User, r.customer_id)
        out.append({"rating": r.rating, "comment": r.comment, "created_at": r.created_at.isoformat() + "Z",
                    "reviewer": (c.name.split()[0] if c and c.active else "Member")})
    return out


# ---------------- partner's own profile ----------------
@router.get("/partner/profile")
def my_profile(u: User = Depends(current_user), db: Session = Depends(get_db)):
    p = _own_profile(db, _partner_user(u))
    db.commit()
    return partner_json(p, own=True)


def _clean_profile(x: ProfileIn, u: User) -> dict:
    headline, bio = x.headline.strip(), x.bio.strip()
    activities, seen = [], set()
    for a in x.activities:
        a = a.strip()
        if not 2 <= len(a) <= 60:
            raise HTTPException(400, "Each activity name must be 2-60 characters")
        if a.lower() not in seen:
            seen.add(a.lower())
            activities.append(a)
    rates = {}
    for k, v in x.rates.items():
        k = k.strip()
        if k not in activities:
            continue
        if not MIN_RATE <= int(v) <= MAX_RATE:
            raise HTTPException(400, f"Rate for '{k}' must be between ₹{MIN_RATE} and ₹{MAX_RATE:,}")
        rates[k] = int(v)
    languages = [l.strip() for l in x.languages if l.strip()][:10]
    for field in [headline, bio, *activities, *languages]:
        problem = check_text(field, "profile")
        if problem:
            raise HTTPException(400, problem)
    photos = []
    for url in x.photos:
        if not re.fullmatch(rf"/uploads/u{u.id}_[0-9a-f]{{16}}\.jpg", url) or not (settings.UPLOAD_DIR / url.split("/")[-1]).is_file():
            raise HTTPException(400, "Photos must be uploaded through PairUp")
        photos.append(url)
    return {"headline": headline, "bio": bio, "activities": activities, "rates": rates,
            "languages": languages, "photos": photos}


@router.put("/partner/profile")
def save_profile(x: ProfileIn, u: User = Depends(current_user), db: Session = Depends(get_db)):
    _partner_user(u)
    c = _clean_profile(x, u)
    p = _own_profile(db, u)
    changed = (p.headline, p.bio, p.activities_json, p.rates_json, p.languages_json, p.photos_json) != (
        c["headline"], c["bio"], json.dumps(c["activities"]), json.dumps(c["rates"]),
        json.dumps(c["languages"]), json.dumps(c["photos"]))
    p.headline, p.bio = c["headline"], c["bio"]
    p.activities_json, p.rates_json = json.dumps(c["activities"]), json.dumps(c["rates"])
    p.languages_json, p.photos_json = json.dumps(c["languages"]), json.dumps(c["photos"])
    message = "Profile saved."
    if changed and p.status in ("approved", "pending"):
        p.status, p.submitted_at = "pending", utcnow()
        message = "Changes saved and sent for re-review. Your profile is hidden until it is approved again."
    db.commit()
    return {"message": message, "status": p.status}


@router.post("/partner/profile/submit")
def submit_profile(u: User = Depends(current_user), db: Session = Depends(get_db)):
    _partner_user(u)
    p = _own_profile(db, u)
    missing = []
    if len(p.bio.strip()) < 30:
        missing.append("a bio of at least 30 characters")
    if not json.loads(p.photos_json or "[]"):
        missing.append("at least one photo")
    if not json.loads(p.rates_json or "{}"):
        missing.append("at least one activity with a rate")
    if missing:
        raise HTTPException(400, "Please add " + ", ".join(missing))
    if p.status == "approved":
        return {"message": "Your profile is already live.", "status": p.status}
    p.status, p.reject_reason, p.submitted_at = "pending", "", utcnow()
    audit(db, u.id, "profile_submitted", f"user:{u.id}")
    db.commit()
    return {"message": "Submitted for review. We'll notify you once it's approved.", "status": "pending"}


@router.patch("/partner/availability")
def set_availability(x: AvailabilityIn, u: User = Depends(current_user), db: Session = Depends(get_db)):
    p = _own_profile(db, _partner_user(u))
    p.available = x.available
    db.commit()
    return {"available": p.available}


@router.post("/uploads/photo")
async def upload_photo(file: UploadFile = File(...), u: User = Depends(current_user)):
    _partner_user(u)
    data = await file.read(settings.MAX_UPLOAD_BYTES + 1)
    if len(data) > settings.MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"Photo must be under {settings.MAX_UPLOAD_BYTES // (1024 * 1024)} MB")
    try:
        Image.open(io.BytesIO(data)).verify()
        img = Image.open(io.BytesIO(data))
        if img.format not in ("JPEG", "PNG", "WEBP"):
            raise ValueError
        # Re-encode: strips EXIF (incl. GPS location) and any embedded payload.
        img = ImageOps.exif_transpose(img).convert("RGB")
    except Exception:
        raise HTTPException(400, "Upload a valid JPG, PNG or WebP image")
    img.thumbnail((1600, 1600))
    settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    if len(list(settings.UPLOAD_DIR.glob(f"u{u.id}_*"))) >= 30:
        raise HTTPException(400, "Upload limit reached. Remove unused photos first.")
    name = f"u{u.id}_{secrets.token_hex(8)}.jpg"
    img.save(settings.UPLOAD_DIR / name, "JPEG", quality=85, optimize=True)
    return {"url": f"/uploads/{name}"}
