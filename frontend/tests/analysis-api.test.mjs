import assert from "node:assert/strict";
import test from "node:test";
import { api, clearAccessToken, setAccessToken } from "../lib/api.ts";

test("analysis API keeps tenant IDs server-derived and preserves language, refresh and retry contracts", async () => {
  const seen = [];
  globalThis.fetch = async (url, init) => { seen.push({ url: new URL(url), init }); return Response.json({}); };
  setAccessToken("analysis-test-session");
  try {
    await api.analyzePaper(7, { language: "bn", force_refresh: true, provider: "offline", request_id: "a2bf4e2d-7abe-439f-a3a7-81837c42477a" });
    await api.getPaperAnalysis(7, "bn");
    await api.getPaperAnalyses(30, 30);
    await api.comparePapers({ user_paper_ids: [7, 9], title: "তুলনা", language: "bn", provider: "local", request_id: "48eecb67-2faa-4c0c-b555-4666e612b52e" });
    await api.getPaperComparisons(30, 60);
    await api.getPaperComparison(3);
  } finally { clearAccessToken(); }
  assert.deepEqual(seen.map((item) => item.url.pathname), ["/api/v1/analysis/7", "/api/v1/analysis/7", "/api/v1/analysis", "/api/v1/analysis/compare", "/api/v1/analysis/comparisons", "/api/v1/analysis/comparisons/3"]);
  const body = JSON.parse(seen[0].init.body);
  assert.equal(body.force_refresh, true); assert.equal(body.language, "bn");
  assert.equal(body.request_id, "a2bf4e2d-7abe-439f-a3a7-81837c42477a");
  assert.equal(seen[1].url.searchParams.get("language"), "bn");
  assert.equal(seen[2].url.searchParams.get("offset"), "30");
  assert.equal(seen[4].url.searchParams.get("offset"), "60");
  assert.deepEqual(JSON.parse(seen[3].init.body).user_paper_ids, [7, 9]);
  for (const { url, init } of seen) {
    assert.equal(init.headers.Authorization, "Bearer analysis-test-session");
    assert.equal(init.credentials, "omit"); assert.equal(init.cache, "no-store");
    assert.equal(init.redirect, "error"); assert.equal(url.searchParams.has("token"), false);
    if (init.body) assert.equal(Object.hasOwn(JSON.parse(init.body), "user_id"), false);
  }
});
