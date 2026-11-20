# Phase 11 — Research Education and Team Collaboration

Implemented on `feat/v2-foundation` after Phase 10 checkpoint **`d9ccac5`**, using
the requested checkpoint message. The actual preceding migration is
`d0f14b8a632e`. This phase adds Module 12's English/Bangla education center and
the deferred team collaboration portion of Module 10.

## Schema and migration

Revision **`e1c25d9b743f`** follows `d0f14b8a632e`. Earlier migrations remain
unchanged. The migration adds five tables and admits `education` in the existing
`AIUsage.feature` check constraint.

- `LearningProgress`: owner, guide slug, completed step IDs, completion flag and
  update timestamp; `(user_id, guide_slug)` is unique, with owner/slug indexes.
- `TeamWorkspace`: immutable owner, name, description and timestamps.
- `TeamMember`: workspace/user pair, role, inviter and join timestamp. The pair is
  unique. A partial unique index admits at most one owner membership; an internal
  owner discriminator, check and composite FK prevent another user from forging
  the workspace owner's role. Other memberships have editor/viewer roles.
- `TeamSharedCollection`: explicit workspace/collection grant, sharer and timestamp.
  Composite FKs require the collection to belong to the sharer and the sharer to
  remain a member. Membership deletion cascades to its sharing grants.
- `TeamNote`: workspace, immutable author, optional shared paper, title, content
  and timestamps. A paper `SET NULL` FK preserves authored notes when the paper
  is deleted. Note authorship is independent of the referenced paper's owner;
  linking requires a current workspace sharing grant in SQL.

User/workspace FKs and indexes support cascades and ACL queries. Deleting a team
removes memberships, grants and team notes without deleting personal collections
or papers. The downgrade refuses to discard learning progress, teams or education
usage; export/purge is required first. Empty-database downgrade is supported.

## Education catalog and private progress

The static curriculum contains **five bilingual guides, 16 guided steps and 18
glossary terms**. Every guide has English/Bangla titles, summaries, step guidance,
checklists, estimated study time, primary reading references and links into
Discover, Library, Analysis or Writing.

Topics cover three-pass paper reading, research questions/gaps, systematic
literature reviews, methodology/experimental design, and statistics/evaluation.
The glossary covers all requested terms plus effect size and reproducibility;
each entry has bilingual equivalents/definitions and academic usage examples.
Search normalizes Unicode/case and searches both languages, with category filters.

The teaching notes are original summaries with checked references to Keshav's
paper-reading guide, PRISMA, the American Statistical Association, NIST, the DOI
Foundation and the U.S. Office of Research Integrity. Serving the catalog makes
no network request. PRISMA is described as reporting guidance; p-values and
confidence intervals distinguish their statistical assumptions from common
misinterpretations.

All education routes require the existing live-session authentication. Progress
reads/writes use the authenticated owner. Updates accept only bounded IDs from
the selected guide, deduplicate them into catalog order, and derive completion
from the complete set of current steps. Account locking and the unique key
serialize progress creation/update. No client-supplied owner/completion flag is
trusted; obsolete step IDs are ignored when reading a revised catalog.

## Beginner paper explanation

The explainer accepts an owned, currently indexed library paper, language,
provider choice and request UUID. SQL ownership checks run before reading source
text. A completed document must have current-version chunks and embeddings.
Context is bounded using the existing analysis selection/fingerprint contract.

The existing `AIProviderGateway` handles offline/local/cloud selection. External
AI requires current `allow_external_ai` consent, checked before reservation and
again immediately before dispatch. Quota reservation holds the durable account
lock and records `AIUsage.feature='education'`. The reservation and missing-usage
fallback use the actual **structured-generation** completion limit
(`ANALYSIS_MAX_COMPLETION_TOKENS`), not the smaller chat limit.

