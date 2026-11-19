# Phase 09 — Multimodal Research Intelligence

Implemented on `feat/v2-foundation` after Phase 08 checkpoint **`907a852`** using the
requested checkpoint message. This phase adds private PDF assets, source-linked
visual explanations/VQA and bilingual panels in Library and Paper Intelligence.

## Schema and migration

Revision **`c9e30f7b521d`** follows `b8d29e6a410c` and adds:

- `DocumentAsset`: requested figure/chart/diagram/table/equation metadata, page,
  caption, raw/normalized extracted text, structured values, private PNG key, linked
  chunk IDs, explanation and timestamps. Additional document version/extraction
  generation/image size and recent response history support safe refresh/replay.
- `AssetChunkLink`: same-owner asset/chunk membership, queried with originating
  document and current version constraints.
- `AssetExtractionJob`: owner/document/version, generation, durable queued/running/
  completed/failed status, attempt counter, sanitized error and lease timestamps.
- `AssetDeletion`: durable private object cleanup, including delayed write intents.

Composite owner foreign keys/indexes enforce tenancy. Cascades remove assets and
links on document/account deletion. A PostgreSQL trigger queues private PNG keys
even for raw cascade deletion; SQLite isolated tests mirror this trigger. The
migration explicitly adds `multimodal` to `AIUsage.feature` and guards downgrade
against discarding assets, pending cleanup or multimodal usage. Earlier migrations
remain unchanged.

## Extraction and indexing integration

An extraction request validates ownership and completed text indexing, commits a
durable job and returns **202 Accepted**. Parsing and crops run in a background
worker, with a standalone deployment command and optional in-API worker. Bounded
database polling recovers stale leases; document locks and generation/attempt/status
checks prevent stale or duplicate worker publication.

The worker reads an authorized private PDF, verifies size/hash and invokes a
killable PyMuPDF subprocess. `find_tables()` produces headers/rows/Markdown; embedded
image rectangles and vector clusters produce PNG figures, nearby captions provide
labels, and caption cues distinguish charts/diagrams. Numbered math expressions
retain normalized source text and context. Page bounding boxes are stored. Explicit
labels link to owned, same-document/version chunks; fallback links use same-page
surrounding text. No OCR/model download or equation-solving claim is introduced.

Limits include 1,000 pages, 200 assets, 100,000 extracted/structured characters,
4 MiB/4 million pixels per PNG and 32 MiB total PNGs. Native parsing has a 60-second
subprocess timeout. Refreshed extraction atomically replaces assets and queues old
crops for deletion. Reindexed documents make obsolete assets inaccessible.

## Private storage and recovery

Crops use generated keys under a configured, nonpublic owner-partitioned directory.
Paths reject traversal, symlinks/reparse points and nonregular/mismatched-size files.
Reads require owner/version checks before opening the image. The API returns no
storage paths, and image responses are PNG/private/no-store.

Known-key cleanup intents are committed before file writes. Successful asset
publication removes those intents transactionally; a canceled thread write remains
recoverable after a five-minute grace period. Ordinary failure cleans finished
objects promptly. Idempotent cleanup handles PDF/paper/account deletion, raw SQL
cascades and I/O retries without retaining private PNGs indefinitely. Production
cleanup runs periodically and alongside PDF cleanup; test paths drain explicitly.

## Vision and evidence

The shared gateway now accepts bounded PNGs for local Ollama and OpenAI-compatible
cloud vision models, plus the deterministic offline adapter. Existing privacy
consent, deadlines, quota locks and stateful authentication apply. Cloud image bytes
cannot leave the service without current `allow_external_ai`; gateway dispatch
also fails closed. All calls are recorded under **`AIUsage.feature='multimodal'`**.
Request UUIDs prevent duplicate successful charge/generation. Missing upstream
usage uses conservative prompt/image estimates; failed reservations remain charged.

English/Bangla results distinguish **extracted facts**, **AI visual interpretation**
and **missing information**. Facts must be exact source substrings from the allowed
caption/table/equation/linked chunk. Server-derived evidence identifies page and
asset. Qualitative interpretation rejects numerical tokens, spelled-out numbers,
math notation, equations, URLs and citations; chart values are never guessed.
Unrelated questions return `insufficient_evidence` before external dispatch. Source
version/generation/linked-text fingerprints are checked again before persistence.

Offline responses quote original source language and explicitly disclose inability
to digitize pixel-only values or verify equation derivations. Table previews retain
actual extracted cells; VQA exposes those facts rather than inventing arithmetic.

## Endpoints

