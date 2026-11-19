# Phase 10 — Research Projects and Insights

Implemented on `feat/v2-foundation` after Phase 09 checkpoint **`c46b6ce`** using
the requested checkpoint message. This phase adds Modules 10 and 11: private
project workspaces, deterministic library analytics, and an interactive bilingual
knowledge graph. No graph library, model download, or external analytics provider
is required.

## Schema and migration

Revision **`d0f14b8a632e`** follows `c9e30f7b521d`. Earlier migrations are unchanged.

- `ResearchProject` stores the owner, title, description, JSON objectives, lifecycle
  status, task-derived progress, deadline, optional collection, timestamps, and a
  revision counter for conflict-aware edits.
- `ProjectPaper` links a project to an owned `UserPaper` with a role and addition
  timestamp. `(project_id, user_paper_id)` is unique. An explicit `user_id` enables
  composite database ownership constraints on both sides.
- `ResearchNote` stores an owned project note and an optional owned library paper.
- `ProjectTask` stores tasks/milestones, status, deadline, completion timestamp and
  creation/update timestamps. A database check keeps completion timestamps
  consistent with `done` status.
- `Conversation.project_id` is nullable and indexed. New conversations can supply
  it atomically, or existing owned conversations can be linked through Projects.
  Conversation source authorization continues to use its explicit paper or
  collection scope; a project link does not broaden retrieval permissions.

Every association has an owner-scoped SQL lookup and database ownership foreign
keys. Deferred composite constraints allow a separate `SET NULL` resource FK to
clear a deleted collection, note paper, or conversation project while preserving
the immutable owner. Project deletion cascades to project memberships, notes and
tasks; it retains library papers and conversations. The downgrade refuses to
discard nonempty projects; export/purge is required first. Empty-database upgrade,
downgrade and re-upgrade are supported.

## Project behavior

Request paths use existing async SQLAlchemy sessions and live-session
authentication. Mutations acquire the existing account lock before resolving
resources, serializing progress edits and association/deletion races. Optional
`expected_revision` detects stale project edits with 409. Foreign resources and
missing resources return non-disclosing 404 responses.

Progress is `100 * done tasks / all tasks`, rounded to two decimals; no tasks means
0%. Milestones have the same weight as other tasks. All tasks done automatically
marks a nonarchived project completed. Reopening/deleting tasks can restore active
status; archived status is preserved. `completed_at` is set/cleared with task state.

Project exports support JSON and Markdown, with objectives, deadlines, papers,
tasks/milestones, research notes, saved paper-analysis snapshots, linked chat
excerpts, and APA/IEEE/MLA/Chicago/Harvard bibliography formatting. Analysis
snapshots carry a current-source `is_stale` flag. Chat summaries are explicitly
identified as latest assistant excerpts, not fresh generated summaries. Canonical
structured authors take precedence; ambiguous legacy names retain surname commas.
Incomplete fallback references remain unverified and include metadata warnings.
Exports contain only the current owner's project-linked records and trigger no
AI/provider calls. Private responses use `private, no-store` and `nosniff` headers.

## Endpoints

All endpoints below require authentication; project IDs and linked resources are
checked against the principal in database queries.

| Methods | Endpoint | Behavior |
| --- | --- | --- |
| GET, POST | `/api/v1/projects` | Paginated/status-filtered list and create |
| GET, PUT, DELETE | `/api/v1/projects/{project_id}` | Workspace detail, edit, delete |
| POST | `/api/v1/projects/{project_id}/papers` | Link an owned library paper, set role |
| DELETE | `/api/v1/projects/{project_id}/papers/{user_paper_id}` | Remove membership |
| GET, POST | `/api/v1/projects/{project_id}/notes` | List/create research notes |
| PUT, DELETE | `/api/v1/projects/{project_id}/notes/{note_id}` | Edit/delete a project note |
| GET, POST | `/api/v1/projects/{project_id}/tasks` | List/create tasks and milestones |
| PUT, DELETE | `/api/v1/projects/{project_id}/tasks/{task_id}` | Edit/delete, recompute progress |
| POST | `/api/v1/projects/{project_id}/conversations/{conversation_id}` | Link an owned conversation |
| GET | `/api/v1/projects/{project_id}/export` | `format=json\|markdown`, optional `citation_style` |
| GET | `/api/v1/analytics/overview` | Library trends, networks, reading/analysis coverage |
| GET | `/api/v1/analytics/timeline` | Actual chronological library/project/task events |
| GET | `/api/v1/analytics/knowledge-graph` | Bounded graph with explicit origins/provenance |

The three analytics endpoints accept optional `project_id`; a foreign/missing
project returns 404 even for an otherwise empty library. The existing
`POST /api/v1/conversations` also accepts an owned `project_id`.

## Analytics and provenance

Analytics applies owner/project SQL predicates before materializing rows. Global
academic metadata is projected only through this owner's selected `UserPaper`
records. Results include known publication-year distributions, unknown-year counts,
reading funnel, recurring authors/coauthors, venue/provider breakdown, tags,
inferred title keywords, and saved/indexed/analyzed coverage.

Indexed coverage requires a completed, current-version document with a matching
chunk and embedding. Analyzed coverage additionally requires a completed analysis
whose source fingerprint still matches the current source. Timeline entries use
actual saved/project/task timestamps; publication dates and reading-completion
dates are never invented from save dates.

