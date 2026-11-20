# Phase 12 — Production Maturity

Implemented on `feat/v2-foundation` after Phase 11 checkpoint **`638d54b`**, using
the requested checkpoint message. This phase adds operational administration,
security/admission boundaries, health/telemetry, backup/restore tooling, deployment
definitions and release documentation. Repository verification and target
deployment acceptance are recorded separately below.

## Administration and migration

Revision **`f2d36e0c854a`** follows `e1c25d9b743f` and adds nonnullable
`User.is_admin`, default/server-default false. Existing accounts stay nonadmin.
Registration and JWT claims cannot assign the role. Downgrade requires explicit
revocation of existing administrator privileges before dropping the column;
empty-database round trips remain supported. Earlier revisions are unchanged.

`require_admin_user` uses the authenticated live session and a fresh stored role.
The async repository rechecks both role and that same session capability for
each operation. Anonymous requests receive 401, authenticated nonadmins 403.
Successful reads/writes, authenticated dependency denials and authorized HTTP
failure outcomes are audited. Rejected actions roll back staged changes before
recording safe operation/status/resource IDs. Audit persistence failure fails
closed; document text, prompts, credentials, token values, storage keys, raw
upstream errors and unstructured audit details are not returned or logged.

| Method | Endpoint | Behavior |
| --- | --- | --- |
| GET | `/api/v1/admin/overview` | Counts for users/verification/sessions, global and saved papers, current indexes, failed jobs, AI usage and teams |
| GET | `/api/v1/admin/users` | Bounded directory with role/verification/activity metadata |
| POST | `/api/v1/admin/users/{user_id}/revoke-sessions` | Emergency revocation, ordered account locks and audit |
| GET | `/api/v1/admin/audit-logs` | Paginated safe security events, optional `action`/`user_id` filters |
| GET | `/api/v1/admin/jobs/failed` | Failed-job operational metadata and current retry eligibility |
| POST | `/api/v1/admin/jobs/{job_id}/requeue` | Versioned recovery of a current failed document/job |

Overview reports database-backed operational state and points to readiness for
dependency health; it does not pretend that database counts prove Redis/storage
health. The module is a supporting operational capability, not a thirteenth
functional product module or a private-document browsing API.

Job recovery retains the original failed job, increments the document version,
and creates a new queued job with a distinct ID and fresh attempt counter. This
avoids an old worker lease matching a reset counter. Document-then-job locking
matches the processor. Repeated requests for the old job return 409. Dispatch
failure leaves a durable queued row recoverable by polling. Admin/account locks
use a non-key update and deterministic ordering to avoid foreign-key lock cycles.

`python -m app.cli.admin --user-id ID --grant|--revoke` is an explicit operator
command for an existing account, requiring a target-specific confirmation and
authorized database credentials. Role changes, existing-session revocation and
the operator-origin audit event commit atomically. No default admin or HTTP role
promotion endpoint is created. Sign in again after a role change.

## Security, admission and observability

The outer ASGI boundary sets `nosniff`, `DENY` framing, strict-origin referrer
policy, restricted permissions and request IDs across success/error/denial
responses. Private API responses use `private, no-store`. Configurable HSTS is
sent only in production. Mounted paths use Starlette's normalized route path, so
a proxy/application `root_path` cannot bypass admission or private-cache policy.
Post-header streaming exceptions are sanitized before propagation; raw private
error messages are not emitted in server tracebacks.

Global API admission covers `/api/v1` and temporary `/auth`, `/papers`, `/research`
aliases. Configured Redis uses one atomic server-time sliding-window Lua
operation. A configured Redis failure returns 503 with retry guidance instead of
silently switching to a weaker per-instance budget. Without Redis, the bounded
in-memory window is suitable for one instance/local tests. It never evicts active
budgets to admit a new identity. Exceeded windows return 429 and `Retry-After`.

Keys HMAC the ASGI peer address; raw bearer tokens and client-supplied forwarded
headers do not identify budgets. The sample server disables proxy-header trust.
Operators must define a strictly trusted ingress strategy before using forwarded
client addresses. Tests can explicitly enable admission in `APP_ENV=test`; normal
fixtures bypass it without disabling production controls.

Production startup validates secret strength, disabled debug, explicit HTTPS CORS,
PostgreSQL, JWT scope, algorithm and enabled admission. `APP_ENV` is canonical;
`ENVIRONMENT` is supported as an alias. Startup no longer opens an unbounded
synchronous database connection: dependency outages must not prevent liveness.
The shared runtime/release secret policy rejects short, low-diversity, completely
periodic and common placeholder values. It is a configuration heuristic, not an
entropy proof; generate signing keys cryptographically as shown in README.

