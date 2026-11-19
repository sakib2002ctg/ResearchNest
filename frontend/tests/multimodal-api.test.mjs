import assert from "node:assert/strict";
import test from "node:test";

import { api, ApiError, clearAccessToken, setAccessToken } from "../lib/api.ts";
import { assetTablePreview, filterDocumentAssets } from "../lib/multimodal.ts";

test("multimodal calls preserve owner-derived APIs, extraction status, typed filters and bilingual questions", async () => {
  const requests = [];
  globalThis.fetch = async (url, init) => {
    requests.push({ url: new URL(url), init });
    return Response.json({});
  };
  setAccessToken("multimodal-private-session");
  try {
    await api.extractDocumentAssets(11);
    await api.getDocumentAssets(11, { asset_type: "table", page_number: 3 });
    await api.getDocumentAsset(17);
    await api.explainDocumentAsset(17, { language: "bn", provider: "offline", request_id: "92ad4528-c9ce-44af-a970-af5ca859d712" });
    await api.questionDocumentAsset(17, { language: "bn", provider: "local", request_id: "c0197950-23e4-4d11-934b-71c0b0c70089", question: "এই সারণিতে কী মান দেখানো হয়েছে?" });
  } finally { clearAccessToken(); }
  assert.deepEqual(requests.map(({ url }) => url.pathname), [
    "/api/v1/multimodal/documents/11/extract", "/api/v1/multimodal/documents/11/assets",
    "/api/v1/multimodal/assets/17", "/api/v1/multimodal/assets/17/explain", "/api/v1/multimodal/assets/17/vqa",
  ]);
  assert.equal(requests[0].init.method, "POST");
  assert.equal(requests[1].url.searchParams.get("asset_type"), "table");
  assert.equal(requests[1].url.searchParams.get("page_number"), "3");
  assert.equal(JSON.parse(requests[3].init.body).request_id, "92ad4528-c9ce-44af-a970-af5ca859d712");
  assert.equal(JSON.parse(requests[4].init.body).question, "এই সারণিতে কী মান দেখানো হয়েছে?");
  assert.equal(JSON.parse(requests[4].init.body).language, "bn");
  for (const { url, init } of requests) {
    assert.equal(init.headers.Authorization, "Bearer multimodal-private-session");
    assert.equal(init.cache, "no-store");
    assert.equal(init.credentials, "omit");
    assert.equal(init.redirect, "error");
    assert.equal(url.searchParams.has("token"), false);
    assert.equal(url.searchParams.has("user_id"), false);
    if (init.body) assert.equal(Object.hasOwn(JSON.parse(init.body), "user_id"), false);
  }
});

test("private PNG previews require bearer transport, preserve cancellation and reject incorrect MIME", async () => {
  const requests = [];
  const controller = new AbortController();
  globalThis.fetch = async (url, init) => {
    requests.push({ url, init });
    return new Response(new Uint8Array([137, 80, 78, 71]), { headers: { "Content-Type": "image/png" } });
  };
  setAccessToken("private-image-session");
  try {
    const blob = await api.getDocumentAssetImage(8, controller.signal);
    assert.equal(blob.type, "image/png");
    assert.equal(blob.size, 4);
    assert.equal(requests[0].init.headers.Authorization, "Bearer private-image-session");
    assert.equal(requests[0].init.headers.Accept, "image/png");
    controller.abort();
    assert.equal(requests[0].init.signal.aborted, true);
    globalThis.fetch = async () => new Response("<script>unsafe</script>", { headers: { "Content-Type": "text/html" } });
    await assert.rejects(api.getDocumentAssetImage(8), (error) => error instanceof ApiError && error.status === 502);
  } finally { clearAccessToken(); }
  await assert.rejects(api.getDocumentAssetImage(8), (error) => error instanceof ApiError && error.status === 401);
});

test("asset filters include diagrams with visual figures and keep equation/table categories separate", () => {
  const assets = ["figure", "chart", "diagram", "table", "equation"].map((asset_type, id) => ({ id, asset_type }));
  assert.deepEqual(filterDocumentAssets(assets, "all"), assets);
  assert.deepEqual(filterDocumentAssets(assets, "visual").map((asset) => asset.asset_type), ["figure", "chart", "diagram"]);
  assert.deepEqual(filterDocumentAssets(assets, "table").map((asset) => asset.asset_type), ["table"]);
  assert.deepEqual(filterDocumentAssets(assets, "equation").map((asset) => asset.asset_type), ["equation"]);
});

test("table previews bound rendering and preserve source cells as literal text without inventing values", () => {
  const asset = {
    asset_type: "table", structured_data: {
      headers: ["Model", "Accuracy"], rows: [
        ["<img src=x onerror=alert(1)>", 97.2], [null, "=SUM(A1:A2)"], [{ untrusted: "object" }, "নির্ভুলতা"],
        ...Array.from({ length: 11 }, () => ["Source", "12"]),
      ],
    },
  };
  const preview = assetTablePreview(asset);
  assert.deepEqual(preview.headers, ["Model", "Accuracy"]);
  assert.equal(preview.total, 14);
  assert.equal(preview.rows.length, 10);
  assert.deepEqual(preview.rows[0], ["<img src=x onerror=alert(1)>", "97.2"]);
  assert.deepEqual(preview.rows[1], ["", "=SUM(A1:A2)"]);
  assert.deepEqual(preview.rows[2], ["", "নির্ভুলতা"]);
  assert.equal(assetTablePreview({ asset_type: "figure", structured_data: asset.structured_data }), null);
  assert.equal(assetTablePreview({ asset_type: "table", structured_data: { rows: "invalid" } }), null);
});
