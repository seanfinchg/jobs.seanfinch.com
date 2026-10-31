import { test } from "node:test";
import assert from "node:assert/strict";
import {
  deriveAts,
  filterJobs,
  paginate,
  parseQuery,
  parseSince,
  runQuery,
  sortJobs,
  type Job,
  type Query,
} from "./jobsQuery.ts";

const NOW = Date.parse("2026-10-31T12:00:00Z");

function job(over: Partial<Job> & { id: string }): Job {
  return {
    company: "Acme",
    title: "Engineer",
    location: "Remote",
    best_apply_url: "https://boards.greenhouse.io/acme/jobs/1",
    apply_urls: ["https://boards.greenhouse.io/acme/jobs/1"],
    first_seen: "2026-10-01T00:00:00Z",
    posted_at: null,
    salary_min: null,
    salary_max: null,
    level: "mid",
    matched_fields: [],
    matched_subfields: [],
    grad_year: null,
    featured: false,
    defense: false,
    ...over,
  };
}

const JOBS: Job[] = [
  job({
    id: "a",
    company: "Acme",
    title: "Security Engineer",
    location: "New York, NY",
    posted_at: "2026-10-30T00:00:00Z",
    salary_min: 150000,
    salary_max: 200000,
    matched_fields: ["security"],
    matched_subfields: ["appsec"],
    featured: true,
  }),
  job({
    id: "b",
    company: "Beta Corp",
    title: "Backend Developer",
    location: "Remote",
    best_apply_url: "https://jobs.lever.co/beta/123",
    posted_at: "2026-10-10T00:00:00Z",
    salary_min: 100000,
    salary_max: 120000,
    level: "senior",
    matched_fields: ["software-engineering"],
  }),
  job({
    id: "c",
    company: "Gamma Defense",
    title: "Intern, Systems",
    location: "Austin, TX",
    best_apply_url: "https://gamma.wd5.myworkdayjobs.com/en-US/x/job/1",
    first_seen: "2026-10-29T00:00:00Z",
    level: "intern",
    matched_fields: ["systems", "security"],
    defense: true,
  }),
  job({
    id: "d",
    company: "acme",
    title: "Data Scientist",
    best_apply_url: "https://example.com/careers/1",
    first_seen: "2026-01-01T00:00:00Z",
    salary_min: 90000,
    level: "new-grad",
    matched_fields: ["data-ml"],
  }),
];

function q(params: Record<string, string>): Query {
  const r = parseQuery(new URLSearchParams(params), NOW);
  assert.ok(r.ok, r.ok ? "" : r.message);
  return r.query;
}

function ids(params: Record<string, string>): string[] {
  return runQuery(JOBS, q(params)).items.map((j) => j.id);
}

test("deriveAts maps hosts and falls back to other", () => {
  assert.equal(deriveAts("https://boards.greenhouse.io/x"), "greenhouse");
  assert.equal(deriveAts("https://job-boards.greenhouse.io/x"), "greenhouse");
  assert.equal(deriveAts("https://jobs.lever.co/x"), "lever");
  assert.equal(deriveAts("https://jobs.ashbyhq.com/x"), "ashby");
  assert.equal(deriveAts("https://a.wd1.myworkdayjobs.com/x"), "workday");
  assert.equal(deriveAts("https://jobs.smartrecruiters.com/x"), "smartrecruiters");
  assert.equal(deriveAts("https://apply.workable.com/x"), "workable");
  assert.equal(deriveAts("https://ats.rippling.com/x"), "rippling");
  assert.equal(deriveAts("https://acme.bamboohr.com/x"), "bamboohr");
  assert.equal(deriveAts("https://example.com/x"), "other");
  assert.equal(deriveAts("https://notlever.co/x"), "other");
  assert.equal(deriveAts("not a url"), "other");
});

test("defaults", () => {
  const query = q({});
  assert.equal(query.limit, 25);
  assert.equal(query.offset, 0);
  assert.equal(query.sort, "newest");
});

test("q matches title or company case-insensitively", () => {
  assert.deepEqual(ids({ q: "SECURITY" }), ["a"]);
  assert.deepEqual(ids({ q: "beta" }), ["b"]);
});

test("company is an exact case-insensitive list", () => {
  assert.deepEqual(ids({ company: "ACME" }).sort(), ["a", "d"]);
  assert.deepEqual(ids({ company: "acme, beta corp" }).sort(), ["a", "b", "d"]);
  assert.deepEqual(ids({ company: "acm" }), []);
});

test("level list", () => {
  assert.deepEqual(ids({ level: "intern,new-grad" }).sort(), ["c", "d"]);
});

test("field matches any listed field", () => {
  assert.deepEqual(ids({ field: "security" }).sort(), ["a", "c"]);
  assert.deepEqual(ids({ field: "data-ml,systems" }).sort(), ["c", "d"]);
});

test("subfield", () => {
  assert.deepEqual(ids({ subfield: "appsec" }), ["a"]);
});

test("location substring", () => {
  assert.deepEqual(ids({ location: "texas" }), []);
  assert.deepEqual(ids({ location: "tx" }), ["c"]);
});