Structured JSON stdout logs contain request UUID, method, route template, status,
duration and safe exception type. They exclude raw URL/query strings, request
bodies, provider payloads and exception tracebacks. Compose disables Uvicorn
access logs to avoid a second unredacted URL log. An external collector/alerting
system must still be provisioned by the deployment operator.

## Liveness and readiness

- `GET /health`: fast `{"status":"ok","version":"2.0.0"}` liveness.
- `GET /health/ready`: bounded async `SELECT 1`, configured Redis ping, and private
  PDF/asset storage create/write/fsync/delete checks; 200 healthy, 503 degraded.

Probe responses contain only generic named statuses, without credentials or
paths. Filesystem checks coalesce into one daemon-thread future per application,
with a short configurable cache. A timeout cannot stop a kernel/NFS write, so
later probes reuse the pending work rather than exhausting the global executor.
Changing storage roots fails closed while an old probe is pending. Liveness
remains independent of these deeper checks. Readiness does not certify worker
progress, scanner/SMTP/provider connectivity or application capacity.

## Backup, restore and release tools

`scripts/backup_db.sh` uses custom-format `pg_dump`, libpq environment/PGPASSFILE
credentials, private permissions and a SHA-256 sidecar. Confirmation is required;
atomic no-overwrite publication avoids exposing partial archives.

`scripts/restore_db.sh` freezes a private archive copy, verifies its checksum and
format before mutation, and requires `RESTORE <target_database>`. It runs a clean
transactional restore with no inherited owners/ACLs. Treat archives as trusted
executable database input; a checksum establishes integrity, not provenance.
Reapply runtime grants and audit protections before routing traffic.

A live isolated **PostgreSQL 18** drill migrated/seeded a source, backed it up and
restored it into a separate database. Migration head, verification/admin flags,
paper data and audit data were preserved. A deliberately corrupted archive was
rejected before restore. This validates a small SQL recovery path, not a measured
production RTO/RPO. Database dumps do not include PDF/PNG volumes: coordinate
their snapshots, encryption, off-host retention and restore validation separately.

`scripts/verify_release.py` checks production configuration, secret strength,
migration head and health endpoints with timeouts and redacted boolean output.
`--config-only` contacts no service and cannot claim launch readiness. Even a
successful full application check does not replace infrastructure, provider or
recovery acceptance in the target environment.

Shell entrypoints are fixed to LF through `.gitattributes`. Script tests use fake
PostgreSQL executables/mock HTTP; all three shell scripts pass Bash syntax checks.

## Deployment and CI

Compose defines PostgreSQL 17/pgvector, Redis 7, one-shot migration, FastAPI,
separate document/multimodal workers and Next.js. Application containers run
nonroot with dropped capabilities, private persistent volumes and health/restart
policies. There are no development source mounts/reload flags or fixed deployment
credentials. Browser API URLs are build-time public configuration; server secrets
are never `NEXT_PUBLIC_` values. API/frontend ports bind to loopback, and public
TLS termination remains an operator responsibility.

Fresh-volume database bootstrap separates migrator and runtime roles, provisions
pgvector and grants runtime DML/sequence access. The migration command removes
runtime audit modification and migration-version mutation privileges. Existing
volumes require an explicit DBA role/grant upgrade and actual password rotation;
editing an environment file does not change an existing database role.

CI definitions include backend Ruff/Black, root release-checker formatting/lint,
shell syntax, Compose validation, real Redis Lua admission, least-privilege role
bootstrap, fresh pgvector migrations/`alembic check`, full backend coverage and
frontend typecheck/lint/tests/build. Local YAML and embedded-code syntax checks
ran. Docker is unavailable on this host: image builds, Compose startup and the
new container-backed CI jobs were **not** executed locally. A live local Redis
server and pgvector extension were also unavailable; local Redis protocol/error
tests use fakes, and local PostgreSQL uses the portable vector profile.

## Performance sanity benchmark

The reproducible offline harness is `backend/scripts/benchmark_api.py`. The
recorded run used the actual application `/health`, `/about`, and
`/api/v1/users/me`, with genuine JWT/live-session checks against an isolated SQLite
fixture. Warmup/setup is excluded; 180 measured requests used concurrency eight.

| Measurement | Result |
| --- | --- |
| p50 | 7.901 ms |
| p95 | **77.252 ms**, below the 500 ms sanity target |
| Maximum | 101.131 ms |
| Closed-loop throughput | 364.72 requests/second |
| Measured request interval | 0.4935 seconds |

