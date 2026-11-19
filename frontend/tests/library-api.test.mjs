import assert from "node:assert/strict";
import test from "node:test";

import {
  api,
  clearAccessToken,
  setAccessToken,
} from "../lib/api.ts";

test("library APIs send owner-scoped routes and private mutations", async () => {
  const requests = [];
  const responses = [
    { items: [], page: 2, size: 10, total: 0, pages: 0 },
    [],
    [],
    { id: 7, reading_status: "reading", reading_progress_percent: 20 },
    undefined,
    undefined,
    undefined,
    undefined,
    { id: 9, type: "note", content: "Text", page_number: null, color: null, created_at: "", updated_at: "" },
  ];
  globalThis.fetch = async (url, init) => {
    requests.push({ url: new URL(url), init });
    const payload = responses.shift();
    return payload === undefined
      ? new Response(null, { status: 204 })
      : Response.json(payload);
  };
  setAccessToken("library-local-test-token");
  try {
    await api.getLibrary({ q: "test paper & author", collection_id: 4, tag_id: undefined, page: 2, size: 10 });
    await api.getLibraryCollections();
    await api.getLibraryTags();
    await api.setReadingProgress(7, { reading_status: "reading", reading_progress_percent: 20 });
    await api.setLibraryMembership("collections", 4, 7, true);
    await api.createLibraryAnnotation(7, { type: "note", content: "Text", page_number: null, color: null });
    await api.updateLibraryAnnotation(7, 9, { type: "highlight", content: "Text", page_number: 2, color: "#fde68a" });
    await api.deleteLibraryAnnotation(7, 9);
  } finally {
    clearAccessToken();
  }

  assert.equal(requests.length, 8);
  assert.equal(requests[0].url.pathname, "/api/v1/library/papers");
  assert.equal(requests[0].url.searchParams.get("q"), "test paper & author");
  assert.equal(requests[0].url.searchParams.get("collection_id"), "4");
  assert.equal(requests[0].url.searchParams.get("tag_id"), null);
  assert.equal(requests[1].url.pathname, "/api/v1/library/collections");
  assert.equal(requests[2].url.pathname, "/api/v1/library/tags");
  assert.equal(requests[3].init.method, "PATCH");
  assert.deepEqual(JSON.parse(requests[3].init.body), {
    reading_status: "reading",
    reading_progress_percent: 20,
  });
  assert.equal(requests[4].url.pathname, "/api/v1/library/collections/4/papers/7");
  assert.equal(requests[4].init.method, "PUT");
  assert.equal(requests[5].url.pathname, "/api/v1/library/papers/7/annotations");
  assert.equal(requests[5].init.method, "POST");
  assert.equal(requests[6].url.pathname, "/api/v1/library/papers/7/annotations/9");
  assert.equal(requests[6].init.method, "PATCH");
  assert.equal(requests[7].url.pathname, "/api/v1/library/papers/7/annotations/9");
  assert.equal(requests[7].init.method, "DELETE");
  for (const request of requests) {
    assert.equal(request.init.headers.Authorization, "Bearer library-local-test-token");
    assert.equal(request.init.credentials, "omit");
    assert.equal(request.init.redirect, "error");
    assert.equal(request.url.searchParams.has("token"), false);
  }
});

test("PDF upload uses multipart form data and the private bearer client", async () => {
  let captured;
  globalThis.fetch = async (url, init) => {
    captured = { url: new URL(url), init };
    return Response.json({
      id: 3,
      user_paper_id: 7,
      original_filename: "paper.pdf",
      size_bytes: 10,
      page_count: 1,
    }, { status: 201 });
  };
  const bytes = Uint8Array.from([37, 80, 68, 70, 45]);
  const file = new File([bytes], "paper.pdf", { type: "application/pdf" });
  setAccessToken("library-upload-test-token");
  try {
    const uploaded = await api.uploadLibraryPDF(file, undefined, 7);
    assert.equal(uploaded.user_paper_id, 7);
  } finally {
    clearAccessToken();
  }
  assert.equal(captured.url.pathname, "/api/v1/library/upload");
  assert.equal(captured.init.method, "POST");
  assert.equal(captured.init.headers.Authorization, "Bearer library-upload-test-token");
  assert.equal(captured.init.headers["Content-Type"], undefined);
  assert.equal(captured.init.body.get("file"), file);
  assert.equal(captured.init.body.get("user_paper_id"), "7");
});

test("PDF download requires the bearer header and validates the response MIME", async () => {
  let captured;
  globalThis.fetch = async (url, init) => {
    captured = { url: new URL(url), init };
    return new Response(new Uint8Array([37, 80, 68, 70, 45]), {
      headers: { "Content-Type": "application/pdf" },
    });
  };
  setAccessToken("library-download-test-token");
  try {
    const blob = await api.getLibraryPDF(7);
    assert.equal(blob.type, "application/pdf");
    assert.equal(blob.size, 5);
  } finally {
    clearAccessToken();
  }
  assert.equal(captured.url.pathname, "/api/v1/library/papers/7/pdf");
  assert.equal(captured.init.method, "GET");
  assert.equal(captured.init.headers.Accept, "application/pdf");
  assert.equal(captured.init.headers.Authorization, "Bearer library-download-test-token");
  assert.equal(captured.url.search, "");
});
