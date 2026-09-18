import { useMemo } from "react";
import { LEVEL_LABELS, LEVEL_ORDER } from "@/types";
import type { FieldMeta } from "@/types";
import type { LocationTreeNode } from "@/lib/location";
import MultiSelectDropdown from "@/components/MultiSelectDropdown";
import LocationTreeFilter from "@/components/LocationTreeFilter";

interface FilterBarProps {
  fields: FieldMeta[];
  locationTags: string[];
  onLocationTagsChange: (value: string[]) => void;
  locationTree: LocationTreeNode[];
  locationTagCounts: Record<string, number>;
  roles: string[];
  onRolesChange: (value: string[]) => void;
  roleCounts: Record<string, number>;
  levels: string[];
  onLevelsChange: (value: string[]) => void;
  levelCounts: Record<string, number>;
  gradYearOptions: { value: string; label: string }[];
  gradYears: string[];
  onGradYearsChange: (value: string[]) => void;
  gradYearCounts: Record<string, number>;
  topOnly: boolean;
  onTopOnlyChange: (value: boolean) => void;
  salaryMin: number | null;
  onSalaryMinChange: (value: number | null) => void;
  hideDefense: boolean;
  onHideDefenseChange: (value: boolean) => void;
  // The onboarding pages (DisciplinePicker/RolePicker) are only a first-
  // launch flourish -- discipline itself is a real, ongoing filter just
  // like Role/Level, so it needs to be changeable from right here too, not
  // just via the header's "Change discipline" link (which re-runs the
  // whole two-step onboarding flow).
  discipline: string | null;
  disciplineOptions: { key: string; label: string }[];
  onDisciplineChange: (key: string) => void;
  // Grayed out until a discipline is picked on the onboarding screens --
  // `fields` here is already scoped to the current discipline (see App.tsx),
  // so this just covers the moment (shouldn't normally be reachable, but
  // defend it anyway) where there isn't one yet.
  roleFilterDisabled?: boolean;
  // The desktop sidebar has nothing above it, so it needs its own "Filters"
  // label for context. The mobile sheet (see App.tsx) already has that in
  // its own header bar -- a second "Filters" heading right underneath it
  // would just be a duplicate.
  showHeading?: boolean;
}

// Fields with sub-tags get a group header (itself checkable -- selects the
// broad field, see MultiSelectDropdown's groupValues) plus each specific
// sub-tag nested under it; fields without sub-tags (qa) render as a single
// plain, ungrouped option. Built from fields.json (see App.tsx), not a
// hardcoded label table -- a new profiles/fields/<name>.yaml with a label:
// shows up here with no frontend edit.
function roleOptions(fields: FieldMeta[]): { value: string; label: string; group?: string }[] {
  return fields.flatMap((field) => {
    if (field.subfields.length === 0) return [{ value: field.slug, label: field.label }];
    return field.subfields.map((sub) => ({ value: sub.tag, label: sub.label, group: field.label }));
  });
}
function roleGroupValues(fields: FieldMeta[]): Record<string, string> {
  return Object.fromEntries(
    fields.filter((field) => field.subfields.length > 0).map((field) => [field.label, field.slug]),
  );
}
const LEVEL_OPTIONS = LEVEL_ORDER.map((value) => ({ value, label: LEVEL_LABELS[value] ?? value }));

function FilterSection({ title, children }: { title: string; children: React.ReactNode }): React.JSX.Element {
  return (
    <div className="flex flex-col gap-1.5">
      <h3 className="text-xs font-semibold tracking-wide text-ultra-light-mode/50 uppercase">{title}</h3>
      {children}
    </div>
  );
}

