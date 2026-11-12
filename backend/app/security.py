import hashlib, hmac, re, secrets
from datetime import datetime, timedelta, timezone, date
from jose import jwt, JWTError
from fastapi import Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from .config import settings
from .db import get_db
from .models import User

ALGORITHM = "HS256"
ITERATIONS = 310_000
oauth = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), ITERATIONS).hex()
    return f"pbkdf2_sha256${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, salt, digest = stored.split("$", 2)
        check = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), ITERATIONS).hex()
        return hmac.compare_digest(check, digest)
    except Exception:
        return False


def password_problem(pw: str) -> str | None:
    if len(pw) < 8:
        return "Password must be at least 8 characters"
    if not re.search(r"[A-Za-z]", pw) or not re.search(r"\d", pw):
        return "Password must contain at least one letter and one number"
    return None


def create_token(user_id: int) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_MINUTES)
    return jwt.encode({"sub": str(user_id), "exp": exp}, settings.JWT_SECRET, algorithm=ALGORITHM)


def sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def age_from(dob: date) -> int:
    today = date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


def _user_from_token(token: str | None, db: Session) -> User | None:
    if not token:
        return None
    try:
        uid = int(jwt.decode(token, settings.JWT_SECRET, algorithms=[ALGORITHM])["sub"])
    except (JWTError, ValueError, KeyError):
        raise HTTPException(401, "Invalid or expired session")
    user = db.get(User, uid)
    if not user or not user.active:
        raise HTTPException(401, "Account unavailable")
    return user


def current_user(token: str | None = Depends(oauth), db: Session = Depends(get_db)) -> User:
    user = _user_from_token(token, db)
    if not user:
        raise HTTPException(401, "Please sign in")
    return user


def optional_user(token: str | None = Depends(oauth), db: Session = Depends(get_db)) -> User | None:
    try:
        return _user_from_token(token, db)
    except HTTPException:
        return None


def admin_user(user: User = Depends(current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(403, "Administrator access required")
    return user


# ---------- tiny in-memory rate limiter (use Redis/nginx limits when scaling out) ----------
_hits: dict[str, list[float]] = {}


def client_ip(request: Request) -> str:
    if settings.TRUST_PROXY:
        fwd = request.headers.get("x-forwarded-for")
        if fwd:
            return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def rate_limit(name: str, limit: int, window: int):
    def dep(request: Request):
        if not settings.RATE_LIMIT_ENABLED:
            return
        import time
        key = f"{name}:{client_ip(request)}"
        now = time.monotonic()
        bucket = [t for t in _hits.get(key, []) if now - t < window]
        if len(bucket) >= limit:
            raise HTTPException(429, "Too many attempts. Please wait a moment and try again.")
        bucket.append(now)
        _hits[key] = bucket
    return dep


def reset_rate_limits():
    _hits.clear()
