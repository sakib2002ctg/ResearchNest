# Multimodal assets and visual evidence

POST extraction records a durable owner-bound job and returns 202. It never makes
an API request wait for PDF parsing. A database-polled worker runs in the API by
default, or separately with `python -m app.modules.multimodal.worker` when
`MULTIMODAL_WORKER_IN_API=false`. Queue rows contain document/version/generation,
status and attempts. Document locks plus generation/attempt/status fencing prevent
duplicate or stale attempts from publishing. Expired running leases recover after
three minutes; at most three attempts are allowed until an explicit new request.
Reindexing makes previous assets inaccessible until extraction runs again.

## Deterministic extraction

PyMuPDF `page.find_tables()` extracts headers, rows and Markdown. Raster-image
rectangles and vector-drawing clusters provide PNG figure candidates; layout-nearby
captions supply figure/table labels. Chart/diagram classification uses caption
cues, otherwise an image remains a figure. Numbered math-like source lines become
equations with normalized raw text and surrounding context. Mathematical truth or
exact LaTeX reconstruction is never asserted. Caption association and boundaries
are heuristics, not a learned document-layout model; some layouts may be missed.

The parser runs in a killable spawned subprocess with a 60-second deadline. Input
PDFs are already size/MIME/signature/parser/scanner validated by the upload module;
the worker additionally verifies expected size and SHA-256 before native parsing.
Budgets: 1,000 pages, 200 assets, 100,000 combined extracted/structured characters,
4 million pixels/4 MiB per PNG, 32 MiB total PNG bytes, 10,000 drawings per page and
5,000 cells per table. Rotated pages retain page-local bounding coordinates.

Links resolve explicit Figure/Table/Equation labels across only the originating
owner/document/current-version chunks. Unlabeled objects fall back to a few
same-page surrounding chunks. An owner-bound association table reinforces the
JSON linked-ID snapshot; detail reads query those links and chunk scope again.

## Storage and cleanup

`ASSET_STORAGE_ROOT/<user_id>/<random-SHA256>.png` is private storage. Generated keys
only, no client filenames/paths, no symlink/reparse directories, restrictive
permissions and checked regular-file sizes apply. Images are served only after
owner/current-document-version authorization, with PNG MIME and private/no-store.

Before each PNG write, a delayed cleanup intent is committed using its known key.
Successful publication removes that intent in the same transaction as asset rows.
Cancellation during a background file write can therefore leave no untracked key;
the intent becomes eligible after five minutes, allowing the write to finish before
cleanup. Parser/publication failures clean completed writes promptly. Database
deletion triggers enqueue PNGs for document, paper and account cascades, including
raw SQL deletion. Cleanup is idempotent, retries I/O failures, and runs periodically
or alongside PDF cleanup. No private content appears in parser/error/audit logs.

## Vision gateway and academic reliability

`AIProviderGateway.generate_vision` supports Ollama image arrays, OpenAI-compatible
image data URLs and deterministic offline evidence. Local models must already be
installed; no weights are downloaded. Cloud requires `allow_external_ai` immediately
before dispatch and a fail-closed gateway consent flag. Use `OLLAMA_VISION_MODEL` or
`CLOUD_VISION_MODEL` with the existing base URLs/secrets. HTTP/total deadlines stay
six/eight seconds; PNGs, context and response JSON are bounded. No redirects, tools,
environment proxies or automatic cloud fallback are allowed.

Each explanation/VQA reserves request/token/concurrency quota under the same user
lock as other AI features, records `AIUsage(feature='multimodal')`, and supports UUID
replay. Token estimates use bounded prompt UTF-8 bytes plus a conservative image
allowance when upstream usage is missing. Failed attempts retain quota charges.
After inference the service rechecks document version, generation, storage key and
linked evidence fingerprint before persisting. Recent responses are owner-private
asset history; explanations have language-specific response fields.

Facts must be exact caption/table/equation/linked-text quotations. The server derives
page/asset labels. Interpretation is clearly marked and rejects numeric tokens,
spelled-out numbers, mathematical symbols/LaTeX, URLs and invented citations. Values
and equations belong only in extracted quotations; no chart pixel digitization or
equation validation is claimed. Unrelated questions get insufficient-evidence
responses before external inference. Offline mode returns source excerpts, not
translated prose or guessed visual trends. The VQA relevance gate is conservative
lexical matching, and structured facts establish provenance rather than scientific
truth. Inference context is explicitly bounded; very large tables may be excerpted.
