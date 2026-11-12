import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from .config import settings, validate_for_production
from .db import Base, engine, SessionLocal
from .routers import auth, partners, bookings, social, membership, admin
from .seed import seed

logging.basicConfig(level=logging.INFO)
FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_for_production()
    settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    seed()
    yield


app = FastAPI(title="PairUp API", version="2.0.0", lifespan=lifespan,
              description="Companion discovery, booking and safety platform",
              docs_url=None if settings.is_production else "/docs",
              redoc_url=None, openapi_url=None if settings.is_production else "/openapi.json")

for r in (auth, partners, bookings, social, membership, admin):
    app.include_router(r.router)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    resp = await call_next(request)
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    resp.headers.setdefault("Permissions-Policy", "geolocation=(), camera=(), microphone=()")
    if not request.url.path.startswith(("/docs", "/openapi")):
        resp.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; "
            "script-src 'self' https://checkout.razorpay.com; frame-src https://api.razorpay.com; "
            "connect-src 'self' https://lumberjack.razorpay.com; object-src 'none'; base-uri 'self'; frame-ancestors 'none'")
    if request.url.path.startswith("/api/"):
        resp.headers.setdefault("Cache-Control", "no-store")
    return resp


@app.get("/api/health")
def health():
    with SessionLocal() as db:
        db.execute(text("SELECT 1"))
    return {"status": "ok", "service": "PairUp API", "version": app.version}


@app.api_route("/api/{rest:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"], include_in_schema=False)
async def api_not_found(rest: str):
    return JSONResponse({"detail": "Not found"}, status_code=404)


# User-uploaded (re-encoded) photos, then the frontend. StaticFiles refuses path traversal.
app.mount("/uploads", StaticFiles(directory=str(settings.UPLOAD_DIR), check_dir=False), name="uploads")
app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
