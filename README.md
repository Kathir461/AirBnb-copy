# Airbnb-inspired club project

A responsive, independent educational recreation using **HTML, CSS, Python Flask and MySQL**. No JavaScript framework, SQLite or browser storage. Demo stays are fictional, with illustrative Unsplash photographs; this is not affiliated with Airbnb and supports demo reservations without payments.

## Included

- Home page with six seeded properties, destination search and category filters.
- Dedicated sign-up and login pages; validation and readable errors.
- Real MySQL user accounts; Werkzeug scrypt password hashing.
- Signed, HttpOnly, SameSite sessions; CSRF tokens on every POST.
- MySQL-backed login throttling (10 failed attempts per email per 15 minutes).
- Property details with guest selection (adults 13+, children under 13), dates, room details and sample facilities.
- Floating booking total, confirmed reservations saved in MySQL, and a private Bookings page.
- Server-side date/capacity checks, overlapping reservation prevention, and duplicate-submit protection.
- Protected wishlist: save, view and remove stays. Each user's data is isolated.
- Persistent MySQL Docker volume; responsive CSS; accessible labels and focus states.
- Gunicorn, Docker Compose and an optional Caddy HTTPS deployment.

## Quick start — Docker (recommended)

Install Docker Desktop with Compose. Extract this folder, then open it in VS Code.

1. Copy `.env.example` to `.env` (Windows: `copy .env.example .env`; macOS/Linux: `cp .env.example .env`).
2. Generate a secret:
   ```sh
   python -c "import secrets; print(secrets.token_hex(32))"
   ```
3. Put the result in `SECRET_KEY` in `.env`. Set different strong values for `MYSQL_PASSWORD` and `MYSQL_ROOT_PASSWORD`. Keep `COOKIE_SECURE=0` locally.
4. Start:
   ```sh
   docker compose up --build -d
   ```
5. Open **http://localhost:8000**. MySQL starts first, and the web container creates tables and seeds stays automatically. The first startup may take a minute.
6. Create your own demo account, save a stay, log out, and log back in to see it persisted.

Stop with `docker compose down`. This preserves accounts and saved stays. **Do not use `down -v` unless you intend to delete all database data.**

View logs: `docker compose logs web`. Changing MySQL passwords in `.env` does not change credentials in an already initialized volume; use MySQL user management for an existing database.

## Without Docker — existing local MySQL

Use Python 3.12 and MySQL 8. Run the following in MySQL as an administrator, replacing the password:

```sql
CREATE DATABASE stayclub CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'stayuser'@'localhost' IDENTIFIED BY 'your-strong-password';
GRANT ALL PRIVILEGES ON stayclub.* TO 'stayuser'@'localhost';
```

Create `.env` as above and set `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD` to your own MySQL connection. Then:

```sh
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS/Linux, instead:
# source .venv/bin/activate
python -m pip install -r requirements.txt
python -m flask --app app:create_app init-db
python -m flask --app app:create_app run
```

Open **http://127.0.0.1:5000**. The Flask development server is for local use only.

## Public deployment — Flask + MySQL + HTTPS

The project has **not been publicly deployed**. Deployment needs access to your server/hosting account. The following is a reproducible deployment for a Linux server with Docker Compose and a domain:

1. Copy the source to your server; keep `.env` private and out of Git.
2. Point the domain's DNS A record to the server. Allow inbound TCP 80/443.
3. Set production secrets in `.env`, `COOKIE_SECURE=1`, and add `SITE_DOMAIN=your-actual-domain` (no scheme or path).
4. Run:
   ```sh
   docker compose -f compose.yaml -f compose.production.yaml up --build -d
   ```
5. Caddy obtains HTTPS certificates and forwards requests to Gunicorn. Open `https://your-actual-domain`, create an account, and verify saving/removing stays. MySQL is private; it has no published host port.

For a managed container host, deploy the Dockerfile with a managed **MySQL** database and set `SECRET_KEY`, `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_DATABASE`, `MYSQL_USER`, `MYSQL_PASSWORD` and `COOKIE_SECURE=1`. Supply `MYSQL_SSL_CA` when using a provider CA. The container uses the provider's `PORT` or 8000. Use `/health` for readiness. Your database user must have permissions to create tables during initialization. Back up MySQL regularly. Host/domain costs depend on your provider.

## Project layout

```text
app.py                       Flask routes, authentication, database access
schema.sql                   MySQL tables and fictional sample listings
templates/                   Jinja HTML pages and property cards
static/style.css             Responsive styling
static/images/               Local illustrative photographs
image-sources.json           Original image sources
requirements.txt             Python dependencies
Dockerfile                   Production Gunicorn container
compose.yaml                 Web + persistent MySQL
compose.production.yaml      Optional public HTTPS reverse proxy
Caddyfile                    HTTPS configuration
tests/                       Unit and opt-in MySQL integration checks
```

## Verification

```sh
python -m pip install pytest
python -m pytest -q
```

Unit tests check form protection, validation, page rendering, hashing and error handling. A separate opt-in integration test requires a **dedicated test MySQL database**. Set `MYSQL_DATABASE=stayclub_test` and its connection variables, then `RUN_MYSQL_TESTS=1 python -m pytest -q` (PowerShell: `$env:RUN_MYSQL_TESTS='1'`). It creates test accounts, verifies login and wishlist isolation, reconnects to check persistence, then deletes its test users.

In the creation environment, no MySQL server or Docker daemon was available. See `VERIFICATION.md` for checks actually run. Run the integration test against MySQL before submitting a live deployment.

## Club demonstration

1. Show the home, sign-up and login pages.
2. Register two accounts with unique demo credentials.
3. Save a stay in account A, log out and sign into B: B's wishlist is empty.
4. Return to A: its saved stay remains; remove it.
5. Restart the containers and show persistence.
6. In MySQL, inspect `users.password_hash` to demonstrate that passwords are hashes.

No email verification, password reset or payment flow is included. These are outside this club task's scope. Do not use this educational project to collect real Airbnb credentials.

## Booking setup for an existing installation

Run `python -m flask --app app:create_app init-db` from this directory, then restart Flask. This adds the bookings table without deleting existing accounts or stays. Docker runs initialization automatically when its web container starts.

Click a property image or title, select adults and children (ages 0?12), then check-in and check-out. At least one adult is required, and all guests count toward the property's capacity. Each listing is an entire property with one reservation available per night. Check-out day can be another booking's check-in day.

The floating bar shows the total at the property's nightly rate, with no extra fees. A three-night stay spans four calendar days; pricing uses nights only. Past dates are checked using India time. Sign in to confirm; Bookings shows only the signed-in user's reservations. Confirmation does not collect payment. Facilities are illustrative demo details.
