import { useCallback, useEffect, useState } from "react";

// Cross-device "have I applied to this" tracking, synced through a Netlify
// Function (frontend/netlify/functions/applied.mts) backed by Netlify Blobs.
// Reads are public; writes need a shared secret token the site owner sets
// once per device (prompted here, then cached in localStorage) -- this is a
// personal sync mechanism, not a multi-user accounts system.
const TOKEN_KEY = "appliedSyncToken";
const IDS_CACHE_KEY = "appliedJobIdsCache";
const ENDPOINT = "/api/applied";

function readLocalCache(): Set<string> {
  try {
    const raw = localStorage.getItem(IDS_CACHE_KEY);
    return new Set(raw ? (JSON.parse(raw) as string[]) : []);
  } catch {
    return new Set();
  }
}

function writeLocalCache(ids: Set<string>): void {
  localStorage.setItem(IDS_CACHE_KEY, JSON.stringify([...ids]));
}

function promptForToken(): string | null {
  const token = window.prompt(
    "Enter your applied-tracking sync token.\nThis is stored only on this device and lets you mark jobs applied everywhere you view this dashboard.",
  );
  if (!token) return null;
  localStorage.setItem(TOKEN_KEY, token);
  return token;
}

export type SetAppliedResult =
  | { ok: true; appliedIds: Set<string> }
  | { ok: false; reason: "no-token" | "unauthorized" | "network" };

export async function fetchAppliedIds(): Promise<Set<string>> {
  try {
    const resp = await fetch(ENDPOINT);
    if (!resp.ok) return readLocalCache();
    const data = (await resp.json()) as { appliedIds: string[] };
    const ids = new Set(data.appliedIds);
    writeLocalCache(ids);
    return ids;
  } catch {
    return readLocalCache();
  }
}

export async function setApplied(id: string, applied: boolean): Promise<SetAppliedResult> {
  let token = localStorage.getItem(TOKEN_KEY);
  if (!token) {
    token = promptForToken();
    if (!token) return { ok: false, reason: "no-token" };
  }

  try {
    const resp = await fetch(ENDPOINT, {
      method: "POST",
      headers: { "Content-Type": "application/json", "x-applied-token": token },
      body: JSON.stringify({ id, applied }),
    });
    if (resp.status === 401) {
      localStorage.removeItem(TOKEN_KEY);
      return { ok: false, reason: "unauthorized" };
    }
    if (!resp.ok) return { ok: false, reason: "network" };
    const data = (await resp.json()) as { appliedIds: string[] };
    const ids = new Set(data.appliedIds);
    writeLocalCache(ids);
    return { ok: true, appliedIds: ids };
  } catch {
    return { ok: false, reason: "network" };
  }
}

interface AppliedTracking {
  appliedIds: Set<string>;
  isApplied: (id: string) => boolean;
  toggleApplied: (id: string) => Promise<void>;
  pendingId: string | null;
  error: string | null;
}

// Hydrates from localStorage immediately (so a repeat visit renders applied
// state with zero network latency), then reconciles against the server in
// the background -- optimistic on write, with a rollback if the token turns
// out to be wrong or the request fails outright.
export function useAppliedTracking(): AppliedTracking {
  const [appliedIds, setAppliedIds] = useState<Set<string>>(() => readLocalCache());
  const [pendingId, setPendingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchAppliedIds().then((ids) => {
      if (!cancelled) setAppliedIds(ids);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const toggleApplied = useCallback(
    async (id: string) => {
      const nextApplied = !appliedIds.has(id);
      const optimistic = new Set(appliedIds);
      if (nextApplied) optimistic.add(id);
      else optimistic.delete(id);
      setAppliedIds(optimistic);
      setPendingId(id);
      setError(null);

      const result = await setApplied(id, nextApplied);
      setPendingId(null);
      if (result.ok) {
        setAppliedIds(result.appliedIds);
        return;
      }

      setAppliedIds((current) => {
        const rolledBack = new Set(current);
        if (nextApplied) rolledBack.delete(id);
        else rolledBack.add(id);
        return rolledBack;
      });
      if (result.reason === "unauthorized") setError("Sync token was rejected -- try again to re-enter it.");
      else if (result.reason === "network") setError("Couldn't reach the sync service -- change wasn't saved.");
    },
    [appliedIds],
  );

  return {
    appliedIds,
    isApplied: (id: string) => appliedIds.has(id),
    toggleApplied,
    pendingId,
    error,
  };
}
