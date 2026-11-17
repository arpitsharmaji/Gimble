# Gimble v7 - production readiness (messaging + permanent storage)

**1. Messaging before booking.** Customers with a membership can now message a partner straight from their profile (new 💬 Message button; also in the
swipe-details sheet). Safeguards: only customers can start a chat, only to live partners; up to **3 messages until the partner replies**; no phone numbers,
links or payment requests until a booking is accepted; partners can't cold-message anyone; blocking works; the partner gets a notification/email for a first
message. Once the partner replies the chat is fully open. Chat UI shows a "Book" shortcut, starter replies, a messages-left hint and a clear locked state
("membership needed" / "wait for a reply"). Messages tab lists inquiries as well as booking chats.

**2. Data no longer disappears.** Root cause: users/bookings lived in a SQLite file and photos in a local folder, which most hosts wipe on every deploy.
* Real **PostgreSQL** support (tested on PostgreSQL 16: full suite + a restart-persistence run with 2 workers), `postgres://` URLs accepted, connection pooling,
  start-up lock so several workers can boot together safely.
* Pluggable **file storage**: local folder *or* any S3-compatible bucket (R2/S3/B2/Spaces) with a **separate private bucket** for ID documents. Optional
  CDN URL for photos. Existing `/uploads/...` links keep working. Tested against a mocked S3.
* **Safety net:** in production the app refuses to start on SQLite (unless you explicitly opt in for a persistent disk), on incomplete S3 settings, or with
  `REQUIRE_VERIFIED_EMAIL=true` but no SMTP (which would lock everyone out of booking).
* `/api/health/deep` checks database *and* storage for uptime monitors.
* Tools: SQLite -> Postgres migration script (verified: identical row counts, ids preserved, sequences continue), local photos -> bucket sync, nightly backup script.
* Admin: **Grant membership** and **Verify email** buttons (for launch before Razorpay/SMTP are ready, and for support).

