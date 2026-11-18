# Phase 02 — Public Platform

Phase 02A completes the backend identity lifecycle for Module 01 and the account export required by Section 7.2. Phase 02B will build the Next.js frontend against these APIs. The Phase 01 checkpoint on `feat/v2-foundation` is `d0a42e6`.

**Phase 02A status: complete — November 19, 2026.** Phase 02B has not started. The Phase 01 checkpoint uses the requested commit message, `feat(phase-01): complete engineering foundation and security hardening`; Phase 02A changes remain separate in the working tree.

## Phase 02A — Identity and privacy API

| Endpoint | Behavior |
|---|---|
| `POST /api/v1/auth/verify-email/request` | Requires an active session. For an unverified account, issues a token valid for 24 hours and invalidates previous unused email verification tokens. |
| `POST /api/v1/auth/verify-email/confirm` | Accepts `{ "token": "..." }`. Consumes the token once and marks the account verified. |
| `POST /api/v1/auth/password-reset/request` | Accepts `{ "email": "..." }`. Returns the same 200 status and message for known and unknown addresses. For a known address, issues a token valid for 20 minutes. |
| `POST /api/v1/auth/password-reset/confirm` | Accepts `{ "token": "...", "new_password": "..." }`. Consumes the token once, saves an Argon2id hash, and revokes every active session for the account. |
| `POST /api/v1/auth/password-change` | Requires an active session and accepts `{ "current_password": "...", "new_password": "..." }`. Checks the current password, saves an Argon2id hash, and revokes the other active sessions. |
| `DELETE /api/v1/users/me/sessions/{session_id}` | Revokes an active session owned by the caller. Returns 204 on success and 404 for foreign, inactive, or missing sessions. |
| `GET /api/v1/users/me/export` | Returns JSON with account, profile, preferences, all owned papers, active session metadata, and account audit history. Credential material and verification tokens are excluded. |
| `GET /api/v1/users/me/dashboard` | Returns the account and profile, verification status, language and privacy preferences, saved-paper count, up to five recent papers, active-session count, and up to five recent activity events. |

The database stores SHA-256 hashes of random, URL-safe tokens. Token purpose, expiry, and unused status are checked when claiming a token. Successful consumption, account changes, session revocation where applicable, and audit recording commit together. Audit events cover verification and reset requests and completion, password changes, individual session revocation, and export. Account export and dashboard responses are marked `Cache-Control: no-store`.

Token issuance is limited to five requests per account and purpose within ten minutes by default. Issuance and consumption serialize on the account row. Password changes also invalidate outstanding reset tokens, and login rechecks the verified password hash under the same lock before creating a session. Validation errors omit input values so they cannot echo credentials.

Migration `b21c4b995d13` follows `8ad1e721e53b`. Existing accounts default to `is_verified=false`. New saved papers record when they were added. Older papers receive the migration timestamp because their original save time is unavailable. Recent papers use descending creation time and ID to break ties.

Configure TLS SMTP to enable email delivery. The API process sends email in the background after responding. For authenticated email verification, `DEBUG=true` with `APP_ENV=local`, `development`, or `test` enables a `debug_token` in the response. Password reset always uses the mail adapter, which tests substitute to capture the token. See [backend/.env.example](../../backend/.env.example).

With `SMTP_HOST` unset, no email is sent and the reset response remains generic. Configure `SMTP_HOST`, `SMTP_FROM`, and optional `SMTP_USERNAME`/`SMTP_PASSWORD` before enabling public recovery. Delivery always uses certificate-verified TLS: STARTTLS defaults to port 587, while `SMTP_USE_SSL=true` defaults to port 465. Optional `SMTP_PORT` overrides that choice. SMTP errors produce a safe warning; the current in-process background task is not a durable delivery queue. Validate real mail delivery and failure handling before public rollout.

### Verification

| Check | Result |
|---|---|
| Full backend suite | **192 passed**, zero failures, skips, or warnings in **29.05 seconds**. |
| Application statement coverage | **97.39%** (1,074 statements, 28 uncovered). |
| PostgreSQL concurrency regression tests | Five cases passed: single-use verification/reset under competing confirmation, one current token after competing issuance for each purpose, and rejection of a stale-password login after replacement. |
| PostgreSQL 18.6 Alembic CLI | `upgrade head -> downgrade base -> upgrade head` passed at `b21c4b995d13`. |
| Alembic model/schema comparison | `alembic check` reported no new upgrade operations. |
| Populated upgrade regression | Existing users and paper rows survived the upgrade; verification defaults to false and legacy paper timestamps are backfilled. |
| Ruff, Black, and whitespace | `ruff check .`, `black --check .`, and `git diff --check` passed. |
| CI configuration | Added a separate disposable identity test database so concurrency tests and migration round trips run independently; YAML configuration checks passed locally. The hosted workflow was not run from this task. |

The suite ran from `backend/` with Python 3.13.16 and pytest 9.1.1. Set `APP_NAME`, a test-only `SECRET_KEY`, and `DATABASE_URL=sqlite://` for the isolated application fixtures. Set `TEST_MIGRATION_DATABASE_URL` and `TEST_IDENTITY_DATABASE_URL` to two separate, empty, disposable PostgreSQL databases to include both live database groups. Without these variables the respective database tests skip. The recorded run set both variables, so no tests were skipped.

The live tests deliberately create and remove schema. Never point their database URLs at a development or production database containing application data. The independent CLI verification also used a disposable database, not the application's configured data store.

## Phase 02B — Frontend checklist

- [ ] Scaffold the Next.js and TypeScript app with a typed client for `/api/v1`, local environment configuration, and CI checks for lint, types, tests, and production build.
- [ ] Set up browser session handling and protected routes. Keep credentials out of URLs, browser logs, and persistent JavaScript storage. Define CSRF protection for any cookie-based transport.
- [ ] Build registration, sign-in, sign-out, email verification, resend, password reset, and password change. Test expired or reused tokens and sign-in after other sessions are revoked.
- [ ] Build the dashboard with profile and verification status, saved papers, active sessions, and recent activity. Include empty, loading, error, and signed-out states.
- [ ] Build account settings for English and Bangla language preferences, theme, privacy, external AI consent, session revocation, data export, and account deletion.
- [ ] Verify registration through dashboard use and account recovery in end-to-end tests. Before public launch, validate real email delivery and apply rate limits to request and resend endpoints.
