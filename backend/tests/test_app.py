import hmac, hashlib, io, json
from datetime import datetime, timedelta
from PIL import Image
from conftest import login, future
from app.config import settings
from app.moderation import check_text

PID = None


def pid(client):
    global PID
    if PID is None:
        PID = next(p["id"] for p in client.get("/api/partners").json()["items"] if p["name"] == "Aanya")
    return PID


def book(client, h, activity="Coffee date", hours=48, **kw):
    body = {"partner_id": pid(client), "activity": activity, "scheduled_at": future(hours),
            "location": "Starbucks, CyberHub", "safety_ack": True, **kw}
    return client.post("/api/bookings", json=body, headers=h)


# ---------- regression tests for bugs found in the original upload ----------
def test_demo_accounts_can_log_in(client):
    for e, p in [("demo@pairup.local", "DemoPass123!"), ("aanya@pairup.local", "DemoPass123!"),
                 ("admin@pairup.local", "ChangeMe_Admin_123!")]:
        assert client.post("/api/auth/login", json={"email": e, "password": p}).status_code == 200


def test_path_traversal_blocked(client):
    for p in ["/%2e%2e/backend/.env.example", "/..%2fbackend%2fapp%2fmain.py", "/%2e%2e%2fbackend%2fapp%2fconfig.py"]:
        r = client.get(p)
        assert "JWT_SECRET" not in r.text and "FastAPI" not in r.text and "settings" not in r.text
        assert r.status_code in (200, 404)  # 200 only if it falls back to the SPA shell
        assert "<!doctype html>" in r.text.lower() or r.status_code == 404


def test_public_api_never_leaks_email(client):
    data = client.get("/api/partners").json()
    assert data["total"] >= 4
    assert all("email" not in p for p in data["items"])
    assert "email" not in client.get(f"/api/partners/{pid(client)}").json()


def test_unknown_api_route_is_json_404(client):
    r = client.get("/api/nope")
    assert r.status_code == 404 and r.headers["content-type"].startswith("application/json")


def test_security_headers(client):
    h = client.get("/api/health").headers
    assert h["x-content-type-options"] == "nosniff" and h["x-frame-options"] == "DENY"


# ---------- auth ----------
def test_register_rules(client):
    base = {"name": "Test User", "email": "t1@example.com", "password": "Passw0rdX", "dob": "2000-01-01",
            "city": "Delhi", "accept_terms": True}
    assert client.post("/api/auth/register", json={**base, "dob": "2015-01-01"}).status_code == 400  # minor
    assert client.post("/api/auth/register", json={**base, "accept_terms": False}).status_code == 400
    assert client.post("/api/auth/register", json={**base, "password": "short"}).status_code == 422
    assert client.post("/api/auth/register", json={**base, "password": "allletters"}).status_code == 400
    assert client.post("/api/auth/register", json={**base, "role": "admin"}).status_code == 400
    r = client.post("/api/auth/register", json=base)
    assert r.status_code == 200 and "dev_verify_link" in r.json()
    assert client.post("/api/auth/register", json={**base, "email": "T1@EXAMPLE.com"}).status_code == 409


def test_email_verification_and_password_reset(client):
    base = {"name": "Reset Me", "email": "reset@example.com", "password": "Passw0rdX", "dob": "1995-05-05",
            "city": "Delhi", "accept_terms": True}
    link = client.post("/api/auth/register", json=base).json()["dev_verify_link"]
    assert client.post("/api/auth/verify-email", json={"token": link.split("/")[-1]}).status_code == 200
    assert client.post("/api/auth/verify-email", json={"token": link.split("/")[-1]}).status_code == 400  # single use
    r = client.post("/api/auth/forgot-password", json={"email": "reset@example.com"}).json()
    tok = r["dev_reset_link"].split("/")[-1]
    assert client.post("/api/auth/reset-password", json={"token": tok, "password": "NewPass123"}).status_code == 200
    assert client.post("/api/auth/reset-password", json={"token": tok, "password": "Another123"}).status_code == 400
    login(client, "reset@example.com", "NewPass123")
    # unknown email gives the same generic answer (no account enumeration)
    assert "message" in client.post("/api/auth/forgot-password", json={"email": "nobody@example.com"}).json()


