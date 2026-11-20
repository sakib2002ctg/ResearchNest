# Phase 07 — Paper Intelligence

Implemented on `feat/v2-foundation` after Phase 06 checkpoint `d364a87`, committed
with the requested Phase 06 message. This phase adds source-attributed single-paper
extraction, multi-paper comparison and research-gap exploration. Earlier modules,
documentation and migration history are preserved.

## Models and migration

Revision **`a7c14e5f902b`** follows `f6b92d04a173` and creates:

- `Analysis` / `analyses`: owner, private library paper, nullable source document,
  language/status, all 13 requested extraction fields, page-level evidence,
  provider/model and timestamps. Additional document version/fingerprint, per-field
  evidence statuses, safe failure message and retry UUID support reliable refresh.
  Unique owner/paper/language rows prevent duplicate saved extractions.
- `PaperComparison` / `paper_comparisons`: owner/title, selected paper IDs/language,
  comparison matrix, literature synthesis, evidence-backed gaps, source snapshots,
  provider/model and timestamp. Unique owner/request UUID supports replay safety.
- `ComparisonPaper` / `comparison_papers`: relational same-owner membership for
  each comparison, providing database constraints independent of JSON paper lists.

Owner-pair foreign keys enforce paper/document/comparison tenancy. Paper and account
deletion cascade private analysis/membership records. Document deletion sets the
analysis document link to null while keeping the owner and labeling its snapshot
stale. Deferred document-owner validation runs after the `SET NULL` action.
Downgrade refuses to silently delete stored intelligence without export/purge.

## Backend behavior

The new bounded module at `backend/app/modules/analysis` owns routes, validation,
repositories, extraction and orchestration. It reuses Phase 05 indexed chunks and
the Phase 06 gateway, consent checks, user-row quota lock and `AIUsage` accounting
with **`feature="analysis"`**. Existing chat adapter contracts remain intact.

All paper IDs are private `UserPaper.id` values. Query predicates enforce ownership
on every selected paper and indexed chunk before context selection. Missing,
processing or unreadable PDFs return a clear 409; foreign resources return 404.
Context is section-diverse and bounded to 10,000 characters, with equal budgets per
paper, from at most 2,000 current chunks per paper. Metadata and exact snippets stay
in the untrusted user message; instructions/JSON schemas stay in the system message.
No ingestion, model download or unbounded provider work occurs in request paths.

Offline mode extracts English/Bangla source quotations using conservative section
cues. Optional local/cloud inference uses strict structured output. Missing fields
are exactly **`Not specified in document`** (a one-item list for list fields).
`field_statuses` marks quoted evidence, tentative interpretation or missing details.
Dataset/model/metric names must occur verbatim in verified quotes. Strengths and
weaknesses require explicit source mention. Every attribution is verified against
offered chunk IDs/quotes, then enriched with server-derived page/title/heading and
document version. Source fingerprints are rechecked under locks before persistence.

Analysis caching is specific to owner, paper, language and source fingerprint.
`force_refresh` regenerates; failed refresh keeps an existing valid result. Saved
responses report stale source versions explicitly. Successful retry UUIDs replay
without duplicate usage. Failed/stale attempts retain quota reservations and safe
audit events. Calls reserve 60,000 input tokens plus the configurable structured
output cap (default 4,096), subject to shared hourly/daily and concurrency limits.
Cloud calls require current external-AI consent; unavailable providers fall back to
private deterministic extraction. Live providers are never used by tests.

Comparisons require 2–5 distinct owned/indexed papers. The matrix shows methodology,
datasets, models, metrics, results and limitations with per-cell evidence. Literature
synthesis and gap claims require evidence from at least two different selected
papers. Gaps must cite explicit limitations/future work and are labeled tentative
interpretations scoped to **selected papers only**. Insufficient gap evidence returns
an empty gap list, never a claim about gaps across the entire literature.

## Endpoints

All routes require a live authenticated session and private/no-store responses.
The API derives ownership from the principal; client owner fields are rejected.

