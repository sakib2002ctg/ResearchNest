# ResearchNest v2

ResearchNest is a bilingual English/Bangla research workspace built with FastAPI,
SQLAlchemy 2.0, PostgreSQL/pgvector, Redis and Next.js/TypeScript. It includes
academic discovery, private PDF libraries, document indexing, source-grounded AI,
paper analysis, citations/writing, multimodal assets, projects/insights, research
education, role-based teams and operational administration.

See [feature status](docs/product/FEATURE_STATUS_REGISTER.md), the
[architecture](docs/architecture/SYSTEM_ARCHITECTURE.md),
[security design](docs/architecture/SECURITY_ARCHITECTURE.md) and
[Phase 12 verification](docs/milestones/PHASE_12.md) for implementation evidence
and the limits of local verification. Passing local checks does not establish
that a public deployment, external providers or restore procedures work in your
own environment.

## Local development

Use Python 3.13, Node.js 24, PostgreSQL 17 with the pgvector extension and Redis 7.
For an isolated local PostgreSQL installation without vector, set
`PGVECTOR_ENABLED=false`; that profile uses JSON vectors and is intended for
local/testing use. Install dependencies from the committed lockfiles/lists:

```sh
cd backend
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Create an ignored `backend/.env` with local values, never deployment credentials:

```dotenv
APP_NAME=ResearchNest
APP_ENV=development
DEBUG=false
DATABASE_URL=postgresql://YOUR_LOCAL_ROLE:YOUR_URL_ENCODED_PASSWORD@127.0.0.1:5432/researchnest
SECRET_KEY=GENERATE_A_UNIQUE_RANDOM_VALUE
REDIS_URL=redis://127.0.0.1:6379/0
PGVECTOR_ENABLED=true
CORS_ORIGINS=["http://localhost:3000","http://127.0.0.1:3000"]
AI_DEFAULT_PROVIDER=offline
PDF_STORAGE_ROOT=storage/pdfs
ASSET_STORAGE_ROOT=storage/assets
```

Generate a secret with `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
Apply migrations, then start the API from `backend/`:

```sh
alembic upgrade head
alembic check
uvicorn app.main:app --reload --no-access-log
```

Run the client in another terminal:

```sh
cd frontend
npm ci
# Set NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1 in .env.local
npm run dev
```

API documentation is at `http://localhost:8000/docs`; the product API is under
`/api/v1`. `/health` is fast liveness; `/health/ready` verifies database, configured
Redis and private storage writability. Production settings also accept
`ENVIRONMENT` as an alias for canonical `APP_ENV`.

Local mode can run document/multimodal workers inside the API. For separate
processes, set `DOCUMENT_WORKER_IN_API=false` and
`MULTIMODAL_WORKER_IN_API=false`, then run these from `backend/`:

```sh
python -m app.modules.documents.worker
python -m app.modules.multimodal.worker
```

The API retains durable PDF cleanup; the multimodal worker also drains asset
cleanup. All processes must share the same private PDF/asset storage. Hash
embeddings and offline AI are deterministic baselines. Sentence-transformer
embeddings require an explicitly provisioned local model/package; configured
Ollama/OpenAI-compatible services provide model inference. No model is downloaded
automatically. Cloud dispatch requires each user's current consent.

## Docker Compose deployment

The Compose stack defines PostgreSQL 17/pgvector, Redis 7, one-shot migrations,
FastAPI, separate document and multimodal workers, and Next.js. It mounts durable
PDF/asset volumes, runs application containers as UID 10001, drops capabilities,
uses restart/health policies and contains no development source mount or reload.
Database and Redis ports are private; API/frontend bind only to host loopback.
Provide a TLS reverse proxy for real public domains.

