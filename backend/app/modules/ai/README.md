# AI assistant operations

`AI_DEFAULT_PROVIDER=offline` uses deterministic, extractive source excerpts.
No LLM service, API key, model weights, or network access is required. This is
an honest excerpt fallback, not a claim of semantic reasoning or translation.

Set `AI_DEFAULT_PROVIDER=local` for an operator-managed Ollama endpoint with
preinstalled `OLLAMA_MODEL` at `OLLAMA_BASE_URL`; the adapter never pulls models.
Set `LOCAL_AI_PROTOCOL=openai` and an appropriate base URL, usually ending `/v1`,
for llama.cpp's OpenAI-compatible server. Local servers must be operator-trusted
and run in the private deployment boundary. `auto` prefers local, never cloud.

Cloud inference uses `CLOUD_AI_BASE_URL`, `CLOUD_AI_MODEL`, and the secret
`CLOUD_AI_API_KEY`. Every cloud request requires the authenticated owner's
`UserPreference.allow_external_ai`; missing preferences mean no consent. Consent
is re-read immediately before dispatch. Changing preferences cannot recall data
already sent to an upstream service. Keys are server-only. There are no redirects,
environment proxies, tools, retries, document logs, or automatic cloud escalation.
Calls have six-second HTTP and eight-second total deadlines, bounded JSON bodies,
and validated structured responses. Errors fall back to private excerpts.

The protocols follow the [Ollama chat API](https://docs.ollama.com/api/chat) and
[OpenAI-compatible Chat Completions](https://developers.openai.com/api/reference/resources/chat).
Tests use `httpx.MockTransport` or deterministic adapters only.

Usage accounting locks the user's database row before checking rolling hour/day
request and token quotas and inserting a durable reservation. The default is one
concurrent request per user, across API processes. A fixed conservative reservation
of 60,000 input tokens plus maximum output bounds the 5-passage UTF-8 prompt. Actual
provider usage replaces the reservation after success; missing usage is estimated
conservatively. Failed/stale attempts retain their reservation charge and count as
requests. Pending leases older than 60 seconds are marked failed on the next
request. Client UUID `request_id` makes successful retries idempotent; a reused UUID
with different content/scope/provider is rejected. Deleting a chat preserves usage.

Only `rag_chat` is exposed in this phase. `summary` and `analysis` are reserved
feature values; they are not implemented endpoints. RAG returns structured quote
evidence, tentative interpretation, missing information and suggested next questions.
Citation validation establishes provenance, not the scientific truth of an excerpt
or entailment of model interpretation. Read and assess the original sources.