| Method | Endpoint | Behavior |
| --- | --- | --- |
| POST | `/api/v1/analysis/{paper_id}` | Analyze/regenerate; optional language and force-refresh in body or query |
| GET | `/api/v1/analysis/{paper_id}` | Retrieve owner's saved extraction for the requested language |
| GET | `/api/v1/analysis` | Paginated owner-scoped saved analyses |
| POST | `/api/v1/analysis/compare` | Generate/save a 2–5 paper comparison |
| GET | `/api/v1/analysis/comparisons` | Paginated accessible saved comparisons |
| GET | `/api/v1/analysis/comparisons/{comparison_id}` | Retrieve owner-scoped matrix, synthesis and gaps |

Provider routing and retry UUID are optional request controls. Quota denial returns
429 before provider calls; consent denial returns 403; stale sources/retry conflicts
return 409. Invalid attributed output returns a safe 502 without persisting claims.
Routes with static comparison paths are registered before the paper-ID route.

## Frontend

`frontend/app/analysis/page.tsx` replaces the Phase 07 preview with English/Bangla
single-paper and comparison workspaces. Features include library search/pagination,
indexed-paper selection, output language/provider controls, regeneration, saved
result browsing, source/missing/interpretation badges, structured cards, comparison
table, synthesis and gap cards. Quota state and external-AI consent are visible.
Evidence badges show paper/page/heading and exact quotations; the authenticated
source dialog verifies document version and quoted page text before display.
Stale results disable evidence navigation. React displays content as text, without
raw HTML. Account changes remount the workspace; bearer tokens remain memory-only.

## Verification

- Full backend suite: **396 passed, 0 failed, 0 skipped**, **87.31% total coverage**
  in **129.14 seconds** on Python 3.13.16 / Windows. XML/HTML coverage reports were
  generated. Five existing PyMuPDF SWIG deprecation warnings remain.
- **50 added backend cases** cover extraction/missing fields, bilingual handling,
  exact source attribution, adversarial claims, 2–5 paper comparisons, evidence
  requirements for research gaps, consent, quotas, caching/refresh/replay, stale
  sources, cross-tenant reads/writes and PostgreSQL persistence constraints.
- PostgreSQL: genuinely empty database `upgrade head → downgrade base → upgrade
  head`, existing-library preservation, analysis/comparison persistence, foreign
  owner denial, nullable document links, cascades and protected downgrade pass.
  Both vector-enabled and JSON-profile offline DDL checks pass.
- `alembic current`: **`a7c14e5f902b (head)`**. `alembic check` reports **No new
  upgrade operations detected**. Previous migration files remain unchanged.
- Ruff and Black pass across **154 Python files**. Black excludes local `.cache`
  scratch paths because earlier Windows security tests restrict their ACLs.
- Frontend: **9 tests passed**; TypeScript, ESLint and production Next.js build
  pass. Node's existing module-type warning remains. Browser interaction and live
  inference were not exercised.
- All provider tests use deterministic local adapters or `httpx.MockTransport`;
  no external LLM calls, model downloads or weights are required by pytest.

## Limits and deployment notes

- Offline extraction preserves source language and uses section cues; it does not
  provide semantic translation or infer unstated conclusions. Local/cloud adapters
  can synthesize, but their interpretations still require academic review.
- Source verification establishes provenance, not semantic entailment or scientific
  truth. The selected set is not a comprehensive literature review.
- Context limits can omit portions of very large papers. Missing markers describe
  the analyzed source context; they do not prove absence from all literature.
- Saved extraction is versioned as a current snapshot per paper/language, not an
  archive of every regeneration. Comparisons retain separate historical snapshots.
- Tests mock all inference HTTP. Live cloud/Ollama/model weight validation is not
  claimed. No new dependencies or model downloads are required.
- Local PostgreSQL lacks pgvector; local live checks use JSON vectors and offline
  DDL exercises both profiles. Existing CI uses `pgvector/pgvector:pg17`; a remote
  workflow run is not claimed here. PostgreSQL RLS remains a deployment option;
  this module enforces application predicates and composite tenant constraints.

See [module operations and boundaries](../../backend/app/modules/analysis/README.md).