**3. Deployment kit:** production `Dockerfile` (the old one didn't include the frontend), `docker-compose.prod.yml` (Postgres + app + Caddy HTTPS, persistent volumes),
`Caddyfile`, `.env.production.example`, and a step-by-step **DEPLOY.md** (VPS path and platform path, R2 walk-through, checklist, backups, troubleshooting).

Tests: 44 backend tests (also run green on PostgreSQL via `TEST_DATABASE_URL`).

---

# Gimble v6 - UI polish pass (bookings, chat, dashboard, account, booking flow)

The browse / landing / profile pages already had the new look; v6 brings the rest of the app up to the same standard.

**Booking flow**: the raw date box is replaced by a Calendly-style picker: next 14 days, 30-minute time slots that respect the partner's weekly hours and the 2-hour lead time, duration chips, public-venue suggestions and a live price summary. Confetti on a sent request, a payment, an accepted booking and a review.

**Bookings page**: Upcoming / Pending / Past tabs with counts, a progress timeline (Requested -> Accepted -> Paid -> Done), countdown ("in 1d 5h"), calendar-style date chip, Google Maps link for the venue, **Add to calendar (.ics)**, "Book again", cleaner pay-now banner and refund notes.

**Chat**: conversation list with photos, last message and plan chip; thread header with the *next* plan as context; day separators, grouped gradient bubbles, "Seen" ticks, quick replies ("On my way", "Running late"...), dismissible safety tip, auto-growing composer, options menu (report / block).

**Partner dashboard**: greeting + status chip, profile-strength ring with next steps, stats cards, **inbox with one-tap accept / decline**, copy-profile-link, sectioned profile editor with a sticky save bar.

**Account**: profile header, membership card with days-left bar, quick links, tidy security / blocked / legal sections.

**Smaller touches**: notifications sheet grouped by day with icons; sign-up with role cards, show/hide password, password-strength meter and live 18+ check; icon toasts; illustrated empty states; rating breakdown and "More companions in <city>" on profiles; saved page header; new footer.

## Bug found and fixed
**Navigation race**: logging in as an admin/partner starts loading the home page and then redirects to the dashboard/admin; if the slower home render finished last it overwrote the page you were on. Each navigation now renders into its own fresh container, so a stale render can never replace the current page.

## Backend (small)
Chat and booking APIs now return the partner's photo and a booking context (next upcoming plan) - 1 new test (30 total).

## Testing
30 backend tests; 70 scripted UI checks (new: wizard, tabs/stepper, chat quick replies, notifications, account, profile extras, sign-up polish); real Chrome screenshots at 390x844 and 1440x900 in `docs/screenshots/`.

---

# Gimble v5 - rebrand

* **New name: Gimble** (was PairUp) everywhere: UI copy, emails, legal pages, API title, Razorpay checkout name, config, database file, Docker names, localStorage keys, demo accounts (`demo@gimble.local`, `aanya@gimble.local`, `admin@gimble.local`).
* **Your logo** is now the app logo. The white background *and* the white inside the heart are transparent (clean anti-aliased edges, checked on dark, light and checkerboard). Used in the header, footer, welcome screen, landing-page phone mockup, favicon, home-screen/PWA icons (dark tile with safe padding so Android circle/squircle crops look right) and share image tag. Source files are in `docs/brand/`.
* **Brand colours follow the logo**: the accent moved from coral-pink to the logo's violet -> orchid gradient (buttons, headline, glows, active states, confetti, Razorpay checkout colour). Text on gradient buttons is now white.
* Upgrade note: login/localStorage keys were renamed, so existing browsers will be signed out once. A dev database created under the old name is simply not picked up (new `gimble.db`).

Verified: 29 backend tests, 55 scripted UI checks, and real Chrome screenshots (`docs/screenshots/gimble_*`).

---

# Gimble v4 - frontend overhaul (swipe browsing, landing page, polish)

**Focus: the experience people see.** Backend is unchanged except demo data (below). Screenshots are in `docs/screenshots/`.

## Swipe browsing (Tinder/Bumble-style)
* Full-bleed card deck with real gesture physics: drag with rotation, fling velocity, SAVE / PASS stamps, a 3-card stack that scales forward as you drag, spring-back on small drags. Mouse, touch and pen all work.
* Tap the photo edges to flip through photos (story-style progress bars), tap the middle or swipe up for a details sheet with rates and a booking button.
* Undo (rewind) the last swipe, keyboard shortcuts on desktop (← → ↑), haptics on supported phones, heart burst on save, images preloaded for smooth swiping, more profiles load automatically.
* Mobile opens in swipe mode by default (fits the screen between header and bottom nav, no page scroll); desktop defaults to a photo-led grid with infinite scroll. Toggle any time.
* Category chips (Airbnb-style), a filters bottom-sheet, sticky search.
* Swiping right as a guest prompts login without interrupting; undoing a swipe-save removes the favourite.

## Landing page (mobile + desktop)
Editorial hero with gradient serif accent, an animated phone mockup that swipes through real featured profiles, floating trust badges, search pill, scrolling activity marquee, count-up live stats, "how it works", featured carousel, bento safety grid, colourful activity tiles, testimonials, interactive partner earnings calculator, pricing, FAQ, final CTA. Scroll-reveal animations; respects *reduce motion*.

## App-like first run
Three-slide onboarding (also the 18+ confirmation) on first visit, page transitions, glass header that changes on scroll, bottom-sheet modals with a drag handle on mobile, redesigned profile (swipeable gallery, floating "from ₹X - Request booking" bar).

## Visual system
Self-hosted fonts (Inter, Bricolage Grotesque, Instrument Serif - OFL licensed, no external requests so the CSP stays strict), refreshed palette and components.

## Demo data
Demo partners now have **illustrated placeholder portraits** generated at first start (`backend/app/demo_art.py`) - no real people or stock photos. Demo ratings/review counts are derived from the real seeded review rows. Real partners upload their own photos as before.

## Bugs found by screenshotting in a real browser (jsdom tests could not see these)
| Bug | Fix |
|---|---|
| `class="browse grid"` collided with the `.grid` card layout and collapsed the whole page | view classes renamed `v-grid` / `v-deck` |
| Onboarding content shifted off-screen; "Leave" showed on slide 1 (`.btn` display overrode `hidden`) | grid minmax track + global `[hidden]` rule |
| Profile: "ID verified" chip stretched into a tall box; gallery slid under the header | positioning fixes |
| Filter bar had a visible dark box; view toggle overflowed on phones | transparent bar, compact controls |
| Hero glow clipped to hard vertical edges on desktop | full-bleed background |
| Details-sheet close button scrolled out of view | sticky close button |

## Testing
29 backend tests, 55 scripted UI checks (landing, onboarding, swipe gestures incl. drag/fling/tap, undo, filters, booking, payment, partner, admin), plus real Chrome screenshots at 390x844 and 1440x900 with real touch input.

---

# Gimble v3 - what's new

v2 fixed the bugs in the original upload (path traversal, broken demo logins, email leak, broken booking rules, etc.). v3 adds the product features a rent-a-companion marketplace needs to actually operate.

## Landing page & marketing pages
Real home page (`#/`): hero with city + activity search, **live stats from your database (nothing invented)**, how-it-works, popular plans, featured partners, cities, safety section, real testimonials (only appear once reviews exist), membership pricing, partner CTA, FAQ. Plus: Browse (`#/browse`, now accepts `?city=` / `?activity=` links), FAQ, Become-a-partner, Help & Support, Refund policy.

## Money (booking payments, earnings, payouts, refunds)
* Customer pays **after the partner accepts**; Gimble holds the money (no more advance-payment scams).
* Partner earns price minus platform fee, released to a wallet 24 h after completion (dispute window).
* Cancellation policy enforced in code: 100% refund if 24 h+ before, 50% at 2-24 h, 0% under 2 h; partner/Gimble cancellations always refund 100%. The retained part compensates the partner.
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
