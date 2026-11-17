from conftest import login
from app.config import settings


def reg(client, email, role="customer", name="Test Person"):
    r = client.post("/api/auth/register", json={"name": name, "email": email, "password": "Passw0rdX", "dob": "1996-04-04",
                    "city": "Delhi", "role": role, "accept_terms": True}).json()
    return {"Authorization": "Bearer " + r["access_token"]}, r["user"]["id"]


def pid(client, name):
    return next(p["id"] for p in client.get("/api/partners?limit=60").json()["items"] if p["name"] == name)


def send(client, h, to, body="Hi! Are you free this weekend?"):
    return client.post("/api/messages", json={"receiver_id": to, "body": body}, headers=h)


def test_inquiry_requires_membership_then_cap_then_reply_opens_chat(client):
    kabir = pid(client, "Kabir")
    kh = login(client, "kabir@gimble.local")
    c, cid = reg(client, "inq1@example.com", name="Ravi Kumar")

    # non-member: can open the thread (to see the prompt) but not send
    t = client.get(f"/api/messages/{kabir}", headers=c).json()
    assert t["state"]["needs_membership"] and not t["state"]["can_send"] and t["messages"] == []
    assert send(client, c, kabir).status_code == 402

    client.post("/api/membership/demo-activate", json={"plan": "monthly"}, headers=c)
    # pre-booking messages may not carry contact details or links
    assert send(client, c, kabir, "call me on 9876543210").status_code == 400
    assert send(client, c, kabir, "add me instagram.com/ravi").status_code == 400
    assert send(client, c, kabir, "pay me on gpay").status_code == 400
    r1 = send(client, c, kabir); assert r1.status_code == 200 and r1.json()["remaining"] == 2
    assert send(client, c, kabir, "Mostly a gym session, around 6pm?").json()["remaining"] == 1
    assert send(client, c, kabir, "Let me know!").json()["remaining"] == 0
    capped = send(client, c, kabir, "Hello?")
    assert capped.status_code == 403 and "wait" in capped.json()["detail"].lower()
    assert client.get(f"/api/messages/{kabir}", headers=c).json()["state"]["can_send"] is False

    # partner sees the inquiry in conversations + notification (only one, for the first message)
    convs = client.get("/api/conversations", headers=kh).json()
    mine = next(x for x in convs if x["user_id"] == cid)
    assert mine["unread"] == 3 and mine["last_message"] == "Let me know!"
    notes = [n for n in client.get("/api/notifications", headers=kh).json()["items"] if "Ravi sent you a message" in n["text"]]
    assert len(notes) == 1

    # partner replies -> conversation fully open for both
    assert send(client, kh, cid, "Sure! 6pm works.").status_code == 200
    again = send(client, c, kabir, "Great, I'll request a booking")
    assert again.status_code == 200 and again.json()["remaining"] is None
    thread = client.get(f"/api/messages/{kabir}", headers=c).json()
    assert [m["body"] for m in thread["messages"]][-2:] == ["Sure! 6pm works.", "Great, I'll request a booking"]
    # still no contact details until a booking is accepted
    assert send(client, kh, cid, "WhatsApp me 9876543210").status_code == 400
    # customer side list shows it too
    assert any(x["user_id"] == kabir for x in client.get("/api/conversations", headers=c).json())


def test_partners_cannot_cold_message_and_targets_are_restricted(client):
    kh = login(client, "kabir@gimble.local")
    c, cid = reg(client, "inq2@example.com")
    client.post("/api/membership/demo-activate", json={"plan": "monthly"}, headers=c)
    assert send(client, kh, cid).status_code == 403                       # partner -> customer who never wrote
    assert client.get(f"/api/messages/{cid}", headers=kh).status_code == 403
    assert send(client, c, 1).status_code == 403                          # admin is not a partner
    c2, c2id = reg(client, "inq3@example.com")
    assert send(client, c, c2id).status_code == 403                       # customer -> customer
    assert send(client, c, cid).status_code == 403                        # to yourself
    draft_h, draft_id = reg(client, "draftpartner@example.com", role="partner")
    assert send(client, c, draft_id).status_code == 403                   # partner profile not approved/live
    assert client.get(f"/api/messages/{draft_id}", headers=c).status_code == 403


def test_blocking_stops_inquiries(client):
    ih = login(client, "ishita@gimble.local")
    c, cid = reg(client, "inq4@example.com")
    client.post("/api/membership/demo-activate", json={"plan": "monthly"}, headers=c)
    ishita = pid(client, "Ishita")
    assert send(client, c, ishita).status_code == 200
    assert client.put(f"/api/blocks/{cid}", headers=ih).status_code == 200      # partner blocks the customer
    assert send(client, c, ishita, "Are you there?").status_code == 403
    assert client.get(f"/api/messages/{cid}", headers=ih).status_code == 403
    assert all(x["user_id"] != cid for x in client.get("/api/conversations", headers=ih).json())
    client.delete(f"/api/blocks/{cid}", headers=ih)


def test_booking_chat_still_allows_contact_details(client, customer, partner):
    """Once a booking is accepted, coordination details (phone numbers) are fine - only scams stay blocked."""
    from conftest import future
    client.post("/api/membership/demo-activate", json={"plan": "monthly"}, headers=customer)
    p = pid(client, "Aanya")
    b = client.post("/api/bookings", json={"partner_id": p, "activity": "Coffee date", "scheduled_at": future(400),
                    "location": "Cafe", "safety_ack": True}, headers=customer).json()
    client.patch(f"/api/bookings/{b['id']}", json={"status": "accepted"}, headers=partner)
    assert send(client, customer, p, "I'll be at the cafe, call 9876543210 if you can't find me").status_code == 200
    assert send(client, customer, p, "send advance payment on gpay").status_code == 400
