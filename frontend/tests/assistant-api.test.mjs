import assert from "node:assert/strict";
import test from "node:test";
import { api, clearAccessToken, setAccessToken } from "../lib/api.ts";

test("assistant requests preserve scoped IDs, bilingual questions, idempotency and private transport", async () => {
  const seen = [];
  globalThis.fetch = async (url, init) => {
    seen.push({ url: new URL(url), init });
    return init.method === "DELETE" ? new Response(null, { status: 204 }) : Response.json({});
  };
  setAccessToken("offline-test-session");
  try {
    await api.createConversation({ title: "উদ্ভিদ", scope_type: "selected_papers", scope_paper_ids: [2, 5], scope_collection_id: null, language: "bn" });
    await api.getConversations(50, 50);
    await api.getConversation(4);
    await api.sendAssistantMessage(4, { content: "সালোকসংশ্লেষণ কী?", provider: "offline", request_id: "847e446b-16c1-46ad-8356-7f1fa017049a" });
    await api.getAIUsage();
    await api.deleteConversation(4);
  } finally { clearAccessToken(); }
  assert.deepEqual(seen.map((r) => r.url.pathname), ["/api/v1/conversations", "/api/v1/conversations", "/api/v1/conversations/4", "/api/v1/conversations/4/messages", "/api/v1/ai/usage", "/api/v1/conversations/4"]);
  assert.equal(seen[1].url.searchParams.get("offset"), "50");
  assert.deepEqual(JSON.parse(seen[0].init.body).scope_paper_ids, [2, 5]);
  assert.equal(JSON.parse(seen[3].init.body).content, "সালোকসংশ্লেষণ কী?");
  assert.equal(JSON.parse(seen[3].init.body).request_id, "847e446b-16c1-46ad-8356-7f1fa017049a");
  for (const { url, init } of seen) {
    assert.equal(init.headers.Authorization, "Bearer offline-test-session");
    assert.equal(init.cache, "no-store");
    assert.equal(init.credentials, "omit");
    assert.equal(url.searchParams.has("token"), false);
    if (init.body) assert.equal(Object.hasOwn(JSON.parse(init.body), "user_id"), false);
  }
});