test("salary_min requires a known floor at or above the value", () => {
  assert.deepEqual(ids({ salary_min: "100000" }).sort(), ["a", "b"]);
  assert.deepEqual(ids({ salary_min: "0" }).sort(), ["a", "b", "d"]);
});

test("has_salary true and false", () => {
  assert.deepEqual(ids({ has_salary: "true" }).sort(), ["a", "b", "d"]);
  assert.deepEqual(ids({ has_salary: "false" }), ["c"]);
});

test("posted_since falls back to first_seen and supports relative values", () => {
  assert.deepEqual(ids({ posted_since: "3d" }), ["a", "c"]);
  assert.deepEqual(ids({ posted_since: "2026-10-05" }), ["a", "c", "b"]);
});

test("featured", () => {
  assert.deepEqual(ids({ featured: "true" }), ["a"]);
  assert.equal(ids({ featured: "false" }).length, 3);
});

test("exclude_defense", () => {
  assert.equal(ids({ exclude_defense: "true" }).includes("c"), false);
  assert.equal(ids({ exclude_defense: "false" }).includes("c"), true);
});

test("ats filter", () => {
  assert.deepEqual(ids({ ats: "lever" }), ["b"]);
  assert.deepEqual(ids({ ats: "workday,other" }).sort(), ["c", "d"]);
});

test("filters combine with AND", () => {
  assert.deepEqual(ids({ field: "security", exclude_defense: "true" }), ["a"]);
});

test("sort newest, salary_desc, company", () => {
  assert.deepEqual(ids({ sort: "newest" }), ["a", "c", "b", "d"]);
  assert.deepEqual(ids({ sort: "salary_desc" }), ["a", "b", "d", "c"]);
  assert.deepEqual(ids({ sort: "company" }), ["a", "d", "b", "c"]);
});

test("sortJobs does not mutate its input", () => {
  const copy = [...JOBS];
  sortJobs(JOBS, "company");
  assert.deepEqual(JOBS, copy);
});

test("pagination", () => {
  const first = paginate([1, 2, 3, 4, 5], 2, 0);
  assert.deepEqual(first.items, [1, 2]);
  assert.equal(first.next_offset, 2);
  const last = paginate([1, 2, 3, 4, 5], 2, 4);
  assert.deepEqual(last.items, [5]);
  assert.equal(last.next_offset, null);
  const exact = paginate([1, 2, 3, 4], 2, 2);
  assert.equal(exact.next_offset, null);
  const past = paginate([1, 2], 2, 10);
  assert.deepEqual(past.items, []);
  assert.equal(past.total, 2);
  assert.equal(past.next_offset, null);
  assert.equal(paginate([], 10, 0).next_offset, null);
});

test("runQuery adds ats and apply_url and keeps original fields", () => {
  const out = runQuery(JOBS, q({ company: "beta corp" })).items[0];
  assert.ok(out);
  assert.equal(out.ats, "lever");
  assert.equal(out.apply_url, out.best_apply_url);
  assert.equal(out.company, "Beta Corp");
});

test("limit and offset paginate through runQuery", () => {
  const page = runQuery(JOBS, q({ limit: "2", offset: "1" }));
  assert.equal(page.total, 4);
  assert.deepEqual(page.items.map((j) => j.id), ["c", "b"]);
  assert.equal(page.next_offset, 3);
});

test("parseSince relative and absolute", () => {
  assert.equal(parseSince("7d", NOW), NOW - 7 * 86400000);
  assert.equal(parseSince("12h", NOW), NOW - 12 * 3600000);
  assert.equal(parseSince("2w", NOW), NOW - 14 * 86400000);
  assert.equal(parseSince("2026-10-01", NOW), Date.parse("2026-10-01"));
  assert.equal(parseSince("2026-10-01T05:00:00Z", NOW), Date.parse("2026-10-01T05:00:00Z"));
  assert.equal(parseSince("yesterday", NOW), null);
  assert.equal(parseSince("2026-13-45", NOW), null);
  assert.equal(parseSince("-3d", NOW), null);
});

test("bad params are rejected with a message", () => {
  const bad: Array<Record<string, string>> = [
    { limit: "0" },
    { limit: "101" },
    { limit: "abc" },
    { limit: "-1" },
    { offset: "-1" },
    { offset: "1.5" },
    { salary_min: "lots" },
    { has_salary: "maybe" },
    { featured: "yes" },
    { exclude_defense: "2" },
    { posted_since: "soon" },
    { sort: "random" },
    { ats: "monster" },
  ];
  for (const params of bad) {
    const r = parseQuery(new URLSearchParams(params), NOW);
    assert.equal(r.ok, false, JSON.stringify(params));
    if (!r.ok) assert.ok(r.message.length > 0);
  }
});

test("limit of 100 is accepted and empty params are ignored", () => {
  assert.equal(q({ limit: "100" }).limit, 100);
  assert.equal(q({ q: "", company: "", limit: "" }).limit, 25);
  assert.equal(filterJobs(JOBS, q({ q: "" })).length, 4);
});
