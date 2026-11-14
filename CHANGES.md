# PairUp v4 - frontend overhaul (swipe browsing, landing page, polish)

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