# ---------- moderation ----------
def test_moderation():
    assert check_text("Essex based, love coffee", "profile") is None
    assert check_text("full service escort", "profile")
    assert check_text("pay advance payment on gpay", "message")
    assert check_text("call me 9876543210", "profile")
    assert check_text("call me 9876543210", "message") is None
    assert check_text("hotel room after dinner", "booking")


# ---------- partner profile ----------
def make_photo():
    buf = io.BytesIO()
    Image.new("RGB", (300, 400), (200, 80, 120)).save(buf, "PNG")
    return buf.getvalue()


def test_partner_profile_flow(client, admin):
    r = client.post("/api/auth/register", json={"name": "Nina Shah", "email": "nina@example.com", "password": "Passw0rdX",
                    "dob": "1998-03-03", "city": "Pune", "role": "partner", "gender": "female", "accept_terms": True})
    h = {"Authorization": "Bearer " + r.json()["access_token"]}
    uid = r.json()["user"]["id"]
    assert client.post("/api/uploads/photo", files={"file": ("x.txt", b"not an image", "text/plain")}, headers=h).status_code == 400
    up = client.post("/api/uploads/photo", files={"file": ("a.png", make_photo(), "image/png")}, headers=h)
    assert up.status_code == 200
    url = up.json()["url"]
    assert client.get(url).status_code == 200
    # can't use someone else's / external photo URLs
    bad = {"bio": "x" * 40, "photos": ["https://evil.example/x.jpg"], "activities": ["Coffee date"], "rates": {"Coffee date": 300}}
    assert client.put("/api/partner/profile", json=bad, headers=h).status_code == 400
    # solicitation is blocked
    assert client.put("/api/partner/profile", json={"bio": "Full service escort available tonight", "photos": [url],
                      "activities": ["Coffee date"], "rates": {"Coffee date": 300}}, headers=h).status_code == 400
    assert client.put("/api/partner/profile", json={"bio": "Rate too low", "photos": [url], "activities": ["Coffee date"],
                      "rates": {"Coffee date": 5}}, headers=h).status_code == 400
    good = {"headline": "Chai & chats", "bio": "Friendly, punctual and happy to explore Pune's cafés with you.",
            "photos": [url], "activities": ["Coffee date", "Video call"], "rates": {"Coffee date": 400, "Video call": 200}}
    assert client.put("/api/partner/profile", json=good, headers=h).status_code == 200
    assert client.get("/api/partner/profile", headers=h).json()["bio"].startswith("Friendly")  # editor can load own data
    assert client.get(f"/api/partners/{uid}").status_code == 404  # not live yet
    assert client.post("/api/partner/profile/submit", headers=h).json()["status"] == "pending"
    ah = admin
    assert client.patch(f"/api/admin/partners/{uid}", json={"approved": False}, headers=ah).status_code == 400  # reason needed
    assert client.patch(f"/api/admin/partners/{uid}", json={"approved": True}, headers=ah).status_code == 200
    assert client.get(f"/api/partners/{uid}").status_code == 200
    # toggling availability must NOT send a live profile back to review
    client.patch("/api/partner/availability", json={"available": False}, headers=h)
    assert client.get("/api/partner/profile", headers=h).json()["status"] == "approved"
    # content edits do trigger re-review
    client.put("/api/partner/profile", json={**good, "bio": good["bio"] + " Updated!"}, headers=h)
    assert client.get("/api/partner/profile", headers=h).json()["status"] == "pending"


def test_discovery_filters(client):
    assert all(p["city"] == "Delhi" for p in client.get("/api/partners?city=delhi").json()["items"])
    items = client.get("/api/partners?activity=Gym partner&sort=price_low").json()["items"]
    assert items and all("Gym partner" in p["activities"] for p in items)
    assert [p["min_rate"] for p in items] == sorted(p["min_rate"] for p in items)
    assert all(p["min_rate"] <= 300 for p in client.get("/api/partners?max_price=300").json()["items"])
    assert client.get("/api/partners?q=cricket").json()["total"] == 1
    assert client.get("/api/partners?limit=2").json()["items"].__len__() == 2


