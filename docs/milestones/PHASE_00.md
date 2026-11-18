# Phase 00 — Baseline Audit and v2 Specification

**Status:** Documentation baseline recorded. No application code, dependencies, database, or branch were changed for this deliverable.

## Audit scope and baseline identity

This audit records the repository state inspected for the v2 planning work. The task designates the baseline as ResearchNest v1.5; the checked-in `docs/project-overview.md` still identifies the project as v1.4.0. At inspection the Git branch was `main`, the HEAD was `c061d9cb272d`, and the working tree was clean before these documentation additions. This is a source inspection, not a claim that tests or migrations were executed in this documentation task.

The repository has a Python/FastAPI backend and Markdown documentation. There is no frontend directory or `package.json`. Existing `docs/*.md` files are retained as historical/current-state references; the v2 specification lives in the new `docs/architecture/` and `docs/milestones/` directories.

## v1.5 baseline inventory

```text
.
├── .github/
│   └── workflows/
│       └── ci.yml
├── .gitignore
├── CONTRIBUTING.md
├── LICENSE
├── README.md
├── docker-compose.yml
├── backend/
│   ├── .dockerignore
│   ├── .env.docker
│   ├── .env.example
│   ├── .pre-commit-config.yaml
│   ├── Dockerfile
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── versions/
│   │   │   ├── 009360f02c17_add_paper_owner.py
│   │   │   ├── 146022ae25cb_create_users_table.py
│   │   │   └── f49273ec7757_initial_migration.py
│   │   ├── env.py
│   │   ├── README
│   │   └── script.py.mako
│   ├── app/
│   │   ├── clients/
│   │   │   ├── arxiv_client.py
│   │   │   └── base.py
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── config.py
│   │   │   ├── logging.py
│   │   │   └── security.py
│   │   ├── database/
│   │   │   ├── __init__.py
│   │   │   └── database.py
│   │   ├── dependencies/
│   │   │   ├── __init__.py
│   │   │   ├── auth_dependencies.py
│   │   │   ├── current_user.py
│   │   │   ├── paper_dependencies.py
│   │   │   └── research_dependencies.py
│   │   ├── exceptions/
│   │   │   ├── __init__.py
│   │   │   ├── custom_exceptions.py
│   │   │   └── handlers.py
│   │   ├── middleware/
│   │   │   ├── __init__.py
│   │   │   └── logging.py
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── research_paper.py
│   │   │   └── user.py
│   │   ├── repositories/
│   │   │   ├── paper_repository.py
│   │   │   └── user_repository.py
│   │   ├── routers/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py
│   │   │   ├── papers.py
│   │   │   ├── research.py
│   │   │   └── users.py
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   ├── external_paper.py
│   │   │   ├── research_paper.py
│   │   │   └── user.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── paper_service.py
│   │   │   ├── research_service.py
│   │   │   └── user_service.py
│   │   ├── __init__.py
│   │   └── main.py
│   ├── pyproject.toml
│   ├── requirements.txt
│   └── tests/
│       ├── clients/
│       │   └── test_arxiv_client.py
│       ├── repositories/
│       │   ├── __init__.py
│       │   └── test_paper_repository.py
│       ├── routers/
│       │   ├── __init__.py
│       │   ├── test_auth_router.py
│       │   ├── test_paper_router.py
│       │   └── test_research_router.py
│       ├── services/
│       │   ├── __init__.py
│       │   ├── test_paper_service.py
│       │   └── test_research_service.py
│       ├── __init__.py
│       └── conftest.py
└── docs/
    ├── api.md
    ├── deployment.md
    ├── development.md
    ├── project-overview.md
    ├── roadmap.md
    ├── system-architecture.md
    └── README.md
```

The tree above lists source-controlled files at the audited commit; it omits Git internals and ignored/local files. The current branch and commit are a baseline record, not a request to branch during Phase 00.

## Existing stack and layout

- Backend dependencies are pinned in `backend/requirements.txt`: FastAPI, Pydantic v2/settings, SQLAlchemy 2.0, Alembic, PostgreSQL driver, Passlib/bcrypt, python-jose, HTTPX/feedparser, pytest/coverage, Ruff, Black, and pre-commit, plus transitive pins. `backend/pyproject.toml` configures Python 3.13 targets, 88-column Black/Ruff formatting, Ruff `E/F/I` lint rules, pytest coverage, and optional pytest dev dependencies.
- Current application code is layered in flat `app/routers`, `services`, `repositories`, `models`, `schemas`, and `clients` packages. Database sessions use synchronous SQLAlchemy sessions. The external arXiv adapter uses synchronous HTTPX.
- The two declared ORM models are `User` (`users`: `id`, unique indexed `username`, unique indexed `email`, `hashed_password`) and `ResearchPaper` (`research_papers`: `id`, `title`, `authors`, `abstract`, `source`, `url`, non-null `owner_id` FK to `users.id`). A user has a delete-orphan relationship to papers.
- The checked-in Alembic chain contains empty initial revision `f49273ec7757`, `146022ae25cb` creating `users`, and `009360f02c17` adding `owner_id` to `research_papers`. The listed revisions do not create `research_papers`; the last revision assumes that table already exists. The actual database state cannot be inferred from source alone.

## Existing API surface

Application-declared routes, with router prefixes resolved:

