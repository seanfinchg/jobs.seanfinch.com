from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import yaml

FIELDS_DIR = Path("profiles") / "fields"


def grad_year_pattern(today: date | None = None) -> str:
    """Regex alternation matching the current year through two years out
    (e.g. "2026|2027|2028"), recomputed from the real date instead of a
    literal a human has to remember to bump every year. Any filters regex
    in a profile YAML can embed the `{grad_years}` placeholder token
    and have it substituted with this (see engine.py's _load_yaml)."""
    year = (today or date.today()).year
    return "|".join(str(year + offset) for offset in range(3))


# Grad/intern-program vocabulary a stated year needs to sit near to count --
# same words classify_level's intern/new-grad bands already key on, so a
# title tagged "new-grad" here is never at odds with what classify_level said
# about the same title.
_GRAD_YEAR_CONTEXT = (
    r"new ?grad|university grad|class of|\bgraduate\b|\bintern(?:ship)?\b|\bco-?op\b|"
    r"early career|entry[ -]level|early talent|emerging talent|exceptional talent"
)


def classify_grad_year(title: str, body: str = "", today: date | None = None) -> int | None:
    """Explicit graduating/start year stated near grad/intern wording, e.g.
    "New Grad 2027", "Summer 2026 Intern", "(2027 Graduate)". Checks the
    title first, then falls back to the body. Most postings never state a
    year at all -- that's a legitimate "not specified" outcome (returns
    None), not a failure to guess one. Only years in grad_year_pattern()'s
    current-through-+2 window count as a match, so an unrelated 4-digit
    number elsewhere in the text (a street address, a ticket number) can't
    false-positive into a year."""
    years = grad_year_pattern(today)
    pattern = rf"\b({years})\b(?:.|\n){{0,30}}?(?:{_GRAD_YEAR_CONTEXT})|(?:{_GRAD_YEAR_CONTEXT})(?:.|\n){{0,30}}?\b({years})\b"
    for text in (title, body):
        match = re.search(pattern, text or "", re.IGNORECASE)
        if match:
            return int(match.group(1) or match.group(2))
    return None

# Checked in priority order so the first, most specific match wins -- e.g.
# "senior" alone comes late in the list because it shows up as a modifier
# inside several more specific titles ("Senior Staff", "Senior Principal",
# "Senior Director") that each need to land in their own band, not fall
# into plain "senior". Best-effort classification from title text alone --
# same "best-effort, conservative default" spirit as salary extraction
# elsewhere in this codebase. Words aren't the only convention in real
# postings -- numbered ladders ("Software Engineer II/III/IV", "L3", "IC4")
# are just as common, so the IC bands also match their usual numeric
# shorthand, anchored to the end of the title (or a clear L#/IC# token) to
# avoid a stray digit elsewhere in the title causing a false match.
LEVEL_PATTERNS: list[tuple[str, str]] = [
    ("intern", r"intern\b|internship|co-?op"),
    ("vp", r"\bvp\b|vice president"),
    ("director", r"\bdirector\b|\bhead of\b"),
    ("manager", r"\bmanager\b"),
    ("distinguished", r"distinguished|\bfellow\b"),
    ("senior-principal", r"senior principal|sr\.? principal"),
    ("principal", r"\bprincipal\b|\bl[6-9]\b|\bic[6-9]\b"),
    ("senior-staff", r"senior staff|sr\.? staff"),
    ("staff", r"\bstaff\b|\bl[45]\b|\bic[45]\b|\b(iv|4)\s*$"),
    ("senior", r"senior|\bsr\.?\b|\blead\b|\bl3\b|\bic3\b|\b(iii|3)\s*$"),
    # Bare "Graduate" (no "new"/"university" prefix) is its own extremely
    # common convention -- "Graduate Software Engineer" (Optiver, Citadel,
    # IMC, Motorola, HP), "Software Engineer Graduate" / "... Engineer
    # Graduate - <team>" (ByteDance/TikTok's house style), "(2027 Graduate)"
    # -- found affecting 155 real postings across the dataset, all
    # genuinely entry-level, none miscaught (no \b before "graduate" alone
    # would also true-positive on "undergraduate", but \bgraduate\b's
    # leading boundary requires a non-word character before it, and
    # "undergraduate" has none there, so it's naturally excluded -- those
    # are academic research-assistant postings, not industry new-grad
    # roles, and correctly don't match this pattern).
    # "Early Talent"/"Emerging Talent"/"Exceptional Talent" are real
    # program-name conventions (seen in the wild at Boom Supersonic, Verse
    # Medical, and used as an official new-grad-hiring-program name at
    # several larger companies) -- distinct from a bare "talent" match,
    # which would false-positive on HR/recruiting titles ("Talent
    # Acquisition Manager", "Head of Talent") that aren't entry-level
    # engineering roles at all.
    ("new-grad", r"new ?grad|university grad|\bgraduate\b|early career|entry[ -]level|\bassociate\b|early talent|emerging talent|exceptional talent|\bl1\b|\bic1\b|\b(i|1)\s*$"),
    ("mid", r"\bl2\b|\bic2\b|\b(ii|2)\s*$"),
]
DEFAULT_LEVEL = "mid"

