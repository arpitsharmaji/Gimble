"""Hire / Get hired modes, customer profiles (photos + bio), and partners swiping on customers."""
import io, itertools
from PIL import Image
from app.config import settings

_n = itertools.count(1)


def photo():
    b = io.BytesIO(); Image.new("RGB", (200, 260), (90, 40, 200)).save(b, "PNG"); return b.getvalue()


def register(client, role, name, city="Gurugram"):
    email = f"mode{next(_n)}_{role}@example.com"
    r = client.post("/api/auth/register", json={"name": name, "email": email, "password": "Passw0rdX", "dob": "1998-03-03",
                                                "city": city, "role": role, "gender": "female", "accept_terms": True})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["access_token"]}, r.json()["user"]


def upload(client, h):
    r = client.post("/api/uploads/photo", files={"file": ("a.png", photo(), "image/png")}, headers=h)
    assert r.status_code == 200, r.text
    return r.json()["url"]


BIO = "Friendly and curious. I love cafes, live music and weekend walks in the city."


def approved_customer(client, admin, name):
    h, u = register(client, "customer", name)
    url = upload(client, h)
    r = client.put("/api/me/customer-profile", json={"bio": BIO, "photos": [url], "discoverable": True}, headers=h)
    assert r.status_code == 200 and r.json()["status"] == "pending"
    assert client.patch(f"/api/admin/customer-profiles/{u['id']}", json={"approved": True}, headers=admin).status_code == 200
    return h, u


def approved_partner(client, admin, name):
    h, u = register(client, "partner", name)
    url = upload(client, h)
    good = {"headline": "Chai & chats", "bio": "Friendly, punctual and happy to explore the city's cafes with you.", "photos": [url],
            "activities": ["Coffee date"], "rates": {"Coffee date": 400}}
    assert client.put("/api/partner/profile", json=good, headers=h).status_code == 200
    assert client.post("/api/partner/profile/submit", headers=h).json()["status"] == "pending"
    assert client.patch(f"/api/admin/partners/{u['id']}", json={"approved": True}, headers=admin).status_code == 200
    return h, u


def test_customer_profile_needs_photo_and_bio_and_admin_approval(client, admin):
    h, u = register(client, "customer", "Riya Sen")
    assert u["modes"]["active"] == "hire" and u["modes"]["hire"]["complete"] is False
    # incomplete: stays a draft
    r = client.put("/api/me/customer-profile", json={"bio": "short", "photos": []}, headers=h).json()
    assert r["status"] == "draft" and r["complete"] is False
    # external photo URLs and sexual wording are refused
    assert client.put("/api/me/customer-profile", json={"bio": BIO, "photos": ["https://evil.example/x.jpg"]}, headers=h).status_code == 400
    url = upload(client, h)
    assert client.put("/api/me/customer-profile", json={"bio": "Escort services available tonight, call me", "photos": [url]}, headers=h).status_code == 400
    r = client.put("/api/me/customer-profile", json={"bio": BIO, "photos": [url]}, headers=h).json()
    assert r["status"] == "pending" and r["complete"] is True
    assert client.get("/api/auth/me", headers=h).json()["modes"]["hire"]["complete"] is True
    # admin queue: reject needs a reason, then approve
    q = client.get("/api/admin/customer-profiles", headers=admin).json()
    assert any(c["id"] == u["id"] for c in q)
    assert client.patch(f"/api/admin/customer-profiles/{u['id']}", json={"approved": False}, headers=admin).status_code == 400
    assert client.patch(f"/api/admin/customer-profiles/{u['id']}", json={"approved": True}, headers=admin).status_code == 200
    assert client.get("/api/me/customer-profile", headers=h).json()["status"] == "approved"
    # editing the content sends it back for review; a toggle alone does not
    client.put("/api/me/customer-profile", json={"bio": BIO, "photos": [url], "discoverable": False}, headers=h)
    assert client.get("/api/me/customer-profile", headers=h).json()["status"] == "approved"
    client.put("/api/me/customer-profile", json={"bio": BIO + " Updated!", "photos": [url]}, headers=h)
    assert client.get("/api/me/customer-profile", headers=h).json()["status"] == "pending"


def test_switch_between_hire_and_get_hired(client, admin):
    h, u = register(client, "customer", "Dev Arora")
    r = client.post("/api/auth/switch-mode", json={"mode": "hired"}, headers=h).json()["user"]
    assert r["role"] == "partner" and r["modes"]["active"] == "hired" and r["modes"]["hired"]["exists"] is True
    assert r["modes"]["hire"]["exists"] is True                      # the customer side is kept
    r = client.post("/api/auth/switch-mode", json={"mode": "hire"}, headers=h).json()["user"]
    assert r["role"] == "customer"
    assert client.post("/api/auth/switch-mode", json={"mode": "nope"}, headers=h).status_code == 400
    assert client.post("/api/auth/switch-mode", json={"mode": "hire"}, headers=admin).status_code == 400