| Method | Path | Existing behavior / access |
|---|---|---|
| GET | `/` | Welcome response. |
| GET | `/health` | Basic health response. |
| GET | `/about` | Project/version response. |
| GET | `/greet/{name}` | Demo greeting route. |
| GET | `/add?a=…&b=…` | Demo integer addition route. |
| POST | `/student` | Demo request/response using a local `Student` schema. |
| POST | `/auth/register` | Creates account; validates duplicate email/username. |
| POST | `/auth/login` | Checks email/password and returns a bearer access JWT. |
| GET | `/auth/me` | Returns current authenticated user. |
| POST | `/users/` | Second, unauthenticated account-creation route. |
| POST | `/papers/` | Authenticated paper creation; assigns current user as owner. |
| GET | `/papers/` | Paginated paper list; no auth or owner filter. |
| GET | `/papers/search?q=…` | Paginated paper search; no auth or owner filter. |
| GET | `/papers/{paper_id}` | Single-paper retrieval; no auth or owner filter. |
| PUT | `/papers/{paper_id}` | Authenticated; verifies the paper owner before update. |
| DELETE | `/papers/{paper_id}` | Authenticated; verifies the paper owner before deletion. |
| GET | `/research/search?q=…&limit=…` | Public external arXiv search. |

FastAPI's default OpenAPI/Swagger/ReDoc routes are enabled. No `/api/v1` prefix is applied to the application routers.

## Current authentication and authorization

`core/security.py` configures Passlib bcrypt and `python-jose`. Passwords are hashed at account creation and verified at login. Login issues a JWT with email in `sub`, `exp` based on `ACCESS_TOKEN_EXPIRE_MINUTES` (default 30), and settings-selected signing key/algorithm (default `HS256`). `OAuth2PasswordBearer` reads bearer tokens. `get_current_user` decodes the JWT, extracts `sub`, looks up the user by email, and returns 401 for invalid/expired/missing-subject or absent-user cases. Registration/login schemas validate email; password length is 8–128 characters. `UserResponse` does not include `hashed_password`.

Paper creation derives `owner_id` from the authenticated user. Update/delete compare the loaded paper's `owner_id` with the current user's ID and return 403 on a mismatch. The list, search, and single-paper read endpoints do not require authentication and repository queries do not scope by user. User accounts have no session revocation, email verification, or security audit model in the current app. There is no upload/RAG/AI usage implementation in the audited backend.

## Feature Reconciliation Register

“Partial / Existing” means v1 has a related implementation, not that the v2 module is complete or meets the target architecture. “Missing” means no corresponding v2 module or feature implementation was found in the audited application.

| v2 module | v1.5 status | Evidence / gap |
|---|---|---|
| `auth` | Partial / Existing | Register, login, `/me`, bcrypt hashes, stateless JWT; no revocable sessions, verification, Argon2id, or audit trail. |
| `users` | Partial / Existing | `User` model/repository and user creation; no complete profile/lifecycle/security management. |
| `papers` | Partial / Existing | `ResearchPaper` CRUD/search exists, but academic metadata and private library state are coupled and read routes expose rows publicly. |
| `arxiv_client` | Partial / Existing | Synchronous arXiv search adapter and tests; no async worker ingestion or durable provider-source reconciliation. |
| `collections` | Missing | No collection model/API. |
| `documents` | Missing | No private document model, upload pipeline, PDF validation, or page extraction. |
| `annotations` | Missing | No private annotation model/API. |
| `research_projects` | Missing | No project model/API or project-level access policy. |
| `writing_documents` | Missing | No writing workspace/document model/API. |
| `conversations` | Missing | No conversation model, chat API, or citations. |
| `rag` | Missing | No chunking, embedding, vector search, citation ACL, or RAG query pipeline. |
| `ai` | Missing | No AI analysis/usage accounting, quota enforcement, or provider orchestration module. |

## Technical Debt & Security Gap Report

1. **Broken/incomplete migration baseline:** `f49273ec7757` is empty. The listed later migration adds a foreign key/column to `research_papers`, but no listed revision creates that table. A clean empty-database migration path is therefore not established by the checked-in history.
2. **Public private-paper reads:** `GET /papers/`, `/papers/search`, and `/papers/{paper_id}` are public and query without an owner condition. Once paper rows contain user-owned material, these routes leak private data.
3. **Duplicate user creation surface:** both `POST /auth/register` and `POST /users/` create users, duplicating registration behavior and policy surface.
4. **Demo routes mixed into production app:** `/greet/{name}`, `/add`, and `/student` live in `main.py` and should not be part of the versioned product API.
5. **Pytest path mismatch:** `backend/pyproject.toml` sets `testpaths = ["app/tests"]`, while tests are under `backend/tests/`.
6. **Missing API version namespace:** routers are mounted without `/api/v1`, making planned API evolution and compatibility boundaries unclear.
7. **Authentication gaps:** bcrypt is used rather than the v2 Argon2id target; access is stateless and not revocable; there are no verification tokens or `AuditLog`; security events lack structured audit persistence.
8. **Tenant isolation gaps:** only writes check paper ownership. Read endpoints and repositories have no `user_id` predicate; no row-level isolation or cross-tenant test gate is defined in v1.
9. **No document/AI safety boundaries:** there is no PDF validation or private storage flow, no RAG tenant filter/citation authorization, and no `AIUsage` quota enforcement.
10. **CI/migration coverage gap:** `.github/workflows/ci.yml` runs Ruff, Black, and pytest with SQLite; it does not run Alembic against PostgreSQL. The test fixture creates tables from ORM metadata, so passing those tests alone would not prove migrations work from an empty database.
11. **Baseline validation not established by this documentation task:** source inspection does not establish that the test suite passes or that Alembic upgrades from an empty database. Phase 01 must execute these gates and record results.

## Phase 00 exit record

- [x] Capture the v1.5 source baseline and reconcile its version label discrepancy.
- [x] Record current modules, declared models, routes, authentication behavior, and technical/security gaps.
- [x] Specify v2 architecture, data boundaries, database plan, and security target.
- [x] Define Phase 01 foundation/security checklist.
- [ ] Create the Phase 01 development branch (intentionally not done by this documentation deliverable).