1. Copy `.env.example` to the ignored root `.env`.
2. Generate `SECRET_KEY` with the URL-safe random generator above. Generate
   **distinct random hexadecimal values** for `POSTGRES_PASSWORD`,
   `MIGRATION_DATABASE_PASSWORD` and `APP_DATABASE_PASSWORD`, using
   `secrets.token_hex(32)`. Hex database passwords avoid connection-URI quoting
   mistakes; URI-percent-encode reserved characters in other passwords.
3. Set `CORS_ORIGINS` to exact HTTPS browser origins, and
   `NEXT_PUBLIC_API_BASE_URL` to the **browser-visible** HTTPS API origin ending
   `/api/v1`. Never use the Docker service name `backend` as a browser URL.
4. Configure real SMTP and ClamAV endpoints before opening account recovery and
   PDF-upload flows. Production PDF scanning fails closed without a scanner.
5. Validate and start:

```sh
docker compose config --quiet
docker compose up --build -d
docker compose ps
```

`NEXT_PUBLIC_API_BASE_URL` is embedded during the Next.js build. Rebuild the client
when it changes. SMTP/provider secrets are server-only environment values; do not
prefix secrets with `NEXT_PUBLIC_`. Replace example domains before building.

For a fresh PostgreSQL volume, `scripts/docker/init_db.sh` creates a dedicated
`researchnest_migrator` role and a non-DDL `researchnest_app` runtime role. The
bootstrap role creates pgvector; the migrator owns the application schema. Default
privileges grant runtime table CRUD/sequence access, then the migration service
removes runtime UPDATE/DELETE/TRUNCATE privileges on audit logs. Existing database
volumes need an explicit DBA-reviewed role/grant upgrade; initialization scripts
are not rerun on them. Changing a password in `.env` also does not rotate an
existing PostgreSQL role automatically. The old `backend/.env.docker` contains
only non-secret reference flags and is no longer loaded by Compose.

The former tracked Docker configuration contained a fixed signing key and
database password. Those values remain in Git history. Generate new credentials
and rotate any deployment that used them; do not reuse the old examples.

Compose worker healthchecks confirm process liveness, not queue progress. Monitor
failed jobs, queue age, storage usage, database backups and alerts in the deployed
environment. Run behind an ingress with bounded request/body/time limits. The
sample disables proxy-header trust; configure a strictly trusted proxy strategy
before relying on forwarded client addresses for per-client limits. Do not make
Redis or database ports public. Local Docker availability and execution evidence
are recorded in the Phase 12 report rather than assumed.

## Security and operations

- Argon2id password hashing and short-lived JWTs bound to live, revocable sessions.
- Separate global academic metadata, private user records and owner-scoped AI
  indexes. Team sharing exposes explicit bibliographic metadata, not private PDFs
  or RAG permissions.
- PDF MIME/signature/size checks, private generated storage keys and scanning.
- External-AI consent, conservative usage reservations and source/citation checks.
- Strict administrator authorization; registration/profile requests cannot grant
  admin privileges. Provision the initial admin through the documented operator
  procedure, never by adding a public signup field.
- Security headers, production HSTS, global API rate limits and safe structured
  request logging. Redis coordinates rate limits across instances; in-memory
  fallback is for a single process/instance. A configured Redis outage fails closed.
- Admin operations expose safe counts/directories, session revocation, audit
  metadata and failed-job recovery. They do not return credentials or documents.

To provision the first administrator, first register the normal account, identify
its exact user ID through trusted database/operator access, and ensure migrations
are current. From `backend/`, with operator/migrator database credentials, run:

```sh
python -m app.cli.admin --user-id 42 --grant
# Type GRANT ADMIN 42 when prompted; replace 42 with the verified account ID.
python -m app.cli.admin --user-id 42 --revoke
# Type REVOKE ADMIN 42 when prompted.
```

For Compose, run the same module through the migrator service, for example
`docker compose run --rm --no-deps migrate python -m app.cli.admin --user-id 42 --grant`.
Both operations audit the change and revoke prior sessions; the user signs in
again. Never make role assignment part of registration or a client-controlled
request.

