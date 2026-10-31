// Pure query logic for the read-only jobs API. Kept dependency-free and
// limited to erasable TypeScript so node can run it directly via type
// stripping in tests.

export interface Job {
  id: string;
  company: string;
  title: string;
  location: string;
  best_apply_url: string;
  apply_urls: string[];
  first_seen: string;
  posted_at: string | null;
  salary_min: number | null;
  salary_max: number | null;
  level: string;
  matched_fields: string[];
  matched_subfields: string[];
  grad_year: number | null;
  featured: boolean;
  defense: boolean;
}

export interface ApiJob extends Job {
  ats: string;
  apply_url: string;
}

export type SortKey = "newest" | "salary_desc" | "company";

export interface Query {
  q?: string;
  company?: string[];
  level?: string[];
  field?: string[];
  subfield?: string[];
  location?: string;
  salary_min?: number;
  has_salary?: boolean;
  posted_since?: number;
  featured?: boolean;
  exclude_defense?: boolean;
  ats?: string[];
  sort: SortKey;
  limit: number;
  offset: number;
}

export type ParseResult =
  | { ok: true; query: Query }
  | { ok: false; message: string };

export const DEFAULT_LIMIT = 25;
export const MAX_LIMIT = 100;
export const SORTS: readonly SortKey[] = ["newest", "salary_desc", "company"];

const ATS_HOSTS: ReadonlyArray<readonly [string, string]> = [
  ["greenhouse", "greenhouse.io"],
  ["lever", "lever.co"],
  ["ashby", "ashbyhq.com"],
  ["workday", "myworkdayjobs.com"],
  ["workday", "workday.com"],
  ["smartrecruiters", "smartrecruiters.com"],
  ["workable", "workable.com"],
  ["rippling", "rippling.com"],
  ["bamboohr", "bamboohr.com"],
];

export const ATS_NAMES: readonly string[] = [
  "greenhouse",
  "lever",
  "ashby",
  "workday",
  "smartrecruiters",
  "workable",
  "rippling",
  "bamboohr",
  "other",
];

export function deriveAts(url: string): string {
  let host: string;
  try {
    host = new URL(url).hostname.toLowerCase();
  } catch {
    return "other";
  }
  for (const [name, suffix] of ATS_HOSTS) {
    if (host === suffix || host.endsWith("." + suffix)) return name;
  }
  return "other";
}

export function toApiJob(job: Job): ApiJob {
  return { ...job, ats: deriveAts(job.best_apply_url), apply_url: job.best_apply_url };
}

function splitList(value: string): string[] {
  return value
    .split(",")
    .map((s) => s.trim().toLowerCase())
    .filter((s) => s.length > 0);
}

function parseBool(name: string, value: string): boolean | string {
  const v = value.toLowerCase();
  if (v === "true" || v === "1") return true;
  if (v === "false" || v === "0") return false;
  return `${name} must be true or false`;
}

function parseIntParam(name: string, value: string): number | string {
  if (!/^\d+$/.test(value.trim())) return `${name} must be a non-negative integer`;
  return Number(value.trim());
}

const DAY_MS = 24 * 60 * 60 * 1000;

// Returns an epoch-ms cutoff. Relative forms (7d, 12h, 2w) are measured back
// from `now`, which is injected so tests are deterministic.
export function parseSince(value: string, now: number): number | null {
  const v = value.trim();
  const rel = /^(\d+)([hdw])$/i.exec(v);
  if (rel) {
    const unit = (rel[2] as string).toLowerCase();
    const mult = unit === "h" ? DAY_MS / 24 : unit === "d" ? DAY_MS : 7 * DAY_MS;
    return now - Number(rel[1]) * mult;
  }
  if (/^\d{4}-\d{2}-\d{2}([T ].*)?$/.test(v)) {
    const t = Date.parse(v);
    return Number.isNaN(t) ? null : t;
  }
  return null;
}

