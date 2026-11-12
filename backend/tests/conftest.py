import os, tempfile, pathlib
_tmp = tempfile.mkdtemp()
os.environ.update({
    "DATABASE_URL": f"sqlite:///{_tmp}/test.db", "UPLOAD_DIR": f"{_tmp}/uploads", "PRIVATE_DIR": f"{_tmp}/private", "APP_ENV": "development",
    "SEED_DEMO": "true", "DEMO_PAYMENTS_ENABLED": "true", "RATE_LIMIT_ENABLED": "false",
    "RAZORPAY_KEY_ID": "", "RAZORPAY_KEY_SECRET": "",
})
import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


def login(client, email, pw="DemoPass123!"):
    r = client.post("/api/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["access_token"]}


@pytest.fixture(scope="session")
def customer(client): return login(client, "demo@pairup.local")
@pytest.fixture(scope="session")
def partner(client): return login(client, "aanya@pairup.local")
@pytest.fixture(scope="session")
def admin(client): return login(client, "admin@pairup.local", "ChangeMe_Admin_123!")


def future(hours=48):
    return (datetime.utcnow() + timedelta(hours=hours)).isoformat() + "Z"
