# Profile schema

A profile is a YAML file in `profiles/`, loaded by name (no extension) via
`--profile`. It's the only place level, role, and location preferences live --
the engine itself doesn't know what a "new grad" or a "senior" title is.

## `meta`

- `name` -- human-readable label, shown nowhere critical, just for your own sanity.
- `owner` -- whoever this profile belongs to.

## `include` (optional)

Path to a YAML file (relative to the repo root) containing its own `boards:`
key. Lets a board/company list be shared across profiles instead of copy-pasted.
The profile's own `boards:` (if any) is appended per-adapter after the
included list, not replaced.

## `level` / `fields` (optional)

Instead of writing `filters` out flat, a profile can compose them from
reusable layers: `level: <name>` loads `profiles/levels/<name>.yaml` once
(properties tied to a candidate's experience tier -- seniority/intern/PhD
exclusions -- independent of career track), and `fields: [<name>, ...]`
loads one or more `profiles/fields/<name>.yaml` (properties of a track --
title vocabulary -- independent of tier). Layers merge in order (level,
then each field, then the profile's own YAML last): list-valued filter keys
concatenate across every layer that defines them. A profile with neither
key behaves exactly as before: flat `filters` straight off its own YAML.
Run `jobfinder profile show <name>` to print the fully merged result.

## `boards`

Maps an adapter name (must be registered -- see `jobfinder/adapters/`) to a
list of board configs. Every adapter needs at least `token`; most also take
`company` for a friendlier display name. What `token` means depends on the
adapter (a Greenhouse/Lever/Ashby/SmartRecruiters/Workable/Rippling board
slug, or for `simplify_listings` just a label since it isn't a per-company
feed). `workday` is the exception -- it needs `tenant`, `wd` (the pod
number, e.g. `wd12`), and `site` in addition to `token`, since a Workday
board isn't addressable by one slug. `simplify_listings` also takes
`season` (`new-grad` or `summer-internship`) and, for `summer-internship`,
`year` -- picks which SimplifyJobs repo to read instead of a hardcoded one.

## `label` / `subfields` (fields only)

A `profiles/fields/<name>.yaml` can also declare dashboard display metadata,
independent of its `filters`:

- `label` -- human-readable name for the field, e.g. `label: "Security"` for
  `security.yaml`. Read by `jobfinder/dashboard.py`'s `export_data()` and
  written into `fields.json` alongside `data.json`; the frontend uses it
  instead of showing the raw slug in the Role filter. A field with no
  `label` is skipped from `fields.json` entirely.
- `subfields` -- a list of finer-grained role tags nested under this field,
  each `{tag, pattern, label}`: `tag` is the dashboard/matched_subfields
  value, `pattern` is a case-insensitive regex matched against the job
  title only, `label` is the display name (falls back to `tag` if omitted).
  Read by `jobfinder/classify.py`'s `classify_subfields()` for tagging and
  by `dashboard.py` for `fields.json`. A field with no `subfields` key just
  has no sub-tags -- not every field needs them (see `qa.yaml`).

This is purely additive to a field file -- a new `profiles/fields/<name>.yaml`
with `filters` but no `label`/`subfields` still works for ingest, it just
won't get a real dashboard label or any sub-tags until those are added.

See [adding-a-field.md](adding-a-field.md) for a full worked example (writing a
field file, wiring it into a profile, verifying it end to end).

## `{grad_years}` placeholder

Any regex string in `filters` (in a profile, level, or field YAML) can embed
the literal token `{grad_years}`. `jobfinder/engine.py`'s `_load_yaml()`
substitutes it with an alternation of the current year through two years out
(e.g. `2026|2027|2028`), computed from `jobfinder/classify.py`'s
`grad_year_pattern()` at load time -- so a "graduating in `<year>`" pattern
never needs a human to bump a literal year by hand. See
`profiles/fields/security.yaml`'s `title_include_weak` for an example.

## `filters`

All values are lists of case-insensitive regexes, matched with `re.search`
(not `fullmatch`) against the job's title, location, or body text.

- `title_include` -- title must match at least one. Omit or leave empty to
  skip this check.
- `title_include_weak` / `body_include_for_weak_title` -- a second, looser
  title tier for a generic title that isn't explicit evidence of security
  relevance on its own (e.g. a plain "Software Engineer, New Grad"). A job
  matching only the weak tier (not `title_include`) also needs its body to
  match something in `body_include_for_weak_title`, or it's dropped. A job
  matching `title_include` passes regardless. Sources with no body text
  (aggregators, or adapters that don't fetch a description) can never
  satisfy the weak tier -- intentional, since there's nothing to check.
- `title_exclude` -- any match disqualifies the job outright.
- `location_include` / `location_exclude` -- same idea, against location.
- `body_exclude` -- checked against the stripped posting body. This is the
  seniority guard ("5+ years") for boards where the title alone doesn't say
  it.

A job passes filtering only if it clears every check that has patterns
configured.
