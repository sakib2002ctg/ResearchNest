import assert from "node:assert/strict";
import test from "node:test";
import { api, ApiError, clearAccessToken, setAccessToken } from "../lib/api.ts";
import { graphWindow, layoutGraph, publicationBuckets } from "../lib/knowledge-graph.ts";
import { projectConversationInput } from "../lib/projects.ts";

test("new project chats bind the project atomically and preserve the 50-paper source limit", async () => {
  const project = { id: 9, title: "Project sources", papers: Array.from({ length: 53 }, (_, i) => ({ user_paper_id: i + 1 })) };
  const body = projectConversationInput(project, "bn");
  assert.equal(body.project_id, 9); assert.equal(body.language, "bn");
  assert.equal(body.scope_type, "selected_papers"); assert.equal(body.scope_collection_id, null);
  assert.deepEqual(body.scope_paper_ids, Array.from({ length: 50 }, (_, i) => i + 1));
  assert.equal(project.papers.length, 53);
  const longTitle = projectConversationInput({ ...project, title: "🔬".repeat(205) }, "en");
  assert.equal(Array.from(longTitle.title).length, 200);
  assert.equal(longTitle.title, "🔬".repeat(200), "the conversation title cap preserves complete Unicode characters");
  let sent;
  globalThis.fetch = async (_url, init) => { sent = JSON.parse(init.body); return Response.json({}); };
  setAccessToken("phase10-atomic-chat");
  try { await api.createConversation(body); } finally { clearAccessToken(); }
  assert.deepEqual(sent, body);
});

test("project workspaces send owner-derived, revision guarded private requests", async () => {
  const seen = [];
  globalThis.fetch = async (url, init) => {
    seen.push({ url: new URL(url), init });
    return init.method === "DELETE" ? new Response(null, { status: 204 }) : Response.json({});
  };
  setAccessToken("phase10-project-session");
  try {
    await api.getProjects(30, 60);
    await api.createProject({ title: "গবেষণা প্রকল্প", description: null, objectives: ["Compare methods"], status: "planning", target_deadline: null, collection_id: null });
    await api.getProject(7);
    await api.updateProject(7, { expected_revision: 3, status: "active", objectives: ["Compare methods", "Read baseline"] });
    await api.addProjectPaper(7, 12, "core_baseline");
    await api.getProjectNotes(7);
    await api.createProjectNote(7, { title: "পর্যবেক্ষণ", content: "My own observation", user_paper_id: 12 });
    await api.updateProjectNote(7, 3, { content: "Updated own observation" });
    await api.getProjectTasks(7);
    await api.createProjectTask(7, { title: "Review baseline", description: null, is_milestone: true, status: "todo", due_date: "2027-01-01T00:00:00Z" });
    await api.updateProjectTask(7, 4, { status: "done" });
    await api.linkProjectConversation(7, 21);
    await api.removeProjectPaper(7, 12);
    await api.deleteProjectNote(7, 3);
    await api.deleteProjectTask(7, 4);
    await api.deleteProject(7);
  } finally { clearAccessToken(); }
  assert.deepEqual(seen.map(({ url }) => url.pathname), [
    "/api/v1/projects", "/api/v1/projects", "/api/v1/projects/7", "/api/v1/projects/7",
    "/api/v1/projects/7/papers", "/api/v1/projects/7/notes", "/api/v1/projects/7/notes",
    "/api/v1/projects/7/notes/3", "/api/v1/projects/7/tasks", "/api/v1/projects/7/tasks",
    "/api/v1/projects/7/tasks/4", "/api/v1/projects/7/conversations/21", "/api/v1/projects/7/papers/12",
    "/api/v1/projects/7/notes/3", "/api/v1/projects/7/tasks/4", "/api/v1/projects/7",
  ]);
  assert.equal(seen[0].url.searchParams.get("offset"), "60");
  assert.equal(JSON.parse(seen[3].init.body).expected_revision, 3);
  assert.equal(JSON.parse(seen[9].init.body).is_milestone, true);
  assert.deepEqual(JSON.parse(seen[4].init.body), { user_paper_id: 12, role_in_project: "core_baseline" });
  for (const { url, init } of seen) {
    assert.equal(init.headers.Authorization, "Bearer phase10-project-session");
    assert.equal(init.credentials, "omit"); assert.equal(init.cache, "no-store");
    assert.equal(init.redirect, "error"); assert.equal(init.referrerPolicy, "no-referrer");
    assert.equal(url.searchParams.has("user_id"), false);
    if (init.body) assert.equal(Object.hasOwn(JSON.parse(init.body), "user_id"), false);
  }
});

test("project exports verify file types and reject foreign or invalid responses", async () => {
  const seen = [];
  setAccessToken("phase10-export");
  try {
    globalThis.fetch = async (url, init) => {
      seen.push({ url: new URL(url), init });
      return new Response("private project bundle", { headers: { "Content-Type": new URL(url).searchParams.get("format") === "json" ? "application/json" : "text/markdown; charset=utf-8" } });
    };
    assert.equal((await api.exportProject(2, "json")).size, 22);
    assert.equal((await api.exportProject(2, "markdown")).type, "text/markdown;charset=utf-8");
    globalThis.fetch = async () => new Response("<html>not a project</html>", { headers: { "Content-Type": "text/html" } });
    await assert.rejects(api.exportProject(2, "json"), (error) => error instanceof ApiError && error.status === 502);
    globalThis.fetch = async () => Response.json({ detail: "Not found" }, { status: 404 });
    await assert.rejects(api.exportProject(99, "markdown"), (error) => error instanceof ApiError && error.status === 404);
  } finally { clearAccessToken(); }
  assert.equal(seen[0].init.headers.Accept, "application/json");
  assert.equal(seen[1].init.headers.Accept, "text/markdown");
  seen.forEach(({ init }) => assert.equal(init.headers.Authorization, "Bearer phase10-export"));
});

