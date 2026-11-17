import io, boto3, pytest
from moto import mock_aws
from PIL import Image
from conftest import login
from app.config import settings, _normalise_db_url, validate_for_production
from app import storage
from app.storage import get_storage, reset_storage, media_url, canonical_photo


def png():
    b = io.BytesIO(); Image.new("RGB", (240, 300), (90, 40, 200)).save(b, "PNG"); return b.getvalue()


@pytest.fixture
def s3(monkeypatch):
    with mock_aws():
        c = boto3.client("s3", region_name="us-east-1", aws_access_key_id="x", aws_secret_access_key="y")
        c.create_bucket(Bucket="gimble-public"); c.create_bucket(Bucket="gimble-private")
        for k, v in dict(STORAGE_BACKEND="s3", S3_ENDPOINT_URL="", S3_REGION="us-east-1", S3_ACCESS_KEY_ID="x", S3_SECRET_ACCESS_KEY="y",
                         S3_PUBLIC_BUCKET="gimble-public", S3_PRIVATE_BUCKET="gimble-private", S3_PUBLIC_BASE_URL="").items():
            monkeypatch.setattr(settings, k, v)
        reset_storage(); yield c; reset_storage()


# ---------- configuration ----------
def test_database_url_is_normalised_for_hosting_providers():
    assert _normalise_db_url("postgres://u:p@h:5432/db") == "postgresql+psycopg://u:p@h:5432/db"
    assert _normalise_db_url("postgresql://u:p@h/db?sslmode=require") == "postgresql+psycopg://u:p@h/db?sslmode=require"
    assert _normalise_db_url("postgresql+psycopg://u:p@h/db") == "postgresql+psycopg://u:p@h/db"
    assert _normalise_db_url("sqlite:///x.db") == "sqlite:///x.db"


def _prod(monkeypatch, **over):
    base = dict(APP_ENV="production", JWT_SECRET="j" * 40, ADMIN_PASSWORD="A-very-long-admin-pw-1", DEMO_PAYMENTS_ENABLED=False, SEED_DEMO=False,
                DATABASE_URL="postgresql+psycopg://u:p@h/db", STORAGE_BACKEND="local", ALLOW_SQLITE_IN_PRODUCTION=False)
    base.update(over)
    for k, v in base.items(): monkeypatch.setattr(settings, k, v)


def test_production_refuses_ephemeral_sqlite(monkeypatch):
    _prod(monkeypatch); validate_for_production()                       # postgres + local volume: fine
    _prod(monkeypatch, DATABASE_URL="sqlite:///./gimble.db")
    with pytest.raises(RuntimeError, match="SQLite"): validate_for_production()
    _prod(monkeypatch, DATABASE_URL="sqlite:////data/gimble.db", ALLOW_SQLITE_IN_PRODUCTION=True); validate_for_production()   # explicit opt-in (persistent disk)


def test_production_s3_needs_credentials_and_separate_private_bucket(monkeypatch):
    _prod(monkeypatch, STORAGE_BACKEND="s3", S3_PUBLIC_BUCKET="", S3_ACCESS_KEY_ID="", S3_SECRET_ACCESS_KEY="", S3_PRIVATE_BUCKET="")
    with pytest.raises(RuntimeError, match="S3_PUBLIC_BUCKET"): validate_for_production()
    _prod(monkeypatch, STORAGE_BACKEND="s3", S3_PUBLIC_BUCKET="pub", S3_ACCESS_KEY_ID="k", S3_SECRET_ACCESS_KEY="s", S3_PRIVATE_BUCKET="pub")
    with pytest.raises(RuntimeError, match="SEPARATE"): validate_for_production()
    _prod(monkeypatch, STORAGE_BACKEND="s3", S3_PUBLIC_BUCKET="pub", S3_ACCESS_KEY_ID="k", S3_SECRET_ACCESS_KEY="s", S3_PRIVATE_BUCKET="priv"); validate_for_production()


# ---------- S3 backend (mocked AWS) ----------
def test_s3_storage_roundtrip(s3):
    st = get_storage(); assert st.kind == "s3"
    name = "u7_" + "a1" * 8 + ".jpg"
    assert not st.exists_public(name) and st.get_public(name) is None
    st.put_public(name, b"photo-bytes"); assert st.exists_public(name) and st.get_public(name) == b"photo-bytes" and st.count_public("u7_") == 1
    st.put_private("kyc_" + "b2" * 12 + ".jpg", b"secret"); assert st.get_private("kyc_" + "b2" * 12 + ".jpg") == b"secret"
    assert "Contents" not in s3.list_objects_v2(Bucket="gimble-public", Prefix="kyc_")      # private docs never land in the public bucket
    st.delete_private("kyc_" + "b2" * 12 + ".jpg"); assert st.get_private("kyc_" + "b2" * 12 + ".jpg") is None
    assert st.ping() == "s3:gimble-public"


