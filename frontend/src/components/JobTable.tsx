import { useEffect, useMemo, useState } from "react";
import type { FieldMeta, Job, SortKey } from "@/types";
import { LEVEL_LABELS, LEVEL_ORDER } from "@/types";
import { relativeDate } from "@/lib/date";
import { parseLocation } from "@/lib/location";

interface JobTableProps {
  jobs: Job[];
  fields: FieldMeta[];
}

// Secondary columns (className) collapse on narrow screens -- Company/
// Title/Location/Posted/Apply stay put as the columns worth a horizontal
// scroll on mobile, the rest just add noise there.
const COLUMNS: { key: SortKey; label: string; className?: string }[] = [
  { key: "company", label: "Company" },
  { key: "title", label: "Title" },
  { key: "location", label: "Location" },
  { key: "level", label: "Level", className: "hidden md:table-cell" },
  { key: "posted", label: "Posted" },
];

function fieldLabelMaps(fields: FieldMeta[]): { fieldLabels: Record<string, string>; subfieldLabels: Record<string, string> } {
  return {
    fieldLabels: Object.fromEntries(fields.map((f) => [f.slug, f.label])),
    subfieldLabels: Object.fromEntries(fields.flatMap((f) => f.subfields.map((s) => [s.tag, s.label]))),
  };
}

function roleLabel(job: Job, fieldLabels: Record<string, string>, subfieldLabels: Record<string, string>): string {
  const labels = job.matched_subfields.length > 0
    ? job.matched_subfields.map((s) => subfieldLabels[s] ?? s)
    : job.matched_fields.map((f) => fieldLabels[f] ?? f);
  return labels.length > 0 ? labels.join(", ") : "—";
}

// Levels don't sort alphabetically (LEVEL_ORDER runs intern -> vp, not
// A -> Z), so this needs its own comparator instead of the generic
// string/number compare used for every other column.
function levelRank(level: string | null): number {
  if (level === null) return LEVEL_ORDER.length;
  const idx = LEVEL_ORDER.indexOf(level);
  return idx === -1 ? LEVEL_ORDER.length : idx;
}

const PAGE_SIZE = 50;

function formatSalary(min: number | null, max: number | null): string {
  const fmt = (n: number) => `$${Math.round(n / 1000)}k`;
  if (min != null && max != null && min !== max) return `${fmt(min)}–${fmt(max)}`;
  if (min != null) return `${fmt(min)}+`;
  if (max != null) return fmt(max);
  return "—";
}

// posted_at (the employer's own stated date) is more meaningful to a reader
// than first_seen (jobfinder's own ingestion bookkeeping) whenever the
// source actually provides one -- several adapters never do.
function displayDate(job: Job): string {
  return job.posted_at ?? job.first_seen;
}

// Every adapter formats location differently ("US - Remote", "New York
// City; Seattle; United States", "NYC-Privy", ...) -- run every row through
// the same parser used for the location filter tags so what's actually
// displayed reads consistently too, not just what's filterable. Falls back
// to the raw string only when parsing found nothing recognizable.
function displayLocation(job: Job): string {
  const labels = parseLocation(job.location).labels;
  return labels.length > 0 ? labels.join(" / ") : job.location;
}

interface ApplyCellProps {
  job: Job;
  expanded: boolean;
  onToggleExpanded: () => void;
}

