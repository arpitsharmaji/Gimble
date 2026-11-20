"""Manual UPI QR payments: submit proof -> admin approves/rejects -> membership / booking activates."""
import io, secrets
from PIL import Image
from app.config import settings
from test_v3 import member, book, accept


def shot():
    b = io.BytesIO(); Image.new("RGB", (240, 400), tuple(secrets.randbelow(256) for _ in range(3))).save(b, "PNG"); return b.getvalue()


def utr(): return "".join(secrets.choice("0123456789") for _ in range(12))


def submit(client, h, data, img=None):
    return client.post("/api/payments/manual", data=data, files={"proof": ("proof.png", img or shot(), "image/png")}, headers=h)


def listing(client, admin): return client.get("/api/admin/manual-payments", headers=admin).json()


def test_membership_proof_to_admin_approval(client, customer, admin, monkeypatch):
    member(client, customer)                                   # demo shortcut (before manual UPI is switched on)
    monkeypatch.setattr(settings, "UPI_ID", "gimble@okaxis")
    assert client.get("/api/membership/plans", headers=customer).json()["mode"] == "manual"
    assert client.get("/api/payments/manual/info", headers=customer).json()["upi_id"] == "gimble@okaxis"
    assert client.post("/api/membership/demo-activate", json={"plan": "monthly"}, headers=customer).status_code == 404
    # validation: missing proof, bad UTR, unknown plan, non-image proof
    assert client.post("/api/payments/manual", data={"kind": "membership", "plan": "monthly", "utr": utr()}, headers=customer).status_code == 422
    assert submit(client, customer, {"kind": "membership", "plan": "monthly", "utr": "12"}).status_code == 400
    assert submit(client, customer, {"kind": "membership", "plan": "nope", "utr": utr()}).status_code == 400
    assert client.post("/api/payments/manual", data={"kind": "membership", "plan": "monthly", "utr": utr()},
                       files={"proof": ("x.png", b"not an image", "image/png")}, headers=customer).status_code == 400
    # valid submission -> pending, amount comes from the server's plan price
    u1, img = utr(), shot()
    r = submit(client, customer, {"kind": "membership", "plan": "monthly", "utr": u1}, img); assert r.status_code == 200, r.text
    pend = [p for p in listing(client, admin)["pending"] if p["utr"] == u1]
    assert len(pend) == 1 and pend[0]["tag"] == "Membership" and pend[0]["amount"] == 500
    pid = pend[0]["id"]
    # duplicate pending / reused UTR / reused screenshot are blocked
    assert submit(client, customer, {"kind": "membership", "plan": "monthly", "utr": utr()}).status_code == 409
    assert client.get("/api/membership/status", headers=customer).json()["pending_review"] is True
    # only admins see the proof and the queue
    assert client.get(f"/api/admin/manual-payments/{pid}/proof", headers=customer).status_code == 403
    assert client.get("/api/admin/manual-payments", headers=customer).status_code == 403
    assert client.get(f"/api/admin/manual-payments/{pid}/proof", headers=admin).headers["content-type"] == "image/jpeg"
    # reject needs a reason, then the customer can resubmit
    assert client.patch(f"/api/admin/manual-payments/{pid}", json={"approved": False}, headers=admin).status_code == 400
    assert client.patch(f"/api/admin/manual-payments/{pid}", json={"approved": False, "reason": "Amount too low"}, headers=admin).status_code == 200
    assert client.patch(f"/api/admin/manual-payments/{pid}", json={"approved": True}, headers=admin).status_code == 404   # already decided
    # approve a fresh one -> membership active
    r = submit(client, customer, {"kind": "membership", "plan": "annual", "utr": utr()}); assert r.status_code == 200, r.text
    p2 = r.json()["id"]
    assert client.patch(f"/api/admin/manual-payments/{p2}", json={"approved": True}, headers=admin).status_code == 200
    st = client.get("/api/membership/status", headers=customer).json()
    assert st["active"] and st["pending_review"] is False


def test_booking_payment_review_then_manual_refund(client, customer, partner, admin, monkeypatch):
    member(client, customer)
    b = book(client, customer, 210, activity="Walk in the park"); accept(client, partner, b["id"])
    monkeypatch.setattr(settings, "UPI_ID", "gimble@okaxis")
    co = client.post(f"/api/bookings/{b['id']}/pay", headers=customer).json()
    assert co["mode"] == "manual"
    u = utr()
    assert submit(client, customer, {"kind": "booking", "booking_id": b["id"], "utr": u}).status_code == 200
    # a booking that isn't yours can't be paid for
    assert submit(client, partner, {"kind": "booking", "booking_id": b["id"], "utr": utr()}).status_code in (403, 404)
    pend = [p for p in listing(client, admin)["pending"] if p["utr"] == u][0]
    assert pend["tag"] == "Companion booking" and pend["booking_id"] == b["id"] and pend["amount"] == b["price"]
    assert client.post(f"/api/bookings/{b['id']}/pay", headers=customer).status_code == 409      # already under review
    assert client.patch(f"/api/admin/manual-payments/{pend['id']}", json={"approved": True}, headers=admin).status_code == 200
    mine = {x["id"]: x for x in client.get("/api/bookings", headers=customer).json()}
    assert mine[b["id"]]["payment_status"] == "paid" and mine[b["id"]]["paid_amount"] == b["price"]
    # cancelling a manually-paid booking never calls a gateway: refund waits for staff
    r = client.patch(f"/api/bookings/{b['id']}", json={"status": "cancelled", "reason": "Change of plans"}, headers=customer).json()
    assert r["payment_status"] == "refund_pending"
    assert client.post(f"/api/admin/bookings/{b['id']}/retry-refund", headers=admin).status_code == 400
    assert client.post(f"/api/admin/bookings/{b['id']}/mark-refunded", json={"reference": ""}, headers=admin).status_code == 400
    r = client.post(f"/api/admin/bookings/{b['id']}/mark-refunded", json={"reference": "REF123456789"}, headers=admin)
    assert r.status_code == 200 and r.json()["payment_status"] in ("refunded", "partially_refunded")


def test_manual_upi_is_off_without_upi_id(client, customer):
    assert settings.UPI_ID == ""
    assert client.get("/api/payments/manual/info", headers=customer).status_code == 503
    assert submit(client, customer, {"kind": "membership", "plan": "monthly", "utr": utr()}).status_code == 503
