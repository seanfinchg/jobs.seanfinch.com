"""Typed shapes for the YAML config files (profiles, levels, fields, boards).

The YAML is parsed into these TypedDicts with Pydantic at load time, so the
rest of the code gets real types while still working with plain dicts (tests
and callers pass dict literals). Keys a file doesn't set stay absent and
keys left empty stay None, exactly as before validation existed; unknown keys
(meta:, per-board notes) are kept as-is. Numbers are coerced to strings for string
fields, since YAML reads an unquoted token like `3m` fine but `123` as an int.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Literal, TypedDict

import yaml
from pydantic import ConfigDict, TypeAdapter, with_config

_CONFIG = ConfigDict(extra="allow", coerce_numbers_to_str=True)


@with_config(_CONFIG)
class Filters(TypedDict, total=False):
    title_include: list[str] | None
    title_include_weak: list[str] | None
    body_include_for_weak_title: list[str] | None
    title_exclude: list[str] | None
    location_include: list[str] | None
    location_exclude: list[str] | None
    body_exclude: list[str] | None


FilterKey = Literal[
    "title_include",
    "title_include_weak",
    "body_include_for_weak_title",
    "title_exclude",
    "location_include",
    "location_exclude",
    "body_exclude",
]


@with_config(_CONFIG)
class Board(TypedDict, total=False):
    """One board entry. Which keys are needed depends on the adapter: most
    want `token` (and optionally `company`); workday also wants
    tenant/wd/site; manual wants company/title/url; simplify_listings uses
    season/year or url."""

    token: str
    company: str
    title: str
    location: str
    url: str | None
    posted_at: str | None
    tenant: str
    wd: str
    site: str
    season: str
    year: int | None


@with_config(_CONFIG)
class Subfield(TypedDict, total=False):
    tag: str
    label: str
    pattern: str


@with_config(_CONFIG)
class Profile(TypedDict, total=False):
    """A profile, level, field or included board file -- they share one
    loader (engine._load_yaml), so one shape with every key optional."""

    include: str | list[str] | None
    level: str | None
    fields: list[str] | None
    boards: dict[str, list[Board]] | None
    filters: Filters | None
    label: str | None
    subfields: list[Subfield] | None


_PROFILE_ADAPTER: TypeAdapter[Profile] = TypeAdapter(Profile)


def parse_profile(data: object) -> Profile:
    """Validate already-loaded YAML data (an empty file loads as None)."""
    return _PROFILE_ADAPTER.validate_python(data or {})


def read_config_file(path: Path) -> Profile:
    """Read and validate one config YAML, without any placeholder
    substitution (see engine._load_yaml for that)."""
    return parse_profile(yaml.safe_load(path.read_text(encoding="utf-8")))


def required_str(entry: Mapping[str, object], key: str) -> str:
    """entry[key] for a key the caller can't do without. A missing key raises
    KeyError, the same as plain indexing always did; validation already
    guarantees the value is a string when present."""
    value = entry[key]
    if not isinstance(value, str):
        raise TypeError(f"{key!r} must be a string, got {value!r}")
    return value
