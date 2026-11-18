# ResearchNest v2 Engineering Rules

These rules govern implementation and review of ResearchNest v2. Treat the architecture and entities below as target design; do not describe planned behavior as implemented behavior. Preserve existing documentation and migration history unless a reviewed migration plan explicitly changes it.

## Architecture

- Build a modular monolith with bounded backend modules, a versioned FastAPI API, and separately deployable asynchronous background workers. Modules own their routes, schemas, use cases/services, repositories, and persistence mappings; cross-module access goes through explicit interfaces.
- Use FastAPI, SQLAlchemy 2.0 typed mappings and async sessions for request paths, Pydantic v2 for validation and serialization, Alembic for every schema change, PostgreSQL with pgvector, and Redis for broker/cache/coordination needs. Use Next.js and TypeScript for the web client.
- Keep HTTP handlers thin. Put orchestration in application services, persistence in repositories, provider calls behind adapters, and long-running/retryable work in idempotent background jobs. Do not make a request wait for ingestion, embedding, or other long-running AI work.
- Keep secrets and environment-specific values out of source control. Validate settings at startup, use least-privilege service credentials, and never log passwords, bearer tokens, session tokens, uploaded document text, prompts, or provider secrets.

## Three-tier data separation

Keep these domains distinct in schema, APIs, repositories, and query construction:

1. **Global academic metadata:** `Paper`, `Author`, and `PaperSource`. This describes scholarly works and provider records, not a user's private library state.
2. **Private user data:** `UserPaper`, `Collection`, `Document`, `Annotation`, `ResearchProject`, `WritingDocument`, and `Conversation`. Every user-owned record has an explicit owner and authorization policy. A global paper can be referenced by many users through `UserPaper`; private notes or membership must never be stored on the global `Paper` row.
3. **Shared AI/RAG index:** `DocumentPage`, `DocumentChunk`, `Embedding`, `MessageCitation`, and `Analysis`. “Shared” means shared platform infrastructure and indexing code, not cross-tenant access. Persist enough owner/resource scope on indexed records and citations to enforce the originating document's ACL on every retrieval.

Use explicit foreign keys, uniqueness constraints, and indexes for the intended access patterns. Model any required association tables and session/security records explicitly. Do not add tenant data to global academic records to simplify a query.

## Security requirements

- Hash passwords with Argon2id using maintained libraries and deployment-appropriate parameters. Never store or log plaintext passwords. Verify hashes with constant-time library primitives and rehash on successful login when parameters need upgrading.
- Issue short-lived JWT access tokens and require a live, stateful, revocable `Session` for authenticated use. Bind the token to its session and user, validate signature, algorithm, expiry, issuer/audience as configured, and session revocation/expiry on every protected request. Rotate refresh/session credentials; store only hashes of opaque secrets where applicable.
- Implement one-time, expiring, hashed `VerificationToken` values for email/account verification. Make verification and token consumption atomic and replay-resistant.
- Write security-relevant events to an append-only `AuditLog` with actor, action, target, timestamp, and safe request context. Exclude credentials, raw tokens, full document contents, and sensitive prompts. Restrict audit access and retention.
- Require an explicit `user_id` ownership/ACL predicate for every private `/api/v1/` endpoint, repository operation, worker job, and RAG retrieval. Derive the actor from the authenticated principal; never trust a client-supplied owner ID. Scope by owner in the database query itself before returning rows or constructing an AI prompt. Return non-disclosing not-found/forbidden responses consistently.
- Use PostgreSQL row-level security as defense in depth where enabled. Set tenant context transaction-locally, fail closed if it is missing, and test connection-pool/session cleanup so context cannot leak between requests.
- Accept PDF uploads only after size limits, declared MIME checks, magic-byte/signature validation, safe parsing, and configured malware/content scanning. Store under generated object keys outside a public web root; never trust filenames or paths supplied by clients. Enforce authorization on download, parsing, chunking, and deletion.
- Enforce `AIUsage` quotas and rate/concurrency limits before expensive provider calls. Account usage atomically and idempotently; define limits for tokens, pages, storage, and spend. Do not use another tenant's content in prompts, caches, embeddings, or citations without explicit authorization.
- Treat uploaded content and retrieved passages as untrusted input. Keep system instructions separate, constrain tools, validate provider output, and avoid exposing one user's sources, citations, or generated content to another user.

## Change, migration, and quality gates

- Keep changes focused and reviewable. Add or update tests with behavior changes, especially authorization boundaries and failure cases. Do not weaken a test or security control merely to make a check pass.
- Use forward-only, reviewed Alembic migrations with explicit constraints and indexes. Test `alembic upgrade head` from a genuinely empty PostgreSQL database and verify upgrade/data-preservation behavior for supported existing databases. Do not rely on ORM `create_all()` as a production migration strategy.
- The required backend quality gates are: `pytest` passing in `backend/tests`, clean `alembic upgrade head` from an empty database, and tenant-isolation tests proving cross-user reads, writes, citations, and RAG retrieval are denied.
- Run formatting, linting, type checks, and the relevant test suite for changed components. Record checks that could not run; never claim success without running them.
- Do not edit backend Python code as part of a documentation-only task. Do not create or switch a development branch unless the task explicitly authorizes that operation.
