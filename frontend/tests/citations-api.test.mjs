import assert from "node:assert/strict";
import test from "node:test";
import { api, ApiError, clearAccessToken, setAccessToken } from "../lib/api.ts";

test("citation manager sends private CRUD, import and style formatting requests", async () => {
  const seen = [];
  globalThis.fetch = async (url, init) => { seen.push({ url: new URL(url), init }); return init.method === "DELETE" ? new Response(null, { status: 204 }) : Response.json({}); };
  setAccessToken("citation-offline-session");
  try {
    await api.getCitations(50, 100, "বাংলা & research");
    await api.createCitation({ title: "Private paper", authors: ["Jane Doe"], year: 2026 });
    await api.createCitation({ doi: "10.1234/paper" });
    await api.createCitation({ user_paper_id: 7 });
    await api.updateCitation(2, { venue: "Journal", pages: "1–7" });
    await api.importCitations("bibtex", "@article{key,title={Paper}}");
    await api.importCitations("ris", "TY  - JOUR\nTI  - Paper\nER  - ");
    for (const style of ["apa", "ieee", "mla", "chicago", "harvard"]) await api.formatCitations([2, 7], style);
    await api.deleteCitation(2);
  } finally { clearAccessToken(); }
  assert.equal(seen[0].url.searchParams.get("q"), "বাংলা & research");
  assert.equal(seen[0].url.searchParams.get("offset"), "100");
  assert.deepEqual(JSON.parse(seen[2].init.body), { doi: "10.1234/paper" });
  assert.deepEqual(JSON.parse(seen[3].init.body), { user_paper_id: 7 });
  assert.deepEqual(seen.slice(7, 12).map((item) => JSON.parse(item.init.body).style), ["apa", "ieee", "mla", "chicago", "harvard"]);
  for (const { url, init } of seen) {
    assert.equal(init.headers.Authorization, "Bearer citation-offline-session");
    assert.equal(init.cache, "no-store"); assert.equal(init.credentials, "omit");
    assert.equal(init.redirect, "error"); assert.equal(url.searchParams.has("token"), false);
    if (init.body) assert.equal(Object.hasOwn(JSON.parse(init.body), "user_id"), false);
  }
});

test("reference exports preserve selected IDs and reject unexpected MIME", async () => {
  const seen = [];
  const mimes = { bibtex: "application/x-bibtex", ris: "application/x-research-info-systems" };
  globalThis.fetch = async (url, init) => { seen.push({ url: new URL(url), init }); return new Response("Reference text", { headers: { "Content-Type": mimes[new URL(url).searchParams.get("format")] } }); };
  setAccessToken("citation-export-offline");
  try {
    assert.equal((await api.exportCitations("bibtex", [4, 9])).type, mimes.bibtex);
    assert.equal((await api.exportCitations("ris")).type, mimes.ris);
    globalThis.fetch = async () => new Response("Unexpected HTML", { headers: { "Content-Type": "text/html" } });
    await assert.rejects(api.exportCitations("bibtex"), (error) => error instanceof ApiError && error.status === 502);
  } finally { clearAccessToken(); }
  assert.deepEqual(seen[0].url.searchParams.getAll("citation_ids"), ["4", "9"]);
  assert.equal(seen[1].url.searchParams.has("citation_ids"), false);
  assert.equal(seen[0].init.headers.Authorization, "Bearer citation-export-offline");
  assert.equal(seen[1].init.headers.Authorization, "Bearer citation-export-offline");
});
