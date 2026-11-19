# Phase 05 — Document Intelligence

Phase 04 was checkpointed as `e002295` on `feat/v2-foundation`.

## Implemented pipeline

The document module extracts and indexes private PDFs asynchronously. Upload creates the document and its `pdf_extract_and_index` job in one transaction. After commit, the dispatcher publishes only the job ID to Redis when configured or to a bounded local queue. Database polling recovers queued work and stale running leases. A separately deployed worker can run with `python -m app.modules.documents.worker`.

Processing verifies the document owner, private storage object, byte size, and SHA-256 content hash. PyMuPDF reads each page separately. Low-text pages use an optional Tesseract pass with bounded image dimensions and OCR timeout. Missing OCR support leaves the extracted text available without preventing digital-text indexing. Section headings use an initial text-line heuristic.

Chunks overlap within a page and preserve Unicode text. A chunk records its page number, section heading, owner, document version, chunk index, and approximate whitespace token count. Page/chunk/vector rows commit together with completed job and document status. Version and attempt checks fence stale jobs, and duplicate deliveries do not append duplicate rows. Errors exposed by status endpoints use safe messages.

The embedding interface supports deterministic 384-dimensional hash vectors and an explicitly configured local Sentence Transformers model. Tests never install Sentence Transformers or download a model. Hash vectors support predictable local indexing; they do not provide the semantic quality of a trained model. A configured local model must produce 384 dimensions. External AI provider integration remains an explicit provider implementation.

## Schema and migrations

Migration `e5a14c7b9d32` follows `d429e3a5b6c1`. It extends the existing Document with pending/processing/completed/failed status, error, version and update timestamps; `file_hash` maps to the existing physical `sha256` field. It adds DocumentPage, DocumentChunk, Embedding and ProcessingJob. Composite owner foreign keys prevent cross-tenant index/job associations. Existing PDFs receive one queued job on upgrade.

Set `PGVECTOR_ENABLED=True` before migration in the pgvector PostgreSQL deployment. This profile provisions the vector extension and a 384-dimensional vector column/HNSW index, alongside portable JSON vectors. Docker and CI enable it. The disabled profile supports stock PostgreSQL and SQLite with JSON vectors. Keep this deployment setting consistent with the database migration profile; changing it later requires a reviewed type-conversion migration.

Downgrade refuses to remove intelligence tables while documents, pages, chunks, embeddings, or jobs remain. Export/purge documents and drain file cleanup before an intentional rollback.

## API and library UI

All routes authenticate the caller and scope queries to the owner:

| Route | Method | Behavior |
| --- | --- | --- |
| `/api/v1/documents/{document_id}` | GET | Current document metadata, page count, status and version. |
| `/api/v1/documents/{document_id}/status` | GET | Status plus recent jobs, attempt counts and safe errors. |
| `/api/v1/documents/{document_id}/pages` | GET | Extracted text, OCR flags, section headings and page numbers, paginated by page/size. |
| `/api/v1/documents/{document_id}/retry` | POST | Queue a failed document with a new version. Rejects duplicate active work. |

Responses omit private storage keys. Extracted pages are scoped to the current document version. The bilingual library and viewer show Pending, Processing, Indexed and Failed status, page counts and a failed-job retry action. The viewer polls active jobs and requests at most ten extracted pages per UI request.

## Configuration and runtime bounds

- `DOCUMENT_WORKER_IN_API=True` enables the local background worker. Set it false in API processes when deploying the standalone worker. Database jobs are durable when Redis is unavailable.
- `DOCUMENT_EMBEDDING_PROVIDER=hash` is the lightweight default. Choose `sentence_transformers` only with the optional package and an already installed model directory in `DOCUMENT_EMBEDDING_MODEL_PATH`. No automatic downloads occur.
- Install system Tesseract and the English/Bangla language data for OCR. Missing binary or OCR failure preserves the available page text, with `ocr_used=False`.
- Extraction and embedding run outside the event loop. Native PDF extraction runs in a subprocess that is terminated on timeout. Byte, page, text, chunk, OCR pixel and retry bounds limit resource consumption. Production workers should also have OS/container memory limits.
- PDF validation, malware scan requirements, private storage, ownership checks and deletion cascades from Phase 04 remain applicable.

## Verification

- All 297 backend tests passed with 86.59% statement coverage. This includes generated-PDF extraction, English/Bangla chunking, OCR fallback, versioned retries, duplicate/concurrent delivery, owner isolation, and PostgreSQL migration/identity checks.
- Fresh PostgreSQL upgrade, downgrade to base, re-upgrade, and `alembic check` passed at `e5a14c7b9d32`. No schema drift was detected.
- `ruff check .` and Black formatting checks passed.
- Frontend typecheck, lint, seven Node tests, and the production build passed.
- Both vector migration profiles passed offline SQL checks. SQLite tests also passed with the vector-enabled model profile. A live pgvector/HNSW run could not execute locally because the extension is absent; CI uses the pgvector image.
- OCR success/failure paths use mocks, and tests never download embedding models. The installed PyMuPDF version emits five SWIG deprecation warnings during pytest imports.

