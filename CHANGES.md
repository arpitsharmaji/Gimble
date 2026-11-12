# PairUp v3 - what's new

v2 fixed the bugs in the original upload (path traversal, broken demo logins, email leak, broken booking rules, etc.). v3 adds the product features a rent-a-companion marketplace needs to actually operate.

## Landing page & marketing pages
Real home page (`#/`): hero with city + activity search, **live stats from your database (nothing invented)**, how-it-works, popular plans, featured partners, cities, safety section, real testimonials (only appear once reviews exist), membership pricing, partner CTA, FAQ. Plus: Browse (`#/browse`, now accepts `?city=` / `?activity=` links), FAQ, Become-a-partner, Help & Support, Refund policy.

## Money (booking payments, earnings, payouts, refunds)
* Customer pays **after the partner accepts**; PairUp holds the money (no more advance-payment scams).
* Partner earns price minus platform fee, released to a wallet 24 h after completion (dispute window).
* Cancellation policy enforced in code: 100% refund if 24 h+ before, 50% at 2-24 h, 0% under 2 h; partner/PairUp cancellations always refund 100%. The retained part compensates the partner.
* Unpaid accepted bookings auto-cancel 30 min before start; bookings need 2 h lead time.
* Partner wallet + ledger, UPI payout requests (needs ID verification, min amount), admin payout queue with UTR recording, reject-returns-funds, manual adjustments, refund retry.
* Razorpay: order creation, HMAC verification, idempotent webhook for **both** membership and bookings, gateway refunds, auto-refund if someone pays for an already-cancelled booking.

## Trust & operations
* **ID verification**: partner uploads ID + selfie to *private* storage; admin reviews; files are **deleted on decision**; approval = ✓ badge and unlocks payouts.
* Partner **weekly hours** (IST) enforced when booking.
* Partner **replies to reviews**.
* **Support tickets** (visitors + members) with admin reply by email.
* Email notifications for bookings, payments, payouts, ID checks (SMTP, or logged in dev).
* Admin console: finance overview, ID checks, payouts, support, payment status per booking, refund retry.
* **In-place database upgrade** (`migrate.py`) - verified against a real v2 database.

## Bug found and fixed during v3 testing
The browser test showed a new rule I'd written would instantly cancel any booking made less than 2 h ahead (the form defaulted to 45 min). Fixed: 2 h minimum lead time, 30 min payment deadline, partners can't accept requests too close to the start. Covered by a test.

## Tests
28 backend tests (money flows, refunds, payouts, KYC, schedule, support, webhook idempotency, migration) + a 40-step browser-simulation run across landing, booking, payment, partner and admin flows.