Freshness work is bounded to 100 candidate papers and 20,000 budgeted chunk rows
per overview. A grouped SQL count precedes text reads; each selected paper uses
the analysis API's first-2,000-chunk fingerprint contract. The response reports
`coverage.analysis_freshness` with checked/unchecked papers, work limits and
truncation. When unchecked candidates remain, analyzed counts/percentages are
explicit verified lower bounds; the UI uses `≥` and does not label unchecked
analyses as absent. This path makes no AI or embedding-provider calls.

Every graph node and edge carries `origin: verified_metadata | inferred_similarity`
and a more specific `provenance`. Here `verified_metadata` identifies recorded
provider metadata or explicit user records, not an independent validation of
user-entered scholarly facts. Nodes include papers, authors, tags, title-derived
topics and projects. Edges include `authored_by`, `tagged_with`,
`project_contains`, actual recorded `cites_or_related`, and
`shared_topic_inferred`. Inference uses deterministic title-keyword overlap; it
never becomes a verified citation. Adjacent shared-topic connections avoid a
quadratic clique. Citation edges require recorded DOI links with both endpoint
papers in the authorized scope.

The discovery save path now retains a bounded allowlist of public, server-verified
provider metadata in `PaperSource.metadata_json`, including up to 20 citation
links. Verified refetches refresh metadata while preserving prior links when the
provider omits citations; previously recorded, validated venue metadata is also
retained. Unknown/private fields are excluded. Semantic Scholar ID lookup now
parses the same incoming citation records as DOI lookup. The broad
`cites_or_related` label and provenance disclose these as incoming citing-paper
links, without claiming outgoing reference direction. Both edge endpoints must
still belong to the authorized library/project scope.

Overview materializes at most 5,000 papers and reports included/total papers and
truncation. Graph input is capped at 300 papers, with at most 1,000 nodes and 3,000
edges. Limits are returned and displayed rather than hiding partial results.
Project totals use a separate exact SQL count; at most 1,000 project records are
materialized, with `project_scope` included/total/truncated disclosure. Author
networks use at most 30 recorded author names per paper; inferred title topics
use at most 12 non-stopword keywords. These are descriptive metadata projections,
not a claim that the library covers an entire scientific field.

## Frontend

`/projects` replaces the preview with English/Bangla cards, progress bars, deadlines,
paginated lists, create/edit/delete dialogs, and workspace tabs for overview and
objectives, papers, tasks/milestones, notes and linked AI chats. Users can link/unlink
papers, manage notes/tasks, open existing chats, create a scoped project chat, and
download JSON/Markdown bundles. Project chat creation is atomic; the bounded
50-paper conversation scope is disclosed before creation.

`/insights` provides project filtering, publication-year SVG bars starting at zero,
reading/index/analysis metrics, author/coauthor and venue lists, tags/topics, and a
chronological timeline. The SVG graph supports search, node-type filtering,
inferred-edge toggling, zoom, keyboard/click selection and neighbor inspection.
Solid recorded edges and dashed inferred edges have an explicit bilingual legend.
The client displays at most 120 nodes per page with clear server/view limits.
Private requests and downloads use the existing authenticated transport; stale
loads are aborted when account/scope/view changes. No heavy chart dependencies
were added.

## Verification

- Full backend suite: **693 passed, 0 failed/errors/skipped**, **83.91% total
  application coverage** (6,628 / 7,899 executable lines), **247.29 seconds** on
  this Windows host. Coverage XML/HTML and JUnit results were generated. The
  Phase 09 baseline was 621 tests; **72 cases were added**. Five existing
  PyMuPDF SWIG deprecation warnings remain.
- Tests cover project CRUD, all required authentication boundaries, cross-user
  and wrong-project associations, derived progress/reopening/milestones, revision
  conflicts, cascades/nullable references, new/existing conversation links,
  JSON/Markdown export isolation and dates, canonical author attribution, stale
  summaries, analytics counts/filtering/freshness budgets, graph origin labels,
  truncation, malformed metadata, and mocked verified discovery-save-to-graph
  citation persistence/refetches. No external HTTP or AI service was used.
- Real PostgreSQL tests pass for composite owner constraints, `SET NULL`
  preservation, concurrent task completion/progress, and stale revision conflicts.
  The migration suite passes **empty DB → head → base → head**, further cleanup,
  and supported-existing-data upgrades, including a Phase 09 conversation whose
  title/paper scope survives with `project_id = NULL`.
- `alembic check`: **passed**, no new upgrade operations detected, current head
  `d0f14b8a632e`. Local live PostgreSQL uses `PGVECTOR_ENABLED=false`; offline DDL
  generation passes for both vector profiles. A live pgvector-extension run was
  not performed locally; Phase 10 does not change vector mappings.
- `ruff check .`: **passed**. `black --check --extend-exclude '(.cache)' .`:
  **passed, 217 files unchanged**. `git diff --check`: **passed**.
- Frontend `npm run typecheck`, `npm run lint`, **26/26 tests** (7 added), and
  `npm run build`: **passed**, production build includes **21 routes**. Client
  tests exercise authenticated request contracts, privacy/download checks,
  project-chat bounds, publication buckets, graph filtering and deterministic
  layout. Browser end-to-end tests were not run.

Phase 10 implementation is left uncommitted for review; the requested Phase 09
checkpoint is the only new commit made for this task. No dependencies were added.