export function parseQuery(params: URLSearchParams, now: number = Date.now()): ParseResult {
  const query: Query = { sort: "newest", limit: DEFAULT_LIMIT, offset: 0 };
  const get = (k: string): string | null => {
    const v = params.get(k);
    return v === null || v.trim() === "" ? null : v;
  };

  const q = get("q");
  if (q !== null) query.q = q.trim().toLowerCase();
  const location = get("location");
  if (location !== null) query.location = location.trim().toLowerCase();

  for (const key of ["company", "level", "field", "subfield", "ats"] as const) {
    const raw = get(key);
    if (raw === null) continue;
    const list = splitList(raw);
    if (list.length === 0) continue;
    if (key === "ats") {
      const bad = list.find((a) => !ATS_NAMES.includes(a));
      if (bad !== undefined) {
        return { ok: false, message: `ats must be one of: ${ATS_NAMES.join(", ")}` };
      }
    }
    query[key] = list;
  }

  for (const key of ["has_salary", "featured", "exclude_defense"] as const) {
    const raw = get(key);
    if (raw === null) continue;
    const r = parseBool(key, raw);
    if (typeof r === "string") return { ok: false, message: r };
    query[key] = r;
  }

  const salary = get("salary_min");
  if (salary !== null) {
    const r = parseIntParam("salary_min", salary);
    if (typeof r === "string") return { ok: false, message: r };
    query.salary_min = r;
  }

  const since = get("posted_since");
  if (since !== null) {
    const cutoff = parseSince(since, now);
    if (cutoff === null) {
      return {
        ok: false,
        message: "posted_since must be an ISO date (2026-01-31) or relative (12h, 7d, 2w)",
      };
    }
    query.posted_since = cutoff;
  }

  const sort = get("sort");
  if (sort !== null) {
    if (!SORTS.includes(sort as SortKey)) {
      return { ok: false, message: `sort must be one of: ${SORTS.join(", ")}` };
    }
    query.sort = sort as SortKey;
  }

  const limit = get("limit");
  if (limit !== null) {
    const r = parseIntParam("limit", limit);
    if (typeof r === "string") return { ok: false, message: r };
    if (r < 1 || r > MAX_LIMIT) {
      return { ok: false, message: `limit must be between 1 and ${MAX_LIMIT}` };
    }
    query.limit = r;
  }

  const offset = get("offset");
  if (offset !== null) {
    const r = parseIntParam("offset", offset);
    if (typeof r === "string") return { ok: false, message: r };
    query.offset = r;
  }

  return { ok: true, query };
}

function postedTime(job: Job): number {
  const t = Date.parse(job.posted_at ?? job.first_seen);
  return Number.isNaN(t) ? 0 : t;
}

export function filterJobs(jobs: readonly Job[], query: Query): Job[] {
  return jobs.filter((job) => {
    if (query.q !== undefined) {
      const hay = `${job.title}\n${job.company}`.toLowerCase();
      if (!hay.includes(query.q)) return false;
    }
    if (query.company && !query.company.includes(job.company.toLowerCase())) return false;
    if (query.level && !query.level.includes(job.level.toLowerCase())) return false;
    if (query.field && !job.matched_fields.some((f) => query.field?.includes(f.toLowerCase()))) {
      return false;
    }
    if (
      query.subfield &&
      !job.matched_subfields.some((f) => query.subfield?.includes(f.toLowerCase()))
    ) {
      return false;
    }
    if (query.location !== undefined && !job.location.toLowerCase().includes(query.location)) {
      return false;
    }
    if (query.salary_min !== undefined) {
      if (job.salary_min === null || job.salary_min < query.salary_min) return false;
    }
    if (query.has_salary === true && job.salary_min === null && job.salary_max === null) {
      return false;
    }
    if (query.has_salary === false && (job.salary_min !== null || job.salary_max !== null)) {
      return false;
    }
    if (query.posted_since !== undefined && postedTime(job) < query.posted_since) return false;
    if (query.featured !== undefined && job.featured !== query.featured) return false;
    if (query.exclude_defense === true && job.defense) return false;
    if (query.ats && !query.ats.includes(deriveAts(job.best_apply_url))) return false;
    return true;
  });
}

export function sortJobs(jobs: readonly Job[], sort: SortKey): Job[] {
  const copy = [...jobs];
  const byNewest = (a: Job, b: Job): number => postedTime(b) - postedTime(a);
  if (sort === "company") {
    copy.sort(
      (a, b) =>
        a.company.toLowerCase().localeCompare(b.company.toLowerCase()) ||
        byNewest(a, b) ||
        a.id.localeCompare(b.id),
    );
  } else if (sort === "salary_desc") {
    // Postings without a salary sort last rather than first.
    const top = (j: Job): number => j.salary_max ?? j.salary_min ?? -1;
    copy.sort((a, b) => top(b) - top(a) || byNewest(a, b) || a.id.localeCompare(b.id));
  } else {
    copy.sort((a, b) => byNewest(a, b) || a.id.localeCompare(b.id));
  }
  return copy;
}

export interface Page<T> {
  total: number;
  limit: number;
  offset: number;
  next_offset: number | null;
  items: T[];
}

export function paginate<T>(items: readonly T[], limit: number, offset: number): Page<T> {
  const total = items.length;
  const slice = items.slice(offset, offset + limit);
  const end = offset + slice.length;
  return {
    total,
    limit,
    offset,
    next_offset: end < total ? end : null,
    items: slice,
  };
}

export function runQuery(jobs: readonly Job[], query: Query): Page<ApiJob> {
  const sorted = sortJobs(filterJobs(jobs, query), query.sort);
  const page = paginate(sorted, query.limit, query.offset);
  return { ...page, items: page.items.map(toApiJob) };
}

export function countByAts(jobs: readonly Job[]): Array<{ name: string; count: number }> {
  const counts = new Map<string, number>();
  for (const job of jobs) {
    const name = deriveAts(job.best_apply_url);
    counts.set(name, (counts.get(name) ?? 0) + 1);
  }
  return [...counts.entries()]
    .map(([name, count]) => ({ name, count }))
    .sort((a, b) => b.count - a.count || a.name.localeCompare(b.name));
}

export function distinctLevels(jobs: readonly Job[]): string[] {
  return [...new Set(jobs.map((j) => j.level))].sort();
}