# ---------- bookings, membership, messaging, reviews ----------
def test_booking_lifecycle(client, customer, partner):
    # needs membership first
    r = client.post("/api/auth/register", json={"name": "Fresh Cust", "email": "fresh@example.com", "password": "Passw0rdX",
                    "dob": "1999-09-09", "city": "Delhi", "accept_terms": True})
    fresh = {"Authorization": "Bearer " + r.json()["access_token"]}
    assert book(client, fresh).status_code == 402
    assert client.post("/api/membership/checkout", json={"plan": "monthly"}, headers=fresh).json()["mode"] == "demo"
    assert client.post("/api/membership/demo-activate", json={"plan": "monthly"}, headers=customer).status_code == 200
    assert client.get("/api/membership/status", headers=customer).json()["active"]

    assert book(client, customer, safety_ack=False).status_code == 400
    assert book(client, customer, activity="Skydiving").status_code == 400
    assert book(client, customer, hours=0).status_code == 400  # < 30 minutes ahead
    assert book(client, customer, location="hotel room 5").status_code == 400
    assert client.post("/api/bookings", json={"partner_id": pid(client), "activity": "Coffee date", "scheduled_at": future(),
                       "location": "Cafe", "safety_ack": True, "price": 1}, headers=customer).json()["price"] == 399  # price from rate card
    b = book(client, customer, hours=72).json()
    bid = b["id"]
    assert b["price"] == 399 and b["status"] == "requested"
    assert book(client, customer, hours=72).status_code == 409  # duplicate slot

    patch = lambda h, status, **kw: client.patch(f"/api/bookings/{bid}", json={"status": status, **kw}, headers=h)
    assert patch(customer, "accepted").status_code == 403      # customer can't accept
    assert patch(customer, "completed").status_code == 400     # can't complete a mere request (original bug)
    assert patch(partner, "accepted").status_code == 200
    assert patch(partner, "accepted").status_code == 400
    assert patch(partner, "completed").status_code == 400      # future plan can't be completed
    assert client.post("/api/messages", json={"receiver_id": 1, "body": "hi admin"}, headers=customer).status_code == 403  # no booking with admin

    # chat opens once accepted
    pidv = pid(client)
    assert client.post("/api/messages", json={"receiver_id": pidv, "body": "Looking forward to it!"}, headers=customer).status_code == 200
    assert client.post("/api/messages", json={"receiver_id": pidv, "body": "send advance payment on gpay"}, headers=customer).status_code == 400
    convs = client.get("/api/conversations", headers=partner).json()
    assert convs and convs[0]["unread"] == 1
    thread = client.get(f"/api/messages/{convs[0]['user_id']}", headers=partner).json()
    assert thread["messages"][0]["body"].startswith("Looking")
    assert client.get("/api/conversations", headers=partner).json()[0]["unread"] == 0

    assert patch(customer, "cancelled").status_code == 400  # reason required once accepted
    assert patch(customer, "cancelled", reason="Plans changed").status_code == 200
    assert patch(partner, "accepted").status_code == 409    # closed


def test_overlap_review_and_completion(client, customer, partner):
    from app.db import SessionLocal
    from app.models import Booking
    c2 = {"Authorization": "Bearer " + client.post("/api/auth/register", json={"name": "Second Cust", "email": "c2@example.com",
          "password": "Passw0rdX", "dob": "1999-09-09", "city": "Delhi", "accept_terms": True}).json()["access_token"]}
    client.post("/api/membership/demo-activate", json={"plan": "monthly"}, headers=c2)
    r1 = book(client, customer, hours=100).json()
    assert book(client, customer, hours=100, activity="Dinner").status_code == 409  # same customer, overlapping
    r2 = book(client, c2, hours=100, activity="Dinner").json()
    ok = client.patch(f"/api/bookings/{r1['id']}", json={"status": "accepted"}, headers=partner)
    clash = client.patch(f"/api/bookings/{r2['id']}", json={"status": "accepted"}, headers=partner)
    assert ok.status_code == 200 and clash.status_code == 409  # partner can't double-book
    # simulate the plan having started, then complete + review
    with SessionLocal() as db:
        b = db.get(Booking, r1["id"]); b.scheduled_at = datetime.utcnow() - timedelta(hours=2); db.commit()
    assert client.patch(f"/api/bookings/{r1['id']}", json={"status": "completed"}, headers=customer).status_code == 200
    assert client.post(f"/api/bookings/{r1['id']}/reviews", json={"rating": 5, "comment": "Lovely"}, headers=partner).status_code == 400
    assert client.post(f"/api/bookings/{r1['id']}/reviews", json={"rating": 5, "comment": "Lovely"}, headers=customer).status_code == 200
    assert client.post(f"/api/bookings/{r1['id']}/reviews", json={"rating": 4}, headers=customer).status_code == 409
    revs = client.get(f"/api/partners/{pid(client)}/reviews").json()
    assert revs[0]["comment"] == "Lovely" and revs[0]["reviewer"] == "Demo"
    n = client.get(f"/api/notifications", headers=partner).json()
    assert n["unread"] > 0


