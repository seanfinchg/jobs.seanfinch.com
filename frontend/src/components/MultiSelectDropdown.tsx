import { useEffect, useRef, useState } from "react";

interface Option {
  value: string;
  label: string;
  group?: string;
}

interface MultiSelectDropdownProps {
  label: string;
  options: Option[];
  selected: string[];
  onChange: (selected: string[]) => void;
  // Group label -> the value toggled when that group's header itself is
  // clicked (a "select this whole category" checkbox instead of a
  // separate "All <category>" leaf option under it).
  groupValues?: Record<string, string>;
  // How many currently-visible jobs (under every *other* active filter)
  // each option's value would match -- lets this filter react to the
  // others instead of always showing counts as if nothing else were set.
  // An option with no entry here (rather than 0) means counts aren't wired
  // up for this dropdown; it renders with no count at all.
  counts?: Record<string, number>;
  // Stacked-sidebar usage (see FilterBar) wants the trigger button to fill
  // its column instead of shrinking to its label's width.
  fullWidth?: boolean;
  // Grayed out and inert -- for a facet that depends on a choice made
  // elsewhere first (see FilterBar's Role dropdown, locked until a
  // discipline is picked on the onboarding screens).
  disabled?: boolean;
}

// Below this many options a search box is just another thing to click
// past -- it earns its place once scanning the list itself stops being
// faster than typing (Location alone can carry 500+ options here).
const SEARCH_THRESHOLD = 8;