# Canonical display/sort order for the dashboard's level filter -- roughly
# junior to senior on the IC track, then the management track.
LEVEL_ORDER: list[str] = [
    "intern", "new-grad", "mid", "senior", "staff", "senior-staff",
    "principal", "senior-principal", "distinguished",
    "manager", "director", "vp",
]


def classify_level(title: str) -> str:
    """Best-effort seniority band from the title text alone. Titles with no
    recognizable marker default to "mid" -- the most common unlabeled case
    in practice -- rather than guessing entry-level or senior."""
    for level, pattern in LEVEL_PATTERNS:
        if re.search(pattern, title or "", re.IGNORECASE):
            return level
    return DEFAULT_LEVEL


# Finer-grained tags within a broad field, for the dashboard's role filter --
# the same archetypes profiles/fields/*.yaml's own filters already target,
# so picking "AppSec" here means the same thing it means in that field's
# vocabulary. Purely a dashboard classification concern: doesn't touch
# filtering. Declared per-field in each profiles/fields/<name>.yaml's
# own `subfields:` list (tag + pattern + label), not hardcoded here -- so a
# new field YAML brings its own subfield tags with it, no code change.
def _load_field_subfield_patterns(fields_dir: Path) -> dict[str, list[tuple[str, str]]]:
    patterns: dict[str, list[tuple[str, str]]] = {}
    for path in sorted(fields_dir.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        subfields = data.get("subfields") or []
        if subfields:
            patterns[path.stem] = [(sf["tag"], sf["pattern"]) for sf in subfields]
    return patterns


_field_subfield_patterns_cache: dict[str, list[tuple[str, str]]] = {}


def classify_subfields(title: str, fields_dir: Path = FIELDS_DIR) -> list[str]:
    """Finer-grained tags than classify_fields() -- e.g. a security title
    also gets "appsec"/"iam"/etc. where its text supports it. Not every
    field has sub-tags defined (qa doesn't); a title matching none just
    gets an empty list, same as classify_fields()."""
    if not _field_subfield_patterns_cache:
        _field_subfield_patterns_cache.update(_load_field_subfield_patterns(fields_dir))

    return [
        subfield
        for patterns in _field_subfield_patterns_cache.values()
        for subfield, pattern in patterns
        if re.search(pattern, title or "", re.IGNORECASE)
    ]


def classify_subfields_by_field(title: str, fields_dir: Path = FIELDS_DIR) -> list[tuple[str, str]]:
    """Same matching as classify_subfields(), but keeps each tag paired with
    the field it belongs to as (field_slug, tag) -- needed for job_subfields'
    composite foreign key (db.py), since a tag string is only unique within
    its own field, not globally. classify_subfields() stays as-is (flattened)
    since existing callers depend on that shape."""
    if not _field_subfield_patterns_cache:
        _field_subfield_patterns_cache.update(_load_field_subfield_patterns(fields_dir))

    return [
        (field_name, subfield)
        for field_name, patterns in _field_subfield_patterns_cache.items()
        for subfield, pattern in patterns
        if re.search(pattern, title or "", re.IGNORECASE)
    ]


def _load_field_title_patterns(fields_dir: Path) -> dict[str, list[str]]:
    patterns: dict[str, list[str]] = {}
    for path in sorted(fields_dir.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        title_include = (data.get("filters") or {}).get("title_include") or []
        if title_include:
            patterns[path.stem] = title_include
    return patterns


_field_patterns_cache: dict[str, list[str]] = {}


def classify_fields(title: str, fields_dir: Path = FIELDS_DIR) -> list[str]:
    """Which career tracks (profiles/fields/*.yaml) this title matches --
    computed independent of which profile actually ingested the job, so the
    dashboard can filter by track regardless of how broad or narrow the
    ingesting profile's own `fields:` list was."""
    if not _field_patterns_cache:
        _field_patterns_cache.update(_load_field_title_patterns(fields_dir))

    return [
        field_name
        for field_name, title_patterns in _field_patterns_cache.items()
        if any(re.search(p, title or "", re.IGNORECASE) for p in title_patterns)
    ]