def test_photo_upload_end_to_end_on_s3(client, s3, monkeypatch):
    h = {"Authorization": "Bearer " + client.post("/api/auth/register", json={"name": "S Three", "email": "s3p@example.com", "password": "Passw0rdX",
         "dob": "1997-07-07", "city": "Pune", "role": "partner", "accept_terms": True}).json()["access_token"]}
    uid = client.get("/api/auth/me", headers=h).json()["id"]
    url = client.post("/api/uploads/photo", files={"file": ("a.png", png(), "image/png")}, headers=h).json()["url"]
    assert url.startswith(f"/uploads/u{uid}_") and s3.list_objects_v2(Bucket="gimble-public")["KeyCount"] == 1
    r = client.get(url); assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg" and "immutable" in r.headers["cache-control"]
    prof = {"bio": "x" * 40, "photos": [url], "activities": ["Coffee date"], "rates": {"Coffee date": 300}}
    assert client.put("/api/partner/profile", json=prof, headers=h).status_code == 200
    # someone else's / forged photo names are rejected
    assert client.put("/api/partner/profile", json={**prof, "photos": ["/uploads/u1_" + "0" * 16 + ".jpg"]}, headers=h).status_code == 400
    # switch on a CDN/public URL: API hands out the CDN URL, DB keeps the canonical path, CSP allows the CDN origin
    monkeypatch.setattr(settings, "S3_PUBLIC_BASE_URL", "https://cdn.example.com/photos")
    mine = client.get("/api/partner/profile", headers=h).json()
    assert mine["photos"][0] == f"https://cdn.example.com/photos/{url.split('/')[-1]}"
    assert "https://cdn.example.com" in client.get("/api/health").headers["content-security-policy"]
    assert client.put("/api/partner/profile", json={**prof, "photos": mine["photos"]}, headers=h).status_code == 200   # CDN form accepted
    from app.db import SessionLocal
    from app.models import PartnerProfile
    with SessionLocal() as db:
        assert db.query(PartnerProfile).filter_by(user_id=uid).one().photos_json == f'["{url}"]'


def test_kyc_documents_stay_in_the_private_bucket(client, s3, admin):
    kh = login(client, "kabir@gimble.local")
    r = client.post("/api/partner/kyc", data={"id_type": "pan"}, files={"id_file": ("i.png", png(), "image/png"), "selfie_file": ("s.png", png(), "image/png")}, headers=kh)
    assert r.status_code == 200
    assert s3.list_objects_v2(Bucket="gimble-private")["KeyCount"] == 2 and s3.list_objects_v2(Bucket="gimble-public").get("KeyCount", 0) == 0
    sub = next(x for x in client.get("/api/admin/kyc", headers=admin).json() if x["name"] == "Kabir")
    assert client.get(f"/api/admin/kyc/{sub['id']}/file/id", headers=admin).status_code == 200
    assert client.get(f"/api/admin/kyc/{sub['id']}/file/id", headers=kh).status_code == 403
    client.patch(f"/api/admin/kyc/{sub['id']}", json={"approved": False, "reason": "blurry"}, headers=admin)
    assert s3.list_objects_v2(Bucket="gimble-private").get("KeyCount", 0) == 0                   # deleted after the decision


def test_upload_route_rejects_traversal_and_junk(client):
    for p in ["/uploads/../../etc/passwd", "/uploads/..%2f..%2fetc%2fpasswd", "/uploads/evil.jpg", "/uploads/u1_zzzz.jpg"]:
        assert client.get(p).status_code in (404, 200) and "root:" not in client.get(p).text


def test_deep_health_reports_storage(client, monkeypatch):
    assert client.get("/api/health/deep").json() == {"database": "ok", "storage": "ok", "backend": "local"}
    class Broken:
        def ping(self): raise RuntimeError("bucket unreachable")
    monkeypatch.setattr("app.main.get_storage", lambda: Broken())
    r = client.get("/api/health/deep"); assert r.status_code == 503 and r.json()["storage"] == "down"


def test_production_requires_smtp_when_email_verification_is_on(monkeypatch):
    _prod(monkeypatch, REQUIRE_VERIFIED_EMAIL=True, SMTP_HOST="")
    with pytest.raises(RuntimeError, match="SMTP_HOST"): validate_for_production()
    _prod(monkeypatch, REQUIRE_VERIFIED_EMAIL=True, SMTP_HOST="smtp.example.com"); validate_for_production()
    _prod(monkeypatch, REQUIRE_VERIFIED_EMAIL=False, SMTP_HOST=""); validate_for_production()


def test_admin_can_grant_membership_and_verify_email(client, admin, customer):
    r = client.post("/api/auth/register", json={"name": "Needs Help", "email": "needshelp@example.com", "password": "Passw0rdX", "dob": "1994-02-02",
                    "city": "Delhi", "accept_terms": True}).json()
    h, uid = {"Authorization": "Bearer " + r["access_token"]}, r["user"]["id"]
    assert not client.get("/api/membership/status", headers=h).json()["active"]
    assert client.post(f"/api/admin/users/{uid}/membership", json={"plan": "monthly", "note": "launch comp"}, headers=customer).status_code == 403
    assert client.post(f"/api/admin/users/{uid}/membership", json={"plan": "bogus"}, headers=admin).status_code == 400
    assert client.post(f"/api/admin/users/{uid}/membership", json={"plan": "monthly", "note": "launch comp"}, headers=admin).status_code == 200
    assert client.get("/api/membership/status", headers=h).json()["active"]
    row = next(u for u in client.get("/api/admin/users?q=needshelp", headers=admin).json() if u["id"] == uid)
    assert row["member"] is True and row["email_verified"] is False
    assert client.patch(f"/api/admin/users/{uid}/verify-email", headers=admin).status_code == 200
    assert client.get("/api/auth/me", headers=h).json()["email_verified"] is True
    assert client.post("/api/admin/users/1/membership", json={"plan": "monthly"}, headers=admin).status_code == 400   # not a customer
