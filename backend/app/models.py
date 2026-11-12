from datetime import datetime, date, timezone
from sqlalchemy import (String, Integer, Float, Boolean, DateTime, Date, ForeignKey, Text,
                        UniqueConstraint, Index)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base


def utcnow() -> datetime:
    """Naive UTC timestamp (all datetimes are stored as naive UTC)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    email: Mapped[str] = mapped_column(String(180), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    dob: Mapped[date] = mapped_column(Date)
    gender: Mapped[str] = mapped_column(String(20), default="")
    city: Mapped[str] = mapped_column(String(100), default="")
    role: Mapped[str] = mapped_column(String(20), default="customer")  # customer|partner|admin
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    suspended_reason: Mapped[str] = mapped_column(String(300), default="")
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    partner: Mapped["PartnerProfile"] = relationship(back_populates="user", uselist=False)


class PartnerProfile(Base):
    __tablename__ = "partner_profiles"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    headline: Mapped[str] = mapped_column(String(120), default="")
    bio: Mapped[str] = mapped_column(Text, default="")
    photos_json: Mapped[str] = mapped_column(Text, default="[]")
    activities_json: Mapped[str] = mapped_column(Text, default="[]")
    rates_json: Mapped[str] = mapped_column(Text, default="{}")
    languages_json: Mapped[str] = mapped_column(Text, default="[]")
    available: Mapped[bool] = mapped_column(Boolean, default=True)
    # draft -> pending -> approved | rejected
    status: Mapped[str] = mapped_column(String(16), default="draft", index=True)
    reject_reason: Mapped[str] = mapped_column(String(300), default="")
    # Identity (KYC) verification is separate from content approval.
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    rating: Mapped[float] = mapped_column(Float, default=0)
    review_count: Mapped[int] = mapped_column(Integer, default=0)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    schedule_json: Mapped[str] = mapped_column(Text, default="{}")  # weekly hours in IST; empty = any time
    payout_upi: Mapped[str] = mapped_column(String(80), default="")
    payout_name: Mapped[str] = mapped_column(String(80), default="")
    user: Mapped[User] = relationship(back_populates="partner")


class Membership(Base):
    __tablename__ = "memberships"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="active")
    plan: Mapped[str] = mapped_column(String(30), default="monthly")
    starts_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    payment_ref: Mapped[str] = mapped_column(String(120), default="")


class PaymentOrder(Base):
    __tablename__ = "payment_orders"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    plan: Mapped[str] = mapped_column(String(30))
    amount_paise: Mapped[int] = mapped_column(Integer)
    provider: Mapped[str] = mapped_column(String(20), default="razorpay")
    kind: Mapped[str] = mapped_column(String(12), default="membership")  # membership|booking
    booking_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    provider_order_id: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    payment_id: Mapped[str] = mapped_column(String(80), default="")
    status: Mapped[str] = mapped_column(String(16), default="created")  # created|paid|failed
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Booking(Base):
    __tablename__ = "bookings"
    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    partner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    activity: Mapped[str] = mapped_column(String(100))
    scheduled_at: Mapped[datetime] = mapped_column(DateTime)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=60)
    location: Mapped[str] = mapped_column(String(200), default="")
    price: Mapped[int] = mapped_column(Integer)
    note: Mapped[str] = mapped_column(Text, default="")
    # requested|accepted|rejected|cancelled|completed|expired
    status: Mapped[str] = mapped_column(String(24), default="requested", index=True)
    status_reason: Mapped[str] = mapped_column(String(300), default="")
    payment_status: Mapped[str] = mapped_column(String(20), default="unpaid")  # unpaid|paid|refunded|partially_refunded|refund_pending
    paid_amount: Mapped[int] = mapped_column(Integer, default=0)
    refund_amount: Mapped[int] = mapped_column(Integer, default=0)
    platform_fee: Mapped[int] = mapped_column(Integer, default=0)
    payment_id: Mapped[str] = mapped_column(String(80), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class Favorite(Base):
    __tablename__ = "favorites"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    partner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    __table_args__ = (UniqueConstraint("user_id", "partner_id"),)


class Review(Base):
    __tablename__ = "reviews"
    id: Mapped[int] = mapped_column(primary_key=True)
    booking_id: Mapped[int] = mapped_column(ForeignKey("bookings.id"), unique=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    partner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    rating: Mapped[int] = mapped_column(Integer)
    comment: Mapped[str] = mapped_column(Text, default="")
    partner_reply: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Message(Base):
    __tablename__ = "messages"
    id: Mapped[int] = mapped_column(primary_key=True)
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    receiver_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    body: Mapped[str] = mapped_column(Text)
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    __table_args__ = (Index("ix_msg_pair", "sender_id", "receiver_id"),)


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(30), default="info")
    text: Mapped[str] = mapped_column(String(300))
    link: Mapped[str] = mapped_column(String(120), default="")
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Block(Base):
    __tablename__ = "blocks"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    blocked_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    __table_args__ = (UniqueConstraint("user_id", "blocked_id"),)


class Report(Base):
    __tablename__ = "reports"
    id: Mapped[int] = mapped_column(primary_key=True)
    reporter_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    target_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    booking_id: Mapped[int | None] = mapped_column(ForeignKey("bookings.id"), nullable=True)
    category: Mapped[str] = mapped_column(String(30))
    details: Mapped[str] = mapped_column(Text, default="")
    severity: Mapped[str] = mapped_column(String(10), default="normal")  # normal|critical
    status: Mapped[str] = mapped_column(String(12), default="open", index=True)  # open|resolved
    resolution: Mapped[str] = mapped_column(String(300), default="")
    resolved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class AuthToken(Base):
    """Single-use email-verification / password-reset tokens (stored hashed)."""
    __tablename__ = "auth_tokens"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    purpose: Mapped[str] = mapped_column(String(12))  # verify|reset
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    used: Mapped[bool] = mapped_column(Boolean, default=False)


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(60))
    target: Mapped[str] = mapped_column(String(60), default="")
    detail: Mapped[str] = mapped_column(String(400), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class LedgerEntry(Base):
    """Partner wallet ledger. Positive = money owed to the partner, negative = paid out / deducted."""
    __tablename__ = "ledger"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    booking_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    kind: Mapped[str] = mapped_column(String(24))  # earning|cancel_compensation|payout|payout_reversal|adjustment
    amount: Mapped[int] = mapped_column(Integer)
    available_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    note: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class PayoutRequest(Base):
    __tablename__ = "payout_requests"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    amount: Mapped[int] = mapped_column(Integer)
    upi: Mapped[str] = mapped_column(String(80))
    account_name: Mapped[str] = mapped_column(String(80), default="")
    status: Mapped[str] = mapped_column(String(12), default="requested", index=True)  # requested|paid|rejected
    reference: Mapped[str] = mapped_column(String(80), default="")  # UTR / transaction id
    reason: Mapped[str] = mapped_column(String(300), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class KycSubmission(Base):
    """ID check. Files are deleted as soon as an admin decides; we keep only the outcome."""
    __tablename__ = "kyc_submissions"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    id_type: Mapped[str] = mapped_column(String(20))
    id_file: Mapped[str] = mapped_column(String(80), default="")
    selfie_file: Mapped[str] = mapped_column(String(80), default="")
    status: Mapped[str] = mapped_column(String(12), default="pending", index=True)  # pending|approved|rejected
    reason: Mapped[str] = mapped_column(String(300), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class SupportTicket(Base):
    __tablename__ = "support_tickets"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(80))
    email: Mapped[str] = mapped_column(String(180))
    category: Mapped[str] = mapped_column(String(30), default="other")
    message: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(10), default="open", index=True)  # open|closed
    admin_reply: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
