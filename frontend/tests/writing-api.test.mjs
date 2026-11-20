import assert from "node:assert/strict";
import test from "node:test";
import { api, ApiError, clearAccessToken, setAccessToken } from "../lib/api.ts";
import { insertWritingSuggestion, reconcileSavedDraft } from "../lib/writing.ts";

test("writing calls preserve revision guards, checkpoints, restoration and separate AI requests", async () => {
  const seen = [];
  globalThis.fetch = async (url, init) => {
    seen.push({ url: new URL(url), init });
    return init.method === "DELETE" ? new Response(null, { status: 204 }) : Response.json({});
  };
  setAccessToken("writing-offline-test");
  try {
    await api.getWritingDocuments(30, 60);
    await api.createWritingDocument({ title: "গবেষণা", doc_type: "research_paper", language: "bn", outline: ["ভূমিকা"] });
    await api.getWritingDocument(5);
    await api.updateWritingDocument(5, { content_markdown: "আমার লেখা [@paper2026]", expected_revision: 3, create_version: true, change_summary: "Checkpoint" });
    await api.getWritingVersions(5);
    await api.restoreWritingVersion(5, 11, 4);
    await api.assistWriting(5, { action: "draft_section", section: "introduction", user_paper_ids: [7], provider: "offline", request_id: "e698e2f1-58fb-492a-8317-a33688507ee8" });
    await api.assistWriting(5, { action: "grammar", section: "introduction", text: "My own research paragraph.", user_paper_ids: [], provider: "offline", request_id: "48a0d6e9-cebd-424d-a408-3db80bcd4c2f" });
    await api.deleteWritingDocument(6);
  } finally { clearAccessToken(); }
  assert.deepEqual(seen.map((item) => item.url.pathname), ["/api/v1/writing", "/api/v1/writing", "/api/v1/writing/5", "/api/v1/writing/5", "/api/v1/writing/5/versions", "/api/v1/writing/5/versions/11/restore", "/api/v1/writing/5/assist", "/api/v1/writing/5/assist", "/api/v1/writing/6"]);
  assert.equal(seen[0].url.searchParams.get("offset"), "60");
  assert.equal(JSON.parse(seen[3].init.body).expected_revision, 3);
  assert.equal(JSON.parse(seen[3].init.body).create_version, true);
  assert.equal(JSON.parse(seen[5].init.body).expected_revision, 4);
  assert.equal(seen.filter((item) => item.init.method === "PUT").length, 1, "asking AI does not autosave model output");
  assert.deepEqual(JSON.parse(seen[6].init.body).user_paper_ids, [7]);
  assert.deepEqual(JSON.parse(seen[7].init.body).user_paper_ids, []);
  assert.equal(JSON.parse(seen[7].init.body).text, "My own research paragraph.");
  for (const { url, init } of seen) {
    assert.equal(init.headers.Authorization, "Bearer writing-offline-test");
    assert.equal(init.cache, "no-store"); assert.equal(init.credentials, "omit");
    assert.equal(init.redirect, "error"); assert.equal(url.searchParams.has("token"), false);
    if (init.body) assert.equal(Object.hasOwn(JSON.parse(init.body), "user_id"), false);
  }
});

test("autosave keeps edits typed while the earlier revision was being saved", () => {
  const sent = { title: "Research", doc_type: "research_paper", language: "en", outline: [], content_markdown: "First paragraph", cited_citation_ids: [] };
  const local = { ...sent, content_markdown: "First paragraph\nSecond paragraph typed during save" };
  const saved = { ...sent, title: "Research (canonical)" };
  assert.deepEqual(reconcileSavedDraft(local, sent, saved), local);
  assert.deepEqual(reconcileSavedDraft(sent, sent, saved), saved);
  assert.equal(sent.content_markdown, "First paragraph");
});

test("explicit AI insertion preserves user writing and merges owned reference membership", () => {
  const draft = { title: "Research", doc_type: "thesis", language: "bn", outline: [], content_markdown: "আমার লেখা [@first]", cited_citation_ids: [1] };
  const suggestion = { kind: "ai_generated_suggestion", content_markdown: "উৎসভিত্তিক পরামর্শ [@second]", citation_ids: [1, 2] };
  const inserted = insertWritingSuggestion(draft, suggestion);
  assert.equal(draft.content_markdown, "আমার লেখা [@first]");
  assert.deepEqual(draft.cited_citation_ids, [1]);
  assert.equal(inserted.content_markdown, "আমার লেখা [@first]\n\nউৎসভিত্তিক পরামর্শ [@second]\n");
  assert.deepEqual(inserted.cited_citation_ids, [1, 2]);
});

test("all manuscript downloads validate MIME and use private bearer transport", async () => {
  const mime = { md: "text/markdown", tex: "application/x-tex", docx: "application/vnd.openxmlformats-officedocument.wordprocessingml.document", pdf: "application/pdf" };
  const seen = [];
  setAccessToken("writing-export-offline");
  try {
    globalThis.fetch = async (url, init) => {
      seen.push({ url: new URL(url), init });
      return new Response(new Uint8Array([1, 2, 3]), { headers: { "Content-Type": `${mime[new URL(url).searchParams.get("format")]}; charset=utf-8` } });
    };
    for (const format of Object.keys(mime)) {
      const blob = await api.exportWriting(7, format, "ieee");
      assert.equal(blob.size, 3);
    }
    globalThis.fetch = async () => new Response("<html>wrong file</html>", { headers: { "Content-Type": "text/html" } });
    await assert.rejects(api.exportWriting(7, "pdf", "apa"), (error) => error instanceof ApiError && error.status === 502);
    globalThis.fetch = async () => Response.json({ detail: "Foreign draft" }, { status: 404 });
    await assert.rejects(api.exportWriting(7, "docx", "apa"), (error) => error instanceof ApiError && error.status === 404);
  } finally { clearAccessToken(); }
  for (const { url, init } of seen) {
    assert.equal(url.searchParams.get("style"), "ieee");
    assert.equal(init.headers.Accept, mime[url.searchParams.get("format")]);
    assert.equal(init.headers.Authorization, "Bearer writing-export-offline");
    assert.equal(init.redirect, "error");
  }
});