This is an in-process ASGI smoke benchmark in test mode, with global admission
bypassed. It excludes network/TLS, PostgreSQL/Redis admission, ingestion, academic
providers, model inference and sustained production load. It proves no general
capacity or external-AI latency claim. The report is generated at
`backend/.cache/phase12-benchmark.json`.

## Security sign-off and launch status

| Area | Repository evidence | Target-environment acceptance |
| --- | --- | --- |
| Identity/tenancy/team ACL | Automated role/session/ownership/citation/retrieval isolation checks | Operator credential lifecycle and access review |
| Administration | Default nonadmin, fresh capability, safe audited operations, session emergency control, fenced retries | Explicit least-privilege admin provisioning |
| HTTP/admission/log privacy | Header/error/mount tests, atomic-window protocol/fail-closed tests, safe telemetry checks | Live Redis, trusted proxy, TLS/HSTS and log collection |
| PDF/AI boundaries | Existing scanner-policy, storage, consent, quota, evidence and worker regressions | Real scanner signatures/connectivity and enabled model/provider validation |
| Recovery | Real isolated SQL backup/restore and corruption rejection | Coordinated private-volume recovery, off-site encryption, retention and recovery objectives |
| Deployability | Compose/CI source and syntax checks, frontend production build | Actual images/containers, pgvector profile, worker progress and CI execution |
| Performance | Local p95 sanity benchmark | Representative hardware/data, sustained traffic and provider latency |

Repository security sign-off is complete for the automated boundaries above.
**Launch disposition: implementation verified; target-environment acceptance
pending.** Docker images/Compose, live Redis/pgvector, trusted ingress/TLS, SMTP,
scanning, enabled providers, worker monitoring, coordinated off-host recovery and
realistic workload capacity must be validated before approving public traffic.
No public deployment or external notification has been performed.

## Final verification record

- Final full backend suite: **901 passed, 0 failures/errors/skips**, **83.34% total
  application coverage** (7,531 / 9,036 executable lines), **1,881.62 seconds** on
  this Windows host. Coverage XML/HTML and JUnit reports were generated. This
  includes the entire earlier PDF/OCR/index/AI/storage regression suite; it is not
  a runtime claim for the new operational endpoints. Five existing PyMuPDF SWIG
  deprecation warnings remain.
- **121 backend cases added** over the Phase 11 baseline: 38 admin, 51 operational,
  25 release-tool, two operator bootstrap, three PostgreSQL admin and two real-app
  readiness cases. They cover 401/403 isolation, forged-role prevention, audit
  outcomes/fail-closed behavior, safe projections, revocation, fenced recovery,
  headers/errors/mounted paths, rate admission, Redis failure, production settings,
  secret policy, health/degradation, storage coalescing, log privacy, scripts and
  the latency sanity target. Four legacy cache assertions were updated to the
  stronger intended `private, no-store` policy; their identity/privacy checks
  remain intact.
- Real PostgreSQL tests pass for simultaneous administrators revoking one another
  without deadlock, duplicate job recovery creating one new fenced version,
  delayed old-job delivery, admin downgrade protection and full-app readiness.
  Empty-database **head → base → head** round trips and supported existing-data
  preservation pass through the complete migration chain. Existing users receive
  `is_admin=false`; schema head is **`f2d36e0c854a`**.
- `alembic check`: **passed**, no new upgrade operations detected. Local live
  PostgreSQL is version 18 with `PGVECTOR_ENABLED=false`; both vector-profile
  offline DDL checks pass. PostgreSQL 17/pgvector and Redis 7 live checks are
  configured in CI, not claimed executed on this host.
- Backend/root release checker Ruff: **passed**. Black: **passed, 265 files
  unchanged**. Shell syntax, Compose/CI YAML and embedded CI code syntax checks:
  **passed**. `git diff --check`: **passed**.
- Frontend typecheck, ESLint, **37/37 tests** and production build: **passed**, with
  **22 generated static pages**. Frontend application behavior was not changed by
  this phase; deployment/build definitions were added. Browser end-to-end tests
  and Docker image/container execution were not run locally.
- The standalone latency harness passed the 500 ms p95 smoke target with the
  measured scope/results above. SQL backup/restore and deliberate corruption
  rejection passed against isolated real databases. The release-checker's live
  migration-head probe passed and its configuration checks correctly rejected
  the local test environment as launch-ready.

The feature register now records all twelve functional modules and all thirteen
phases as **Implemented & Verified**, with this explicit deployment qualification.
Phase 12 changes are left uncommitted for review; the requested Phase 11 checkpoint
is the only commit created for this task. No package dependencies were added.