// Shared between the table row and the mobile card so there's one place to
// touch instead of two copies drifting apart. Module-level rather than
// defined inside JobTable so its identity is stable across renders -- a
// component redefined per render would remount (and lose the open popover)
// on every sort/expand.
//
// Applied-tracking (mark applied / synced across devices) is deliberately
// not rendered here -- the Netlify Function backing it was never verified
// against a real deploy, so it doesn't work yet. Pull the
// UI back in once that's actually confirmed working, not before.
function ApplyCell({ job, expanded, onToggleExpanded }: ApplyCellProps): React.JSX.Element {
  const otherUrls = job.apply_urls.filter((url) => url !== job.best_apply_url);
  return (
    <>
      <a href={job.best_apply_url} target="_blank" rel="noopener noreferrer" className="text-accent hover:underline">
        apply
      </a>
      {otherUrls.length > 0 && (
        <div className="relative inline-block">
          <button
            type="button"
            onClick={onToggleExpanded}
            className="ml-2 inline-block px-1 py-1.5 text-ultra-light-mode/50 hover:text-light-mode sm:py-0"
          >
            +{otherUrls.length} more
          </button>
          {expanded && (
            // Anchored (absolute, not fixed) to the local `relative` wrapper
            // above -- the page root has its own entrance-animation
            // transform (animate-fade-up), and a transformed ancestor
            // hijacks the containing block for any `fixed` descendant, so
            // `fixed` here would resolve against that faraway root instead
            // of the viewport. `absolute` doesn't have that problem: it
            // already resolves to the nearest positioned ancestor, which is
            // the wrapper right above, so it stays anchored to the button.
            <div className="absolute bottom-full left-1/2 z-10 mb-1 w-64 max-w-[calc(100vw-2rem)] -translate-x-1/2 rounded-md border border-white/10 bg-dark-mode p-2 shadow-lg sm:top-full sm:right-0 sm:left-auto sm:bottom-auto sm:mt-1 sm:mb-0 sm:translate-x-0">
              <p className="mb-1 text-xs text-ultra-light-mode/50">also posted via:</p>
              {otherUrls.map((url) => (
                <a
                  key={url}
                  href={url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block truncate py-1 text-xs text-blue-400 hover:text-blue-300 hover:underline"
                >
                  {url}
                </a>
              ))}
            </div>
          )}
        </div>
      )}
    </>
  );
}

export default function JobTable({ jobs, fields }: JobTableProps): React.JSX.Element {
  // Most-recent-first by default -- "what's new" is what a reader coming
  // back to this page day-to-day actually wants to see first.
  const [sortKey, setSortKey] = useState<SortKey>("posted");
  const [sortDir, setSortDir] = useState<1 | -1>(-1);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [page, setPage] = useState(0);
  const { fieldLabels, subfieldLabels } = useMemo(() => fieldLabelMaps(fields), [fields]);

  // Rendering the full filtered set unconditionally (up to ~6,000 rows, each
  // now with its own logo image request) is what actually made changing a
  // filter feel slow -- a real page boundary (not an ever-growing "show
  // more" list) keeps the DOM bounded to one page's worth of rows no matter
  // how large the filtered set gets. Reset to page 1 whenever the filtered
  // set OR the sort changes -- a re-sort should show the new top results,
  // not leave you stranded on what's now an arbitrary slice.
  useEffect(() => {
    setPage(0);
  }, [jobs, sortKey, sortDir]);

  function toggleSort(key: SortKey): void {
    setSortDir((prevDir) => (key === sortKey ? ((-prevDir) as 1 | -1) : -1));
    setSortKey(key);
  }

  const sorted = [...jobs].sort((a, b) => {
    if (sortKey === "level") return (levelRank(a.level) - levelRank(b.level)) * sortDir;
    if (sortKey === "posted") {
      const ad = displayDate(a);
      const bd = displayDate(b);
      if (ad === bd) return 0;
      return ad > bd ? sortDir : -sortDir;
    }
    const av = a[sortKey];
    const bv = b[sortKey];
    if (av === bv) return 0;
    return av > bv ? sortDir : -sortDir;
  });
  const pageCount = Math.max(1, Math.ceil(sorted.length / PAGE_SIZE));
  const clampedPage = Math.min(page, pageCount - 1);
  const visible = sorted.slice(clampedPage * PAGE_SIZE, (clampedPage + 1) * PAGE_SIZE);

  return (
    <div>
      {/* Desktop/tablet: a real table reads better once there's room for
          columns to breathe. Below md a <table> either overflows or
          squishes every column unreadably, so mobile gets its own card
          layout instead of a horizontal scroll. */}
      <div className="hidden overflow-x-auto rounded-lg border border-white/10 md:block">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-white/10 text-ultra-light-mode/60">
              {COLUMNS.map((col) => (
                <th
                  key={col.key}
                  onClick={() => toggleSort(col.key)}
                  className={`cursor-pointer select-none px-4 py-3 font-jost font-medium hover:text-light-mode ${col.className ?? ""}`}
                >
                  {col.label}
                  {sortKey === col.key ? (sortDir === 1 ? " ▲" : " ▼") : ""}
                </th>
              ))}
              <th className="hidden px-4 py-3 font-jost font-medium lg:table-cell">Role</th>
              <th className="hidden px-4 py-3 font-jost font-medium md:table-cell">Salary</th>
              <th className="px-4 py-3 font-jost font-medium">Apply</th>
            </tr>
          </thead>
          <tbody>
            {visible.map((job) => {
              const posted = relativeDate(displayDate(job));
              return (
                <tr key={job.id} className="border-b border-white/5 hover:bg-white/5">
                  <td className="px-4 py-3">
                    {job.featured && (
                      <span title="Featured company" className="mr-1 text-status-warning">
                        ★
                      </span>
                    )}
                    {job.company}
                  </td>
                  <td className="px-4 py-3">{job.title}</td>
                  <td className="px-4 py-3 text-ultra-light-mode/80" title={job.location}>
                    {displayLocation(job)}
                  </td>
                  <td className="hidden px-4 py-3 text-ultra-light-mode/80 md:table-cell">
                    {job.level ? (LEVEL_LABELS[job.level] ?? job.level) : "—"}
                  </td>
                  <td className="px-4 py-3 text-ultra-light-mode/60" title={posted.title}>
                    {posted.label}
                  </td>
                  <td className="hidden px-4 py-3 text-ultra-light-mode/80 lg:table-cell">{roleLabel(job, fieldLabels, subfieldLabels)}</td>
                  <td className="hidden px-4 py-3 tabular-nums text-ultra-light-mode/80 md:table-cell">
                    {formatSalary(job.salary_min, job.salary_max)}
                  </td>
                  <td className="px-4 py-3">
                    <ApplyCell
                      job={job}
                      expanded={expandedId === job.id}
                      onToggleExpanded={() => setExpandedId((cur) => (cur === job.id ? null : job.id))}
                    />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="flex flex-col gap-3 md:hidden">
        {visible.map((job) => {
          const posted = relativeDate(displayDate(job));
          return (
            <div key={job.id} className="rounded-lg border border-white/10 p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="truncate font-jost text-base font-medium text-light-mode">
                    {job.featured && (
                      <span title="Featured company" className="mr-1 text-status-warning">
                        ★
                      </span>
                    )}
                    {job.company}
                  </p>
                  <p className="mt-0.5 truncate text-sm text-ultra-light-mode/80">{job.title}</p>
                </div>
                <span className="shrink-0 text-xs text-ultra-light-mode/50" title={posted.title}>
                  {posted.label}
                </span>
              </div>
              {/* Unlike the table's fixed columns, a card has no alignment
                  to preserve -- a bare "—" placeholder for missing level/
                  salary/role reads as clutter here rather than structure,
                  so those chips just don't render at all when there's
                  nothing to say. */}
              <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-xs text-ultra-light-mode/60">
                <span title={job.location}>{displayLocation(job)}</span>
                {job.level && <span>{LEVEL_LABELS[job.level] ?? job.level}</span>}
                {(job.salary_min != null || job.salary_max != null) && (
                  <span className="tabular-nums">{formatSalary(job.salary_min, job.salary_max)}</span>
                )}
              </div>
              {(job.matched_fields.length > 0 || job.matched_subfields.length > 0) && (
                <p className="mt-1 truncate text-xs text-ultra-light-mode/50">
                  {roleLabel(job, fieldLabels, subfieldLabels)}
                </p>
              )}
              <div className="mt-3 text-sm">
                <ApplyCell
                  job={job}
                  expanded={expandedId === job.id}
                  onToggleExpanded={() => setExpandedId((cur) => (cur === job.id ? null : job.id))}
                />
              </div>
            </div>
          );
        })}
      </div>

      {sorted.length === 0 && (
        <p className="px-4 py-6 text-center text-ultra-light-mode/50">no roles match that filter</p>
      )}
      {sorted.length > 0 && (
        <div className="mt-3 flex items-center justify-center gap-3 border-t border-white/10 pt-3 text-sm">
          <button
            type="button"
            onClick={() => setPage((n) => Math.max(0, n - 1))}
            disabled={clampedPage === 0}
            className="rounded-md border border-white/10 px-3 py-1.5 text-ultra-light-mode/70 hover:border-accent/40 hover:text-light-mode disabled:cursor-not-allowed disabled:opacity-30 disabled:hover:border-white/10 disabled:hover:text-ultra-light-mode/70"
          >
            ← Prev
          </button>
          <span className="text-ultra-light-mode/50">
            Page {clampedPage + 1} of {pageCount}
          </span>
          <button
            type="button"
            onClick={() => setPage((n) => Math.min(pageCount - 1, n + 1))}
            disabled={clampedPage >= pageCount - 1}
            className="rounded-md border border-white/10 px-3 py-1.5 text-ultra-light-mode/70 hover:border-accent/40 hover:text-light-mode disabled:cursor-not-allowed disabled:opacity-30 disabled:hover:border-white/10 disabled:hover:text-ultra-light-mode/70"
          >
            Next →
          </button>
        </div>
      )}
    </div>
  );
}