test("analytics filters scope every endpoint, support cancellation, and require a session", async () => {
  const seen = [];
  const controller = new AbortController();
  globalThis.fetch = async (url, init) => { seen.push({ url: new URL(url), init }); return Response.json({}); };
  setAccessToken("phase10-analytics");
  try {
    await api.getAnalyticsOverview(17, controller.signal);
    await api.getAnalyticsTimeline(17, controller.signal);
    await api.getKnowledgeGraph(17, controller.signal);
    await api.getAnalyticsOverview();
    controller.abort();
    assert.equal(seen[0].init.signal.aborted, true);
  } finally { clearAccessToken(); }
  assert.deepEqual(seen.slice(0, 3).map(({ url }) => url.pathname), ["/api/v1/analytics/overview", "/api/v1/analytics/timeline", "/api/v1/analytics/knowledge-graph"]);
  seen.slice(0, 3).forEach(({ url }) => assert.equal(url.searchParams.get("project_id"), "17"));
  assert.equal(seen[3].url.searchParams.has("project_id"), false);
  await assert.rejects(api.getProjects(), (error) => error instanceof ApiError && error.status === 401);
  await assert.rejects(api.getKnowledgeGraph(), (error) => error instanceof ApiError && error.status === 401);
  assert.equal(seen.length, 4, "unauthenticated requests never reach fetch");
});

const graph = {
  nodes: [
    { id: "paper:1", type: "paper", label: "বাংলা baseline", origin: "verified_metadata", provenance: "user_record" },
    { id: "paper:2", type: "paper", label: "Related method", origin: "verified_metadata", provenance: "provider_metadata" },
    { id: "topic:1", type: "topic", label: "Method", origin: "inferred_similarity", provenance: "title_tokens" },
    { id: "author:1", type: "author", label: "Author One", origin: "verified_metadata", provenance: "provider_metadata" },
  ],
  edges: [
    { id: "actual", source: "paper:1", target: "author:1", type: "authored_by", origin: "verified_metadata", provenance: "provider_metadata" },
    { id: "guess", source: "paper:1", target: "paper:2", type: "shared_topic_inferred", origin: "inferred_similarity", provenance: "title_tokens" },
    { id: "topic", source: "paper:2", target: "topic:1", type: "shared_topic_inferred", origin: "inferred_similarity", provenance: "title_tokens" },
  ],
  truncated: false, limits: { papers: 300, nodes: 1000, edges: 3000 }, project_id: null,
};

test("graph origin filtering preserves recorded edges and never promotes inferred links", () => {
  const source = structuredClone(graph);
  const recorded = graphWindow(graph, { query: "", type: "all", inferred: false, page: 0, size: 120 });
  assert.equal(recorded.nodes.length, 3);
  assert.deepEqual(recorded.edges.map((edge) => edge.id), ["actual"]);
  assert.equal(recorded.edges[0].origin, "verified_metadata");
  const inferred = graphWindow(graph, { query: "", type: "all", inferred: true, page: 0, size: 120 });
  assert.equal(inferred.edges.find((edge) => edge.id === "guess").origin, "inferred_similarity");
  assert.deepEqual(graph, source, "UI filters leave server provenance unchanged");
});

test("graph pages contain only their own connecting edges and retain stable accessible coordinates", () => {
  const page = graphWindow(graph, { query: "", type: "all", inferred: true, page: 0, size: 2 });
  assert.deepEqual(page.nodes.map((node) => node.id), ["paper:1", "paper:2"]);
  assert.deepEqual(page.edges.map((edge) => edge.id), ["guess"]);
  assert.equal(page.total, 4); assert.equal(page.pageCount, 2);
  const search = graphWindow(graph, { query: "বাংলা", type: "paper", inferred: true, page: 99, size: 120 });
  assert.equal(search.page, 0); assert.equal(search.nodes[0].id, "paper:1"); assert.equal(search.edges.length, 0);
  assert.deepEqual(layoutGraph(page.nodes), layoutGraph(page.nodes));
  for (const node of layoutGraph(page.nodes).nodes) {
    assert.ok(Number.isFinite(node.x) && Number.isFinite(node.y));
    assert.ok(node.x >= 0 && node.y >= 0);
  }
  assert.equal(layoutGraph([]).height, 420);
});

test("publication bars aggregate the same year across distinct metadata provenance", () => {
  const records = [{ year: 2025, count: 2, provenance: "provider_metadata" }, { year: 2024, count: 1, provenance: "verified_citation" }, { year: 2025, count: 3, provenance: "verified_citation" }];
  assert.deepEqual(publicationBuckets(records), [{ year: 2024, count: 1 }, { year: 2025, count: 5 }]);
  assert.equal(records[0].count, 2);
  assert.deepEqual(publicationBuckets([]), []);
});
