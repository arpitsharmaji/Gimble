import secrets
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from ..config import settings
from ..db import get_db
from ..mailer import send_email
from ..models import User, PartnerProfile, AuthToken, Booking, utcnow
from ..schemas import (RegisterIn, LoginIn, ForgotIn, ResetIn, TokenIn, ChangePasswordIn, DeleteAccountIn)
from ..security import (hash_password, verify_password, create_token, current_user, password_problem,
                        sha256, age_from, rate_limit)
from ..services import user_json, audit

router = APIRouter(prefix="/api/auth", tags=["auth"])
GENDERS = {"", "female", "male", "non-binary", "other"}


def _issue_token(db: Session, user: User, purpose: str, minutes: int) -> str:
    raw = secrets.token_urlsafe(32)
    db.add(AuthToken(user_id=user.id, purpose=purpose, token_hash=sha256(raw), expires_at=utcnow() + timedelta(minutes=minutes)))
    db.flush()
    return raw


def _send_verify(db: Session, user: User) -> str:
    raw = _issue_token(db, user, "verify", 60 * 24)
    link = f"{settings.PUBLIC_URL}/#/verify/{raw}"
    send_email(user.email, "Verify your Gimble email", f"Hi {user.name},\n\nConfirm your email: {link}\n\nThis link expires in 24 hours.")
    return link


@router.post("/register", dependencies=[Depends(rate_limit("register", 10, 3600))])
def register(x: RegisterIn, db: Session = Depends(get_db)):
    if x.role not in ("customer", "partner"):
        raise HTTPException(400, "Role must be customer or partner")
    if not x.accept_terms:
        raise HTTPException(400, "You must accept the Terms and Community Standards")
    if x.gender not in GENDERS:
        raise HTTPException(400, "Invalid gender option")
    if age_from(x.dob) < 18:
        raise HTTPException(400, "You must be at least 18 years old to join Gimble")
    if age_from(x.dob) > 100:
        raise HTTPException(400, "Enter a valid date of birth")
    problem = password_problem(x.password)
    if problem:
        raise HTTPException(400, problem)
    if db.query(User).filter(func.lower(User.email) == x.email).first():
        raise HTTPException(409, "This email is already registered")
    u = User(name=x.name.strip(), email=x.email, password_hash=hash_password(x.password), dob=x.dob,
             gender=x.gender, city=x.city.strip(), role=x.role)
    db.add(u)
    db.flush()
    if x.role == "partner":
        db.add(PartnerProfile(user_id=u.id))
    link = _send_verify(db, u)
    db.commit()
    out = {"access_token": create_token(u.id), "token_type": "bearer", "user": user_json(u)}
    if not settings.is_production and not settings.SMTP_HOST:
        out["dev_verify_link"] = link  # convenience while email isn't configured
    return out


@router.post("/login", dependencies=[Depends(rate_limit("login", 15, 300))])
def login(x: LoginIn, db: Session = Depends(get_db)):
    u = db.query(User).filter(func.lower(User.email) == x.email).first()
    if not u or not verify_password(x.password, u.password_hash):
        raise HTTPException(401, "Incorrect email or password")
    if not u.active:
        raise HTTPException(403, u.suspended_reason or "This account is unavailable")
    return {"access_token": create_token(u.id), "token_type": "bearer", "user": user_json(u)}


@router.get("/me")
def me(u: User = Depends(current_user)):
    return user_json(u)


@router.post("/verify-email")
def verify_email(x: TokenIn, db: Session = Depends(get_db)):
    t = db.query(AuthToken).filter_by(token_hash=sha256(x.token), purpose="verify", used=False).first()
    if not t or t.expires_at < utcnow():
        raise HTTPException(400, "This verification link is invalid or has expired")
    user = db.get(User, t.user_id)
    user.email_verified = True
    t.used = True
    db.commit()
    return {"message": "Email verified"}


@router.post("/resend-verification", dependencies=[Depends(rate_limit("resend", 5, 3600))])
def resend(u: User = Depends(current_user), db: Session = Depends(get_db)):
    if u.email_verified:
        return {"message": "Email already verified"}
    link = _send_verify(db, u)
    db.commit()
    out = {"message": "Verification email sent"}
    if not settings.is_production and not settings.SMTP_HOST:
        out["dev_verify_link"] = link
    return out


@router.post("/forgot-password", dependencies=[Depends(rate_limit("forgot", 5, 900))])
def forgot(x: ForgotIn, db: Session = Depends(get_db)):
    u = db.query(User).filter(func.lower(User.email) == x.email, User.active.is_(True)).first()
    out = {"message": "If that email is registered, a reset link has been sent."}
    if u:
        raw = _issue_token(db, u, "reset", 30)
        link = f"{settings.PUBLIC_URL}/#/reset/{raw}"
        send_email(u.email, "Reset your Gimble password", f"Reset your password: {link}\n\nThis link expires in 30 minutes. Ignore this if it wasn't you.")
        db.commit()
        if not settings.is_production and not settings.SMTP_HOST:
            out["dev_reset_link"] = link
    return out


@router.post("/reset-password", dependencies=[Depends(rate_limit("reset", 10, 900))])
def reset(x: ResetIn, db: Session = Depends(get_db)):
    problem = password_problem(x.password)
    if problem:
        raise HTTPException(400, problem)
    t = db.query(AuthToken).filter_by(token_hash=sha256(x.token), purpose="reset", used=False).first()
    if not t or t.expires_at < utcnow():
        raise HTTPException(400, "This reset link is invalid or has expired")
    db.get(User, t.user_id).password_hash = hash_password(x.password)
    t.used = True
    db.commit()
    return {"message": "Password updated. You can now log in."}


@router.post("/change-password")
def change_password(x: ChangePasswordIn, u: User = Depends(current_user), db: Session = Depends(get_db)):
    if not verify_password(x.current_password, u.password_hash):
        raise HTTPException(400, "Current password is incorrect")
    problem = password_problem(x.new_password)
    if problem:
        raise HTTPException(400, problem)
    u.password_hash = hash_password(x.new_password)
    db.commit()
    return {"message": "Password changed"}


@router.post("/delete-account")
def delete_account(x: DeleteAccountIn, u: User = Depends(current_user), db: Session = Depends(get_db)):
    """Deactivate and anonymise the account. Closed bookings/reviews stay for dispute records."""
    if u.role == "admin":
        raise HTTPException(400, "Admin accounts can't be self-deleted")
    if not verify_password(x.password, u.password_hash):
        raise HTTPException(400, "Password is incorrect")
    open_bookings = db.query(Booking).filter(
        (Booking.customer_id == u.id) | (Booking.partner_id == u.id), Booking.status == "accepted").count()
    if open_bookings:
        raise HTTPException(409, "Cancel or complete your accepted bookings before deleting your account")
    for b in db.query(Booking).filter((Booking.customer_id == u.id) | (Booking.partner_id == u.id), Booking.status == "requested"):
        b.status, b.status_reason = "cancelled", "Account deleted"
    u.active = False
    u.suspended_reason = "Account deleted by user"
    u.name = "Deleted user"
    u.email = f"deleted-{u.id}-{secrets.token_hex(4)}@deleted.invalid"
    u.password_hash = "!"
    if u.partner:
        u.partner.status = "draft"
        u.partner.available = False
        u.partner.bio = u.partner.headline = ""
        u.partner.photos_json = "[]"
    audit(db, u.id, "account_deleted", f"user:{u.id}")
    db.commit()
    return {"message": "Account deleted"}
