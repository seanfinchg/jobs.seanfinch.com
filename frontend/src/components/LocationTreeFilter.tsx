import { useEffect, useMemo, useRef, useState } from "react";
import type { LocationTreeNode } from "@/lib/location";

interface LocationTreeFilterProps {
  tree: LocationTreeNode[];
  selected: string[];
  onChange: (selected: string[]) => void;
  counts: Record<string, number>;
}

// Below this many top-level countries, scanning the (collapsed) list is
// already faster than typing -- the search box only earns its place once
// the tree is big enough that finding a branch by eye is slow.
const SEARCH_THRESHOLD = 8;

// Only the label needs to match -- "toronto" should surface the Canada
// branch with just its Toronto leaf, not force the user to know it's
// nested under Canada first.
function filterTree(nodes: LocationTreeNode[], q: string): LocationTreeNode[] {
  const out: LocationTreeNode[] = [];
  for (const node of nodes) {
    const selfMatch = node.label.toLowerCase().includes(q);
    const filteredChildren = selfMatch ? node.children : filterTree(node.children, q);
    if (selfMatch || filteredChildren.length > 0) out.push({ ...node, children: filteredChildren });
  }
  return out;
}

function collectValues(nodes: LocationTreeNode[]): string[] {
  return nodes.flatMap((n) => [n.value, ...collectValues(n.children)]);
}

interface TreeRowProps {
  node: LocationTreeNode;
  depth: number;
  selected: string[];
  onToggle: (value: string) => void;
  expanded: Set<string>;
  onToggleExpand: (value: string) => void;
  forceExpanded: boolean;
  counts: Record<string, number>;
}

function TreeRow({ node, depth, selected, onToggle, expanded, onToggleExpand, forceExpanded, counts }: TreeRowProps): React.JSX.Element {
  const hasChildren = node.children.length > 0;
  const isExpanded = forceExpanded || expanded.has(node.value);
  const count = counts[node.value] ?? 0;
  const isZero = count === 0 && !selected.includes(node.value);

  return (
    <div>
      <div
        className="flex items-center justify-between gap-2 rounded py-1 pr-2 hover:bg-white/5"
        style={{ paddingLeft: 4 + depth * 16 }}
      >
        <span className="flex min-w-0 flex-1 items-center gap-1.5">
          {hasChildren ? (
            <button
              type="button"
              onClick={() => onToggleExpand(node.value)}
              aria-label={isExpanded ? `Collapse ${node.label}` : `Expand ${node.label}`}
              className="w-3.5 shrink-0 text-ultra-light-mode/40 hover:text-light-mode"
            >
              {isExpanded ? "▾" : "▸"}
            </button>
          ) : (
            <span className="w-3.5 shrink-0" />
          )}
          <label className="flex min-w-0 flex-1 cursor-pointer items-center gap-2">
            <input
              type="checkbox"
              checked={selected.includes(node.value)}
              onChange={() => onToggle(node.value)}
              className="accent-accent"
            />
            <span className={`truncate text-sm ${isZero ? "text-ultra-light-mode/40" : "text-ultra-light-mode/80"}`}>
              {node.label}
            </span>
          </label>
        </span>
        <span className="shrink-0 font-mono text-xs text-ultra-light-mode/40">{count}</span>
      </div>
      {hasChildren && isExpanded && (
        <div>
          {node.children.map((child) => (
            <TreeRow
              key={child.value}
              node={child}
              depth={depth + 1}
              selected={selected}
              onToggle={onToggle}
              expanded={expanded}
              onToggleExpand={onToggleExpand}
              forceExpanded={forceExpanded}
              counts={counts}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// A Country -> State -> City picker (state only exists as a level under
// United States; every other country's cities nest directly under it, and
// "Remote" sits flat at the top since it isn't a place). Checking a
// country or state matches every job under it directly -- see
// lib/location.ts's locationTagsFor, which tags a job with every level its
// location resolves to, not just the most specific one.
export default function LocationTreeFilter({ tree, selected, onChange, counts }: LocationTreeFilterProps): React.JSX.Element {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onClickOutside(e: MouseEvent): void {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, []);

  useEffect(() => {
    if (!open) setQuery("");
  }, [open]);

  function toggle(value: string): void {
    onChange(selected.includes(value) ? selected.filter((v) => v !== value) : [...selected, value]);
  }

  function toggleExpand(value: string): void {
    setExpanded((cur) => {
      const next = new Set(cur);
      if (next.has(value)) next.delete(value);
      else next.add(value);
      return next;
    });
  }

  const q = query.trim().toLowerCase();
  const visibleTree = useMemo(() => (q ? filterTree(tree, q) : tree), [tree, q]);
  const totalOptions = useMemo(() => collectValues(tree).length, [tree]);

  return (
    <div className="relative w-full" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className={`flex w-full items-center justify-between gap-2 rounded-md border px-3 py-2 text-sm transition-colors ${
          selected.length > 0
            ? "border-accent/40 bg-accent/10 text-light-mode"
            : "border-white/10 bg-dark-mode text-ultra-light-mode/70 hover:text-light-mode"
        }`}
      >
        <span className="flex items-center gap-2">
          Location
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
            aria-label="Clear Location filter"
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
        // Same inline-expand-below-sm fix as MultiSelectDropdown: a
        // floating popover can open past the bottom of a phone viewport
        // with no way to scroll it into view short of scrolling the whole
        // page; below sm this renders in normal flow instead.
        <div className="relative z-20 mt-1 max-h-96 w-full overflow-y-auto rounded-md border border-white/10 bg-dark-mode p-2 shadow-xl sm:absolute sm:min-w-64">
          {totalOptions > SEARCH_THRESHOLD && (
            <input
              type="text"
              autoFocus
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search location..."
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
          {visibleTree.length === 0 && <p className="px-2 py-3 text-center text-xs text-ultra-light-mode/40">no matches</p>}
          {visibleTree.map((node) => (
            <TreeRow
              key={node.value}
              node={node}
              depth={0}
              selected={selected}
              onToggle={toggle}
              expanded={expanded}
              onToggleExpand={toggleExpand}
              forceExpanded={q.length > 0}
              counts={counts}
            />
          ))}
        </div>
      )}
    </div>
  );
}
