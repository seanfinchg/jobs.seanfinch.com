// Request handling for the jobs API, separate from api.mts so it can be
// exercised in tests without the Netlify runtime. Only erasable TypeScript.

import {
  countByAts,
  distinctLevels,
  deriveAts,
  MAX_LIMIT,
  parseQuery,
  runQuery,
  toApiJob,
  type Job,
} from "./jobsQuery.ts";

export const TTL_MS = 5 * 60 * 1000;
export const REQUESTS_PER_MINUTE = 60;

const NOTE =
  "This API cannot submit applications. A human opens the URL and submits the application themselves.";

interface Dataset {
  jobs: Job[];
  fields: unknown[];
  generatedAt: string | null;
  loadedAt: number;
}

let cache: Dataset | null = null;

export function resetCache(): void {
  cache = null;
}

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
};

function json(body: unknown, status = 200, extra: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8", ...CORS, ...extra },
  });
}

function errorResponse(status: number, error: string, message: string, extra = {}): Response {
  return json({ error, message }, status, extra);
}

async function fetchJson(req: Request, path: string): Promise<unknown> {
  const res = await fetch(new URL(path, req.url));
  if (!res.ok) throw new Error(`${path} returned ${res.status}`);
  return res.json();
}

async function loadDataset(req: Request): Promise<Dataset> {
  const now = Date.now();
  if (cache && now - cache.loadedAt < TTL_MS) return cache;
  try {
    const [jobs, fields, meta] = await Promise.all([
      fetchJson(req, "/data.json"),
      fetchJson(req, "/fields.json"),
      fetchJson(req, "/meta.json"),
    ]);
    if (!Array.isArray(jobs)) throw new Error("data.json is not an array");
    const generatedAt =
      meta && typeof meta === "object" && typeof (meta as Record<string, unknown>).generated_at === "string"
        ? ((meta as Record<string, unknown>).generated_at as string)
        : null;
    cache = {
      jobs: jobs as Job[],
      fields: Array.isArray(fields) ? fields : [],
      generatedAt,
      loadedAt: now,
    };
    return cache;
  } catch (err) {
    // Serving slightly stale data beats a 503 when only a refresh failed.
    if (cache) return cache;
    throw err;
  }
}

const CACHE_HEADERS = { "Cache-Control": "public, max-age=60" };

export async function handleApi(req: Request): Promise<Response> {
  if (req.method === "OPTIONS") {
    return new Response(null, { status: 204, headers: { ...CORS, "Access-Control-Max-Age": "86400" } });
  }
  if (req.method !== "GET") {
    return errorResponse(405, "method_not_allowed", "Only GET and OPTIONS are supported.", {
      Allow: "GET, OPTIONS",
    });
  }

  const url = new URL(req.url);
  const path = url.pathname.replace(/\/+$/, "");

  let data: Dataset;
  try {
    data = await loadDataset(req);
  } catch {
    return errorResponse(503, "unavailable", "Job data is temporarily unavailable. Retry shortly.", {
      "Retry-After": "30",
    });
  }

  if (path === "/api/meta") {
    return json(
      {
        generated_at: data.generatedAt,
        total_jobs: data.jobs.length,
        levels: distinctLevels(data.jobs),
        fields: data.fields,
        ats: countByAts(data.jobs),
        limits: { requests_per_minute: REQUESTS_PER_MINUTE, max_page_size: MAX_LIMIT },
      },
      200,
      CACHE_HEADERS,
    );
  }

  if (path === "/api/jobs") {
    const parsed = parseQuery(url.searchParams);
    if (!parsed.ok) return errorResponse(400, "bad_request", parsed.message);
    const page = runQuery(data.jobs, parsed.query);
    return json(
      {
        total: page.total,
        limit: page.limit,
        offset: page.offset,
        next_offset: page.next_offset,
        generated_at: data.generatedAt,
        jobs: page.items,
      },
      200,
      CACHE_HEADERS,
    );
  }

  const match = /^\/api\/jobs\/([^/]+)$/.exec(path);
  if (match) {
    let id: string;
    try {
      id = decodeURIComponent(match[1] as string);
    } catch {
      return errorResponse(400, "bad_request", "Malformed job id.");
    }
    const job = data.jobs.find((j) => j.id === id);
    if (!job) return errorResponse(404, "not_found", `No job with id ${id}.`);
    return json(
      {
        ...toApiJob(job),
        apply: {
          url: job.best_apply_url,
          urls: job.apply_urls,
          ats: deriveAts(job.best_apply_url),
          note: NOTE,
        },
      },
      200,
      CACHE_HEADERS,
    );
  }

  return errorResponse(404, "not_found", "Unknown endpoint.");
}