Exact quotations remain separate from qualitative plain-language AI sections.
Every section references server-validated quotations from the offered owned
chunks. Source/page/version metadata comes from the server. Invented chunk IDs,
quotes, numerical details, mathematical notation, URLs and reference markup are
rejected; duplicate section focuses are rejected too. The lexical guard is a
heuristic, not a proof of semantic entailment. Bangla negation `নয়` is distinguished
from explicit quantity forms. Interpretations are labeled tentative and require
review against the original evidence; exact source quotations are never rewritten.

Offline mode provides source quotations, curated bilingual terminology and reading
guidance. It explicitly does **not** claim to paraphrase or translate a paper's
factual statements. Configured local/cloud models can produce actual source-linked
plain-language sections. Provider errors can fall back safely to the offline aid.

After generation, document locks, current indexing checks and fingerprints reject
stale/replaced sources before returning the result. Failed/canceled reservations
are marked failed and retain conservative quota accounting. UUID reuse returns
409, preventing repeat provider calls/charges; successful explanations are not
stored as a new durable result entity or replay cache. Safe success/failure events
are audited without document text, prompts, credentials or raw provider responses.

## Team ACLs and privacy

Membership predicates run in SQL before workspace, member, note or shared-paper
projection. Nonmembers see non-disclosing 404 responses. Successful private
responses, including deletion responses, use `private, no-store` and `nosniff`
headers.

| Role | Read workspace/shared metadata/notes | Edit workspace and notes | Share own collection | Manage members/roles or delete workspace |
| --- | --- | --- | --- | --- |
| Owner | Yes | Yes | Yes | Yes |
| Editor | Yes | Yes | Yes | No |
| Viewer | Yes | No | No | No |
| Nonmember | No | No | No | No |

Adding by email/username immediately adds an existing registered account; it does
not send email or create a pending invitation. Only editor/viewer roles may be
assigned. The original owner cannot be removed/demoted through membership APIs;
ownership transfer is not introduced. Member responses expose usernames/IDs and
roles, rather than broadcasting email addresses.

Sharing requires the actor's own collection. The resulting live ACL projects only
bibliographic paper metadata (title, authors, source, URL and DOI), with necessary
membership/library IDs. It grants no access to personal notes, annotations,
documents, PDF files, storage keys, chunks, embeddings or existing RAG endpoints.
The private Library and education/explanation APIs continue to require ownership.

The owner can unshare any grant; editors can unshare their own. Removing a member
or demoting an editor revokes their grants. Shared notes remain explicitly
collaborative content after the author's departure; note paper IDs are hidden
unless the referenced paper is still available through a current team grant.
Workspace/editor note permissions never transfer ownership of the linked paper.

Mutations serialize on the workspace and recheck membership/role after acquiring
the lock, so a waiting editor cannot write after revocation commits. Existing-team
operations avoid actor account locks that could deadlock two owners cross-inviting
one another. Creation retains its self-contained owner/account lock. Safe audit
events record workspace creation/change/deletion, member addition/removal/role
change, collection sharing/unsharing and note writes, without shared text content.

Detail responses disclose their limits/truncation: 200 members, 100 collections,
100 notes and 200 papers per collection. Team lists and separate note lists are
paginated. These caps are visible in the client rather than silently implying an
unlimited result.

## Endpoints

| Methods | Endpoint | Purpose |
| --- | --- | --- |
| GET | `/api/v1/education/guides` | Bilingual catalog plus private completion |
| GET | `/api/v1/education/guides/{slug}` | Guide/checklists and owned progress |
| POST | `/api/v1/education/guides/{slug}/progress` | Replace completed step set |
| GET | `/api/v1/education/glossary` | Bilingual `q`/`category` search |
| POST | `/api/v1/education/explain-paper/{user_paper_id}` | Owned indexed beginner explanation |
| GET, POST | `/api/v1/teams` | List joined teams/create owned workspace |
| GET, PUT, DELETE | `/api/v1/teams/{workspace_id}` | Authorized detail/update/delete |
| POST | `/api/v1/teams/{workspace_id}/members` | Owner adds account by identifier |
| PUT, DELETE | `/api/v1/teams/{workspace_id}/members/{member_user_id}` | Owner manages nonowner membership |
| POST | `/api/v1/teams/{workspace_id}/collections` | Owner/editor shares own collection |
| DELETE | `/api/v1/teams/{workspace_id}/collections/{collection_id}` | Authorized grant revocation |
| GET, POST | `/api/v1/teams/{workspace_id}/notes` | Read/create collaborative notes |
| PUT, DELETE | `/api/v1/teams/{workspace_id}/notes/{note_id}` | Owner/editor updates/deletes note |

