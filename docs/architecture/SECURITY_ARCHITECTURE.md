# ResearchNest v2 Security Architecture

## Security objectives

Treat authentication, authorization, document processing, vector retrieval, and AI usage as one tenant-bound workflow. The user identity and current permissions are established at the API boundary, propagated safely through the request/job context, and enforced again at data access. A shared database, Redis instance, or embedding index must never become an implicit cross-user sharing mechanism.

## Passwords, JWTs, and revocable sessions

- Replace the current bcrypt configuration with Argon2id using a maintained password-hashing library. Set and benchmark memory/time/parallelism parameters for deployment. Store only encoded Argon2id hashes, verify through the library's constant-time interface, and rehash on successful authentication when parameters change. Support a deliberate migration path for existing bcrypt hashes; never reset or log passwords as a shortcut.
- Issue short-lived, signed JWT access tokens with a narrow purpose and explicit `sub`, `sid` session identifier, `iat`, `exp`, issuer, and audience claims as deployment requires. Pin allowed algorithms in configuration; reject algorithm substitution, malformed claims, expired tokens, and wrong issuer/audience.
- A JWT is not sufficient by itself: each protected request validates that its `Session` exists, belongs to the subject, is active, and has not expired or been revoked. Store hashes for refresh/opaque session secrets, rotate them after use, detect replay, and revoke the session on logout, credential reset, suspicious activity, or administrative action.
- Keep access-token lifetime short. Define refresh behavior, session/device limits, logout-all behavior, clock-skew policy, key rotation, and signing-secret storage. Never put credentials in URL parameters or logs. For browser clients, use secure HttpOnly cookies plus an explicit CSRF defense where cookie transport is selected.

## Verification and security audit records

`VerificationToken` values are high entropy, purpose-bound, stored as hashes, expire quickly, are single-use, and are consumed atomically. Responses should avoid account enumeration. Rate-limit registration, login, verification, reset, and resend operations.

`AuditLog` records security-relevant events such as registration/verification, authentication success/failure, session creation/revocation, permission changes, upload lifecycle, sensitive export, and quota rejection. Events are append-only to application roles, timestamped, attributable, and carry a correlation ID and safe target metadata. Exclude passwords, raw JWT/session/verification values, PDF text, prompts, and other secrets. Restrict reads and define retention/integrity monitoring.

## Tenant isolation and private API rules

Every private `/api/v1/` endpoint authenticates first, derives `user_id` from the validated principal, and passes an explicit tenant context into its application service. Every private repository operation includes an owner/ACL predicate in the database query. Never accept a body/query `user_id` as authority or load an unscoped row and authorize it only after serialization.

For PostgreSQL defense in depth, enable row-level security on private tables and establish the authenticated user ID transaction-locally for each transaction. Policies fail closed with no context. Reset or overwrite context before a pooled connection is reused. Use separate migration/owner and runtime roles; runtime code must not have `BYPASSRLS` or table-owner powers that bypass policy.

Tests must create at least two users and verify that one cannot enumerate, read, edit, delete, download, annotate, cite, or process another user's resources. Test list/search pagination, error behavior, nested IDs, caches, worker jobs, and vector retrieval, not only direct object endpoints. IDs are not secrets; authorization must work regardless of whether identifiers are guessed or observed.

## PDF upload and processing boundary

1. Authenticate and authorize the destination user/project and check storage/page/AI quotas before accepting bytes.
2. Enforce request and decompressed-size/page limits. Validate extension and declared MIME as hints, then inspect file signatures/magic bytes and parse as PDF with a maintained hardened parser. Reject mismatches, malformed/encrypted files unless explicitly supported, decompression bombs, and unsafe embedded content according to policy.
3. Use a generated opaque storage key; never derive a filesystem path or public URL from the submitted filename. Store privately, encrypt in transit/at rest, and provide time-limited authorized downloads if needed.
4. Scan uploaded content as configured, then enqueue an idempotent processing job. Workers re-check the document owner and status before reading or writing pages/chunks/embeddings. Keep raw files and derived text under the same retention/deletion policy.
5. Record safe audit/status events. Do not place extracted text or raw file content in exception logs, telemetry, job names, or Redis keys.

## AI, RAG, and privacy controls

- Resolve allowed source IDs under the current user's permissions before retrieval. Apply the tenant and ACL predicates inside the vector/SQL query, then construct context only from authorized chunks. A global embedding index is shared infrastructure; it does not authorize global nearest-neighbor results.
- Re-check ownership when rendering saved analyses/citations and when workers process delayed jobs. Bind `MessageCitation` to its originating conversation, user, and source record so a citation cannot be replayed across tenants.
- Treat paper text, uploaded PDFs, retrieved passages, and model responses as untrusted. Defend against prompt injection by isolating retrieved context from system instructions, disabling unnecessary tools, constraining tool arguments, and validating outputs.
- Minimize data sent to providers. Define provider retention/training settings, data-region constraints, redaction, consent, and user-facing disclosure. Send only task-required content; never disclose other tenants' data or secrets. Scope cache keys by tenant, model, and resource ACL version; do not cache authorization decisions beyond their validity.
- Track every billable or expensive action against `AIUsage`. Reserve/check quota atomically before provider work, settle usage idempotently, cap pages/tokens/cost/concurrency, rate-limit abuse, and provide safe behavior on quota exhaustion. Prevent duplicate queue delivery from charging or processing twice.
- Store model, prompt/template, embedding, and source versions so results can be audited, invalidated, and rebuilt. Keep raw prompts/results out of ordinary logs; define encryption, access, and retention for stored analyses and conversations.

## Operational controls and security tests

Use TLS, managed secrets, least-privilege database/Redis/object-store credentials, dependency patching, secure CORS/CSRF configuration, request/body limits, rate limits, and safe error responses. Keep production debug mode off. Avoid logging authorization headers and query-string tokens. Alert on repeated authentication failures, anomalous session use, cross-tenant policy denials, upload parser errors, and quota abuse without logging private content.

The Phase 01 security gate includes password-hash verification/upgrade tests, expired and revoked-session tests, verification-token replay tests, audit redaction tests, per-endpoint tenant tests, RLS/pool-context tests, PDF MIME/signature/size tests, RAG cross-tenant retrieval tests, and concurrent/idempotent quota accounting tests.
