# Phase 01 — Engineering Foundation & Security Hardening

**Goal:** Establish the v2 engineering base and close foundational migration, authentication, and tenant-isolation gaps before adding broad product features. This is a work checklist; unchecked items are not represented as completed.

**Status:** Phase 01A and Phase 01B deliverables are complete. The checklist also tracks broader architecture and security work that carries forward beyond these deliverables.

## Branch and baseline

- [x] Create the Phase 01 development branch from the agreed baseline commit after Phase 00 review.
- [ ] Record Python/tool versions, database version, enabled PostgreSQL extensions, and current migration state.
- [ ] Run and record the current test/lint/format checks as a baseline; distinguish pre-existing failures from new failures.
- [x] Establish a disposable PostgreSQL test database and a reproducible empty-database migration check.

## Engineering foundation

- [ ] Adopt the bounded modular-monolith layout in `docs/architecture/SYSTEM_ARCHITECTURE.md`; keep `/api/v1` router assembly separate from module internals.
- [ ] Standardize SQLAlchemy 2.0 typed mappings, async session lifecycle, transaction boundaries, Pydantic v2 request/response contracts, and Alembic migration ownership.
- [ ] Add validated configuration for PostgreSQL/pgvector, Redis, object storage, signing keys, provider credentials, and environment-specific security settings; keep secrets outside source control.
- [ ] Select the Redis worker/job framework, retry/idempotency/dead-letter semantics, and worker deployment entry point. Add a minimal job health/status path.
- [ ] Define structured request/job correlation logging and metrics with secret/private-content redaction.
- [x] Resolve the pytest `testpaths` mismatch so `pytest` discovers `backend/tests`; align CI commands with local checks.

## Database and migrations

- [ ] Inventory supported existing database states and determine whether revision `f49273ec7757` has been applied/shared.
- [ ] Implement the reviewed forward migration repair for the empty initial revision and missing `research_papers` creation path; do not rewrite applied history.
- [ ] Verify `alembic upgrade head` from a genuinely empty PostgreSQL database, including pgvector extension setup and required permissions.
- [ ] Test the upgrade against a representative populated v1 database and preserve all existing paper/user relationships.
- [ ] Design and test the `ResearchPaper` backfill to global `Paper` plus private `UserPaper`; preserve provenance, avoid unsafe title-only merges, compare counts, and define rollback/recovery.
- [ ] Add migration and ORM constraints/indexes in dependency order; document retention and delete behavior.

## Security hardening

- [x] Upgrade password hashing to Argon2id and support secure verification/rehash of legacy hashes.
- [ ] Add stateful, revocable `Session` records; issue short-lived JWTs bound to sessions; implement rotation, logout, revocation, and key/claim validation.
- [ ] Add one-time hashed/expiring `VerificationToken` flows with rate limits and account-enumeration-resistant responses.
- [x] Add append-only application audit events for account actions and test that credentials are excluded.
- [x] Establish authenticated tenant context and scope the shipped private account and paper endpoints to the current user.
- [ ] Implement PostgreSQL RLS as defense in depth where selected; prove transaction-local tenant context is reset safely with pooled connections.
- [x] Remove duplicate user creation and demo routes; keep `/`, `/health`, `/about`, and the explicitly requested temporary hidden compatibility aliases outside `/api/v1`.
- [ ] Define secure browser token transport, CSRF protection, CORS, request limits, and rate limits.
- [ ] Add PDF MIME/magic-byte, size/page, parser, storage-key, scan, authorization, and lifecycle controls before enabling uploads.
- [ ] Add `AIUsage` quotas and atomic/idempotent accounting before enabling AI provider calls or retrieval jobs.
- [ ] Implement RAG retrieval filters and citation ownership checks before any private content reaches a model prompt.

## Verification and exit criteria

- [x] `pytest` passes from `backend/` and discovers the full `backend/tests` suite.
- [x] Ruff and Black checks pass; configured type/security checks (if adopted) pass.
- [x] `alembic upgrade head` succeeds on a clean, empty PostgreSQL database.
- [ ] Upgrade/backfill checks preserve data from a representative v1 database.
- [ ] Tenant-isolation tests cover API reads/writes, nested resources, search, worker processing, citations, caches, and RAG retrieval for at least two users.
- [ ] Authentication tests cover invalid/expired/revoked JWTs and sessions, Argon2id behavior, session rotation, and one-time verification.
- [ ] Security tests cover audit redaction, upload validation, RLS/pool reuse, and quota concurrency/idempotency.
- [ ] Update deployment and developer documentation with verified setup/migration commands and the exact checks run.

**Exit condition:** All required engineering and security gates pass, the migration path is reviewed for clean and populated databases, and unresolved exceptions are documented with an owner and mitigation. Product feature expansion remains outside this phase until these gates are satisfied.

## Phase 01A execution record — November 18, 2026

Branch: `feat/v2-foundation`, created from `c061d9cb272d`. The Phase 00 documentation additions were retained. This checkpoint completes the requested baseline repairs, not the entire Phase 01 checklist.