## Frontend

`/learn` replaces the preview with bilingual guide cards, interactive step
checklists, saved progress, glossary search/categories/examples and safe external
reading references. The beginner drawer selects only the user's indexed library
papers, language/provider controls, consent/quota feedback, clearly separated
interpretations/quotations, terminology help and current source-page inspection.

`/teams` and navigation provide bilingual workspace CRUD, existing-account member
addition, immutable owner/editor/viewer controls, explicit collection-share
warnings, metadata browsing and collaborative note CRUD/pagination. Viewers see
read-only controls. Membership/role failures clear stale workspace details, and
focus refresh checks current access. Sharing exposes no teammate PDF controls.

Both screens use existing authenticated transport, abort obsolete account/view
loads, render text safely and disclose bounded result sets. No dependencies were
added; all automated inference/provider tests are offline/mocked.

## Verification

- Final full backend suite: **780 passed, 0 failures/errors/skips**, **83.13% total
  application coverage** (7,071 / 8,506 executable lines), **752.02 seconds** on
  this Windows host. Coverage XML/HTML and JUnit reports were generated. The run
  includes all earlier PDF/indexing/AI regressions, not just the new modules.
  Five existing PyMuPDF SWIG deprecation warnings remain.
- **87 backend cases added** over the 693-test Phase 10 baseline: 36 education,
  43 team and eight PostgreSQL collaboration/migration-protection cases. These
  exercise bilingual curriculum/progress, glossary search, explanation ownership,
  missing indexes, consent rechecks, source drift, exact evidence, tentative
  interpretations, numerical/reference guards, Bangla negation, quota accounting,
  replay rejection, roles/nonmembers, cross-workspace isolation, metadata-only
  grants, shared-paper notes, revocation/masking, private PDF/RAG/education denial,
  safe audits and cascades.
- Real PostgreSQL checks pass for owner/membership/collection FKs, one-owner
  constraints, progress uniqueness, note `SET NULL`, grant revocation, a waiting
  editor denied after demotion/removal, and simultaneous cross-workspace owner
  invitations without account-lock deadlock.
- Migration checks pass from a **genuinely empty PostgreSQL database → head →
  base → head**, with cleanup/repeatability and supported-data preservation.
  Existing Phase 09 conversation scope and Phase 10 project/objective/task data
  survive upgrade. Downgrade protection is tested separately for learning state,
  teams and education usage. The earlier migration files were not changed.
- `alembic check`: **passed**, no schema drift, head **`e1c25d9b743f`**. Local live
  PostgreSQL uses `PGVECTOR_ENABLED=false`; offline SQL generation passes for
  both vector profiles. A live pgvector-extension run was not performed locally;
  this phase does not change vector mappings.
- `ruff check .`: **passed**. `black --check --extend-exclude '(.cache)' .`:
  **passed, 238 files unchanged**. `git diff --check`: **passed**.
- Frontend `npm run typecheck`, `npm run lint`, **37/37 tests** (11 added), and
  `npm run build`: **passed**, including `/teams` and **22 generated static pages**.
  Tests cover API/auth/privacy contracts, permissions, progress ordering, safe
  links and source inspection. Source inspection tolerates whitespace formatting
  while retaining digits/case, returns original text and rechecks document version
  after loading the page. Browser end-to-end tests were not run.

All provider/inference tests use offline or mock adapters, with no external
network service or model download required. No dependencies were added. Phase 11
changes are left uncommitted for review; the requested Phase 10 checkpoint is the
only commit made during this task.