def test_favorites_are_idempotent(client, customer):
    p = pid(client)
    client.put(f"/api/favorites/{p}", headers=customer); client.put(f"/api/favorites/{p}", headers=customer)
    assert client.get("/api/favorites/ids", headers=customer).json().count(p) == 1  # liking twice never un-likes
    assert len(client.get("/api/favorites", headers=customer).json()) >= 1
    client.delete(f"/api/favorites/{p}", headers=customer)
    assert p not in client.get("/api/favorites/ids", headers=customer).json()


# ---------- safety ----------
def test_block_report_sos_and_admin(client, admin):
    mk = lambda e, n: {"Authorization": "Bearer " + client.post("/api/auth/register", json={
        "name": n, "email": e, "password": "Passw0rdX", "dob": "1997-07-07", "city": "Delhi", "accept_terms": True}).json()["access_token"]}
    h1, h2, h3 = mk("r1@example.com", "Rep One"), mk("r2@example.com", "Rep Two"), mk("r3@example.com", "Rep Three")
    p = pid(client)
    for h in (h1, h2):
        assert client.post("/api/reports", json={"target_id": p, "category": "fake_profile", "details": "x"}, headers=h).status_code == 200
    assert client.get(f"/api/partners/{p}").status_code == 200  # 2 reports: still live
    client.post("/api/reports", json={"target_id": p, "category": "scam_or_payment"}, headers=h3)
    assert client.get(f"/api/partners/{p}").status_code == 404  # 3 distinct reporters auto-hold the profile
    reports = client.get("/api/admin/reports", headers=admin).json()
    assert len(reports) >= 3
    assert client.get("/api/admin/reports", headers=h1).status_code == 403
    for r in reports:
        assert client.patch(f"/api/admin/reports/{r['id']}", json={"resolution": "Reviewed"}, headers=admin).status_code == 200
    # restore the profile for later tests
    assert client.patch(f"/api/admin/partners/{p}", json={"approved": True}, headers=admin).status_code == 200
    assert client.post("/api/reports", json={"target_id": p, "category": "bogus"}, headers=h1).status_code == 400

    assert client.put(f"/api/blocks/{p}", headers=h1).status_code == 200
    assert p not in [x["id"] for x in client.get("/api/partners", headers=h1).json()["items"]]
    assert client.get(f"/api/partners/{p}", headers=h1).status_code == 404
    client.delete(f"/api/blocks/{p}", headers=h1)
    assert client.get(f"/api/partners/{p}", headers=h1).status_code == 200

    assert client.post("/api/safety/sos", json={"note": "Feeling unsafe"}, headers=h1).status_code == 200
    crit = [r for r in client.get("/api/admin/reports", headers=admin).json() if r["severity"] == "critical"]
    assert crit and crit[0]["category"] == "sos"
    assert client.get("/api/admin/overview", headers=admin).json()["open_reports"] >= 1


