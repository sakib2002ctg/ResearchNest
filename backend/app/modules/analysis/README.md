# Paper intelligence

The module owns `/api/v1/analysis` routes, typed provider output schemas,
extraction/verification, private repositories and orchestration. Provider calls
go through the existing `AIProviderGateway.generate_structured` interface, with
the same local/cloud/offline routes and privacy consent as chat. Existing chat
output contracts remain unchanged. No new model dependencies or downloads exist.

## Source contract

Select owned `UserPaper` records, then retrieve only completed/current-version
`DocumentChunk` rows through SQL predicates on chunk, document, paper and title
projection ownership. Every selected paper needs a readable indexed PDF. The
bounded scan reads at most 2,000 chunks per paper and constructs a section-diverse
10,000-character context, split equally between at most five papers. Claims can
only cite exact quotes offered in that context. A full source fingerprint includes
owner-scoped IDs, document version/hash, title, page, heading and chunk content.

Successful analysis is cached per `(user_id, user_paper_id, language)` until sources
change or `force_refresh` is true. Historical comparisons are separate snapshots.
GET responses report `is_stale` when sources are removed, modified or reindexed.
Old evidence cards are disabled in the UI until regenerated. The server rechecks
fingerprints under document locks after inference, before saving any result.

## Honesty and provenance

The deterministic adapter extracts verbatim sentences with explicit section/field
cues (including English and Bangla). It preserves original source language and
does not pretend to translate, reason about novel findings, or infer missing
strengths/weaknesses. Missing scalar values are exactly `Not specified in document`;
missing lists contain that same string. `field_statuses` distinguishes supported
quotes, tentative AI interpretations and unspecified fields.

Local/cloud structured adapters receive bilingual instructions and strict Pydantic
JSON schemas. Every claim needs source quotations, a matching field/section cue,
and a verified chunk ID from its paper. Technical dataset, model and metric values
must appear verbatim in the cited quote. The server supplies paper titles, page
numbers, headings and document IDs/versions. Unknown fields/IDs, fabricated quotes,
external/inline citations and unmentioned fields fail closed. Failed refreshes keep
the previous valid extraction. A first failed attempt can save an owner-scoped
`failed` snapshot with no evidence and a safe error message.

Comparison matrices use the same verified field extraction for each paper.
Cross-paper synthesis and gap claims require citations from at least two distinct
selected papers. Gaps additionally require explicit limitation/future-work cues in
every supporting source. Gap cards are marked tentative interpretation and scoped
to `selected_papers_only`; they cannot establish a gap in all research literature.
No such evidence means an empty gap list, not a fabricated opportunity. These
checks establish provenance, not semantic entailment or scientific correctness.

## Accounting, failures and deletion

Generation reserves `60000 + ANALYSIS_MAX_COMPLETION_TOKENS` tokens under the
existing per-user quota lock, shared with chat. The default structured output cap
is 4,096 tokens; HTTP and total provider deadlines remain six/eight seconds.
Reported token usage settles the reservation; missing usage is conservatively
estimated. Failed reservations stay charged, and retry UUIDs prevent duplicate
successful operations. Cached reads do not call providers or consume generation
quota. Cloud inference rechecks `allow_external_ai` immediately before dispatch.
Provider failures use the deterministic adapter; invalid source attribution rejects
the result instead of saving unverified claims. Audits contain safe event metadata.

An explicit `ComparisonPaper` association enforces owner membership with composite
foreign keys independently of JSON snapshots. Deleting a scoped paper makes its
old comparison inaccessible; account deletion cascades all intelligence records.
Deleting a document sets `Analysis.document_id` to null and preserves a stale
quote snapshot. Alembic downgrade requires explicit export/purge if intelligence
rows exist. No production tables are created with ORM `create_all()`.
