import { useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import type { FieldMeta, Job } from "@/types";
import StatsBar from "@/components/StatsBar";
import FilterBar from "@/components/FilterBar";
import JobTable from "@/components/JobTable";
import FeaturedToday from "@/components/FeaturedToday";
import ExternalSearchLinks from "@/components/ExternalSearchLinks";
import CompanyTracker from "@/components/CompanyTracker";
import DisciplinePicker from "@/components/DisciplinePicker";
import RolePicker from "@/components/RolePicker";
import { buildLocationTree, locationTagsFor } from "@/lib/location";
import { relativeDate } from "@/lib/date";

// Onboarding is two screens, not one: pick a top-level discipline, then a
// role within it. Both persist to localStorage independently so a returning
// visitor skips straight to the results page; "Change discipline" clears
// both and starts over. "everything"/"__all__" are explicit opt-outs (a
// multi-discipline viewer's "see everything" shouldn't have to survive a
// fight with the picker), not the same as "never asked" (null/absent).
const DISCIPLINE_KEY = "jobfinder:discipline";
const ROLE_KEY = "jobfinder:role";
const EVERYTHING = "everything";
const ALL_ROLES = "__all__";

// Fixed, small top-level buckets -- deliberately NOT the full fields.json
// list (that's the role-picker page, scoped to whichever of these three get
// picked here). "cs" is a synthetic bucket, not a real profiles/fields/
// slug -- see disciplineFieldSlugs().
const DISCIPLINES = [
  { key: "cs", label: "Computer Science" },
  { key: "finance", label: "Finance" },
  { key: "mechanical-engineering", label: "Mechanical Engineering" },
];

// Same 3 buckets as the onboarding pages, plus the "see everything" option
// as a real fourth choice -- used by FilterBar's Discipline section, which
// (unlike the onboarding pages) needs an explicit way to get back to
// "everything" without leaving the results page.
const DISCIPLINE_FILTER_OPTIONS = [...DISCIPLINES, { key: EVERYTHING, label: "Everything" }];

// Which field slugs belong to a top-level discipline bucket. "cs" is
// everything that isn't finance or mechanical-engineering, computed from
// whatever fields.json actually has -- not a hardcoded list -- so a new
// CS-adjacent profiles/fields/<name>.yaml shows up under "cs" automatically,
// same extensibility principle as the rest of the fields system.
function disciplineFieldSlugs(discipline: string | null, fields: FieldMeta[]): string[] {
  if (discipline === null || discipline === EVERYTHING) return fields.map((f) => f.slug);
  if (discipline === "finance" || discipline === "mechanical-engineering") return [discipline];
  return fields.filter((f) => f.slug !== "finance" && f.slug !== "mechanical-engineering").map((f) => f.slug);
}

// The role-picker page's options for a given discipline: if it spans several
// distinct fields (cs), each field itself is a role choice; if it's a single
// field (finance, mechanical-engineering), that field's own subfields are
// the meaningful next narrowing step instead (picking the one field it
// already implicitly is would be a no-op page).
function roleOptionsFor(discipline: string, fields: FieldMeta[]): { value: string; label: string }[] {
  const slugs = disciplineFieldSlugs(discipline, fields);
  const disciplineFields = fields.filter((f) => slugs.includes(f.slug));
  const onlyField = disciplineFields.length === 1 ? disciplineFields[0] : undefined;
  if (onlyField) {
    return onlyField.subfields.map((sf) => ({ value: sf.tag, label: sf.label }));
  }
  return disciplineFields.map((f) => ({ value: f.slug, label: f.label }));
}

// Every filter dimension the table applies. Kept as a set of independently
// skippable checks (rather than one inline predicate per consumer) so
// "how many jobs would match if I only changed this one filter" -- the Role/
// Level facet counts and the company tracker's "ignore search" behavior --
// can reuse the exact same matching logic the main table uses, instead of a
// second hand-maintained copy that drifts out of sync with it.
type FilterDim = "locationTags" | "roles" | "levels" | "gradYears" | "search" | "top" | "salary" | "defense";

interface FilterState {
  search: string;
  locationTags: string[];
  roles: string[];
  levels: string[];
  gradYears: string[];
  topOnly: boolean;
  salaryMin: number | null;
  hideDefense: boolean;
}

// Only new-grad/intern postings ever carry a meaningful grad year -- a
// senior posting has no such concept, so it should stay visible no matter
// what the grad-year facet is set to rather than getting swept into an
// "unspecified" bucket alongside entry-level postings that genuinely never
// stated one.
function isEntryLevel(job: Job): boolean {
  return job.level === "new-grad" || job.level === "intern";
}

function gradYearBucket(job: Job): string {
  return job.grad_year != null ? String(job.grad_year) : "unspecified";
}

function makeMatcher(state: FilterState) {
  const q = state.search.trim().toLowerCase();
  return (job: Job, skip?: FilterDim): boolean => {
    if (
      skip !== "locationTags" &&
      state.locationTags.length > 0 &&
      !locationTagsFor(job.location).some((tag) => state.locationTags.includes(tag))
    ) {
      return false;
    }
    if (
      skip !== "roles" &&
      state.roles.length > 0 &&
      !state.roles.some((r) => job.matched_fields.includes(r) || job.matched_subfields.includes(r))
    ) {
      return false;
    }
    if (skip !== "levels" && state.levels.length > 0 && !(job.level && state.levels.includes(job.level))) {
      return false;
    }
    if (skip !== "gradYears" && state.gradYears.length > 0 && isEntryLevel(job)) {
      if (!state.gradYears.includes(gradYearBucket(job))) return false;
    }
    if (skip !== "top" && state.topOnly && !job.featured) return false;
    if (skip !== "defense" && state.hideDefense && job.defense) return false;
    if (skip !== "salary" && state.salaryMin != null) {
      // A job's stated minimum is the conservative reading of "does this
      // pay at least $X" -- fall back to salary_max only when no minimum
      // was posted at all. Jobs with no salary data either way can't be
      // confirmed to clear the bar, so they drop out while this is active.
      const floor = job.salary_min ?? job.salary_max;
      if (floor == null || floor < state.salaryMin) return false;
    }
    if (
      skip !== "search" &&
      q &&
      ![job.company, job.title, job.location].some((field) => field.toLowerCase().includes(q))
    ) {
      return false;
    }
    return true;
  };
}

export default function App(): React.JSX.Element {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [fields, setFields] = useState<FieldMeta[]>([]);
  const [search, setSearch] = useState("");
  const [locationTags, setLocationTags] = useState<string[]>([]);
  const [roles, setRoles] = useState<string[]>([]);
  const [levels, setLevels] = useState<string[]>([]);
  const [gradYears, setGradYears] = useState<string[]>([]);
  const [topOnly, setTopOnly] = useState(false);
  const [salaryMin, setSalaryMin] = useState<number | null>(null);
  const [hideDefense, setHideDefense] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [generatedAt, setGeneratedAt] = useState<string | null>(null);
  // The filter rail is a permanent left column at lg+, but on a phone it
  // would otherwise sit between the stats bar and the job list, burying
  // every result under six facets' worth of scrolling before the first
  // card appears. Below lg it's a hidden-by-default full-screen sheet
  // instead, opened from a single "Filters" button.
  const [mobileFiltersOpen, setMobileFiltersOpen] = useState(false);
  const [discipline, setDiscipline] = useState<string | null>(() =>
    typeof window === "undefined" ? EVERYTHING : window.localStorage.getItem(DISCIPLINE_KEY),
  );
  const [roleChoice, setRoleChoice] = useState<string | null>(() =>
    typeof window === "undefined" ? ALL_ROLES : window.localStorage.getItem(ROLE_KEY),
  );

  function chooseDiscipline(key: string): void {
    window.localStorage.setItem(DISCIPLINE_KEY, key);
    window.localStorage.removeItem(ROLE_KEY);
    setDiscipline(key);
    setRoleChoice(null);
    if (key === EVERYTHING) {
      window.localStorage.setItem(ROLE_KEY, ALL_ROLES);
      setRoleChoice(ALL_ROLES);
      setRoles([]);
    }
  }

  // The onboarding pages (DisciplinePicker/RolePicker) are a one-time,
  // first-launch flourish, not the only way to change this -- discipline is
  // a real filter like Location/Role/Level, so switching it later from the
  // filter menu goes straight to "all roles in this discipline" rather than
  // re-running the two-step onboarding interstitial.
  function setDisciplineFilter(key: string): void {
    window.localStorage.setItem(DISCIPLINE_KEY, key);
    window.localStorage.setItem(ROLE_KEY, ALL_ROLES);
    setDiscipline(key);
    setRoleChoice(ALL_ROLES);
    setRoles([]);
  }

  function chooseRole(value: string | null): void {
    const stored = value ?? ALL_ROLES;
    window.localStorage.setItem(ROLE_KEY, stored);
    setRoleChoice(stored);
    setRoles(value ? [value] : []);
  }

  function changeDiscipline(): void {
    window.localStorage.removeItem(DISCIPLINE_KEY);
    window.localStorage.removeItem(ROLE_KEY);
    setDiscipline(null);
    setRoleChoice(null);
    setRoles([]);
  }

  useEffect(() => {
    fetch("data.json")
      .then((res) => {
        if (!res.ok) throw new Error(`data.json ${res.status}`);
        return res.json() as Promise<Job[]>;
      })
      .then(setJobs)
      .catch((err: unknown) => setError(err instanceof Error ? err.message : String(err)));

    // meta.json is a nice-to-have (when the pipeline last actually ran, as
    // opposed to StatsBar's "newest match" which only reflects the newest
    // *job*, not the run itself -- a healthy run that finds nothing new
    // would look identical to a stalled one without this) -- its absence or
    // failure shouldn't surface as a page-level error the way data.json's
    // would, since the dashboard is fully usable without it.
    fetch("meta.json")
      .then((res) => (res.ok ? (res.json() as Promise<{ generated_at: string }>) : null))
      .then((meta) => setGeneratedAt(meta?.generated_at ?? null))
      .catch(() => setGeneratedAt(null));

    // fields.json carries each field's display label and subfields (see
    // jobfinder.dashboard._load_fields_metadata()) -- same "absence isn't a
    // page-level error" treatment as meta.json, since the Role filter just
    // falls back to raw slugs rather than the whole page failing.
    fetch("fields.json")
      .then((res) => (res.ok ? (res.json() as Promise<FieldMeta[]>) : []))
      .then(setFields)
      .catch(() => setFields([]));
  }, []);

  // The discipline gate: a hard pre-filter, not one of the skippable
  // FilterDim checks below -- nothing needs to see counts "as if discipline
  // weren't set" the way Role/Level facet counts do, so it doesn't need the
  // skip machinery, just narrows the pool everything else operates on.
  const disciplineSlugs = useMemo(() => disciplineFieldSlugs(discipline, fields), [discipline, fields]);
  const disciplineJobs = useMemo(
    () => jobs.filter((job) => job.matched_fields.some((f) => disciplineSlugs.includes(f))),
    [jobs, disciplineSlugs],
  );
  const scopedFields = useMemo(
    () => fields.filter((f) => disciplineSlugs.includes(f.slug)),
    [fields, disciplineSlugs],
  );

  const matches = useMemo(
    () => makeMatcher({ search, locationTags, roles, levels, gradYears, topOnly, salaryMin, hideDefense }),
    [search, locationTags, roles, levels, gradYears, topOnly, salaryMin, hideDefense],
  );

  const filtered = useMemo(() => disciplineJobs.filter((job) => matches(job)), [disciplineJobs, matches]);

  // The company tracker's whole job is to let you pick a company by
  // clicking it, which sets `search` -- so it has to ignore the search
  // filter itself (otherwise selecting a company would immediately shrink
  // the list down to just that one company). Every other active filter
  // (role, level, location, salary, top-companies-only) still narrows it,
  // which is the actual "filters affect each other" fix.
  const companyTrackerJobs = useMemo(
    () => disciplineJobs.filter((job) => matches(job, "search")),
    [disciplineJobs, matches],
  );

  // Facet counts: "if I only changed this one dropdown, how many jobs would
  // match", i.e. every *other* active filter still applies. Without this,
  // the Role/Level dropdowns show options as if no other filter were set,
  // which is exactly the "filters don't affect each other" complaint.
  const roleCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const job of disciplineJobs) {
      if (!matches(job, "roles")) continue;
      for (const tag of [...job.matched_fields, ...job.matched_subfields]) {
        counts[tag] = (counts[tag] ?? 0) + 1;
      }
    }
    return counts;
  }, [disciplineJobs, matches]);

  const levelCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const job of disciplineJobs) {
      if (!matches(job, "levels")) continue;
      if (job.level) counts[job.level] = (counts[job.level] ?? 0) + 1;
    }
    return counts;
  }, [disciplineJobs, matches]);

  // Distinct grad years actually present in the loaded new-grad/intern
  // postings, sorted ascending, with an explicit "unspecified" bucket
  // appended last -- built from real data rather than a hardcoded year
  // range, so next year's postings show up with zero frontend changes.
  const gradYearOptions = useMemo(() => {
    const years = new Set<number>();
    for (const job of disciplineJobs) {
      if (isEntryLevel(job) && job.grad_year != null) years.add(job.grad_year);
    }
    return [
      ...[...years].sort((a, b) => a - b).map((year) => ({ value: String(year), label: String(year) })),
      { value: "unspecified", label: "Year not specified" },
    ];
  }, [disciplineJobs]);

  const gradYearCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const job of disciplineJobs) {
      if (!isEntryLevel(job) || !matches(job, "gradYears")) continue;
      const bucket = gradYearBucket(job);
      counts[bucket] = (counts[bucket] ?? 0) + 1;
    }
    return counts;
  }, [disciplineJobs, matches]);

  const locationTagCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const job of disciplineJobs) {
      if (!matches(job, "locationTags")) continue;
      for (const tag of locationTagsFor(job.location)) {
        counts[tag] = (counts[tag] ?? 0) + 1;
      }
    }
    return counts;
  }, [disciplineJobs, matches]);

  // The Country -> State -> City shape itself is static (independent of
  // the active filters, same split as roleCounts/roleOptions above) --
  // only the per-node counts should react to other filters narrowing the
  // list, not the tree's own branches disappearing and reappearing.
  const locationTree = useMemo(() => buildLocationTree(disciplineJobs.map((j) => j.location)), [disciplineJobs]);

  // Same "how many facets are actively narrowing the list" idea as the
  // per-option counts above, just totaled -- drives the badge on the
  // mobile Filters button so it's obvious at a glance whether anything's
  // set without having to open the sheet to check.
  const activeFilterCount =
    locationTags.length +
    roles.length +
    levels.length +
    gradYears.length +
    (topOnly ? 1 : 0) +
    (salaryMin != null ? 1 : 0) +
    (hideDefense ? 1 : 0);

  // Background scroll fights the sheet's own scroll on iOS Safari
  // otherwise -- a real bottom-sheet/full-screen filter panel needs the
  // page underneath frozen while it's open.
  useEffect(() => {
    if (!mobileFiltersOpen) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [mobileFiltersOpen]);

  if (discipline === null) {
    return <DisciplinePicker options={DISCIPLINES} onSelect={chooseDiscipline} onSelectEverything={() => chooseDiscipline(EVERYTHING)} />;
  }

  if (discipline !== EVERYTHING && roleChoice === null) {
    const disciplineLabel = DISCIPLINES.find((d) => d.key === discipline)?.label ?? discipline;
    return (
      <RolePicker
        disciplineLabel={disciplineLabel}
        options={roleOptionsFor(discipline, fields)}
        onSelect={chooseRole}
        onSelectAll={() => chooseRole(null)}
      />
    );
  }

  return (
    <div className="min-h-screen bg-ultra-dark-mode px-4 py-6 font-raleway text-ultra-light-mode sm:px-10 sm:py-10">
      <div className="mx-auto max-w-6xl animate-fade-up lg:max-w-352 2xl:max-w-400">
        <header className="mb-5 border-b border-white/10 pb-4 sm:mb-8 sm:pb-6">
          <h1 className="font-jost text-2xl font-semibold text-light-mode sm:text-3xl">
            <a href="https://seanfinch.com" className="hover:text-accent">
              Sean Finch
            </a>{" "}
            — Job Search
          </h1>
          <p className="mt-1 text-sm text-ultra-light-mode/50">
            Open roles, updated daily.
            {generatedAt && (
              <span title={relativeDate(generatedAt).title}> Jobs last updated: {relativeDate(generatedAt).label}.</span>
            )}
            {" · "}
            <button
              type="button"
              onClick={changeDiscipline}
              className="underline underline-offset-4 hover:text-light-mode"
            >
              Change discipline
            </button>
          </p>
        </header>

        {error && (
          <p className="mb-6 rounded-md border border-status-critical/40 bg-status-critical/10 px-4 py-3 text-status-critical">
            couldn't load data.json: {error}
          </p>
        )}

        <div className="relative mb-4 w-full max-w-md sm:mb-6">
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by company, title, or location"
            className="w-full rounded-md border border-white/10 bg-dark-mode px-3 py-2.5 pr-8 text-base
                       text-ultra-light-mode placeholder:text-ultra-light-mode/40
                       focus:border-accent/50 focus:outline-none sm:py-2 sm:text-sm"
          />
          <button
            type="button"
            onClick={() => setSearch("")}
            aria-label="Clear search"
            tabIndex={search ? 0 : -1}
            className={`absolute inset-y-0 right-2 text-ultra-light-mode/40 transition-opacity hover:text-light-mode ${
              search ? "opacity-100" : "pointer-events-none opacity-0"
            }`}
          >
            ×
          </button>
        </div>

        <div className="mb-4 sm:mb-6">
          <StatsBar jobs={filtered} />
        </div>

        <FeaturedToday jobs={filtered} />

        {/* The Filters button + sheet only exist below lg -- see
            mobileFiltersOpen above. Putting the results first and gating
            filters behind one tap is the actual mobile-first fix: at lg+
            nothing here renders (the permanent sidebar below takes over)
            so desktop is untouched. */}
        <div className="mb-4 lg:hidden">
          <button
            type="button"
            onClick={() => setMobileFiltersOpen(true)}
            className="flex w-full items-center justify-center gap-2 rounded-md border border-white/10 bg-dark-mode px-4 py-3 text-sm font-medium text-ultra-light-mode/80 hover:text-light-mode"
          >
            <span aria-hidden>☰</span>
            Filters
            {activeFilterCount > 0 && (
              <span className="rounded-full bg-accent/20 px-2 py-0.5 text-xs font-semibold text-accent">
                {activeFilterCount}
              </span>
            )}
          </button>
        </div>

        {mobileFiltersOpen && createPortal(
          // Rendered via a portal straight into document.body -- the page
          // root has its own permanent transform (see index.css's fade-up
          // animation, `animation: ... both` keeps `transform: translateY(0)`
          // applied forever after it finishes), and any non-`none` transform
          // on an ancestor hijacks the containing block for `position:
          // fixed` descendants. Nested inside that root, `fixed inset-0`
          // here would resolve against the root's own (shorter, non-viewport)
          // box instead of the real viewport -- which is exactly what broke
          // scrolling inside this sheet. A portal escapes that ancestor
          // chain entirely, the same fix already applied to the apply-links
          // popover for the same underlying reason.
          <div className="fixed inset-0 z-30 flex flex-col bg-ultra-dark-mode lg:hidden">
            <div className="flex shrink-0 items-center justify-between border-b border-white/10 px-4 py-3">
              <h2 className="font-jost text-base font-semibold text-light-mode">Filters</h2>
              <button
                type="button"
                onClick={() => setMobileFiltersOpen(false)}
                className="rounded-md px-3 py-2 text-sm text-ultra-light-mode/70 hover:text-light-mode"
              >
                Done
              </button>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
              <FilterBar
                showHeading={false}
                fields={scopedFields}
                discipline={discipline}
                disciplineOptions={DISCIPLINE_FILTER_OPTIONS}
                onDisciplineChange={setDisciplineFilter}
                roleFilterDisabled={discipline === null}
                locationTags={locationTags}
                onLocationTagsChange={setLocationTags}
                locationTree={locationTree}
                locationTagCounts={locationTagCounts}
                roles={roles}
                onRolesChange={setRoles}
                roleCounts={roleCounts}
                levels={levels}
                onLevelsChange={setLevels}
                levelCounts={levelCounts}
                gradYearOptions={gradYearOptions}
                gradYears={gradYears}
                onGradYearsChange={setGradYears}
                gradYearCounts={gradYearCounts}
                topOnly={topOnly}
                onTopOnlyChange={setTopOnly}
                salaryMin={salaryMin}
                onSalaryMinChange={setSalaryMin}
                hideDefense={hideDefense}
                onHideDefenseChange={setHideDefense}
              />
            </div>
            <div className="shrink-0 border-t border-white/10 px-4 py-3">
              <button
                type="button"
                onClick={() => setMobileFiltersOpen(false)}
                className="w-full rounded-md bg-accent px-4 py-3 text-sm font-semibold text-ultra-dark-mode"
              >
                Show {filtered.length} result{filtered.length === 1 ? "" : "s"}
              </button>
            </div>
          </div>,
          document.body,
        )}

        {/* Amazon-style refinement rail: filters live in their own column
            on the left, results in the middle, the company tracker on the
            right -- lg+ only (see the mobile Filters button/sheet above
            for below-lg, where there's no room for three columns). */}
        <div className="flex flex-col gap-6 lg:flex-row lg:items-start">
          <aside className="hidden shrink-0 lg:block lg:w-56">
            <FilterBar
              fields={scopedFields}
              discipline={discipline}
              disciplineOptions={DISCIPLINE_FILTER_OPTIONS}
              onDisciplineChange={setDisciplineFilter}
              roleFilterDisabled={discipline === null}
              locationTags={locationTags}
              onLocationTagsChange={setLocationTags}
              locationTree={locationTree}
              locationTagCounts={locationTagCounts}
              roles={roles}
              onRolesChange={setRoles}
              roleCounts={roleCounts}
              levels={levels}
              onLevelsChange={setLevels}
              levelCounts={levelCounts}
              gradYearOptions={gradYearOptions}
              gradYears={gradYears}
              onGradYearsChange={setGradYears}
              gradYearCounts={gradYearCounts}
              topOnly={topOnly}
              onTopOnlyChange={setTopOnly}
              salaryMin={salaryMin}
              onSalaryMinChange={setSalaryMin}
              hideDefense={hideDefense}
              onHideDefenseChange={setHideDefense}
            />
          </aside>

          <div className="min-w-0 flex-1">
            <JobTable jobs={filtered} fields={fields} />

            <div className="mt-6">
              <ExternalSearchLinks roles={roles} levels={levels} />
            </div>
          </div>

          <CompanyTracker
            jobs={companyTrackerJobs}
            selectedCompany={search}
            onSelectCompany={(company) => setSearch((cur) => (cur === company ? "" : company))}
          />
        </div>
      </div>
    </div>
  );
}
