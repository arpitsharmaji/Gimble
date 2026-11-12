import re
from datetime import date, datetime
from typing import Annotated
from pydantic import BaseModel, Field, AfterValidator, field_validator

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _email(v: str) -> str:
    v = v.strip().lower()
    if len(v) > 180 or not _EMAIL_RE.match(v):
        raise ValueError("Enter a valid email address")
    return v


Email = Annotated[str, AfterValidator(_email)]


class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    email: Email
    password: str = Field(min_length=8, max_length=128)
    dob: date
    gender: str = Field(default="", max_length=20)
    city: str = Field(min_length=2, max_length=100)
    role: str = "customer"
    accept_terms: bool = False


class LoginIn(BaseModel):
    email: Email
    password: str


class ForgotIn(BaseModel):
    email: Email


class ResetIn(BaseModel):
    token: str
    password: str = Field(min_length=8, max_length=128)


class TokenIn(BaseModel):
    token: str


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class DeleteAccountIn(BaseModel):
    password: str


class ProfileIn(BaseModel):
    headline: str = Field(default="", max_length=120)
    bio: str = Field(default="", max_length=1500)
    photos: list[str] = Field(default_factory=list, max_length=6)
    activities: list[str] = Field(default_factory=list, max_length=30)
    rates: dict[str, int] = Field(default_factory=dict)
    languages: list[str] = Field(default_factory=list, max_length=10)


class AvailabilityIn(BaseModel):
    available: bool


class BookingIn(BaseModel):
    partner_id: int
    activity: str
    scheduled_at: datetime
    duration_minutes: int = Field(default=60, ge=60, le=480)
    location: str = Field(min_length=3, max_length=200)
    note: str = Field(default="", max_length=1000)
    safety_ack: bool = False


class BookingStatusIn(BaseModel):
    status: str
    reason: str = Field(default="", max_length=300)


class ReviewIn(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: str = Field(default="", max_length=1000)


class MessageIn(BaseModel):
    receiver_id: int
    body: str = Field(min_length=1, max_length=2000)

    @field_validator("body")
    @classmethod
    def strip(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("Message is empty")
        return v


class ReportIn(BaseModel):
    target_id: int
    booking_id: int | None = None
    category: str
    details: str = Field(default="", max_length=2000)


class SosIn(BaseModel):
    booking_id: int | None = None
    note: str = Field(default="", max_length=500)


class CheckoutIn(BaseModel):
    plan: str = "monthly"


class VerifyPaymentIn(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


class AdminPartnerDecisionIn(BaseModel):
    approved: bool
    reason: str = Field(default="", max_length=300)


class AdminVerifyIn(BaseModel):
    verified: bool


class AdminSuspendIn(BaseModel):
    suspended: bool
    reason: str = Field(default="", max_length=300)


class AdminResolveIn(BaseModel):
    resolution: str = Field(default="", max_length=300)
    suspend_target: bool = False
