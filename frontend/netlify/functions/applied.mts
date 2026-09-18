import type { Config } from "@netlify/functions";
import { getStore } from "@netlify/blobs";

// One shared secret gates writes (APPLIED_SYNC_TOKEN, set as a Netlify env
// var on the real site -- never committed). Reads stay public/unauthenticated
// on purpose: this is a personal cross-device sync of "have I applied to
// this", not a multi-user accounts system, and the dashboard itself is
// already public.
const STORE_NAME = "applied-jobs";
const KEY = "ids";

async function readAppliedIds(): Promise<string[]> {
  const store = getStore(STORE_NAME);
  const raw = await store.get(KEY, { type: "json" });
  return Array.isArray(raw) ? (raw as string[]) : [];
}

export default async (req: Request): Promise<Response> => {
  if (req.method === "GET") {
    const appliedIds = await readAppliedIds();
    return Response.json({ appliedIds });
  }

  if (req.method === "POST") {
    const expected = process.env.APPLIED_SYNC_TOKEN ?? "";
    const provided = req.headers.get("x-applied-token") ?? "";
    if (!expected || provided !== expected) {
      return new Response("unauthorized", { status: 401 });
    }

    let body: { id?: string; applied?: boolean };
    try {
      body = await req.json();
    } catch {
      return new Response("invalid json body", { status: 400 });
    }
    if (!body.id || typeof body.applied !== "boolean") {
      return new Response("body must be {id: string, applied: boolean}", { status: 400 });
    }

    const store = getStore(STORE_NAME);
    const current = await readAppliedIds();
    const appliedIds = body.applied
      ? [...new Set([...current, body.id])]
      : current.filter((id) => id !== body.id);
    await store.setJSON(KEY, appliedIds);
    return Response.json({ appliedIds });
  }

  return new Response("method not allowed", { status: 405 });
};

export const config: Config = {
  path: "/api/applied",
};
