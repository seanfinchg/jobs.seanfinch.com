# How to add a new discipline/field

Worked example: adding **hardware** (chip design, embedded silicon, ASIC/FPGA
work — not currently covered by any existing field) as a new career track.
Adding a field should mean writing one new file in `profiles/fields/`; nothing
outside that one file should need to change.

## 1. What a field owns

A `profiles/fields/<name>.yaml` is a self-contained layer covering everything
specific to one career track:

- `filters` — the title/body vocabulary that decides whether a posting
  belongs to this track at all (`title_include`, `title_exclude`, etc.).
- `label` — the display name the dashboard's Role filter shows instead of
  the raw file-name slug.
- `subfields` — optional finer-grained tags nested under this field (e.g.
  security's AppSec/IAM/GRC), each with its own title-matching `pattern`.

None of this needs to touch `jobfinder/classify.py`, `jobfinder/engine.py`,
`jobfinder/dashboard.py`, or anything on the frontend — those all read field
files dynamically at runtime. See `profiles/_schema.md` for the exhaustive
key-by-key reference; this doc is the worked walkthrough.

## 2. Write the field file

`profiles/fields/hardware.yaml`:

```yaml
meta:
  name: "Field: Hardware"

label: "Hardware"

subfields:
  - tag: chip-design
    label: "Chip Design"
    pattern: 'chip design|digital design engineer|analog design engineer|\basic\b'
  - tag: fpga
    label: "FPGA"
    pattern: '\bfpga\b'
  - tag: verification
    label: "Verification"
    pattern: 'verification engineer|\bdv engineer\b|design verification'

filters:
  title_include:
    - 'hardware engineer'
    - 'asic (design|verification) engineer'
    - '\bfpga\b'
    - 'silicon (design|validation) engineer'
    - 'digital design engineer'
    - 'analog design engineer'

  # Same false-positive-guard convention every field uses: titles that would
  # otherwise slip through title_include but aren't the engineering roles
  # this field targets.
  title_exclude:
    - 'sales|account executive|marketing|recruit|customer success'
```

Points worth calling out:

- **`label`/`subfields` are purely additive dashboard metadata** — a field
  file with `filters` but no `label` still works for ingest, it just won't
  get a real dashboard label or sub-tags. Add them from the start if the
  field is meant to show up in the dashboard, which in practice is always.
- **`subfields[].pattern` matches against the title only**, not the body.
  Reuse the same archetype phrasing used in `filters` (like `security.yaml`
  does) so a subfield tag means the same thing the field's own filters mean.
- **This is the entire file.** No Python code, no frontend code, no second
  config to register it in.

## 3. Wire it into a profile

Add `hardware` to a profile's `fields:` list — either an existing one
(`profiles/broad-cs.yaml`, alongside its other tracks) or a new persona
profile:

```yaml
fields: [software-engineering, data-ml, devops-sre, qa, mobile, systems, hardware]
```

`engine.load_profile()` loads every listed field's YAML and merges its
`filters` into the profile's effective rules (list-valued filter keys
concatenate across every layer that defines them; see `profiles/_schema.md`'s
`level`/`fields` section for the full merge semantics) — no other edit
needed for ingest to pick it up.

## 4. Verify end to end

1. **`jobfinder profile show <name>`** — confirm the merged `filters`
   include hardware's entries, and that they didn't clobber any other
   field's keys with the same regex.
2. **`jobfinder run --profile <name>`** — confirm it matches real postings
   against the new field's vocabulary. Run this against the real live
   boards, not just a unit test — a field's title/body vocabulary is only
   really proven against actual posting text.
3. **`jobfinder dashboard`** — confirm `frontend/public/fields.json` now has
   a `hardware` entry with `label: "Hardware"` and its three subfields.
4. **The built dashboard** — confirm the Role filter shows "Hardware" (not
   a raw `hardware` slug) with a grouped subfield dropdown, and that a
   hardware posting's card actually gets tagged with it.

If any of steps 3-4 required editing `classify.py`, `dashboard.py`, or
anything under `frontend/src`, something regressed — those are supposed to
read every field file generically, not hardcode a list of known fields.

## Definition of done

- `pytest` green from `backend/` — regression tests should confirm existing
  fields' `classify_fields()`/`classify_subfields()` output is unchanged by
  adding a new field (a new field's patterns must never accidentally match
  an unrelated title).
- Confirmed against real live postings, not just fixtures — same rule as
  every other change to the ingest/filtering path.
- `profiles/_schema.md` already documents `label`/`subfields`; only touch it
  if this field needs a genuinely new key shape neither already covers.
