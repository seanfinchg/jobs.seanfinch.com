// Mirrors what jobfinder.dashboard.export_data() actually writes per row
// (jobfinder.dashboard.PUBLIC_FIELDS, minus content_hash which is renamed
// to `id`, plus apply_urls/featured which are computed at export time) --
// if that shape changes, this needs to change with it.
export interface Job {
  id: string;
  company: string;
  title: string;
  location: string;
  best_apply_url: string;
  apply_urls: string[];
  first_seen: string;
  posted_at: string | null;
  salary_min: number | null;
  salary_max: number | null;
  featured: boolean;
  defense: boolean;
  level: string | null;
  matched_fields: string[];
  matched_subfields: string[];
  grad_year: number | null;
}

export type SortKey = "company" | "title" | "location" | "posted" | "level";

// Canonical order for the level filter -- matches
// jobfinder/classify.py's LEVEL_ORDER exactly. A job whose level isn't in
// this list (shouldn't happen, but the classifier defaults unknowns to
// "mid") sorts after everything named here.
export const LEVEL_ORDER = [
  "intern", "new-grad", "mid", "senior", "staff", "senior-staff",
  "principal", "senior-principal", "distinguished",
  "manager", "director", "vp",
];

export const LEVEL_LABELS: Record<string, string> = {
  intern: "Intern",
  "new-grad": "Entry-level / New grad",
  mid: "Mid-level",
  senior: "Senior",
  staff: "Staff",
  "senior-staff": "Senior Staff",
  principal: "Principal",
  "senior-principal": "Senior Principal",
  distinguished: "Distinguished / Fellow",
  manager: "Manager",
  director: "Director",
  vp: "VP+",
};

// Mirrors jobfinder.dashboard._load_fields_metadata()'s fields.json export --
// one entry per profiles/fields/<name>.yaml that declares a `label:`, with
// its `subfields:` (if any) carried along as {tag, label} pairs. A new field
// YAML shows up here with zero frontend edits -- adding one is purely a
// backend/data change (see profiles/_schema.md).
export interface FieldMeta {
  slug: string;
  label: string;
  subfields: { tag: string; label: string }[];
}
