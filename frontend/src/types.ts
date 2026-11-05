import { z } from "zod";

// Mirrors what jobfinder.dashboard.export_data() actually writes per row
// (jobfinder.dashboard.PUBLIC_FIELDS, minus content_hash which is renamed
// to `id`, plus apply_urls/featured which are computed at export time) --
// if that shape changes, this needs to change with it. Parsed, not cast, so
// a drifted export fails loudly at load instead of deep inside a filter.
export const JobSchema = z.object({
  id: z.string(),
  company: z.string(),
  title: z.string(),
  location: z.string(),
  best_apply_url: z.string(),
  apply_urls: z.array(z.string()),
  first_seen: z.string(),
  posted_at: z.string().nullable(),
  salary_min: z.number().nullable(),
  salary_max: z.number().nullable(),
  featured: z.boolean(),
  defense: z.boolean(),
  level: z.string().nullable(),
  matched_fields: z.array(z.string()),
  matched_subfields: z.array(z.string()),
  grad_year: z.number().nullable(),
});
export type Job = z.infer<typeof JobSchema>;
export const JobsSchema = z.array(JobSchema);

// meta.json: when the pipeline last ran (written by jobfinder.dashboard.export_data()).
export const MetaSchema = z.object({ generated_at: z.string() });

export type SortKey = "company" | "title" | "location" | "posted" | "level";

// Canonical order for the level filter -- matches
// jobfinder/classify.py's LEVEL_ORDER exactly. A job whose level isn't in
// this list (shouldn't happen, but the classifier defaults unknowns to
// "mid") sorts after everything named here.
export const LEVEL_ORDER = [
  "intern",
  "new-grad",
  "mid",
  "senior",
  "staff",
  "senior-staff",
  "principal",
  "senior-principal",
  "distinguished",
  "manager",
  "director",
  "vp",
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
export const FieldMetaSchema = z.object({
  slug: z.string(),
  label: z.string(),
  subfields: z.array(z.object({ tag: z.string(), label: z.string() })),
});
export type FieldMeta = z.infer<typeof FieldMetaSchema>;
export const FieldsSchema = z.array(FieldMetaSchema);
