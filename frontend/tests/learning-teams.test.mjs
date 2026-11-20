import assert from "node:assert/strict";
import test from "node:test";
import { api, ApiError, setAccessToken, clearAccessToken } from "../lib/api.ts";
import { completedLearningSteps, learningModulePath, readVerifiedEducationPage, safePublicLink, sourceContainsQuote, teamPermissions } from "../lib/learning-teams.ts";

test("learning guides and progress use authenticated owner-derived requests", async () => {
  const requests = [];
  const controller = new AbortController();
  globalThis.fetch = async (url, init) => { requests.push({ url: new URL(url), init }); return Response.json({}); };
  setAccessToken("phase11-learning-session");
  try {
    await api.getLearningGuides(controller.signal);
    await api.getLearningGuide("three-pass-reading", controller.signal);
    await api.updateLearningProgress("three-pass-reading", ["first-pass", "second-pass"], controller.signal);
    await api.getGlossary("অনুমান", "methodology", controller.signal);
  } finally { clearAccessToken(); }
  assert.deepEqual(requests.map(({ url }) => url.pathname), [
    "/api/v1/education/guides", "/api/v1/education/guides/three-pass-reading",
    "/api/v1/education/guides/three-pass-reading/progress", "/api/v1/education/glossary",
  ]);
  assert.deepEqual(JSON.parse(requests[2].init.body), { completed_step_ids: ["first-pass", "second-pass"] });
  assert.equal(requests[3].url.searchParams.get("q"), "অনুমান");
  assert.equal(requests[3].url.searchParams.get("category"), "methodology");
  for (const { init, url } of requests) {
    assert.equal(init.headers.Authorization, "Bearer phase11-learning-session");
    assert.equal(init.cache, "no-store"); assert.equal(init.credentials, "omit");
    assert.equal(init.referrerPolicy, "no-referrer"); assert.equal(init.redirect, "error");
    assert.ok(init.signal); assert.equal(url.searchParams.has("user_id"), false);
    assert.equal(init.body?.includes("user_id") ?? false, false);
  }
});

test("beginner explanation preserves locale provider and replay identity without sending document contents", async () => {
  let captured;
  const response = {
    user_paper_id: 17, language: "bn", title: "Owned indexed paper",
    supported_evidence: [{ chunk_id: 4, document_id: 7, document_version: 2, page_number: 3, paper_title: "Owned indexed paper", quoted_snippet: "Source facts remain verbatim." }],
    beginner_explanation: "গবেষণার প্রশ্নটি খুঁজুন।", plain_language_interpretation: [],
    mode_notice: "অফলাইন উৎসের উদ্ধৃতি", term_explanations: [], missing_information: "", follow_up_questions: [],
    provider_used: "offline", model_used: "deterministic", evidence_status: "supported", response_kind: "beginner_guide_with_source_quotes",
  };
  globalThis.fetch = async (url, init) => { captured = { url: new URL(url), init }; return Response.json(response); };
  setAccessToken("phase11-explain-session");
  const body = { language: "bn", provider: "offline", request_id: "4cad0e3e-9598-4029-a8c3-b32499ae0832" };
  try {
    const result = await api.explainPaperForBeginners(17, body);
    assert.deepEqual(result, response);
    assert.equal(result.supported_evidence[0].quoted_snippet, "Source facts remain verbatim.");
  } finally { clearAccessToken(); }
  assert.equal(captured.url.pathname, "/api/v1/education/explain-paper/17");
  assert.equal(captured.init.method, "POST");
  assert.deepEqual(JSON.parse(captured.init.body), body);
  assert.equal(captured.init.headers.Authorization, "Bearer phase11-explain-session");
});

test("education quota consent and unavailable-source errors propagate without a successful result", async () => {
  const options = { language: "en", provider: "cloud", request_id: "4cad0e3e-9598-4029-a8c3-b32499ae0832" };
  setAccessToken("phase11-error-session");
  try {
    for (const status of [403, 404, 409, 429]) {
      globalThis.fetch = async () => Response.json({ detail: "Request refused" }, { status });
      await assert.rejects(api.explainPaperForBeginners(99, options), (error) => error instanceof ApiError && error.status === status);
    }
  } finally { clearAccessToken(); }
});

