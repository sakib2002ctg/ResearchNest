# Phase 08 — Citation & Writing Studio

Implemented on `feat/v2-foundation` after Phase 07 checkpoint **`adc1aaa`** using
the requested checkpoint message. The phase adds a private reference manager,
academic draft editor, separate source-verified AI suggestions and lightweight
document exports. No earlier migration or milestone document is overwritten.

## Persistence

Sequential Alembic revision **`b8d29e6a410c`** follows `a7c14e5f902b` and adds:

- `Citation` / `citations`: the requested bibliographic metadata, nullable private
  library link, stable per-user cite key, verification status and timestamps.
  Owner identity/title-year keys support DOI or normalized title/year deduplication.
- `WritingDocument` / `writing_documents`: document type, English/Bangla language,
  title/outline, Markdown, cited IDs, separate suggestion log, derived word count,
  timestamps and a revision counter for conflict-safe saving.
- `WritingVersion` / `writing_versions`: owner-bound numbered draft snapshots,
  title/content/outline/references and safe change summary. Owner/document/version
  uniqueness prevents duplicate checkpoint numbering.
- `WritingCitation` / `writing_citations`: relational same-owner reference membership,
  providing tenant constraints independent of a draft's JSON citation list.

Composite foreign keys enforce owner boundaries. Deleting a library paper nulls
the reference's paper link while retaining private bibliographic metadata; document
deletion cascades versions/membership. Account deletion cascades private records.
The migration explicitly extends the existing `AIUsage.feature` constraint to allow
`writing`. Downgrade refuses to discard stored citations/drafts/writing usage until
explicit export/purge; historical migrations remain unchanged.

## Reference manager

`backend/app/modules/citations` implements owner-scoped CRUD, creation from owned
library papers or DOI metadata, per-user deduplication, deterministic style output,
and atomic BibTeX/RIS import/export. Existing unlinked duplicates can be linked to
their owned library paper without inventing or replacing metadata. Cite keys remain
immutable so saved manuscripts/version placeholders retain stable identifiers.

Title and field validation is explicit. Missing authors/year/venue-or-DOI are exposed
as warnings and incomplete references remain unverified. Manual/imported records
cannot self-assert verification; trusted fetched metadata is verified only when
complete and not changed or supplemented with unverified client metadata.

APA 7, IEEE, MLA 9, Chicago author-date and a common Harvard variant produce in-text
strings plus bibliography entries. Plain-text templates cover common article,
conference, preprint and book metadata. Rich typography and every institutional/
CSL variant are not implemented. Missing/unverified metadata is flagged for review.
BibTeX macros/preambles/concatenation are rejected rather than executed. Import is
bounded to 200 records / 500,000 characters and all-reference exports refuse silent
truncation. All citation IDs supplied for formatting/export must belong to the actor.

## Writing and academic integrity

`backend/app/modules/writing` provides four bilingual templates, draft CRUD,
revision-aware autosave, manual/major-save checkpoints, history and restoration.
Restoring an old version preserves the current draft as a new snapshot first. The
server computes word count and resolves `[@cite_key]` only to real owned references;
unknown or deleted references block saves/exports instead of silently fabricating
or removing attribution. Version/reference associations are owner-constrained.

AI assistance supports abstract/introduction/literature-review/methodology/results
sections plus tone/grammar/paraphrase requests through the existing gateway. Quotas,
consent, request UUIDs and safe audit events are shared with previous AI features;
usage is recorded as **`feature="writing"`**. Cloud routing fails closed without
`allow_external_ai`; local/offline fallback never escalates private data to cloud.

Section drafts require owned indexed papers and owned library-linked citations.
Strict integrity mode returns source-backed quotations with server-injected real
cite keys; unreported experimental results and invented references are rejected.
Copy editing preserves Unicode-aware factual token order, numerical claims and
citations; only punctuation/spacing/case edits pass. This deliberately restricts
deep paraphrasing. Offline copy editing returns the original text honestly.

Every output is tagged **`ai_generated_suggestion`**, retained separately in the
latest 50 suggestion records. Assistance never overwrites authored Markdown or
silently creates an authored version. The UI requires explicit insertion. Draft
revision, source fingerprints and complete reference metadata/link fingerprints
are revalidated after generation before saving a suggestion. Citation deletion or
reassignment and source changes fail closed. All AI tests remain offline.

## Exports

Owned drafts export as Markdown, editable LaTeX, DOCX via `python-docx==1.2.0`, and
PDF via existing PyMuPDF, with a bibliography in the selected style. Everything is
generated in memory; no TeX installation/compilation or external HTML/font fetches
are used. LaTeX content is escaped; PDF HTML is built only from escaped text. Native
downloads use private bearer requests, validated MIME types and generated filenames.

