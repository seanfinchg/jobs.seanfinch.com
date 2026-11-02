import { test, beforeEach, afterEach } from "node:test";
import assert from "node:assert/strict";
import { handleApi, resetCache } from "./apiHandler.ts";

const JOBS = [
  {
    id: "j1",
    company: "Acme",
    title: "Security Engineer",
    location: "Remote",
    best_apply_url: "https://boards.greenhouse.io/acme/1",
    apply_urls: ["https://boards.greenhouse.io/acme/1", "https://example.com/1"],
    first_seen: "2026-10-01T00:00:00Z",
    posted_at: "2026-10-30T00:00:00Z",
    salary_min: 120000,
    salary_max: 160000,
    level: "mid",
    matched_fields: ["security"],
    matched_subfields: [],
    grad_year: null,
    featured: false,
    defense: false,
  },
  {
    id: "j2",
    company: "Beta",
    title: "Backend Developer",
    location: "Austin",
    best_apply_url: "https://jobs.lever.co/beta/2",
    apply_urls: ["https://jobs.lever.co/beta/2"],
    first_seen: "2026-10-02T00:00:00Z",
    posted_at: null,
    salary_min: null,
    salary_max: null,
    level: "senior",
    matched_fields: ["software-engineering"],
    matched_subfields: [],
    grad_year: null,
    featured: true,
    defense: false,
  },
];

const FIELDS = [{ slug: "security", label: "Security", subfields: [{ tag: "appsec", label: "AppSec" }] }];
const META = { generated_at: "2026-10-31T06:00:00+00:00" };

const realFetch = globalThis.fetch;
let calls: string[] = [];
let failing = false;

beforeEach(() => {
  resetCache();
  calls = [];
  failing = false;
  globalThis.fetch = (async (input: unknown) => {
    const path = new URL(String(input)).pathname;
    calls.push(path);
    if (failing) return new Response("nope", { status: 500 });
    const body = path === "/data.json" ? JOBS : path === "/fields.json" ? FIELDS : META;
    return Response.json(body);
  }) as typeof fetch;
});

afterEach(() => {
  globalThis.fetch = realFetch;
});

const get = (path: string, init?: RequestInit) =>
  handleApi(new Request(`https://example.test${path}`, init));

test("GET /api/jobs returns the envelope", async () => {
  const res = await get("/api/jobs?field=security");
  assert.equal(res.status, 200);
  assert.equal(res.headers.get("access-control-allow-origin"), "*");
  assert.match(res.headers.get("cache-control") ?? "", /public/);
  const body = await res.json();
  assert.equal(body.total, 1);
  assert.equal(body.limit, 25);
  assert.equal(body.offset, 0);
  assert.equal(body.next_offset, null);
  assert.equal(body.generated_at, META.generated_at);
  assert.equal(body.jobs[0].id, "j1");
  assert.equal(body.jobs[0].ats, "greenhouse");
  assert.equal(body.jobs[0].apply_url, JOBS[0]?.best_apply_url);
});

test("pagination cursor", async () => {
  const body = await (await get("/api/jobs?limit=1")).json();
  assert.equal(body.jobs.length, 1);
  assert.equal(body.next_offset, 1);
  assert.equal(body.total, 2);
});

test("GET /api/jobs/:id includes apply block", async () => {
  const res = await get("/api/jobs/j2");
  assert.equal(res.status, 200);
  const body = await res.json();
  assert.equal(body.id, "j2");
  assert.equal(body.apply.url, "https://jobs.lever.co/beta/2");
  assert.deepEqual(body.apply.urls, ["https://jobs.lever.co/beta/2"]);
  assert.equal(body.apply.ats, "lever");
  assert.match(body.apply.note, /cannot submit/);
});

test("unknown id is a JSON 404", async () => {
  const res = await get("/api/jobs/nope");
  assert.equal(res.status, 404);
  const body = await res.json();
  assert.equal(body.error, "not_found");
});

test("GET /api/meta", async () => {
  const body = await (await get("/api/meta")).json();
  assert.equal(body.total_jobs, 2);
  assert.deepEqual(body.levels, ["mid", "senior"]);
  assert.deepEqual(body.fields, FIELDS);
  assert.deepEqual(
    body.ats.map((a: { name: string }) => a.name),
    ["greenhouse", "lever"],
  );
  assert.deepEqual(body.limits, { requests_per_minute: 60, max_page_size: 100 });
});

test("bad params are a JSON 400", async () => {
  const res = await get("/api/jobs?limit=500");
  assert.equal(res.status, 400);
  const body = await res.json();
  assert.equal(body.error, "bad_request");
  assert.ok(body.message);
});

test("non-GET is a JSON 405", async () => {
  const res = await get("/api/jobs", { method: "POST" });
  assert.equal(res.status, 405);
  assert.equal(res.headers.get("allow"), "GET, OPTIONS");
  assert.equal((await res.json()).error, "method_not_allowed");
});

test("OPTIONS is a 204 with CORS", async () => {
  const res = await get("/api/jobs", { method: "OPTIONS" });
  assert.equal(res.status, 204);
  assert.equal(res.headers.get("access-control-allow-origin"), "*");
});

test("data is cached between requests", async () => {
  await get("/api/jobs");
  await get("/api/meta");
  assert.equal(calls.filter((c) => c === "/data.json").length, 1);
});

test("fetch failure is a 503 with Retry-After", async () => {
  failing = true;
  const res = await get("/api/jobs");
  assert.equal(res.status, 503);
  assert.ok(res.headers.get("retry-after"));
  assert.equal((await res.json()).error, "unavailable");
});
