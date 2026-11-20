# Deploying Gimble to production

## Why your data kept disappearing (and what changed)

Gimble used to keep **everything on the server's local disk**: users, bookings and messages in a SQLite file, photos in an `uploads/` folder.
Most hosting platforms (Render, Railway, Heroku, Fly, Vercel-style containers, free tiers...) give your app a **temporary disk that is wiped on every
deploy, restart or sleep**. That is exactly why new users and photos vanished.

Production needs two things that live **outside** the app container:

| What | Production answer | Setting |
|---|---|---|
| Users, bookings, messages, payments | **PostgreSQL** (managed, or a Docker volume) | `DATABASE_URL` |
| Profile photos + ID documents | **S3-compatible bucket** (Cloudflare R2 / AWS S3 / ...) *or* a persistent disk volume | `STORAGE_BACKEND` |

To protect you from repeating this mistake, **Gimble now refuses to start in production** if it would store data on a disk that will be wiped
(SQLite without an explicit opt-in), or if the settings are otherwise unsafe. The error message tells you exactly what to fix.

---

## Path A - one server with Docker Compose (simplest, everything persistent)

Good for launch. A small VPS (2 GB RAM) from any provider is enough.

1. **Domain**: point an `A` record for e.g. `gimble.yourdomain.com` to the server's IP.
2. **Install Docker** on the server (Ubuntu): `curl -fsSL https://get.docker.com | sh`
3. **Copy the project** to the server (`git clone` or `scp`), then:
   ```bash
   cp .env.production.example .env.production
   nano .env.production      # fill: DOMAIN, PUBLIC_URL, JWT_SECRET, ADMIN_EMAIL, ADMIN_PASSWORD, POSTGRES_PASSWORD, SMTP_*
   ```
   Generate secrets with `python3 -c "import secrets; print(secrets.token_urlsafe(48))"`.
4. **Start everything**:
   ```bash
   docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build
   docker compose -f docker-compose.prod.yml logs -f app     # watch it start; Ctrl+C to leave
   ```
   Caddy fetches an HTTPS certificate automatically. Open `https://your-domain`.