test("team CRUD and member roles send no client-supplied owner or membership authority", async () => {
  const requests = [];
  globalThis.fetch = async (url, init) => { requests.push({ url: new URL(url), init }); return init.method === "DELETE" ? new Response(null, { status: 204 }) : Response.json({}); };
  setAccessToken("phase11-team-owner");
  try {
    await api.getTeams(30, 60);
    await api.createTeam({ name: "গবেষণা দল", description: "Joint research" });
    await api.getTeam(6);
    await api.updateTeam(6, { name: "Research group" });
    await api.addTeamMember(6, "collaborator@example.com", "viewer");
    await api.updateTeamMember(6, 12, "editor");
    await api.removeTeamMember(6, 12);
    await api.deleteTeam(6);
  } finally { clearAccessToken(); }
  assert.deepEqual(requests.map(({ url }) => url.pathname), ["/api/v1/teams", "/api/v1/teams", "/api/v1/teams/6", "/api/v1/teams/6", "/api/v1/teams/6/members", "/api/v1/teams/6/members/12", "/api/v1/teams/6/members/12", "/api/v1/teams/6"]);
  assert.equal(requests[0].url.searchParams.get("offset"), "60");
  assert.deepEqual(JSON.parse(requests[4].init.body), { identifier: "collaborator@example.com", role: "viewer" });
  assert.deepEqual(JSON.parse(requests[5].init.body), { role: "editor" });
  for (const { init } of requests) {
    assert.equal(init.headers.Authorization, "Bearer phase11-team-owner");
    assert.equal(init.cache, "no-store"); assert.equal(init.credentials, "omit");
    if (init.body) assert.equal(Object.hasOwn(JSON.parse(init.body), "owner_id"), false);
  }
});

test("team sharing and collaborative notes use explicit workspace routes and preserve note association on edits", async () => {
  const requests = [];
  globalThis.fetch = async (url, init) => { requests.push({ url: new URL(url), init }); return init.method === "DELETE" ? new Response(null, { status: 204 }) : Response.json({}); };
  setAccessToken("phase11-team-editor");
  try {
    await api.shareTeamCollection(5, 11);
    await api.unshareTeamCollection(5, 11);
    await api.getTeamNotes(5, 100, 100);
    await api.createTeamNote(5, { title: "Observations", content: "Team-visible text." });
    await api.updateTeamNote(5, 18, { content: "Revised team text." });
    await api.deleteTeamNote(5, 18);
  } finally { clearAccessToken(); }
  assert.deepEqual(requests.map(({ url }) => url.pathname), ["/api/v1/teams/5/collections", "/api/v1/teams/5/collections/11", "/api/v1/teams/5/notes", "/api/v1/teams/5/notes", "/api/v1/teams/5/notes/18", "/api/v1/teams/5/notes/18"]);
  assert.deepEqual(JSON.parse(requests[0].init.body), { collection_id: 11 });
  assert.deepEqual(JSON.parse(requests[4].init.body), { content: "Revised team text." });
  assert.equal(requests[2].url.searchParams.get("offset"), "100");
  for (const { init, url } of requests) {
    assert.equal(init.headers.Authorization, "Bearer phase11-team-editor");
    assert.equal(url.pathname.includes("/pdf"), false);
    if (init.body) assert.equal(Object.hasOwn(JSON.parse(init.body), "author_id"), false);
  }
});

test("team and learning requests fail closed without a live local session", async () => {
  clearAccessToken();
  globalThis.fetch = async () => { assert.fail("An anonymous private request must not be dispatched"); };
  await assert.rejects(api.getTeams(), (error) => error instanceof ApiError && error.status === 401);
  await assert.rejects(api.getLearningGuides(), (error) => error instanceof ApiError && error.status === 401);
  await assert.rejects(api.shareTeamCollection(1, 2), (error) => error instanceof ApiError && error.status === 401);
});