The lightweight renderer supports basic academic headings/lists/paragraphs, bounded
to 200,000 manuscript characters / 400,000 combined characters / 200 PDF pages.
Bengali glyph shaping is supported by bundled fonts; PDF text extraction may not
exactly reproduce complex-script ligatures. Markdown/LaTeX/DOCX retain Unicode.

## API

Every route requires a live authenticated session with owner-scoped SQL predicates
and private/no-store responses. Client-supplied owner IDs are rejected.

| Method | Path | Behavior |
| --- | --- | --- |
| GET / POST | `/api/v1/citations` | List, manually create, or derive reference from library/DOI |
| PUT / DELETE | `/api/v1/citations/{citation_id}` | Update/delete an owned reference |
| POST | `/api/v1/citations/import` | Atomic BibTeX/RIS payload import and dedupe |
| GET | `/api/v1/citations/export?format=bibtex\|ris` | Selected/all owned reference attachment |
| POST | `/api/v1/citations/format` | Five-style bibliography and in-text strings |
| GET / POST | `/api/v1/writing` | List/create owned drafts |
| GET / PUT / DELETE | `/api/v1/writing/{doc_id}` | Read/save/delete with optional revision/version controls |
| GET | `/api/v1/writing/{doc_id}/versions` | Owner-scoped numbered version history |
| POST | `/api/v1/writing/{doc_id}/versions/{version_id}/restore` | Preserve current draft and restore owned version |
| POST | `/api/v1/writing/{doc_id}/assist` | Return a separate, reviewed AI suggestion |
| GET | `/api/v1/writing/{doc_id}/export?format=md\|tex\|docx\|pdf&style=apa` | Private document attachment with bibliography |

## Frontend

The English/Bangla Citations and Writing Studio preview shells are replaced with
working interfaces. References support metadata editing, DOI/library creation,
import/export, five style previews and verification warnings. The editor supports
templates/outlines, Markdown, citation insertion, conflict-aware autosave, checkpoints,
restore, quota/consent messaging, distinct AI suggestions, explicit insertion and
all export formats. Pending saves preserve newly typed edits; conflicts pause
autosave and offer an explicit reload. Downloads preserve bearer isolation, reject
unexpected MIME/redirects and never put credentials in URLs or persistent storage.

## Verification

- Full backend suite: **525 passed, 0 failed/skipped**, **85.97% total coverage**
  in **246.80 seconds** on Python 3.13.16 / Windows. Coverage XML/HTML generated;
  five existing PyMuPDF SWIG deprecation warnings remain.
- **129 added backend cases** cover reference ownership, DOI/library metadata,
  deduplication, incomplete-data warnings, all five formatting styles, BibTeX/RIS
  parsing/escaping, draft CRUD/revisions/version restore, all four actual export
  formats, Unicode, missing references, AI consent/quota/replay, invented results,
  result-attribute swaps, negation/Bangla vowel edits and inference-time races.
- PostgreSQL: fresh empty-database upgrade/downgrade/re-upgrade and legacy data
  preservation pass. Real concurrent saves produce one success and one 409 with
  unique numbered snapshots. Cross-owner version/reference links are denied;
  unsafe downgrade refuses to discard drafts/citations. Earlier AI concurrency
  and isolation tests remain passing.
- `alembic current`: **`b8d29e6a410c (head)`**. `alembic check`: **No new upgrade
  operations detected**. Vector-enabled/disabled offline PostgreSQL DDL tests pass.
- **178 Python files** pass Black; Ruff and diff checks pass. Local Black excludes
  restricted `.cache` test scratch paths. Previous migration files are unchanged.
- Frontend: **15 tests passed**, including private reference/writing API contracts,
  MIME-checked downloads, in-flight autosave preservation and explicit suggestion
  insertion. TypeScript, ESLint and production Next.js build all pass. Existing
  Node module-type notices remain; interactive browser validation is not claimed.
- All inference/DOI test providers are offline mocks; no external LLM/API requests,
  weight downloads, TeX installation or PDF compilation subprocesses are used.

Local live PostgreSQL checks use the existing JSON-vector profile because pgvector
is not installed on this host. CI remains configured with `pgvector/pgvector:pg17`;
a remote CI run/live pgvector validation is not claimed. Provider integration is
validated through mock HTTP/contracts, not live cloud/Ollama generation.

See [citation module](../../backend/app/modules/citations/README.md) and
[writing module](../../backend/app/modules/writing/README.md) for contracts/limits.
