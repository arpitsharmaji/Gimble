import json
from datetime import date
from .config import settings
from .db import SessionLocal
from datetime import timedelta
from .models import User, PartnerProfile, Booking, Review, utcnow
from .security import hash_password

DEMO_PW = "DemoPass123!"
PARTNERS = [
    ("Aanya", "aanya@pairup.local", date(2000, 5, 14), "female", "Gurugram", "Cafe hopper & movie buff",
     "Easygoing and curious; always up for a café, a film or exploring the city. Happy to chat in English or Hindi.",
     {"Video call": 199, "Coffee date": 399, "Movie companion": 499, "Gym partner": 299, "Shopping": 599, "Dinner": 699, "City exploration": 799},
     ["English", "Hindi"], 4.9, 38, True),
    ("Rohan", "rohan@pairup.local", date(1998, 2, 3), "male", "Delhi", "Sports fan, board-game nerd",
     "Cricket, football and a very competitive Catan habit. Great plus-one for matches and game cafés.",
     {"Sports partner": 349, "Board games": 299, "Coffee date": 349, "Video call": 149}, ["English", "Hindi", "Punjabi"], 4.7, 21, True),
    ("Meera", "meera@pairup.local", date(1996, 9, 21), "female", "Mumbai", "Museums, books & slow walks",
     "I love galleries, bookstores and long walks along the sea face. Calm, curious and a good listener.",
     {"Museum / gallery visit": 449, "City exploration": 699, "Coffee date": 399, "Language practice": 299}, ["English", "Hindi", "Marathi"], 4.8, 29, True),
    ("Kabir", "kabir@pairup.local", date(1999, 11, 30), "male", "Bengaluru", "Gym buddy & weekend trekker",
     "Lifting, running and weekend treks around Bengaluru. Can keep you accountable at the gym.",
     {"Gym partner": 299, "Sports partner": 399, "City exploration": 599, "Video call": 149}, ["English", "Kannada", "Hindi"], 4.6, 12, False),
    ("Ishita", "ishita@pairup.local", date(1997, 7, 8), "female", "Gurugram", "Concert plus-one & foodie",
     "Live music, street food and trying new restaurants. Fun company for events and dinners.",
     {"Event / concert plus-one": 799, "Dinner": 649, "Shopping": 549, "Coffee date": 379}, ["English", "Hindi"], 0, 0, True),
]


def _ensure_user(db, name, email, dob, gender, city, role, password):
    u = db.query(User).filter_by(email=email).first()
    if not u:
        u = User(name=name, email=email, password_hash=hash_password(password), dob=dob, gender=gender,
                 city=city, role=role, email_verified=True)
        db.add(u)
        db.flush()
    return u


def seed():
    db = SessionLocal()
    try:
        _ensure_user(db, "PairUp Admin", settings.ADMIN_EMAIL, date(1990, 1, 1), "", "Gurugram", "admin", settings.ADMIN_PASSWORD)
        if settings.SEED_DEMO:
            _ensure_user(db, "Demo Customer", "demo@pairup.local", date(1999, 1, 1), "male", "Gurugram", "customer", DEMO_PW)
            for name, email, dob, gender, city, headline, bio, rates, langs, rating, n, avail in PARTNERS:
                u = _ensure_user(db, name, email, dob, gender, city, "partner", DEMO_PW)
                if not db.query(PartnerProfile).filter_by(user_id=u.id).first():
                    sched = {d: ["10:00", "22:00"] for d in ("mon", "tue", "wed", "thu", "fri", "sat")} if name == "Rohan" else {}
                    db.add(PartnerProfile(user_id=u.id, schedule_json=json.dumps(sched), headline=headline, bio=bio, activities_json=json.dumps(list(rates)),
                                          rates_json=json.dumps(rates), languages_json=json.dumps(langs), available=avail,
                                          status="approved", verified=name in ("Aanya", "Meera"), rating=rating,
                                          review_count=n, submitted_at=utcnow()))
        db.commit()
        if settings.SEED_DEMO and not db.query(Review).count():
            cust = db.query(User).filter_by(email="demo@pairup.local").one()
            demo_reviews = [("aanya@pairup.local", "Coffee date", 399, 5, "Super easy to talk to and really punctual. We picked a busy cafe and it felt completely comfortable."),
                            ("meera@pairup.local", "Museum / gallery visit", 449, 5, "Meera knew so much about the gallery. A relaxed, thoughtful afternoon."),
                            ("rohan@pairup.local", "Sports partner", 349, 4, "Great energy at the match - exactly the plus-one I needed.")]
            for i, (email, act, price, rating, text) in enumerate(demo_reviews):
                pu = db.query(User).filter_by(email=email).one()
                when = utcnow() - timedelta(days=20 + i * 3)
                b = Booking(customer_id=cust.id, partner_id=pu.id, activity=act, scheduled_at=when, location="Demo venue (public cafe)",
                            price=price, status="completed", payment_status="paid", paid_amount=price, platform_fee=round(price * settings.PLATFORM_FEE_PERCENT / 100),
                            payment_id="DEMO-SEED", created_at=when - timedelta(days=2), updated_at=when)
                db.add(b); db.flush()
                db.add(Review(booking_id=b.id, customer_id=cust.id, partner_id=pu.id, rating=rating, comment=text, created_at=when + timedelta(hours=4)))
            db.commit()
    finally:
        db.close()