test("role controls distinguish immutable owner management, editor writes and read-only viewers", () => {
  assert.deepEqual(teamPermissions("owner"), { canWrite: true, canManageMembers: true, canDelete: true });
  assert.deepEqual(teamPermissions("editor"), { canWrite: true, canManageMembers: false, canDelete: false });
  assert.deepEqual(teamPermissions("viewer"), { canWrite: false, canManageMembers: false, canDelete: false });
  assert.deepEqual(teamPermissions("invalid"), { canWrite: false, canManageMembers: false, canDelete: false });
});

test("guide completion only emits known unique steps in curriculum order", () => {
  const guide = { steps: [{ id: "read" }, { id: "question" }, { id: "compare" }] };
  const before = ["compare", "unknown", "read", "read"];
  assert.deepEqual(completedLearningSteps(guide, before, "question", true), ["read", "question", "compare"]);
  assert.deepEqual(completedLearningSteps(guide, before, "read", false), ["compare"]);
  assert.deepEqual(completedLearningSteps(guide, [], "foreign-step", true), []);
  assert.deepEqual(before, ["compare", "unknown", "read", "read"]);
});

test("learning deep links and public reference links reject unsafe schemes and embedded credentials", () => {
  for (const value of ["javascript:alert(1)", "data:text/html,hello", "file:///private.pdf", "/api/v1/private/pdf", "https://user:secret@example.com/paper"]) assert.equal(safePublicLink(value), null);
  assert.equal(safePublicLink("https://example.com/academic-paper"), "https://example.com/academic-paper");
  assert.equal(learningModulePath("/analysis"), "/analysis");
  assert.equal(learningModulePath("https://example.com/login"), null);
  assert.equal(learningModulePath("/settings?redirect=foreign"), null);
});

test("education quote verification accepts formatting whitespace but rejects changed facts and empty quotes", () => {
  assert.equal(sourceContainsQuote("  Accuracy\t\twas 95%\n  on 100 samples.  ", "Accuracy was 95%\non 100 samples."), true);
  assert.equal(sourceContainsQuote("ফলাফল\t ৯৫%\r\n পাওয়া গেছে।", "ফলাফল ৯৫% পাওয়া গেছে।"), true);
  assert.equal(sourceContainsQuote("Accuracy was 95% on 100 samples.", "Accuracy was 96% on 100 samples."), false);
  assert.equal(sourceContainsQuote("Accuracy was 95%.", "accuracy was 95%."), false);
  assert.equal(sourceContainsQuote("Accuracy was 95%.", " \t\n "), false);
  assert.equal(sourceContainsQuote("", "Accuracy"), false);
});

test("education source-page verification rechecks index version after fetching and preserves raw page text", async () => {
  const calls = [];
  const original = "  Accuracy\twas 95%\n  on 100 samples.  ";
  const evidence = { document_id: 7, document_version: 2, page_number: 3, quoted_snippet: "Accuracy was 95%\non 100 samples." };
  const versions = [{ status: "completed", version: 2 }, { status: "completed", version: 2 }];
  const controller = new AbortController();
  const client = {
    getDocument: async (id, signal) => { calls.push(["metadata", id, signal]); return versions.shift(); },
    getDocumentPages: async (id, page, size, signal) => { calls.push(["page", id, page, size, signal]); return { items: [{ page_number: 3, raw_text: original }] }; },
  };
  assert.equal(await readVerifiedEducationPage(client, evidence, controller.signal), original);
  assert.deepEqual(calls.map((row) => row[0]), ["metadata", "page", "metadata"]);
  assert.equal(calls[1][2], 3); assert.equal(calls[1][3], 1);
  calls.forEach((row) => assert.equal(row.at(-1), controller.signal));
  for (const changed of [{ status: "completed", version: 3 }, { status: "processing", version: 2 }]) {
    versions.push({ status: "completed", version: 2 }, changed);
    await assert.rejects(readVerifiedEducationPage(client, evidence), /Changed source/);
  }
  assert.equal(evidence.quoted_snippet, "Accuracy was 95%\non 100 samples.");
});
