# Phase 06 — AI Research Assistant

Implemented on `feat/v2-foundation`. Phase 05 was already committed at `8788bce`
before this phase. CI retains `pgvector/pgvector:pg17` and now explicitly runs
with `APP_ENV=test` and `AI_DEFAULT_PROVIDER=offline`.

## Database and migration

Additive revision `f6b92d04a173`, following `e5a14c7b9d32`, creates:

- `Conversation`: explicit owner, validated paper/collection scope, English/Bangla
  language, and timestamps. Collection membership resolves dynamically per query.
- `Message`: owner-bound conversation history, user/assistant roles, structured
  evidence status, interpretation, missing information, suggestions and provider.
- `MessageCitation`: owner-bound paper/document/chunk provenance, original title,
  page, section, exact quoted excerpt and relevance score.
- `AIUsage`: owner, feature, provider/model, token counts, rolling-window timestamp,
  durable quota reservation/status, unique request UUID and request fingerprint.

Composite foreign keys enforce same-owner references. Nullable document/chunk and
collection links retain immutable owner IDs; deferred owner checks allow their
separate `SET NULL` actions to complete before commit. Paper deletion cascades
citation cards; conversation deletion cascades messages/cards while retaining quota
history. Downgrade refuses to discard nonempty conversations/usage without an
explicit prior export/purge. Existing migration history is unchanged.

## Provider gateway and privacy

`backend/app/modules/ai` provides Ollama chat, an OpenAI-compatible adapter for
cloud or local llama.cpp servers, and a deterministic extractive fallback. Offline
is the default, without external inference or weight downloads. Local mode uses
operator-managed preinstalled models; `auto` never silently promotes to cloud.

Cloud dispatch fails closed without the owner's `allow_external_ai` consent,
rechecked immediately before dispatch. Provider keys remain server-only. Six-second
HTTP/eight-second total deadlines, no redirects/proxies/retries, bounded responses
and validated JSON prevent indefinite inference waits. Failures fall back to local
source excerpts. No prompts, document text, keys or upstream bodies enter logs.

Daily/hourly request and token limits plus per-user concurrency are enforced under
a database user-row lock. Reserve a conservative 60,000-token input allowance plus
maximum output before embedding/retrieval/inference, then settle provider-reported
usage or conservative estimates. Failed/stale attempts retain reservation charges.
Request UUIDs prevent duplicate successful generations and quota charges; reuse
with different input is rejected. Reservations older than 60 seconds are reclaimed
as failed on the next request. Deleting a conversation cannot reset usage.

## Retrieval and academic reliability

`backend/app/modules/rag` scopes SQL candidates to the authenticated owner, current
document version, completed indexing state, and authorized library paper IDs or
current collection membership **before** any vector or lexical scoring.

Hybrid retrieval combines matching-model cosine similarity (35%) and Unicode-aware
lexical overlap (65%), then stable relevance reranking selects five page-local
passages. The bounded candidate scan reads at most 5,000 chunks and five excerpts
of at most 1,600 characters. Hash embeddings require at least half of meaningful
question terms to match; semantic embeddings need high cosine for paraphrases.
No/weak evidence bypasses inference and returns `insufficient_evidence` in the
conversation language. English/Bangla system instructions isolate untrusted passage
JSON and separate direct evidence, tentative synthesis and missing information.

Only retrieved chunk IDs and exact snippet substrings are accepted as citations.
The server supplies titles/pages; altered quotes, foreign IDs, duplicates or invented
inline references invalidate all generated evidence. After inference, SQL rechecks
scope, ownership, current version, title/page/heading and quote before persistence.
Source changes abort the attempt. Citation verification establishes provenance;
it cannot prove scientific correctness or semantic entailment of interpretation.

## API

All endpoints require a live authenticated session and return private/no-store
responses. Owner IDs are derived server-side; client-supplied owners are rejected.

