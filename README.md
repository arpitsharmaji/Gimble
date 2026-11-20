# Gimble - companion booking platform (v7)

FastAPI + SQLAlchemy backend, dependency-free vanilla-JS PWA frontend (served by the backend).
See **CHANGES.md** for the bugs found in the original upload and everything added.

## Deploying
Read **DEPLOY.md** - it explains why data vanished on hosting platforms and how to run Gimble with permanent storage.

## What's in v4
A swipe-first browsing experience, a redesigned landing page and a polished app shell - see **CHANGES.md** and `docs/screenshots/`. First start generates illustrated demo portraits (takes a few seconds).

## Run locally
```bash
cd backend
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```
Open http://localhost:8000 (API docs: /docs). Run tests: `python -m pytest tests -q`.

Demo logins (password `DemoPass123!`): `demo@gimble.local` (customer), `aanya@gimble.local` (partner).
Admin: `admin@gimble.local` / the `ADMIN_PASSWORD` in `.env`.
In dev, verification / reset links are returned in the API response and shown in the UI (no email server needed).

Docker: `docker compose up --build` (Postgres included).

## Money model (read this)
Customers pay a membership to send requests, then pay each booking **through Gimble** after the partner accepts. Gimble holds it, credits the partner's wallet 24 h after completion (minus `PLATFORM_FEE_PERCENT`), and the partner withdraws to UPI. **Payouts are sent manually** by your staff (Admin → Payouts → record the UTR) - there is no automatic bank transfer. Holding customer money and paying out third parties may require specific RBI-regulated arrangements (e.g. Razorpay Route / a nodal account); get advice before going live.

## Before a real launch (honest checklist)
1. **Legal**: Terms/Privacy pages are *drafts*. Get an Indian lawyer to review (companionship platforms attract scrutiny - keep the no-sexual-services rule and moderation intact), plus GST/invoicing and DPDP Act compliance.
2. **Set `APP_ENV=production`**: the app refuses to start with default secrets, demo payments or demo seed data.
3. **Razorpay**: add test keys, test checkout, refunds and the webhook (`POST /api/webhooks/razorpay`, events `payment.captured`, `order.paid`, `payment.failed`, `refund.failed`), then live keys. The gateway code follows Razorpay's documented API but has only been tested with simulated responses.
4. **Email**: set `SMTP_*` (e.g. SES/Brevo) and `REQUIRE_VERIFIED_EMAIL=true`.
5. **ID verification** is a manual admin review (files deleted after the decision). Integrate a KYC provider for scale. SEO: the app uses hash routes, so search engines can't index individual pages - for SEO, add server-rendered landing/profile pages.
6. **Scale-out**: rate limiter and chat polling are in-process/simple. Add Redis + WebSockets, Alembic migrations, S3 for photos, HTTPS + a reverse proxy (`TRUST_PROXY=true`), backups, monitoring.
7. **Moderation** is keyword-based - a first line, not a substitute for human review. Staff the admin Reports queue.
8. Auth token lives in localStorage (mitigated by auto-escaping templates + CSP); move to httpOnly cookies + CSRF protection if you want stricter.

## Layout
`backend/app/routers/*` API · `backend/app/moderation.py` content rules · `backend/tests/` · `frontend/js/*` UI modules.

## Manual UPI QR payments (no gateway needed)

Used automatically when Razorpay keys are blank and `UPI_ID` is set (Razorpay stays in the code and takes over if you add keys later).

1. Set `UPI_ID`, `UPI_PAYEE_NAME` in `backend/.env` and **replace `frontend/upi-qr.png` with your own UPI QR image**.
2. Customer clicks Membership / Pay on a booking -> sees the QR, pays the exact amount (typed in their UPI app), then submits the UTR + a screenshot.
3. It appears in **Admin -> Payments**, tagged *Membership* or *Companion booking*, with the expected amount, UTR and screenshot. Check your bank/UPI statement, then **Approve** (membership activates / booking is confirmed) or **Reject** with a reason.
4. Refunds for manually paid bookings wait in the admin Bookings tab as `refund_pending`: send the UPI refund yourself, then click **Mark refunded** and enter its UTR.

Safeguards: the amount is set by the server, UTRs and identical screenshots can't be reused, only admins can see proofs, and a booking isn't auto-cancelled while its proof awaits review.