All endpoints require a live authenticated session and scope SQL by the principal.
Foreign/stale private assets return non-disclosing 404. Upload/indexing prerequisites
and stale source conflicts are explicit; quotas/consent use existing 429/403 behavior.

| Method | Endpoint | Behavior |
| --- | --- | --- |
| POST | `/api/v1/multimodal/documents/{document_id}/extract` | Queue or refresh durable extraction; return job status (202) |
| GET | `/api/v1/multimodal/documents/{document_id}/assets` | Assets plus extraction status, optional type/page filters |
| GET | `/api/v1/multimodal/assets/{asset_id}` | Full metadata, structured rows and authorized linked passages |
| GET | `/api/v1/multimodal/assets/{asset_id}/image` | Private PNG crop |
| POST | `/api/v1/multimodal/assets/{asset_id}/explain` | English/Bangla explanation with separated evidence |
| POST | `/api/v1/multimodal/assets/{asset_id}/vqa` | Question with grounded facts/interpretation/missing evidence |

## Frontend

A shared English/Bangla Multimodal Assets panel is mounted in the Library document
viewer and single-paper analysis. It supports extraction/status polling, All /
Figures & Charts / Tables / Equations filters, page filtering, real table previews,
normalized equation cards, private PNGs, Explain Asset and VQA. Facts, interpretation
and missing evidence are displayed separately, with linked text references and
quota/consent state. Crops use bearer-authenticated, MIME-checked Blob requests;
object URLs/polling are canceled on document/account/view changes. No raw HTML or
public object URLs are used.

## Verification

- Full backend suite: **621 passed, 0 failed/skipped**, **85.09% total coverage**
  in **620.62 seconds** on Python 3.13.16 / Windows. Coverage XML/HTML were generated.
  Five existing PyMuPDF SWIG deprecation warnings remain. All inference tests are
  offline; the measured runtime includes the complete earlier-phase regression
  suite, native PDF extraction and private-storage tests on this host.
- **96 added backend cases** cover programmatically generated PDFs containing a
  real table, raster figure, vector chart, captions and numbered equation; layout
  extraction, exact source linking, rotation, resource limits, image MIME/storage,
  explanations/VQA, bilingual handling, invented values/equations, consent and quota
  enforcement, UUID replay, stale document denial and cross-user API isolation.
- Worker tests demonstrate sanitized parser failure, canceled in-flight PNG writes
  recovering via durable delayed cleanup, status/generation fences, traversal/
  symlink rejection, unindexed-job failure and cleanup after PDF/paper/account
  deletion. Native subprocess timeout/termination paths are deterministic tests.
- Live PostgreSQL: empty database upgrade/downgrade/re-upgrade and existing-library
  preservation pass. Cross-owner asset/chunk/document references are denied;
  raw document deletion creates the expected cleanup outbox row. Unsafe downgrade
  protection passes. Existing identity/writing/AI concurrency tests remain green.
- `alembic current`: **`c9e30f7b521d (head)`**. `alembic check`: **No new upgrade
  operations detected**. Both vector-enabled/disabled offline PostgreSQL DDL checks
  pass. Prior migration files remain unchanged.
- Black passes across **197 Python files**; Ruff and diff checks pass. Local Black
  excludes `.cache` paths hardened by Windows private-storage tests.
- Frontend: **19 tests passed**, including four new multimodal API/privacy/MIME/
  rendering-helper tests; TypeScript, ESLint and production Next.js build pass.
  Existing Node module-type notices remain. No interactive browser run is claimed.
- No external inference calls, model-weight downloads, heavy OCR/math dependencies,
  new external service requirements or TeX tooling were introduced by tests.

## Limits

Caption association, vector clustering and equation detection are layout heuristics,
not general scientific visual recognition. Scanned captions or formula glyphs may
need a future OCR/math model. There is no chart digitization, equation correctness
proof, broad arithmetic solver or guarantee of semantic entailment. Offline facts
preserve source language; optional local/cloud qualitative interpretation needs
human review. Large table/context bounds can omit some source rows from inference.
Original PDFs and full persisted extracted table data remain private to the owner.

Tests use generated real PDFs and mock/local provider adapters; live cloud/Ollama
generation and model weights are intentionally not exercised. Local PostgreSQL
uses the JSON-vector profile; CI retains `pgvector/pgvector:pg17`, but no remote CI
or local live pgvector run is claimed. PostgreSQL RLS is not enabled by this phase;
query predicates and composite owner constraints enforce access boundaries.

See [multimodal operations](../../backend/app/modules/multimodal/README.md).