- Corrected `testpaths` to `tests` and removed `/greet/{name}`, `/add`, `/student`, and their local `Student` schema.
- Removed duplicate `POST /users/` registration. Registration remains under the auth router; `/api/v1/users/me` now provides authenticated account lookup.
- Mounted auth, users, papers, and research at `/api/v1`. Temporarily retained `/auth`, `/papers`, and `/research` aliases with `include_in_schema=False`, using the same authentication and authorization as canonical routes. Updated the OAuth token URL to `/api/v1/auth/login`.
- Required authentication for all paper endpoints. List, search, count, and ID queries require an explicit owner ID; list/search counts and pagination are tenant-scoped. Foreign IDs return the same 404 as missing IDs for reads, updates, and deletes. Writes obtain the owner from the authenticated user rather than request data.
- As explicitly requested for Phase 01A, repaired the empty initial revision `f49273ec7757` in place to create/drop the six-column legacy paper table and its ID index. Its descendants remain unchanged: `146022ae25cb` creates users and `009360f02c17` adds the non-null owner FK. This repairs replay from an empty database; it does not repair or re-run a revision already recorded in a deployed database. Deployment inventory and any populated-database corrective path remain unchecked above.
- Added regression tests for canonical/legacy routing, hidden aliases and OAuth metadata, removed demo/registration endpoints, authentication on every paper method, user-profile lookup, owner assignment, tenant-scoped list/search/counts/pagination, and cross-user read/update/delete denial. Updated existing repository/service tests to require owner scope.
- Isolated lifespan database checks in the test client and disposed test database connections after each fixture to avoid using an unrelated configured database or leaking SQLite connections.

### Verified checks

The checks ran from `backend/` with Python 3.13.16 and the pinned requirements. Application/router tests used isolated in-memory SQLite fixtures. The migration test used a separate empty PostgreSQL instance bound to localhost, with `TEST_MIGRATION_DATABASE_URL` explicitly set; it did not use a development or production database.

| Check | Result |
|---|---|
| `python -m pytest` | **133 passed**, zero failures or skips; 1 dependency deprecation warning; 95.64% application statement coverage. |
| `python -m ruff check .` | Passed. |
| `python -m black --check .` | Passed. |
| `git diff --check` | Passed. |
| Alembic revision graph / PostgreSQL offline DDL | One linear chain: `f49273ec7757` -> `146022ae25cb` -> `009360f02c17`; correct create/drop dependency order. |
| Live PostgreSQL round trip | Upgrade to head from empty DB, assert columns/owner FK/non-null constraint, insert a linked user/paper, downgrade to base; passed. |

`backend/tests/test_migrations.py` keeps the graph/DDL check in the default suite. Its live PostgreSQL round trip requires `TEST_MIGRATION_DATABASE_URL` pointing to a dedicated, empty, disposable PostgreSQL database and skips if that variable is absent. It intentionally upgrades/downgrades its test schema; never point this variable at a database containing application data. The run recorded above supplied it, so both migration tests ran and passed.

The remaining warning is Starlette's deprecation of HTTPX-backed `TestClient`; dependency migration is not part of this checkpoint. Argon2id, revocable sessions, verification/audit models, RLS, pgvector, workers, uploads, AI/RAG, and their corresponding gates remain future work, not claimed as implemented here.

## Phase 01B execution record — November 19, 2026

- [x] Switch to Argon2id through `argon2-cffi`. Verify existing bcrypt hashes and replace them with Argon2id after successful login.
- [x] Add `Profile`, `UserPreference`, `Session`, `VerificationToken`, and `AuditLog` in Alembic revision `8ad1e721e53b`. Backfill profiles and preferences for existing users with `en`, system theme, private defaults, and external AI consent off.
- [x] Bind short-lived access JWTs to server-side sessions. The signed claims use the account ID as `sub`, the session ID as `sid`, and a unique `jti` per issued token. Verify issuer, audience, expiry, ownership, and revocation on protected requests. Existing stateless tokens require a fresh login.
- [x] Add current-session and all-session logout, self-service profile and preferences, active sessions, recent activity, and account deletion. Accept `en` and `bn` and require a JSON boolean for explicit external AI consent. Account deletion cascades private records and retains audit history with the user FK cleared.
- [x] Record registration, login success/failure, logout, settings changes, and account deletion. Audit writers store event metadata and changed field names. ORM audit rows reject direct edits and deletes. Database-role restrictions and retention policies remain operational work.
- [x] Add the PostgreSQL 17 pgvector image and a health-checked Redis 7 service to Compose. CI provisions a disposable PostgreSQL service, creates the `vector` extension, and runs the live migration regression test. Install `httpx2` for Starlette's `TestClient` while retaining `httpx` for the arXiv client.

| Check | Result |
|---|---|
| `python -m pytest` with coverage | **155 passed**, zero failures, skips, or warnings. Application statement coverage was **97.64%**. |
| PostgreSQL 18.6, Alembic 1.18.5 | `upgrade head`, `downgrade base`, and `upgrade head` passed at `8ad1e721e53b`. `alembic check` found no schema drift. The populated upgrade test preserved users and papers and backfilled account defaults. |
| Ruff 0.15.20 and Black 26.5.1 | Passed. |
| Compose and CI | YAML and service configuration checks passed locally. Docker was unavailable on this host. The workflow is configured to validate Compose and install pgvector, and that workflow has yet to run. |

The full suite used Python 3.13.16 and pytest 9.1.1 from `backend/` with `TEST_MIGRATION_DATABASE_URL` set to an empty disposable PostgreSQL database. The Alembic CLI uses the app's `DATABASE_URL` when `alembic.ini` does not supply a URL. Under Compose, apply migrations with `docker compose exec backend alembic upgrade head` once the services are healthy.

The verification-token table is ready for email verification and password reset flows. Token delivery and consumption, refresh rotation, PostgreSQL RLS, queue workers, and document/AI controls remain tracked in the broader checklist.