// A left-hand refinement rail (Location/Role/Level/Salary/toggles), each
// facet its own dropdown so a large option list (Location alone can carry
// 500+ entries -- see lib/location.ts) stays out of the way until opened,
// with a search box inside it once it's too long to scan (see
// MultiSelectDropdown). Free-text search across company/title/location
// lives at the top of the page instead of in here -- that's a live filter
// on every keystroke, not a facet you pick values from.
export default function FilterBar({
  fields,
  locationTags,
  onLocationTagsChange,
  locationTree,
  locationTagCounts,
  roles,
  onRolesChange,
  roleCounts,
  levels,
  onLevelsChange,
  levelCounts,
  gradYearOptions,
  gradYears,
  onGradYearsChange,
  gradYearCounts,
  topOnly,
  onTopOnlyChange,
  salaryMin,
  onSalaryMinChange,
  hideDefense,
  onHideDefenseChange,
  discipline,
  disciplineOptions,
  onDisciplineChange,
  roleFilterDisabled = false,
  showHeading = true,
}: FilterBarProps): React.JSX.Element {
  const roleOpts = useMemo(() => roleOptions(fields), [fields]);
  const roleGroups = useMemo(() => roleGroupValues(fields), [fields]);

  return (
    <div className="flex w-full flex-col gap-5">
      {showHeading && <h2 className="font-jost text-sm font-semibold text-light-mode">Filters</h2>}

      <FilterSection title="Discipline">
        <div className="flex flex-wrap gap-2">
          {disciplineOptions.map((option) => (
            <button
              key={option.key}
              type="button"
              onClick={() => onDisciplineChange(option.key)}
              className={`rounded-md border px-3 py-2 text-sm transition-colors ${
                discipline === option.key
                  ? "border-accent/40 bg-accent/10 text-light-mode"
                  : "border-white/10 bg-dark-mode text-ultra-light-mode/70 hover:text-light-mode"
              }`}
            >
              {option.label}
            </button>
          ))}
        </div>
      </FilterSection>

      <FilterSection title="Location">
        <LocationTreeFilter
          tree={locationTree}
          selected={locationTags}
          onChange={onLocationTagsChange}
          counts={locationTagCounts}
        />
      </FilterSection>

      <FilterSection title="Role">
        <MultiSelectDropdown
          label="Role"
          fullWidth
          options={roleOpts}
          selected={roles}
          onChange={onRolesChange}
          groupValues={roleGroups}
          counts={roleCounts}
          disabled={roleFilterDisabled}
        />
      </FilterSection>

      <FilterSection title="Level">
        <MultiSelectDropdown
          label="Level"
          fullWidth
          options={LEVEL_OPTIONS}
          selected={levels}
          onChange={onLevelsChange}
          counts={levelCounts}
        />
      </FilterSection>

      <FilterSection title="Grad Year">
        <MultiSelectDropdown
          label="Grad year"
          fullWidth
          options={gradYearOptions}
          selected={gradYears}
          onChange={onGradYearsChange}
          counts={gradYearCounts}
        />
      </FilterSection>

      <FilterSection title="Salary">
        <div className="relative w-full">
          <input
            type="number"
            min={0}
            step={5}
            value={salaryMin != null ? salaryMin / 1000 : ""}
            onChange={(e) => {
              const raw = e.target.value;
              onSalaryMinChange(raw === "" ? null : Number(raw) * 1000);
            }}
            placeholder="Min salary ($k)"
            title="Only show roles with a posted minimum salary at or above this"
            className="w-full rounded-md border border-white/10 bg-dark-mode px-3 py-2 pr-8
                       text-ultra-light-mode placeholder:text-ultra-light-mode/40
                       focus:border-accent/50 focus:outline-none"
          />
          <button
            type="button"
            onClick={() => onSalaryMinChange(null)}
            aria-label="Clear salary filter"
            tabIndex={salaryMin != null ? 0 : -1}
            className={`absolute inset-y-0 right-2 text-ultra-light-mode/40 transition-opacity hover:text-light-mode ${
              salaryMin != null ? "opacity-100" : "pointer-events-none opacity-0"
            }`}
          >
            ×
          </button>
        </div>
      </FilterSection>

      <FilterSection title="Other">
        <div className="flex flex-col gap-2">
          <button
            type="button"
            onClick={() => onTopOnlyChange(!topOnly)}
            title="Show only featured/top companies"
            className={`flex w-full items-center gap-1.5 rounded-md border px-3 py-2 text-sm transition-colors ${
              topOnly
                ? "border-accent/40 bg-accent/10 text-light-mode"
                : "border-white/10 bg-dark-mode text-ultra-light-mode/70 hover:text-light-mode"
            }`}
          >
            <span className="text-status-warning">★</span>
            Top companies only
          </button>
          <button
            type="button"
            onClick={() => onHideDefenseChange(!hideDefense)}
            title="Hide companies whose primary business is defense contracting, intelligence-community work, or surveillance technology"
            className={`flex w-full items-center gap-1.5 rounded-md border px-3 py-2 text-sm transition-colors ${
              hideDefense
                ? "border-accent/40 bg-accent/10 text-light-mode"
                : "border-white/10 bg-dark-mode text-ultra-light-mode/70 hover:text-light-mode"
            }`}
          >
            Hide defense &amp; surveillance
          </button>
        </div>
      </FilterSection>
    </div>
  );
}
