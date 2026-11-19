# Retrieval and evidence boundaries

Conversation creation rejects foreign/mixed ownership scopes. Single-paper scopes
contain exactly one `UserPaper`; selected scopes allow at most 50. Collection scopes
resolve current membership on each request and fail closed if the collection was
deleted. Owners and scope are checked again before evidence is persisted.

The retrieval SQL filters `DocumentChunk.user_id`, document owner, current version,
completed indexing state, `UserPaper.user_id` and legacy title projection owner,
plus authorized paper IDs. Only then does Python score candidates. A bounded scan
of at most 5,000 current chunks uses stored vectors with a matching model name,
cosine similarity (35%) and multilingual lexical overlap (65%). Stable reranking
selects at most five passages of 1,600 characters. Hash embeddings require at least
half of meaningful query terms to overlap; they are not semantic embeddings.
Installed local semantic embeddings can admit paraphrases with cosine >= 0.7.
This is bounded exact reranking, not an approximate nearest-neighbor SQL search.
Large libraries may need partitioning/candidate-query optimization in a later phase.

No evidence or low relevance returns `insufficient_evidence` without inference.
English/Bangla instructions separate directly supported quotes, interpretation and
missing information. Raw passages and questions remain untrusted user-role JSON.
The adapter cannot invoke tools. Citation output is restricted to supplied chunk IDs
and verbatim snippets. The server derives all title/page/document/paper fields;
provider-supplied titles or pages are rejected as extra fields. Unknown IDs, altered
quotes, duplicates or invented inline citations invalidate the entire generated
evidence. The server rechecks scope, version, title, page, heading and quote against
current rows after generation. A changed source aborts persistence and charges the
failed attempt. Interpretations are never labeled directly supported evidence.

Foreign-key owner pairs also enforce isolation at the persistence layer. Deleting
a paper removes its citation cards; deleting/reindexing a document nulls obsolete
source links while retaining the original quote snapshot in its owner's history.
The UI fetches source pages through the existing authenticated documents API.
