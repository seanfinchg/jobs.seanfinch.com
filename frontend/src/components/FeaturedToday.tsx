import { useMemo } from "react";
import type { Job } from "@/types";

interface FeaturedTodayProps {
  jobs: Job[];
}

interface Spotlight {
  company: string;
  day: number;
  count: number;
  featured: boolean;
}

// Whole-day difference in UTC, so "today" lines up with how the rest of the
// dashboard (and the backend's own exports) treats dates -- not the
// viewer's local midnight.
function dayDiff(dateStr: string, now: Date): number {
  const d = new Date(dateStr);
  const startOfDayUTC = (x: Date) => Date.UTC(x.getUTCFullYear(), x.getUTCMonth(), x.getUTCDate());
  return Math.round((startOfDayUTC(now) - startOfDayUTC(d)) / 86_400_000);
}

function dayLabel(day: number): string {
  if (day === 0) return "today";
  if (day === 1) return "yesterday";
  return `${day}d ago`;
}

// Below this many entries a wrapped chip row already fits without visual
// clutter -- scrolling only earns its keep once there's enough content that
// a static row would wrap several lines or run off the container.
const MARQUEE_THRESHOLD = 7;

// "Today" (and the rest of the 7-day window) is evaluated against whenever
// the viewer loads the page, not baked into the static export -- computed
// client-side on purpose so a dashboard viewed hours after the last ingest
// run still reads correctly.
export default function FeaturedToday({ jobs }: FeaturedTodayProps): React.JSX.Element | null {
  const spotlights = useMemo(() => {
    const now = new Date();
    const byCompanyDay = new Map<string, Spotlight>();
    for (const job of jobs) {
      const day = dayDiff(job.posted_at ?? job.first_seen, now);
      if (day < 0 || day > 6) continue;
      const key = `${job.company}__${day}`;
      const existing = byCompanyDay.get(key);
      if (existing) {
        existing.count += 1;
        existing.featured = existing.featured || job.featured;
      } else {
        byCompanyDay.set(key, { company: job.company, day, count: 1, featured: job.featured });
      }
    }
    // Today first, then working back a day at a time; alphabetical within
    // a day so the order doesn't reshuffle as counts change underneath it.
    return [...byCompanyDay.values()].sort((a, b) => a.day - b.day || a.company.localeCompare(b.company));
  }, [jobs]);

  if (spotlights.length === 0) return null;

  const useMarquee = spotlights.length > MARQUEE_THRESHOLD;

  // Featured companies get their own color, not just a small star -- a
  // star alone was too subtle to notice while the row is mid-scroll, and
  // this ticker otherwise mixes featured and non-featured companies in the
  // same green pill with nothing to tell them apart at a glance.
  const chip = (s: Spotlight, key: string) => (
    <span
      key={key}
      className={`inline-flex shrink-0 items-center gap-1 rounded-full border px-3 py-1 text-sm whitespace-nowrap ${
        s.featured
          ? "border-status-warning/40 bg-status-warning/10 text-status-warning"
          : "border-status-good/40 bg-status-good/10 text-status-good"
      }`}
    >
      {s.featured && <span title="Top company">★</span>}
      {s.company} dropped {s.count} new role{s.count === 1 ? "" : "s"} {dayLabel(s.day)}
    </span>
  );

  if (!useMarquee) {
    return (
      <div className="mb-6 flex flex-wrap gap-2">
        {spotlights.map((s) => chip(s, `${s.company}-${s.day}`))}
      </div>
    );
  }

  return (
    <div className="group relative mb-6 overflow-hidden rounded-lg border border-white/10 py-3">
      {/* Content is duplicated once so the track can translate exactly
          -50% and loop seamlessly -- the animation pauses on hover via
          group-hover so a reader can actually catch a chip mid-scroll. */}
      <div
        className="flex w-max gap-2 px-3 animate-marquee group-hover:[animation-play-state:paused]"
        style={{ animationDuration: `${Math.max(20, spotlights.length * 4)}s` }}
      >
        {spotlights.map((s) => chip(s, `a-${s.company}-${s.day}`))}
        {spotlights.map((s) => chip(s, `b-${s.company}-${s.day}`))}
      </div>
    </div>
  );
}
