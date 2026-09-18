import { useMemo } from "react";
import type { Job } from "@/types";

interface CompanyTrackerProps {
  jobs: Job[];
  selectedCompany: string;
  onSelectCompany: (company: string) => void;
}

interface CompanyStat {
  company: string;
  count: number;
  lastDrop: string;
}

function relativeDay(iso: string): string {
  const days = Math.floor((Date.now() - new Date(iso).getTime()) / 86_400_000);
  if (days <= 0) return "today";
  if (days === 1) return "yesterday";
  return `${days}d ago`;
}

// A count with no time bound at all reads as "to infinity" once a company
// has enough standing open reqs -- e.g. a company sitting on 100+
// permanently-open roles would show the same enormous number forever,
// which tells a reader nothing about *recent* activity. Bounding to the
// current calendar year keeps this a "this application cycle" signal
// instead of an unbounded all-time tally.
function isThisYear(iso: string): boolean {
  return new Date(iso).getUTCFullYear() === new Date().getUTCFullYear();
}

// Only covers featured companies that currently have at least one open
// role in the exported data -- closed/skipped jobs never leave the export
// (see dashboard.export_data()), so a featured company with zero current
// postings has no history to show here, not a "quiet" status to report.
export default function CompanyTracker({
  jobs,
  selectedCompany,
  onSelectCompany,
}: CompanyTrackerProps): React.JSX.Element | null {
  const stats = useMemo(() => {
    const byCompany = new Map<string, CompanyStat>();
    for (const job of jobs) {
      if (!job.featured) continue;
      const date = job.posted_at ?? job.first_seen;
      if (!isThisYear(date)) continue;
      const existing = byCompany.get(job.company);
      if (existing) {
        existing.count += 1;
        if (date > existing.lastDrop) existing.lastDrop = date;
      } else {
        byCompany.set(job.company, { company: job.company, count: 1, lastDrop: date });
      }
    }
    return [...byCompany.values()].sort((a, b) => (a.lastDrop < b.lastDrop ? 1 : -1));
  }, [jobs]);

  if (stats.length === 0) return null;

  return (
    <aside className="w-full shrink-0 rounded-lg border border-white/10 p-4 lg:w-64">
      <h2 className="mb-1 font-jost text-sm font-semibold text-light-mode">Top company tracker</h2>
      <p className="mb-3 text-xs text-ultra-light-mode/40">Roles posted this year</p>
      <ul className="flex flex-col gap-1">
        {stats.map((s) => {
          const active = selectedCompany === s.company;
          return (
            <li key={s.company}>
              <button
                type="button"
                onClick={() => onSelectCompany(s.company)}
                title={active ? `Clear the ${s.company} filter` : `Filter the table to ${s.company}`}
                className={`flex w-full items-center justify-between gap-3 rounded px-1 py-2 text-left text-sm hover:bg-white/5 sm:py-1 ${
                  active ? "bg-accent/10" : ""
                }`}
              >
                <span
                  className={`truncate hover:text-accent hover:underline ${
                    active ? "text-accent" : "text-ultra-light-mode/80"
                  }`}
                >
                  <span className="mr-1 text-status-warning">★</span>
                  {s.company}
                </span>
                <span className="shrink-0 text-right text-xs text-ultra-light-mode/50">
                  {s.count} · {relativeDay(s.lastDrop)}
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </aside>
  );
}