def test_each_side_only_sees_the_other(client, admin):
    ph, pu = approved_partner(client, admin, "Pia Kapoor")
    ch, cu = approved_customer(client, admin, "Karan Bose")
    # customers can't use the partner-side swipe deck, nor swipe
    assert client.get("/api/discover/customers", headers=ch).status_code == 403
    assert client.post("/api/discover/swipe", json={"customer_id": cu["id"], "direction": "right"}, headers=ch).status_code == 403
    # partners can't browse other partners (own profile is still reachable)
    assert client.get("/api/partners", headers=ph).status_code == 403
    other, _ = approved_partner(client, admin, "Other Partner")
    assert client.get(f"/api/partners/{_['id']}", headers=ph).status_code == 403
    assert client.get(f"/api/partners/{pu['id']}", headers=ph).status_code == 200
    # logged-out visitors and customers still browse partners
    assert client.get("/api/partners").status_code == 200 and client.get("/api/partners", headers=ch).status_code == 200
    # a partner whose profile isn't approved yet can't see customers
    nh, _ = register(client, "partner", "Newbie Partner")
    assert client.get("/api/discover/customers", headers=nh).status_code == 403
    # customer cards expose only minimal data
    items = client.get("/api/discover/customers?limit=40", headers=ph).json()["items"]
    mine = next(i for i in items if i["id"] == cu["id"])
    assert set(mine) == {"id", "name", "age", "city", "bio", "photos"} and mine["name"] == "Karan"


def test_swipe_right_sends_free_intro_and_left_passes(client, admin, monkeypatch):
    ph, pu = approved_partner(client, admin, "Anaya Rao")
    c1h, c1 = approved_customer(client, admin, "Sam Iyer")
    c2h, c2 = approved_customer(client, admin, "Tara Nair")
    r = client.post("/api/discover/swipe", json={"customer_id": c1["id"], "direction": "right"}, headers=ph).json()
    assert r["sent"] is True
    body = client.get(f"/api/messages/{pu['id']}", headers=c1h).json()["messages"][-1]["body"]
    assert "I'm Anaya" in body and "interested in being your partner" in body and "Hire me" in body and body.startswith("Hi Sam")
    assert any("Anaya" in n["text"] for n in client.get("/api/notifications", headers=c1h).json()["items"])
    # the partner cannot follow up until the customer replies (no cold messages)
    assert client.post("/api/messages", json={"receiver_id": c1["id"], "body": "Hello again"}, headers=ph).status_code == 403
    # the customer can reply, which opens the conversation both ways
    assert client.post("/api/messages", json={"receiver_id": pu["id"], "body": "Hi Anaya, tell me more"}, headers=c1h).status_code == 200
    assert client.post("/api/messages", json={"receiver_id": c1["id"], "body": "Happy to chat here"}, headers=ph).status_code == 200
    # swiping again is idempotent; a swiped customer no longer appears in the deck
    again = client.post("/api/discover/swipe", json={"customer_id": c1["id"], "direction": "right"}, headers=ph).json()
    assert again["already"] is True and again["sent"] is False
    ids = [i["id"] for i in client.get("/api/discover/customers?limit=40", headers=ph).json()["items"]]
    assert c1["id"] not in ids and c2["id"] in ids
    # passing sends nothing and can be undone; a sent intro cannot
    assert client.post("/api/discover/swipe", json={"customer_id": c2["id"], "direction": "left"}, headers=ph).json()["sent"] is False
    assert client.delete(f"/api/discover/swipes/{c2['id']}", headers=ph).status_code == 200
    assert client.delete(f"/api/discover/swipes/{c1['id']}", headers=ph).status_code == 400
    # invalid input
    assert client.post("/api/discover/swipe", json={"customer_id": c2["id"], "direction": "up"}, headers=ph).status_code == 400
    assert client.post("/api/discover/swipe", json={"customer_id": pu["id"], "direction": "right"}, headers=ph).status_code in (400, 404)


def test_intro_daily_cap_blocks_and_opt_out_hides(client, admin, monkeypatch):
    ph, pu = approved_partner(client, admin, "Cap Partner")
    a_h, a = approved_customer(client, admin, "Cap One")
    b_h, b = approved_customer(client, admin, "Cap Two")
    monkeypatch.setattr(settings, "INTRO_DAILY_CAP", 1)
    assert client.post("/api/discover/swipe", json={"customer_id": a["id"], "direction": "right"}, headers=ph).status_code == 200
    r = client.post("/api/discover/swipe", json={"customer_id": b["id"], "direction": "right"}, headers=ph)
    assert r.status_code == 429
    # a customer who opted out of discovery is not shown, and can't be swiped
    client.put("/api/me/customer-profile", json={"bio": BIO, "photos": client.get("/api/me/customer-profile", headers=b_h).json()["photos"], "discoverable": False}, headers=b_h)
    assert b["id"] not in [i["id"] for i in client.get("/api/discover/customers?limit=40", headers=ph).json()["items"]]
    assert client.post("/api/discover/swipe", json={"customer_id": b["id"], "direction": "left"}, headers=ph).status_code == 404


def test_blocked_customer_is_hidden_from_the_partner(client, admin):
    ph, pu = approved_partner(client, admin, "Block Partner")
    ch, cu = approved_customer(client, admin, "Block Customer")
    assert client.put(f"/api/blocks/{pu['id']}", headers=ch).status_code == 200
    assert cu["id"] not in [i["id"] for i in client.get("/api/discover/customers?limit=40", headers=ph).json()["items"]]
    assert client.post("/api/discover/swipe", json={"customer_id": cu["id"], "direction": "right"}, headers=ph).status_code == 404
