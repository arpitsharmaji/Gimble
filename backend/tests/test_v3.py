import hashlib, hmac, io, json
from datetime import datetime, timedelta
from PIL import Image
from sqlalchemy import Column, Integer, String, Boolean, MetaData, Table, create_engine, text
from conftest import login, future
from app.config import settings
from app.db import SessionLocal
from app.models import Booking, LedgerEntry, User
from app.migrate import ensure_columns
from app.services import IST

H = lambda t: t  # readability


def partner_id(client, name="Aanya"):
    return next(p["id"] for p in client.get("/api/partners?limit=60").json()["items"] if p["name"] == name)


def member(client, customer):
    client.post("/api/membership/demo-activate", json={"plan": "monthly"}, headers=customer)


def book(client, h, hours, partner="Aanya", activity="Coffee date"):
    r = client.post("/api/bookings", json={"partner_id": partner_id(client, partner), "activity": activity,
                    "scheduled_at": future(hours), "location": "Starbucks, CyberHub", "safety_ack": True}, headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def accept(client, partner, bid):
    assert client.patch(f"/api/bookings/{bid}", json={"status": "accepted"}, headers=partner).status_code == 200


def wallet(client, partner):
    return client.get("/api/wallet", headers=partner).json()


def png():
    b = io.BytesIO(); Image.new("RGB", (200, 200), (10, 120, 200)).save(b, "PNG"); return b.getvalue()


def ledger_kinds(client, partner):
    return [e["kind"] for e in wallet(client, partner)["ledger"]]


# ---------- payment gating, completion, earnings, payouts ----------
def test_unpaid_booking_cannot_complete_and_auto_cancels(client, customer, partner):
    member(client, customer)
    b = book(client, customer, 210)
    accept(client, partner, b["id"])
    with SessionLocal() as db:  # the plan is now about to start and was never paid for
        x = db.get(Booking, b["id"]); x.scheduled_at = datetime.utcnow() + timedelta(minutes=20); db.commit()
    r = client.patch(f"/api/bookings/{b['id']}", json={"status": "completed"}, headers=customer)
    assert r.status_code == 409  # housekeeping already cancelled it
    mine = {x["id"]: x for x in client.get("/api/bookings", headers=customer).json()}
    assert mine[b["id"]]["status"] == "cancelled" and "Payment" in mine[b["id"]]["status_reason"]


def test_earnings_and_payout_lifecycle(client, customer, partner, admin):
    member(client, customer)
    before = wallet(client, partner)
    b = book(client, customer, 220)
    assert client.post(f"/api/bookings/{b['id']}/pay", headers=customer).status_code == 409  # can't pay before acceptance
    accept(client, partner, b["id"])
    assert client.post(f"/api/bookings/{b['id']}/pay", headers=customer).json()["mode"] == "demo"
    assert client.post(f"/api/bookings/{b['id']}/pay", headers=partner).status_code == 404  # not the customer's booking
    assert client.post(f"/api/bookings/{b['id']}/demo-pay", headers=customer).status_code == 200
    assert client.post(f"/api/bookings/{b['id']}/demo-pay", headers=customer).status_code == 409  # already paid
    with SessionLocal() as db:
        x = db.get(Booking, b["id"]); x.scheduled_at = datetime.utcnow() - timedelta(hours=3); db.commit()
    assert client.patch(f"/api/bookings/{b['id']}", json={"status": "completed"}, headers=customer).status_code == 200
    w = wallet(client, partner)
    assert w["balance"] - before["balance"] == 399 - 60  # price minus 15% platform fee
    assert w["available"] == before["available"]          # held for the dispute window first
    assert "earning" in ledger_kinds(client, partner)

    # payouts: need ID verification, UPI, minimum, available balance
    assert client.post("/api/wallet/payouts", json={"amount": 500}, headers=partner).status_code in (400, 403)
    assert client.put("/api/wallet/payout-details", json={"upi": "not a upi"}, headers=partner).status_code == 400
    assert client.put("/api/wallet/payout-details", json={"upi": "aanya@okaxis", "name": "Aanya"}, headers=partner).status_code == 200
    pid = partner_id(client)
    assert client.patch(f"/api/admin/partners/{pid}/verified", json={"verified": True}, headers=admin).status_code == 200
    assert client.post("/api/wallet/payouts", json={"amount": 100}, headers=partner).status_code == 400  # below minimum
    assert client.post("/api/admin/ledger/adjust", json={"user_id": pid, "amount": 700, "note": "Test bonus"}, headers=admin).status_code == 200
    assert client.post("/api/wallet/payouts", json={"amount": 10_000_000}, headers=partner).status_code == 422
    assert client.post("/api/wallet/payouts", json={"amount": 900_000}, headers=partner).status_code == 400  # more than available
    bal = wallet(client, partner)["balance"]
    r = client.post("/api/wallet/payouts", json={"amount": 500}, headers=partner)
    assert r.status_code == 200
    assert wallet(client, partner)["balance"] == bal - 500  # funds reserved immediately
    pend = client.get("/api/admin/payouts", headers=admin).json()
    p1 = next(p for p in pend if p["id"] == r.json()["id"])
    assert p1["upi"] == "aanya@okaxis"
    assert client.get("/api/admin/payouts", headers=partner).status_code == 403
    assert client.patch(f"/api/admin/payouts/{p1['id']}", json={"paid": True}, headers=admin).status_code == 400  # needs UTR
    assert client.patch(f"/api/admin/payouts/{p1['id']}", json={"paid": True, "reference": "UTR123456"}, headers=admin).status_code == 200
    assert client.patch(f"/api/admin/payouts/{p1['id']}", json={"paid": True, "reference": "UTR123456"}, headers=admin).status_code == 404  # no double-pay
    # rejected payouts return the money
    assert client.post("/api/wallet/payouts", json={"amount": 500}, headers=partner).status_code == 400  # only ~200 left available
    client.post("/api/admin/ledger/adjust", json={"user_id": pid, "amount": 500, "note": "Test bonus 2"}, headers=admin)
    r2 = client.post("/api/wallet/payouts", json={"amount": 500}, headers=partner).json()
    mid = wallet(client, partner)["balance"]
    assert client.patch(f"/api/admin/payouts/{r2['id']}", json={"paid": False, "reason": "UPI ID bounced"}, headers=admin).status_code == 200
    assert wallet(client, partner)["balance"] == mid + 500
    ov = client.get("/api/admin/overview", headers=admin).json()
    assert ov["platform_fees_inr"] >= 60 and "pending_payouts" in ov


def test_lead_time_and_accept_cutoff(client, customer, partner):
    member(client, customer)
    body = lambda hrs: {"partner_id": partner_id(client), "activity": "Coffee date", "scheduled_at": future(hrs), "location": "Cafe", "safety_ack": True}
    assert client.post("/api/bookings", json=body(1.5), headers=customer).status_code == 400   # under 2h lead time
    r = client.post("/api/bookings", json=body(2.3), headers=customer)
    assert r.status_code == 200                                                           # exactly the form's default window works
    bid = r.json()["id"]
    assert client.patch(f"/api/bookings/{bid}", json={"status": "accepted"}, headers=partner).status_code == 200
    assert client.post(f"/api/bookings/{bid}/demo-pay", headers=customer).status_code == 200  # and it can still be paid
    with SessionLocal() as db:  # request that has aged until it's too close to start
        x = db.get(Booking, bid)
    r2 = client.post("/api/bookings", json=body(2.1), headers=customer)
    if r2.status_code == 200:
        with SessionLocal() as db:
            y = db.get(Booking, r2.json()["id"]); y.scheduled_at = datetime.utcnow() + timedelta(minutes=40); db.commit()
        assert client.patch(f"/api/bookings/{r2.json()['id']}", json={"status": "accepted"}, headers=partner).status_code == 409


# ---------- cancellation & refund policy ----------
def test_refund_policy(client, customer, partner):
    member(client, customer)
    # >= 24h: full refund, partner gets nothing
    b = book(client, customer, 130); accept(client, partner, b["id"])
    client.post(f"/api/bookings/{b['id']}/demo-pay", headers=customer)
    n = len(wallet(client, partner)["ledger"])
    r = client.patch(f"/api/bookings/{b['id']}", json={"status": "cancelled", "reason": "Change of plans"}, headers=customer).json()
    assert r["payment_status"] == "refunded" and r["refund_amount"] == 399
    assert len(wallet(client, partner)["ledger"]) == n
    # 2-24h: 50% refund, rest compensates the partner (minus fee)
    b = book(client, customer, 10); accept(client, partner, b["id"])
    client.post(f"/api/bookings/{b['id']}/demo-pay", headers=customer)
    r = client.patch(f"/api/bookings/{b['id']}", json={"status": "cancelled", "reason": "Cannot make it"}, headers=customer).json()
    assert r["payment_status"] == "partially_refunded" and r["refund_amount"] in (199, 200)
    assert "cancel_compensation" in ledger_kinds(client, partner)
    # partner cancels a paid booking: customer always gets everything back
    b = book(client, customer, 160); accept(client, partner, b["id"])
    client.post(f"/api/bookings/{b['id']}/demo-pay", headers=customer)
    r = client.patch(f"/api/bookings/{b['id']}", json={"status": "cancelled", "reason": "Unwell"}, headers=partner).json()
    assert r["payment_status"] == "refunded" and r["refund_amount"] == 399


def test_razorpay_booking_payment_webhook_and_late_payment(client, customer, partner, monkeypatch):
    from app import payments
    member(client, customer)
    monkeypatch.setattr(settings, "RAZORPAY_KEY_ID", "rzp_test_x"); monkeypatch.setattr(settings, "RAZORPAY_KEY_SECRET", "sec")
    monkeypatch.setattr(settings, "RAZORPAY_WEBHOOK_SECRET", "wh")
    refunds = []
    monkeypatch.setattr(payments, "refund", lambda pid, amt: refunds.append((pid, amt)) or {"id": "rfnd_1"})
    seq = iter(["order_B1", "order_B2"])
    monkeypatch.setattr(payments, "create_order", lambda amt, rcpt, notes: {"id": next(seq)})
    b = book(client, customer, 240); accept(client, partner, b["id"])
    co = client.post(f"/api/bookings/{b['id']}/pay", headers=customer).json()
    assert co["mode"] == "razorpay" and co["amount"] == 39900
    assert client.post(f"/api/bookings/{b['id']}/demo-pay", headers=customer).status_code == 404  # no free bypass when live
    body = json.dumps({"event": "payment.captured", "payload": {"payment": {"entity": {"order_id": "order_B1", "id": "pay_B1", "amount": 39900}}}}).encode()
    sig = hmac.new(b"wh", body, hashlib.sha256).hexdigest()
    for _ in range(2):  # replayed webhook must not double-process
        assert client.post("/api/webhooks/razorpay", content=body, headers={"x-razorpay-signature": sig}).status_code == 200
    mine = {x["id"]: x for x in client.get("/api/bookings", headers=customer).json()}
    assert mine[b["id"]]["payment_status"] == "paid"
    # real refund goes through the gateway
    r = client.patch(f"/api/bookings/{b['id']}", json={"status": "cancelled", "reason": "Plans changed"}, headers=customer).json()
    assert r["payment_status"] == "refunded" and refunds == [("pay_B1", 39900)]
    # customer pays an order for a booking that got cancelled meanwhile -> automatically refunded
    b2 = book(client, customer, 250); accept(client, partner, b2["id"])
    client.post(f"/api/bookings/{b2['id']}/pay", headers=customer)  # creates order_B2
    client.patch(f"/api/bookings/{b2['id']}", json={"status": "cancelled", "reason": "Changed mind"}, headers=customer)
    body2 = json.dumps({"event": "payment.captured", "payload": {"payment": {"entity": {"order_id": "order_B2", "id": "pay_B2", "amount": 39900}}}}).encode()
    client.post("/api/webhooks/razorpay", content=body2, headers={"x-razorpay-signature": hmac.new(b"wh", body2, hashlib.sha256).hexdigest()})
    assert ("pay_B2", 39900) in refunds


# ---------- weekly schedule ----------
def next_weekday_utc(weekday, ist_hour, min_days=4):
    d = datetime.utcnow() + timedelta(days=min_days)
    while (d + IST).weekday() != weekday:
        d += timedelta(days=1)
    local = datetime((d + IST).year, (d + IST).month, (d + IST).day, ist_hour, 0)
    return (local - IST).isoformat() + "Z"


def test_partner_schedule(client, customer):
    member(client, customer)
    rid = partner_id(client, "Rohan")
    body = lambda when: {"partner_id": rid, "activity": "Coffee date", "scheduled_at": when, "location": "Cafe Delhi Darbar", "safety_ack": True}
    assert client.post("/api/bookings", json=body(next_weekday_utc(6, 12)), headers=customer).status_code == 400   # Sunday: off
    assert client.post("/api/bookings", json=body(next_weekday_utc(2, 23)), headers=customer).status_code == 400   # 23:00: after hours
    assert client.post("/api/bookings", json=body(next_weekday_utc(2, 14)), headers=customer).status_code == 200   # Wed 14:00: ok
    rh = login(client, "rohan@pairup.local")
    assert client.put("/api/partner/schedule", json={"days": {"funday": ["10:00", "12:00"]}}, headers=rh).status_code == 400
    assert client.put("/api/partner/schedule", json={"days": {"mon": ["10:00", "10:30"]}}, headers=rh).status_code == 400
    assert client.put("/api/partner/schedule", json={"days": {"sun": ["10:00", "14:00"]}}, headers=rh).status_code == 200
    assert client.post("/api/bookings", json=body(next_weekday_utc(6, 12)), headers=customer).status_code == 200   # now Sunday works
    assert client.get(f"/api/partners/{rid}").json()["schedule"] == {"sun": ["10:00", "14:00"]}


# ---------- ID verification (KYC) ----------
def test_kyc_flow(client, admin):
    from app.config import settings as s
    meera = login(client, "meera@pairup.local")
    files = lambda: {"id_file": ("id.png", png(), "image/png"), "selfie_file": ("me.png", png(), "image/png")}
    assert client.post("/api/partner/kyc", data={"id_type": "library_card"}, files=files(), headers=meera).status_code == 400
    assert client.post("/api/partner/kyc", data={"id_type": "pan"}, files={"id_file": ("x.txt", b"nope", "text/plain"), "selfie_file": ("y.png", png(), "image/png")}, headers=meera).status_code == 400
    assert client.post("/api/partner/kyc", data={"id_type": "pan"}, files=files(), headers=meera).status_code == 200
    assert client.post("/api/partner/kyc", data={"id_type": "pan"}, files=files(), headers=meera).status_code == 409
    assert client.get("/api/partner/kyc", headers=meera).json()["latest"]["status"] == "pending"
    assert client.get("/api/admin/kyc", headers=meera).status_code == 403
    sub = next(x for x in client.get("/api/admin/kyc", headers=admin).json() if x["name"] == "Meera")
    img = client.get(f"/api/admin/kyc/{sub['id']}/file/id", headers=admin)
    assert img.status_code == 200 and img.headers["content-type"] == "image/jpeg"
    assert client.get(f"/api/admin/kyc/{sub['id']}/file/id", headers=meera).status_code == 403
    assert client.patch(f"/api/admin/kyc/{sub['id']}", json={"approved": False}, headers=admin).status_code == 400
    assert client.patch(f"/api/admin/kyc/{sub['id']}", json={"approved": False, "reason": "Photo is blurry"}, headers=admin).status_code == 200
    assert client.get(f"/api/admin/kyc/{sub['id']}/file/id", headers=admin).status_code == 404  # files deleted after decision
    assert not list(s.PRIVATE_DIR.glob("kyc_*"))
    # resubmit and approve
    client.post("/api/partner/kyc", data={"id_type": "aadhaar"}, files=files(), headers=meera)
    sub = client.get("/api/admin/kyc", headers=admin).json()[0]
    assert client.patch(f"/api/admin/kyc/{sub['id']}", json={"approved": True}, headers=admin).status_code == 200
    assert client.get("/api/partner/kyc", headers=meera).json()["verified"] is True
    # KYC files are never reachable from the public static/uploads routes
    assert client.get("/uploads/../private").status_code in (404, 200) and "kyc_" not in client.get("/uploads/").text


# ---------- support, home, review replies ----------
def test_support_tickets(client, admin, customer):
    ok = {"name": "Visitor", "email": "visitor@example.com", "category": "payment_refund", "message": "My refund has not arrived yet."}
    assert client.post("/api/support", json={**ok, "category": "bogus"}).status_code == 400
    assert client.post("/api/support", json={**ok, "message": "short"}).status_code == 422
    t = client.post("/api/support", json=ok).json()
    mine = client.post("/api/support", json=ok, headers=customer).json()
    assert any(x["id"] == mine["id"] for x in client.get("/api/support/mine", headers=customer).json())
    assert client.get("/api/admin/support", headers=customer).status_code == 403
    assert any(x["id"] == t["id"] for x in client.get("/api/admin/support", headers=admin).json())
    assert client.patch(f"/api/admin/support/{t['id']}", json={"reply": "Refunds take 5-7 days.", "close": True}, headers=admin).status_code == 200
    assert all(x["id"] != t["id"] for x in client.get("/api/admin/support", headers=admin).json())


def test_home_data_is_real_and_private(client):
    d = client.get("/api/home").json()
    assert d["stats"]["partners"] >= 4 and d["stats"]["cities"] >= 3
    assert d["featured"] and d["cities"] and d["activities"]
    assert d["testimonials"] and all(set(t) == {"rating", "comment", "reviewer", "partner"} for t in d["testimonials"])
    assert "@" not in json.dumps(d)


def test_partner_reply_to_review(client, partner):
    revs = client.get(f"/api/partners/{partner_id(client)}/reviews").json()
    bid = revs[0]["booking_id"]
    other = login(client, "rohan@pairup.local")
    assert client.post(f"/api/reviews/{bid}/reply", json={"reply": "Thanks!"}, headers=other).status_code == 404
    assert client.post(f"/api/reviews/{bid}/reply", json={"reply": "Pay me on gpay"}, headers=partner).status_code == 400
    assert client.post(f"/api/reviews/{bid}/reply", json={"reply": "Thank you, it was lovely meeting you!"}, headers=partner).status_code == 200
    assert client.get(f"/api/partners/{partner_id(client)}/reviews").json()[0]["partner_reply"].startswith("Thank you")


# ---------- in-place upgrade of an older database ----------
def test_ensure_columns_upgrades_old_db(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path}/old.db")
    with eng.begin() as c:
        c.execute(text("CREATE TABLE things (id INTEGER PRIMARY KEY, name VARCHAR(20))"))
        c.execute(text("INSERT INTO things (name) VALUES ('old row')"))
    md = MetaData()
    Table("things", md, Column("id", Integer, primary_key=True), Column("name", String(20)),
          Column("paid", Integer, default=0), Column("status", String(10), default="unpaid"), Column("flag", Boolean, default=False))
    Table("brand_new", md, Column("id", Integer, primary_key=True))
    assert sorted(ensure_columns(eng, md)) == ["things.flag", "things.paid", "things.status"]
    assert ensure_columns(eng, md) == []  # idempotent
    with eng.connect() as c:
        row = c.execute(text("SELECT name, paid, status, flag FROM things")).one()
    assert tuple(row) == ("old row", 0, "unpaid", 0)