5. **Check health**: `https://your-domain/api/health/deep` should show `{"database":"ok","storage":"ok",...}`. Put this URL in an uptime monitor (UptimeRobot, Better Stack).
6. **Log in** with `ADMIN_EMAIL` / `ADMIN_PASSWORD` and finish the [first-run checklist](#first-run-checklist).
7. **Set up backups** (below) - do this on day one.

Your data lives in Docker volumes (`pgdata`, `uploads`, `private`). `docker compose down` keeps them; **never** run `docker compose down -v` (that deletes them).

---

## Path B - a platform (Render / Railway / Fly.io) + managed Postgres + R2 bucket

Use this if you prefer not to manage a server. **The app container's disk is temporary on all of these**, so you need both of the following.

1. **Create a managed PostgreSQL database** (Render Postgres, Railway Postgres, Supabase, Neon...). Copy its connection string.
   > Free database tiers are often deleted after ~30 days or paused. Use a paid plan for a real launch.
2. **Create two buckets** (see [R2 setup](#cloudflare-r2-setup-photos--documents)): one for photos, one private for ID documents.
3. **Create a web service from this repo using the `Dockerfile`** at the repo root. Set the health check path to `/api/health`.
4. **Set environment variables** (from `.env.production.example`). The important ones:

   | Variable | Value |
   |---|---|
   | `APP_ENV` | `production` |
   | `DATABASE_URL` | the Postgres connection string (`postgres://...` is fine) |
   | `JWT_SECRET`, `ADMIN_EMAIL`, `ADMIN_PASSWORD` | your secrets |
   | `PUBLIC_URL` | `https://your-app-domain` |
   | `TRUST_PROXY` | `true` |
   | `STORAGE_BACKEND` | `s3` |
   | `S3_ENDPOINT_URL`, `S3_REGION`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY` | from your bucket provider |
   | `S3_PUBLIC_BUCKET`, `S3_PRIVATE_BUCKET` | the two bucket names |
   | `S3_PUBLIC_BASE_URL` | public/CDN URL of the photos bucket (optional, faster) |
   | `SMTP_*`, `MAIL_FROM` | your email provider |
   | `REQUIRE_VERIFIED_EMAIL` | `true` once SMTP works, otherwise `false` |

5. Deploy, open `/api/health/deep`, log in as admin.
6. Redeploy once, then confirm your test user and photo are **still there** - that proves persistence.

---

## Cloudflare R2 setup (photos + documents)

R2 has a generous free tier and no egress fees. Any S3-compatible service works the same way.

1. Cloudflare dashboard -> **R2** -> create bucket `gimble-photos` and bucket `gimble-private`.
2. **R2 -> Manage API tokens -> Create token** with *Object Read & Write* for both buckets. Copy the Access Key ID and Secret.
3. Your endpoint is `https://<ACCOUNT_ID>.r2.cloudflarestorage.com` (shown on the R2 page) -> `S3_ENDPOINT_URL`. Use `S3_REGION=auto`.
4. For fast photo loading, open `gimble-photos` -> **Settings -> Public access** -> connect a custom domain (e.g. `photos.yourdomain.com`) and set
   `S3_PUBLIC_BASE_URL=https://photos.yourdomain.com`. If you skip this, photos are served through the app (works fine, just uses the app's bandwidth).
5. **Never** enable public access on `gimble-private` - it holds ID documents. (They are also deleted as soon as an admin reviews them.)

AWS S3 users: leave `S3_ENDPOINT_URL` blank and set `S3_REGION` (e.g. `ap-south-1`).

---

## Email (SMTP)

Verification and password-reset emails need an SMTP service. Easy options: Brevo (free tier), Amazon SES, Zoho ZeptoMail, Resend (SMTP), your Google Workspace.
Set `SMTP_HOST`, `SMTP_PORT` (587), `SMTP_USER`, `SMTP_PASSWORD`, `MAIL_FROM`. Verify your sending domain (SPF/DKIM) so emails don't land in spam.
Until it works, set `REQUIRE_VERIFIED_EMAIL=false` and use **Admin -> Users -> Verify email** for people who need help.

---

## First-run checklist

- [ ] Log in as admin (`ADMIN_EMAIL` / `ADMIN_PASSWORD`) and **change the password** to something only you know.
- [ ] `/api/health/deep` shows database `ok` and storage `ok`.
- [ ] Register a test partner, upload photos, submit the profile; approve it in **Admin -> Approvals**.
- [ ] Register a test customer. Until Razorpay is live, give them access in **Admin -> Users -> Grant membership**.
- [ ] Message the partner from their profile, send a booking request, accept it, and walk through the flow.
- [ ] **Redeploy / restart, then confirm the users, photos and messages are still there.** (This is the test that matters.)
- [ ] Razorpay: add *test* keys first; add the webhook `https://your-domain/api/webhooks/razorpay` for `payment.captured`, `order.paid`, `payment.failed` and `refund.failed`; run a test payment and a test refund; only then switch to live keys.
- [ ] Have a lawyer finalise Terms / Privacy / Refund pages (they are drafts), and review GST / payments / DPDP obligations.
- [ ] Staff the admin queues (approvals, ID checks, reports, payouts, support).

---

## Backups (do not skip)

**Database** - nightly dump, kept 14 days:
```bash
# Docker Compose server:
docker compose -f docker-compose.prod.yml exec -T db pg_dump -U gimble gimble | gzip > backup-$(date +%F).sql.gz
# or, with DATABASE_URL set, anywhere:
backend/scripts/backup.sh          # add to cron:  0 3 * * *
```
Copy backups **off the server** (another bucket, rclone, your laptop). Managed Postgres providers also offer automatic backups - turn them on.

**Photos** - if you use a bucket, enable **object versioning** on it. If you use local volumes, back up the `uploads` volume too:
`docker run --rm -v gimble_uploads:/d -v $PWD:/b alpine tar czf /b/uploads-$(date +%F).tgz -C /d .`

**Restore** (test this once!): `gunzip -c backup-DATE.sql.gz | psql "$DATABASE_URL"`

---

## Updating the app

1. Take a backup. 2. `git pull` (or copy the new files). 3. `docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build`.
New database columns are added automatically at startup; nothing is ever dropped. For rollbacks, restore the backup and redeploy the old version.

---

## Moving data you already have

**SQLite -> PostgreSQL** (keeps every id, so bookings/messages/photos stay linked; refuses to overwrite a non-empty target):
```bash
cd backend
python scripts/migrate_sqlite_to_postgres.py sqlite:///./gimble.db "postgres://user:pass@host:5432/dbname"
```
Make a copy of the `.db` file first. Then set `DATABASE_URL` to the Postgres URL and restart.

**Local photos -> bucket**:
```bash
cd backend
STORAGE_BACKEND=s3 S3_ENDPOINT_URL=... S3_REGION=auto S3_ACCESS_KEY_ID=... S3_SECRET_ACCESS_KEY=... \
S3_PUBLIC_BUCKET=gimble-photos S3_PRIVATE_BUCKET=gimble-private python scripts/sync_uploads_to_s3.py ./uploads
```
(Photo links in the database don't change, so nothing else needs editing.)

---

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| App exits at start with `Unsafe production configuration: ...` | It lists every problem. Typical: default `JWT_SECRET`/admin password, `SEED_DEMO` or demo payments on, SQLite in production, S3 settings incomplete, `REQUIRE_VERIFIED_EMAIL=true` without `SMTP_HOST`. |
| Users/photos disappear after a deploy | You are on a temporary disk. Use Postgres (`DATABASE_URL`) and a bucket or persistent volume. See the top of this file. |
| Nobody can book ("verify your email") | Email isn't being delivered. Fix `SMTP_*`, or set `REQUIRE_VERIFIED_EMAIL=false` and verify users from the admin console. |
| Customers can't buy a membership | Razorpay keys aren't set. Add them, or grant memberships from **Admin -> Users**. |
| Photos show as broken images | With `S3_PUBLIC_BASE_URL`, check that URL opens a photo in your browser and that the bucket's public access/custom domain is on. Without it, check `/api/health/deep` -> storage. |
| Everyone gets "Too many attempts" | The app is behind a proxy but `TRUST_PROXY` isn't `true`, so all users look like one IP. Set `TRUST_PROXY=true`. |
| `502` right after deploy | Normal for ~20-40 s while the app starts and the database is prepared. Check the logs. |
| Password-reset / notification emails missing | SMTP not configured (the log says so at start-up) - or check your provider's spam/DKIM settings. |

---

## Be honest about what is still simple

- **Rate limiting is per process** (fine for a single server; add Redis/nginx limits when you scale to many servers).
- **Chat refreshes every few seconds** (polling), not instantly. WebSockets are a future upgrade.
- **Moderation is keyword-based**: a first line of defence, not a replacement for people reviewing reports.
- **Payouts to partners are sent manually** by your staff (Admin -> Payouts). Holding customer money and paying others may need specific RBI-regulated arrangements - get advice.
- The web app uses hash URLs, so search engines can't index individual profiles; add server-rendered pages when SEO matters.
