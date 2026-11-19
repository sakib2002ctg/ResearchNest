# Academic Writing Studio

The module owns private draft CRUD, revision-aware saves, numbered checkpoints,
restore, AI suggestions and in-memory export. Requests use async SQLAlchemy sessions
and the authenticated owner. Composite foreign keys protect versions/reference
memberships independently of JSON snapshots. Draft updates and reference mutations
share the per-user database lock; `expected_revision` rejects stale saves with 409.

All four templates (`research_paper`, `research_proposal`, `thesis`,
`literature_review`) have English/Bangla default outlines. Word count is derived
server-side. Creation stores version 1; `create_version=true` adds a checkpoint.
Autosave changes the draft without generating a version on every keystroke. Restore
first checkpoints the current draft, then stores the restored state as another
numbered version. Referenced citations must still exist and belong to the owner.
Unknown `[@cite_key]` placeholders are rejected; known placeholders automatically
join `cited_citation_ids`. Draft deletion cascades snapshots/membership.

## AI integrity

The assistant reuses `AIProviderGateway`, consent-aware routing, atomic quota
reservations and `AIUsage(feature='writing')`. Section drafting requires 1–5 owned,
indexed papers and library-linked owned references. Indexed chunks are fetched
through the Phase 07 owner/version filters and bounded, section-diverse context.
References must first be created in the reference manager; missing links return a
clear 409. Raw papers and authored text are untrusted user-message data, never
instructions. No analysis/model weights are loaded or downloaded by this module.

Every result is an `ai_generated_suggestion`, stored separately in the latest 50
suggestions in `ai_suggestions_log`. It never changes `content_markdown` or creates
an authored checkpoint. The UI inserts a suggestion only after an explicit user
action, through the ordinary revision-aware save flow. Generated source references
are injected by the server using actual owned cite keys. Model-supplied reference
markers/URLs and fabricated results are rejected.

Integrity mode deliberately limits section drafts to verbatim, attributed source
passages formatted as quotations; reported results must be explicitly present in
the source. It does not pretend these are the user's experimental findings. Missing
evidence produces an explicit insufficient-evidence suggestion. Copy editing accepts
1–1,500 characters of user-supplied text and preserves Unicode-aware factual token
order, all numbers and citations. It permits punctuation/spacing/case changes; deep
lexical paraphrases are rejected instead of risking altered factual claims. The
offline fallback returns original copy-editing text unchanged. No prose quality or
semantic equivalence guarantee is claimed; authors must review suggestions.

Before generation the service reserves quota and checks external-AI consent. After
generation it rechecks draft revision, current document/chunk fingerprints under
locks, and full reference metadata/link fingerprints. A stale/removed/relinked
source aborts the attempt; failures retain quota charge. UUID retries replay a
successful retained suggestion without duplicate generation. The gateway's bounded
HTTP deadlines and structured JSON validation apply to writing too.

## Exports

Exports append the formatted bibliography from actual owned reference IDs. Markdown,
LaTeX, DOCX (`python-docx==1.2.0`) and PDF (existing PyMuPDF) are produced entirely
in memory; no TeX process, subprocess, document file, external font download or
remote HTML resource is required. LaTeX escapes manuscript content and is an editable
source artifact, not a compiled PDF. DOCX/PDF support basic headings, lists and
paragraph layout. Markdown remains source text, not rendered HTML.

Exports validate citation placeholders and same-owner rows again, reject missing
references and unsupported control characters, and impose text/reference/page
limits (200,000 manuscript characters, 400,000 combined characters, 200 PDF pages).
PDF uses bundled complex-script shaping fonts; Bengali glyphs render, though PDF
text extraction may not round-trip ligatures exactly. Markdown/TeX/DOCX preserve
original Unicode. Review exported formatting against the institution's requirements.

All routes are private/no-store, downloads use generated filenames, and events
contain safe metadata rather than draft contents/prompts. The new Alembic revision
adds the writing usage feature without modifying earlier migration files; downgrade
requires explicit export/purge of citations/drafts/writing usage.