| Method | Path | Behavior |
| --- | --- | --- |
| POST | `/api/v1/conversations` | Create validated single/multi-paper or collection scope |
| GET | `/api/v1/conversations` | List owned conversations with bounded limit/offset |
| GET | `/api/v1/conversations/{id}` | Return owned history and verified evidence cards |
| DELETE | `/api/v1/conversations/{id}` | Delete owned conversation and messages |
| POST | `/api/v1/conversations/{id}/messages` | Ask a question, optionally choose provider and supply retry UUID |
| GET | `/api/v1/ai/usage` | Rolling hour/day usage, remaining quotas and concurrency |

`summary` and `analysis` are reserved usage feature values, not implemented APIs.
Foreign scopes/conversations return non-disclosing 404; consent denial returns 403;
quota/concurrency limits return 429 with Retry-After; conflicting UUIDs or changed
sources return 409. Evidence cards use the existing protected document-page API.

## Frontend

`frontend/app/assistant/page.tsx` replaces the preview shell with an English/Bangla
workspace: paper search/pagination, single/multiple/collection scope selection,
conversation creation/switching/deletion, structured evidence/interpretation/missing
information, follow-up suggestions, provider selector, quota display and Settings
consent banner. Source cards open the exact indexed page in a native dialog via the
authenticated documents client. React renders excerpts as text, never raw HTML.
The workspace remounts on account changes; credentials remain memory-only.

## Verification

- Full backend suite: **346 passed, 0 failed/skipped**, **87.18% total coverage**
  in 111.83 seconds on Python 3.13.16 / Windows. Coverage XML/HTML were generated.
  Five existing PyMuPDF SWIG deprecation warnings remain.
- New tests cover foreign paper/collection/conversation denial, scoped retrieval,
  exact page/title/snippet citations, adversarial citation output, absent-topic
  refusal, Bengali text, consent changes, provider failures/redirects/malformed
  responses, per-window quotas, UUID replay, stale source changes and reservations.
- Real PostgreSQL concurrency tests admit exactly one provider call and reject
  three simultaneous conflicting/pending requests. Usage persists across chat
  deletion. Unsafe downgrade with stored conversations/usage is rejected.
- PostgreSQL 18: fresh `upgrade head → downgrade base → upgrade head`, existing
  library-data preservation, composite tenant constraints, nullable citation-link
  actions and conversation cascades pass. New head: **`f6b92d04a173`**.
- `alembic check`: **No new upgrade operations detected** after applying the final
  migration. Offline PostgreSQL DDL checks pass with pgvector enabled and disabled.
- `ruff check .` and Black pass across **142 Python files**. Black's local command
  excludes `.cache` because Windows test scratch directories have restricted ACLs.
- Frontend: **8 tests passed**, TypeScript, ESLint and production Next.js build
  pass. Node's existing module-type warning remains. No interactive browser or
  live external inference validation is claimed.

## Deployment limitations

- Live Ollama/cloud inference is intentionally not exercised. All generation and
  HTTP-adapter tests use deterministic local/fake adapters or `httpx.MockTransport`.
- Local PostgreSQL 18 has no installed pgvector extension. Live local migration
  checks use the portable JSON profile; offline PostgreSQL DDL covers both vector
  profiles. CI is configured for actual pgvector, but its remote run is not claimed.
- Hash embeddings and offline excerpts are deterministic fallbacks. Meaningful
  semantic synthesis requires an operator-provisioned local model or cloud consent.
- Retrieval is a bounded scan with deterministic reranking, not ANN query planning.
  Large libraries need future candidate-query optimization. No conversational
  memory beyond the submitted question is sent to inference in this phase.
- PostgreSQL RLS is not enabled here; query predicates and composite owner keys
  enforce application isolation. Provider interpretations remain explicitly labeled.

See [AI operations](../../backend/app/modules/ai/README.md) and
[RAG boundaries](../../backend/app/modules/rag/README.md) for configuration details.
