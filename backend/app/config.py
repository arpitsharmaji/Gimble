"""Central configuration. Every setting comes from environment variables / .env."""
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")

DEFAULT_JWT = "local-development-secret-change-before-launch"
DEFAULT_ADMIN_PW = "ChangeMe_Admin_123!"


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


class Settings:
    APP_ENV = os.getenv("APP_ENV", "development").lower()
    DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'pairup.db'}")
    JWT_SECRET = os.getenv("JWT_SECRET", DEFAULT_JWT)
    ACCESS_TOKEN_MINUTES = int(os.getenv("ACCESS_TOKEN_MINUTES", "10080"))

    ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@pairup.local").lower()
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", DEFAULT_ADMIN_PW)

    SEED_DEMO = _bool("SEED_DEMO", os.getenv("APP_ENV", "development").lower() != "production")
    DEMO_PAYMENTS_ENABLED = _bool("DEMO_PAYMENTS_ENABLED", os.getenv("APP_ENV", "development").lower() != "production")
    REQUIRE_VERIFIED_EMAIL = _bool("REQUIRE_VERIFIED_EMAIL", os.getenv("APP_ENV", "development").lower() == "production")
    RATE_LIMIT_ENABLED = _bool("RATE_LIMIT_ENABLED", True)
    TRUST_PROXY = _bool("TRUST_PROXY", False)

    PRIVATE_DIR = Path(os.getenv("PRIVATE_DIR", str(BASE_DIR / "private")))  # KYC files; never served publicly
    PLATFORM_FEE_PERCENT = int(os.getenv("PLATFORM_FEE_PERCENT", "15"))
    MIN_PAYOUT_INR = int(os.getenv("MIN_PAYOUT_INR", "500"))
    PAYOUT_HOLD_HOURS = int(os.getenv("PAYOUT_HOLD_HOURS", "24"))
    SUPPORT_EMAIL = os.getenv("SUPPORT_EMAIL", "support@pairup.local")
    UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", str(BASE_DIR / "uploads")))
    MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(5 * 1024 * 1024)))
    PUBLIC_URL = os.getenv("PUBLIC_URL", "http://localhost:8000").rstrip("/")

    # Razorpay (India). Leave blank to run without a gateway (demo mode only).
    RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "")
    RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "")
    RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")

    # Email. Without SMTP_HOST, emails are printed to the server log (dev only).
    SMTP_HOST = os.getenv("SMTP_HOST", "")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
    MAIL_FROM = os.getenv("MAIL_FROM", "PairUp <no-reply@pairup.local>")

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @property
    def booking_payments_on(self) -> bool:
        return self.razorpay_enabled or self.DEMO_PAYMENTS_ENABLED

    @property
    def razorpay_enabled(self) -> bool:
        return bool(self.RAZORPAY_KEY_ID and self.RAZORPAY_KEY_SECRET)


settings = Settings()

# Amounts are in INR. These are *proposed* prices; confirm before launch.
PLANS = {
    "monthly": {"label": "Monthly", "amount": 500, "days": 30},
    "annual": {"label": "Annual", "amount": 4500, "days": 365},
}

ACTIVITY_SUGGESTIONS = [
    "Video call", "Coffee date", "Movie companion", "Dinner", "Shopping",
    "Gym partner", "City exploration", "Event / concert plus-one", "Cafe study partner",
    "Language practice", "Sports partner", "Museum / gallery visit", "Board games",
]


def validate_for_production() -> None:
    if not settings.is_production:
        return
    problems = []
    if settings.JWT_SECRET == DEFAULT_JWT or len(settings.JWT_SECRET) < 32:
        problems.append("JWT_SECRET must be a unique random string of 32+ characters")
    if settings.ADMIN_PASSWORD == DEFAULT_ADMIN_PW or len(settings.ADMIN_PASSWORD) < 12:
        problems.append("ADMIN_PASSWORD must be changed (12+ characters)")
    if settings.DEMO_PAYMENTS_ENABLED:
        problems.append("DEMO_PAYMENTS_ENABLED must be false in production")
    if settings.SEED_DEMO:
        problems.append("SEED_DEMO must be false in production")
    if problems:
        raise RuntimeError("Unsafe production configuration: " + "; ".join(problems))

# Cancellation policy for a customer cancelling an accepted, paid booking
REFUND_FULL_HOURS = 24   # >= 24h before start: 100% refund
REFUND_HALF_HOURS = 2    # 2-24h before start: 50% refund; under 2h: no refund
PAY_DEADLINE_MINUTES = 30   # accepted bookings must be paid this long before the start
MIN_LEAD_MINUTES = 120      # customers must book at least this far ahead
ACCEPT_MIN_LEAD_MINUTES = 45  # partners can't accept a request this close to the start (no time to pay)
KYC_ID_TYPES = ["aadhaar", "pan", "passport", "driving_licence", "voter_id"]
SUPPORT_CATEGORIES = ["booking", "payment_refund", "account", "safety", "partner_application", "other"]
