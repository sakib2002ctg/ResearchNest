# Phase 04 — Personal Research Library

Phase 03 was checkpointed as `ccdf9e8` on `feat/v2-foundation`.

The library organizes both manually saved and discovered papers. Migration `d429e3a5b6c1` adds collections, tags, notes, highlights, PDFs, and reading progress. It backfills private library entries for existing papers and preserves their owners and saved dates. An uploaded PDF can create a private paper or attach to an existing one. The library stores upload metadata on the private document record. Composite foreign keys enforce the same owner on both sides of collections, tags, annotations, and PDF attachments.

## API

All routes below require the user's active session and use the `/api/v1/library` prefix. In library routes, `paper_id` means the private `UserPaper.id`. The library list also returns `legacy_paper_id` for existing paper routes.

| Route | Methods | Behavior |
| --- | --- | --- |
| `/papers` | GET | List and search owned papers. Filter by collection, tag, or both. |
| `/collections`, `/collections/{collection_id}` | GET, POST, PATCH, DELETE | List, create, read, rename, edit, and delete collections. |
| `/tags`, `/tags/{tag_id}` | GET, POST, PATCH, DELETE | List, create, read, rename, recolor, and delete tags. |
| `/collections/{collection_id}/papers/{paper_id}`, `/tags/{tag_id}/papers/{paper_id}` | PUT, DELETE | Assign or remove papers. Both resources must belong to the caller. |
| `/papers/{paper_id}/annotations`, `/papers/{paper_id}/annotations/{annotation_id}` | GET, POST, PATCH, DELETE | Manage private notes and highlights, with an optional page number and color. |
| `/papers/{paper_id}/progress` | PATCH | Save unread, reading, or completed status and a percentage from 0 to 100. |
| `/upload` | POST | Upload a multipart PDF. Supply `user_paper_id` to attach it to an owned paper. |
| `/papers/{paper_id}/pdf` | GET, DELETE | Download or delete an owned PDF. |

The English and Bangla library provides collection and tag filters, editing and membership controls, reading badges and progress, drag-and-drop uploads, and a local PDF.js canvas viewer with notes and highlights. It uses the authorized PDF endpoint to fetch file bytes. Browser verification did not complete because the local-origin approval gate denied access; the automated frontend build and tests passed.

## PDF storage and deletion

The endpoint accepts up to 25 MiB per PDF. It limits multipart input and validates the declared MIME type, PDF signature, and document structure. It rejects malformed and encrypted PDFs and unsupported active content. It stores originals under opaque SHA-256 keys derived from fresh random bytes and separately records a content checksum. The download endpoint requires an active session, checks ownership, and sends the PDF as a private attachment.

Set `PDF_STORAGE_ROOT` to a dedicated persistent directory, owned by the service and outside any web root; do not point it at a directory containing other files. The default is `backend/storage/pdfs` when starting from the backend directory. The service locks down that directory (including its Windows ACL) and rejects unsafe paths. Configure `CLAMAV_HOST`, and optionally `CLAMAV_PORT` and `CLAMAV_TIMEOUT_SECONDS`, for staging and production uploads. The service rejects uploads when a required scanner is unavailable. Development and test environments can validate PDF structure without a scanner. Keep the scanner connection on a private network and configure its stream limit to accept 25 MiB uploads.

Deleting a PDF, its paper, or its user account records a cleanup job in the same database transaction. Access ends when the transaction commits. The cleanup job retries filesystem deletion if needed. Account JSON exports include owner-scoped collections, tags, annotations, progress, and PDF metadata. They exclude storage keys, content checksums, and file bytes; PDF bytes remain available via the owner-authorized endpoint. Back up private files with the database. Before rolling back past `d429e3a5b6c1`, export or purge the saved PDFs and drain deletion jobs. The downgrade refuses to run while document metadata or deletion jobs remain.

## Verification

- `pytest -q` passed all 268 backend tests with 89.36% statement coverage. This included PostgreSQL empty-database migrations, data backfill, tenant constraints, migration rollback safeguards, and private PDF upload/cleanup tests.
- `alembic upgrade head`, `alembic downgrade base`, and re-upgrade passed on an isolated PostgreSQL database. `alembic check` found no schema drift at `d429e3a5b6c1`.
- `ruff check .` and `black --check .` passed.
- Frontend typecheck, lint, all six Node tests, and the Next.js production build passed with Node 24.
- API-driven tests and the build passed. Browser verification was blocked by the localhost origin approval gate, so the rendered page was not visually verified.
