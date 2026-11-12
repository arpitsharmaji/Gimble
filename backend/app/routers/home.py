"""Public data for the landing page. Only real numbers - nothing is invented."""
import json
from collections import Counter
from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import User, PartnerProfile, Booking, Review
from ..services import partner_json

router = APIRouter(prefix="/api", tags=["home"])


@router.get("/home")
def home(db: Session = Depends(get_db)):
    live = (db.query(PartnerProfile).join(User, User.id == PartnerProfile.user_id)
            .filter(PartnerProfile.status == "approved", User.active.is_(True)).all())
    cities = Counter(p.user.city.title() for p in live if p.user.city)
    acts = Counter(a for p in live for a in json.loads(p.activities_json or "[]"))
    featured = sorted(live, key=lambda p: (not p.available, not p.verified, -p.rating, -p.review_count))[:6]
    reviews = (db.query(Review).filter(Review.rating >= 4, Review.comment != "").order_by(Review.id.desc()).limit(3).all())
    testimonials = []
    for r in reviews:
        c, p = db.get(User, r.customer_id), db.get(User, r.partner_id)
        testimonials.append({"rating": r.rating, "comment": r.comment, "reviewer": c.name.split()[0] if c and c.active else "Member",
                             "partner": p.name if p else ""})
    return {"stats": {"partners": len(live), "cities": len(cities), "reviews": db.query(Review).count(),
                      "completed": db.query(Booking).filter_by(status="completed").count()},
            "featured": [partner_json(p) for p in featured],
            "cities": [{"city": c, "count": n} for c, n in cities.most_common(8)],
            "activities": [{"name": a, "count": n} for a, n in acts.most_common(8)],
            "testimonials": testimonials}