export default function MultiSelectDropdown({
  label,
  options,
  selected,
  onChange,
  groupValues = {},
  counts,
  fullWidth = false,
  disabled = false,
}: MultiSelectDropdownProps): React.JSX.Element {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const ref = useRef<HTMLDivElement>(null);

  // A disabled facet should never stay open from before its dependency
  // disappeared (e.g. discipline gets cleared via "Change discipline"
  // while this dropdown happened to be open).
  useEffect(() => {
    if (disabled) setOpen(false);
  }, [disabled]);

  useEffect(() => {
    function onClickOutside(e: MouseEvent): void {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, []);

  // Query resets on close rather than persisting -- reopening the dropdown
  // should show the full list again, not whatever was last typed.
  useEffect(() => {
    if (!open) setQuery("");
  }, [open]);

  function toggle(value: string): void {
    onChange(selected.includes(value) ? selected.filter((v) => v !== value) : [...selected, value]);
  }

  const q = query.trim().toLowerCase();
  const visibleOptions = q
    ? options.filter((opt) => opt.label.toLowerCase().includes(q) || opt.group?.toLowerCase().includes(q))
    : options;

  // Preserve the order groups first appear in `options` -- ungrouped
  // options (group === undefined) render inline, not under a header.
  const groups = new Map<string | undefined, Option[]>();
  for (const opt of visibleOptions) {
    if (!groups.has(opt.group)) groups.set(opt.group, []);
    groups.get(opt.group)?.push(opt);
  }

  return (
    <div className={`relative ${fullWidth ? "w-full" : ""}`} ref={ref}>
      <button
        type="button"
        disabled={disabled}
        onClick={() => setOpen((o) => !o)}
        className={`flex items-center gap-2 rounded-md border px-3 py-2 text-sm transition-colors ${
          fullWidth ? "w-full justify-between" : ""
        } ${
          disabled
            ? "cursor-not-allowed border-white/5 bg-dark-mode/50 text-ultra-light-mode/30"
            : selected.length > 0
              ? "border-accent/40 bg-accent/10 text-light-mode"
              : "border-white/10 bg-dark-mode text-ultra-light-mode/70 hover:text-light-mode"
        }`}
      >
        <span className="flex items-center gap-2">
          {label}
          {/* Always mounted (opacity/visibility toggled, not conditionally
              rendered) so selecting/clearing this filter never changes the
              button's width -- that would shift every dropdown after it in
              the flex-wrap row. */}
          <span
            aria-hidden={selected.length === 0}
            className={`rounded-full bg-accent/20 px-1.5 py-0.5 text-xs text-accent transition-opacity ${
              selected.length > 0 ? "opacity-100" : "opacity-0"
            }`}
          >
            {selected.length}
          </span>
          <span
            role="button"
            tabIndex={selected.length > 0 ? 0 : -1}
            aria-hidden={selected.length === 0}
            aria-label={`Clear ${label} filter`}
            onClick={(e) => {
              e.stopPropagation();
              if (selected.length > 0) onChange([]);
            }}
            onKeyDown={(e) => {
              if (selected.length > 0 && (e.key === "Enter" || e.key === " ")) {
                e.stopPropagation();
                onChange([]);
              }
            }}
            className={`text-ultra-light-mode/40 transition-opacity hover:text-light-mode ${
              selected.length > 0 ? "opacity-100" : "pointer-events-none opacity-0"
            }`}
          >
            ×
          </span>
        </span>
        <span className="text-ultra-light-mode/40">{open ? "▲" : "▼"}</span>
      </button>
      {open && (
        // A floating popover anchored to the trigger works at desktop
        // widths where there's room around it, but on a phone it can open
        // past the bottom of the viewport with no way to bring the rest of
        // it into view (the page has to scroll, not just the popover).
        // Below sm it renders in normal document flow instead -- a proper
        // inline-expand/accordion, the same pattern the mobile filter
        // sheet itself expects its contents to use.
        <div
          className={`relative z-20 mt-1 max-h-80 w-full overflow-y-auto rounded-md border border-white/10 bg-dark-mode p-2 shadow-xl sm:absolute ${fullWidth ? "sm:w-full" : "sm:w-56"}`}
        >
          {options.length > SEARCH_THRESHOLD && (
            <input
              type="text"
              autoFocus
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={`Search ${label.toLowerCase()}...`}
              className="mb-2 w-full rounded border border-white/10 bg-ultra-dark-mode px-2 py-1 text-sm
                         text-ultra-light-mode placeholder:text-ultra-light-mode/40
                         focus:border-accent/50 focus:outline-none"
            />
          )}
          {selected.length > 0 && (
            <button
              type="button"
              onClick={() => onChange([])}
              className="mb-1 w-full rounded px-2 py-1 text-left text-xs text-ultra-light-mode/50 hover:bg-white/5 hover:text-light-mode"
            >
              clear all
            </button>
          )}
          {visibleOptions.length === 0 && (
            <p className="px-2 py-3 text-center text-xs text-ultra-light-mode/40">no matches</p>
          )}
          {[...groups.entries()].map(([group, opts]) => {
            const groupValue = group ? groupValues[group] : undefined;
            return (
              <div key={group ?? "_ungrouped"} className="mt-2 first:mt-0">
                {group && groupValue && (
                  <label className="flex cursor-pointer items-center justify-between gap-2 rounded bg-white/5 px-2 py-1.5 text-xs font-bold tracking-wide text-light-mode uppercase hover:bg-white/10">
                    <span className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        checked={selected.includes(groupValue)}
                        onChange={() => toggle(groupValue)}
                        className="accent-accent"
                      />
                      {group}
                    </span>
                    {counts && (
                      <span className="font-mono font-normal normal-case text-ultra-light-mode/40">
                        {counts[groupValue] ?? 0}
                      </span>
                    )}
                  </label>
                )}
                {group && !groupValue && (
                  <div className="rounded bg-white/5 px-2 py-1.5 text-xs font-bold tracking-wide text-light-mode uppercase">
                    {group}
                  </div>
                )}
                {/* Sub-items indent + get a left rule so nesting under the
                    group header above is unambiguous, not just a font-size
                    difference. */}
                <div className={group ? "ml-2 border-l border-white/10 pl-2" : ""}>
                  {opts.map((opt) => {
                    const count = counts?.[opt.value] ?? 0;
                    const isZero = counts && count === 0 && !selected.includes(opt.value);
                    return (
                      <label
                        key={opt.value}
                        className={`flex cursor-pointer items-center justify-between gap-2 rounded px-2 py-1.5 text-sm hover:bg-white/5 ${
                          isZero ? "text-ultra-light-mode/40" : "text-ultra-light-mode/80"
                        }`}
                      >
                        <span className="flex items-center gap-2">
                          <input
                            type="checkbox"
                            checked={selected.includes(opt.value)}
                            onChange={() => toggle(opt.value)}
                            className="accent-accent"
                          />
                          {opt.label}
                        </span>
                        {counts && <span className="font-mono text-xs text-ultra-light-mode/40">{count}</span>}
                      </label>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