Use production `APP_ENV=production`, `DEBUG=false`, a strong unique secret,
HTTPS CORS origins and enabled rate limits. Configure `HSTS_ENABLED` and
`HSTS_MAX_AGE` to match the HTTPS deployment. Additional operational controls are
`API_RATE_LIMIT_REQUESTS`, `API_RATE_LIMIT_WINDOW_SECONDS`,
`API_RATE_LIMIT_MAX_CLIENTS` and `READINESS_TIMEOUT_SECONDS`.

## Backup and restore

Use trusted PostgreSQL client tools at the server's major version, a restricted
operator account and `PGPASSFILE`/libpq service credentials. Do not put passwords
in command arguments. Scripts require a plain explicit `PGDATABASE` name;
connection URI values are rejected to avoid printing embedded secrets.

```sh
export PGHOST=127.0.0.1 PGPORT=5432 PGUSER=YOUR_BACKUP_ROLE
export PGPASSFILE=/secure/path/pgpass
export PGDATABASE=researchnest
bash scripts/backup_db.sh /secure/backups/researchnest-2026-11-20.dump
# Type BACKUP when prompted.

# First create an isolated restore target and provision pgvector/roles there.
export PGDATABASE=researchnest_restore_validation
bash scripts/restore_db.sh /secure/backups/researchnest-2026-11-20.dump
# Type RESTORE researchnest_restore_validation when prompted.
```

Backups are custom-format archives with private permissions and a SHA-256 sidecar;
existing files are never replaced. Restore validates the checksum/archive on a
private frozen copy before asking for the target-specific confirmation, then
uses an all-or-nothing clean restore transaction. Only restore trusted archives.
Checksum verification detects corruption, not malicious provenance. Database
backups do **not** include PDF/PNG volumes: back those up consistently with the
database, encrypt/offsite them and test restoration on an isolated target. Keep a
separate retention policy. Run migrations and verification before routing traffic
to a restored database, and reapply runtime grants/audit immutability policies.

With backend dependencies installed and production environment loaded, run from
`backend/`:

```sh
python ../scripts/verify_release.py --config-only
python ../scripts/verify_release.py --api-url https://api.YOUR_REAL_DOMAIN
```

The checker exits nonzero on invalid production configuration, weak secrets,
migration-head mismatch or degraded liveness/readiness. It prints only named
boolean checks, not secrets or driver exceptions. `--config-only` contacts no
service and never claims launch readiness. A successful full check is limited to
these application checks; DNS/TLS, actual worker progress, provider/SMTP/scanner
connectivity, load/capacity and a restore drill still need deployment sign-off.

## Verification

Run tests from `backend/`; external HTTP/AI calls are mocked. PostgreSQL tests
require **genuinely empty disposable databases**, not development/production DBs:

```sh
# Set APP_ENV=test, AI_DEFAULT_PROVIDER=offline, DATABASE_URL=sqlite://
# and PGVECTOR_ENABLED=true for PostgreSQL/pgvector verification.
# Point TEST_MIGRATION_DATABASE_URL and TEST_IDENTITY_DATABASE_URL at separate
# disposable PostgreSQL databases before pytest.
python -m ruff check .
python -m black --check --extend-exclude '(.cache)' .
pytest
```

Without disposable PostgreSQL URLs, those integration tests are skipped; that is
not equivalent to the full release gate. On Windows, a workspace-local
`--basetemp .cache/test-run` can avoid system temporary-directory ACL issues.
Bash is needed for the offline backup/restore tests (Git Bash works on Windows).

```sh
cd frontend
npm run typecheck
npm run lint
npm test
npm run build
```

CI configures pgvector PostgreSQL, empty-database migration round trips and
`alembic check`, full backend coverage, script checks and all frontend gates.
Actual metrics and remaining environmental checks are in
[PHASE_12.md](docs/milestones/PHASE_12.md).
