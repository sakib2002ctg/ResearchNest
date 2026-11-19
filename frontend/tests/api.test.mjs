import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = await readFile(new URL("../lib/api.ts", import.meta.url), "utf8");

test("bearer access token is memory-only and requests are never cookie-backed", () => {
  assert.match(source, /let accessToken: string \| null = null/);
  assert.match(source, /credentials: "omit"/);
  assert.doesNotMatch(source, /localStorage\.(?:get|set)Item\([^\n]*(?:token|auth|session)/i);
  assert.doesNotMatch(source, /sessionStorage\.(?:get|set)Item\([^\n]*(?:token|auth|session)/i);
});

test("all identity, private account, paper, and research routes use the v1 API client", () => {
  for (const path of [
    "/auth/login", "/auth/register", "/auth/verify-email/request",
    "/auth/verify-email/confirm", "/auth/password-reset/request",
    "/auth/password-reset/confirm", "/auth/password-change",
    "/users/me/profile", "/users/me/preferences", "/users/me/sessions",
    "/users/me/activity", "/users/me/export", "/users/me/dashboard",
    "/papers/", "/papers/search", "/research/search",
  ]) assert.ok(source.includes(`"${path}`) || source.includes("`" + path), `missing API path ${path}`);
});

test("API credentials are never forwarded across redirects", () => {
  assert.match(source, /redirect: "error"/);
  assert.match(source, /referrerPolicy: "no-referrer"/);
  assert.match(source, /cache: "no-store"/);
});
