# Phase 03 — Research Discovery

## Delivery record

The discovery module exposes a unified asynchronous provider interface and public search and DOI routes. Saving requires an authenticated user and a source identifier. The server fetches the provider record again before persisting it. Canonical academic metadata is global. Library membership and the compatibility record used by the current library belong to the user.

### Providers and search behavior

- [x] arXiv API adapter with Atom/XML parsing, title/author/ID/all fields, DOI lookup, and provider-paced requests.
- [x] OpenAlex adapter for works, authors, dates, publication types, citation counts, DOI and work-ID lookup, with optional API-key support.
- [x] Crossref search and DOI resolution.
- [x] Semantic Scholar search, DOI and paper ID lookup, recommendations, citation links, and optional API key.
- [x] PubMed Entrez search, PubMed ID and DOI lookup, and XML record parsing. A configured API key is sent in the form body.
- [x] Pydantic discovery result schemas, partial provider warnings, date and publication type filters, result interleaving, and deduplication by DOI or normalized title and author. Redis caches results when `REDIS_URL` is configured. A bounded local cache supports development and Redis outages.
- [x] Provider transport timeouts, bounded retries, Retry-After caps, concurrency/rate pacing and safe upstream errors.
- [x] HTTP client URL logging suppression for `httpx` and `httpcore`.

### API and frontend

- [x] `POST /api/v1/discovery/search` accepts a query, sources, publication year range, publication type, relevance or date sort, limit, and offset.
- [x] `GET /api/v1/discovery/doi/{doi}` returns provider metadata and supports slashes in DOI paths.
- [x] `POST /api/v1/discovery/save-to-library` imports a verified provider reference into the authenticated user's library. Request validation rejects client-supplied metadata and owner identifiers.
- [x] Bilingual Discover screen with source filters/badges, date and publication-type filtering, citation counts/links, DOI lookup, pagination, provider availability and one-click library saves.
- [x] Catalog migration `c83a2f1a4d71` adds `Paper`, `Author`, `PaperAuthor`, `PaperSource` and private `UserPaper` tables. Existing `ResearchPaper` records stay in the legacy library. New saves write a private compatibility entry in the same transaction so the library, dashboard, and export include them.
- [x] Test coverage includes adapter response parsing/failures and endpoint paging, caching, merging, filtering, DOI, private imports, duplicate saves, and cross-user visibility.

Search examines up to 50 results per selected provider. The API reports the number of deduplicated results within that window and returns pages of up to 50 results. Complete snapshots are cached for five minutes and snapshots with provider warnings for 30 seconds. Provider request pacing is per application process.

## Configuration

Configure `REDIS_URL`, `OPENALEX_API_KEY`, `SEMANTIC_SCHOLAR_API_KEY`, `PUBMED_TOOL_EMAIL`, and `PUBMED_API_KEY` as needed. Development Compose points `REDIS_URL` at the Redis service.

Provider references cover rate limits, API keys, and available metadata. [arXiv API terms](https://info.arxiv.org/help/api/tou.html), [OpenAlex authentication](https://help.openalex.org/api/authentication/), [Crossref REST API](https://www.crossref.org/documentation/retrieve-metadata/rest-api/), [Semantic Scholar APIs](https://api.semanticscholar.org/api-docs/), [NCBI E-utilities](https://www.ncbi.nlm.nih.gov/books/NBK25497/).

## Verification

- `pytest -q` passed all 242 backend tests with 93.18% statement coverage. The run included PostgreSQL migration, identity, and concurrent discovery import tests.
- `alembic upgrade head` from an empty PostgreSQL database, `alembic downgrade base`, and a second upgrade passed. `alembic check` found no schema drift at `c83a2f1a4d71`.
- `ruff check .` and `black --check .` passed.
- Frontend typecheck, lint, all three Node tests, and the Next.js production build passed.
- Provider and Redis cache tests used mocks. Test HTTP traffic stayed local.