def test_admin_suspension_blocks_login(client, admin):
    r = client.post("/api/auth/register", json={"name": "Bad Actor", "email": "bad@example.com", "password": "Passw0rdX",
                    "dob": "1990-01-01", "city": "Delhi", "accept_terms": True}).json()
    uid, h = r["user"]["id"], {"Authorization": "Bearer " + r["access_token"]}
    assert client.patch(f"/api/admin/users/{uid}/suspend", json={"suspended": True}, headers=admin).status_code == 400  # reason
    assert client.patch(f"/api/admin/users/{uid}/suspend", json={"suspended": True, "reason": "Harassment"}, headers=admin).status_code == 200
    assert client.get("/api/auth/me", headers=h).status_code == 401  # existing session dies immediately
    assert client.post("/api/auth/login", json={"email": "bad@example.com", "password": "Passw0rdX"}).status_code == 403
    assert client.get("/api/admin/audit", headers=admin).json()[0]["action"]


def test_account_deletion_and_password_change(client):
    r = client.post("/api/auth/register", json={"name": "Del Me", "email": "del@example.com", "password": "Passw0rdX",
                    "dob": "1990-01-01", "city": "Delhi", "accept_terms": True}).json()
    h = {"Authorization": "Bearer " + r["access_token"]}
    assert client.post("/api/auth/change-password", json={"current_password": "wrong", "new_password": "NewPass123"}, headers=h).status_code == 400
    assert client.post("/api/auth/change-password", json={"current_password": "Passw0rdX", "new_password": "NewPass123"}, headers=h).status_code == 200
    assert client.post("/api/auth/delete-account", json={"password": "bad"}, headers=h).status_code == 400
    assert client.post("/api/auth/delete-account", json={"password": "NewPass123"}, headers=h).status_code == 200
    assert client.post("/api/auth/login", json={"email": "del@example.com", "password": "NewPass123"}).status_code == 401


# ---------- payments ----------
def test_razorpay_signatures_and_webhook(client, customer, monkeypatch):
    from app import payments
    from app.db import SessionLocal
    from app.models import PaymentOrder
    monkeypatch.setattr(settings, "RAZORPAY_KEY_ID", "rzp_test_x")
    monkeypatch.setattr(settings, "RAZORPAY_KEY_SECRET", "secret123")
    monkeypatch.setattr(settings, "RAZORPAY_WEBHOOK_SECRET", "whsec")
    monkeypatch.setattr(payments, "create_order", lambda amt, rcpt, notes: {"id": "order_TEST1"})
    co = client.post("/api/membership/checkout", json={"plan": "annual"}, headers=customer).json()
    assert co["mode"] == "razorpay" and co["amount"] == 450000 and co["order_id"] == "order_TEST1"
    # forged signature rejected
    assert client.post("/api/membership/verify", json={"razorpay_order_id": "order_TEST1", "razorpay_payment_id": "pay_1",
                       "razorpay_signature": "forged"}, headers=customer).status_code == 400
    # a new order for the valid-signature + webhook paths
    monkeypatch.setattr(payments, "create_order", lambda amt, rcpt, notes: {"id": "order_TEST2"})
    client.post("/api/membership/checkout", json={"plan": "monthly"}, headers=customer)
    sig = hmac.new(b"secret123", b"order_TEST2|pay_2", hashlib.sha256).hexdigest()
    assert client.post("/api/membership/verify", json={"razorpay_order_id": "order_TEST2", "razorpay_payment_id": "pay_2",
                       "razorpay_signature": sig}, headers=customer).status_code == 200
    with SessionLocal() as db:
        assert db.query(PaymentOrder).filter_by(provider_order_id="order_TEST2").one().status == "paid"
    # webhook: bad signature rejected; good one is idempotent
    body = json.dumps({"event": "payment.captured", "payload": {"payment": {"entity": {"order_id": "order_TEST2", "id": "pay_2", "amount": 50000}}}}).encode()
    assert client.post("/api/webhooks/razorpay", content=body, headers={"x-razorpay-signature": "bad"}).status_code == 400
    good = hmac.new(b"whsec", body, hashlib.sha256).hexdigest()
    assert client.post("/api/webhooks/razorpay", content=body, headers={"x-razorpay-signature": good}).status_code == 200
    with SessionLocal() as db:
        from app.models import Membership
        assert db.query(Membership).filter(Membership.payment_ref == "razorpay:pay_2").count() == 1
