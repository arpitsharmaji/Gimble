import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from .config import settings, validate_for_production
from .db import Base, engine, SessionLocal
from .routers import auth, partners, bookings, social, membership, admin, payments, wallet, kyc, support, home, manual_payments
from .migrate import ensure_columns
from .seed import seed
from .storage import get_storage, NAME_RE
from urllib.parse import urlparse

logging.basicConfig(level=logging.INFO)
FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"


log = logging.getLogger("gimble")


def _init_db():
    Base.metadata.create_all(bind=engine)
    ensure_columns(engine, Base.metadata)  # upgrades older databases in place
    seed()


@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_for_production()
    if settings.STORAGE_BACKEND == "local":
        settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        settings.PRIVATE_DIR.mkdir(parents=True, exist_ok=True)
        if settings.is_production:
            log.warning("STORAGE_BACKEND=local: make sure %s and %s are on a PERSISTENT disk/volume, or uploads will vanish on redeploy.",
                        settings.UPLOAD_DIR, settings.PRIVATE_DIR)
    if settings.is_production and not settings.SMTP_HOST:
        log.warning("SMTP_HOST is not set: password-reset and notification emails will NOT be sent.")
    if settings.is_production and not settings.razorpay_enabled:
        log.warning("Razorpay is not configured: customers can't buy memberships (admins can grant them from the console).")
    log.info("Gimble starting: env=%s db=%s storage=%s", settings.APP_ENV, "sqlite" if settings.uses_sqlite else "postgres", settings.STORAGE_BACKEND)
    if settings.uses_sqlite:
        _init_db()
    else:
        # Several workers/containers may boot at once: serialise first-time setup with a Postgres advisory lock.
        with engine.connect() as lock:
            lock.execute(text("SELECT pg_advisory_lock(727274)"))
            try:
                _init_db()
            finally:
                lock.execute(text("SELECT pg_advisory_unlock(727274)")); lock.commit()
    yield


app = FastAPI(title="Gimble API", version="3.0.0", lifespan=lifespan,
              description="Companion discovery, booking and safety platform",
              docs_url=None if settings.is_production else "/docs",
              redoc_url=None, openapi_url=None if settings.is_production else "/openapi.json")

for r in (auth, partners, bookings, social, membership, payments, manual_payments, wallet, kyc, support, home, admin):
    app.include_router(r.router)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    resp = await call_next(request)
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    resp.headers.setdefault("Permissions-Policy", "geolocation=(), camera=(), microphone=()")
    if not request.url.path.startswith(("/docs", "/openapi")):
        cdn = ""
        if settings.STORAGE_BACKEND == "s3" and settings.S3_PUBLIC_BASE_URL:
            u = urlparse(settings.S3_PUBLIC_BASE_URL); cdn = f" {u.scheme}://{u.netloc}"
        resp.headers.setdefault(
            "Content-Security-Policy",
            f"default-src 'self'; img-src 'self' data: blob: https://*.razorpay.com{cdn}; style-src 'self' 'unsafe-inline'; "
            "script-src 'self' https://checkout.razorpay.com; frame-src https://api.razorpay.com https://checkout.razorpay.com; "
            "connect-src 'self' https://lumberjack.razorpay.com https://api.razorpay.com https://checkout.razorpay.com; "
            "object-src 'none'; base-uri 'self'; frame-ancestors 'none'")
    if request.url.path.startswith("/api/"):
        resp.headers.setdefault("Cache-Control", "no-store")
    return resp


@app.get("/api/health")
def health():
    with SessionLocal() as db:
        db.execute(text("SELECT 1"))
    return {"status": "ok", "service": "Gimble API", "version": app.version}


@app.get("/api/health/deep")
def health_deep():
    """Checks the database AND file storage. Point your uptime monitor here."""
    out = {"database": "ok", "storage": "ok", "backend": settings.STORAGE_BACKEND}
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
    except Exception:
        out["database"] = "down"
    try:
        get_storage().ping()
    except Exception:
        out["storage"] = "down"
    code = 200 if out["database"] == "ok" and out["storage"] == "ok" else 503
    return JSONResponse(out, status_code=code)


@app.api_route("/api/{rest:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"], include_in_schema=False)
async def api_not_found(rest: str):
    return JSONResponse({"detail": "Not found"}, status_code=404)


# User-uploaded (re-encoded) photos, then the frontend. StaticFiles refuses path traversal.
@app.get("/uploads/{name}", include_in_schema=False)
def serve_upload(name: str):
    """Profile photos, from local disk or the S3 bucket - same URL either way. Names are strictly validated (no traversal)."""
    data = get_storage().get_public(name) if NAME_RE.match(name) else None
    if data is None:
        return JSONResponse({"detail": "Not found"}, status_code=404)
    return Response(data, media_type="image/jpeg", headers={"Cache-Control": "public, max-age=31536000, immutable"})



app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
