# Verification status

- Python/Flask unit checks: **13 passed**. These cover login/signup page rendering, CSRF protection (including malformed tokens), authentication guard, signup input validation, scrypt hashing, parameterized search, database outage handling and missing-page handling.
- Home, signup and login templates were rendered using Flask's test client. The home-page rendering used a mocked database, not a real MySQL connection.
- All six local JPEG assets were downloaded and decoded successfully.
- MySQL integration test: **1 skipped**, because no MySQL server or Docker daemon was available in the creation environment. The opt-in test is included in `tests/test_app.py`; it exercises account creation, login, logout, duplicate accounts, save/remove, separate-user isolation and persistence using a fresh database connection.
- Docker and public deployment: **not run**. Deployment requires a suitable server/hosting account.
- Browser screenshot/mobile visual QA: **not completed**; no Chromium binary was installed, and its download failed. Responsive media queries are included, but should be reviewed in your local browser before submission.

The project must pass the included MySQL integration test and a live deployment check before claiming that the club's public deployment requirement is complete.

## Booking feature verification (2026-10-01)

- `.venv/Scripts/python -m pytest -q`: **27 passed, 1 skipped**.
- `node --check static/booking.js`: passed.
- Python compilation checks passed for app.py and tests/test_app.py.
- Booking tests cover server-calculated prices, invalid guests/dates, overlap and duplicate-request handling, CSRF/authentication, private booking queries, saved totals/durations, login draft preservation, and missing properties.
- Database interactions in these booking tests use mocks. The existing opt-in MySQL integration test was skipped; no live MySQL server or browser interaction was verified in this environment.
- Run `python -m flask --app app:create_app init-db` with your configured MySQL connection before using bookings on an existing installation. This creates the new table without deleting existing data.
