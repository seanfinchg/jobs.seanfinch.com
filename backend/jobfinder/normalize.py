from __future__ import annotations

import hashlib
import re

# Known abbreviation/variant collisions. Order matters a little (longer,
# more specific patterns first) but nothing here is order-sensitive today.
_TITLE_VARIANTS = {
    r"\bsr\.?\b": "senior",
    r"\bjr\.?\b": "junior",
    r"\bswe\b": "software engineer",
    r"\bsw eng(ineer)?\b": "software engineer",
    r"\bsre\b": "site reliability engineer",
}

_MA_MARKER = r",?\s*(ma\b|massachusetts)"

_LOCATION_BUCKETS: list[tuple[str, list[str]]] = [
    # cambridge/lexington/newton/burlington all name other, more famous
    # places (Cambridge UK, Lexington SC/KY, Newton IA/KS, Burlington VT/ON)
    # -- only bucket them as Boston-area when the state actually says so.
    ("boston", [r"\bboston\b", r"somerville", r"waltham", r"\bmassachusetts\b", r"\bma\b",
                rf"cambridge{_MA_MARKER}", rf"lexington{_MA_MARKER}",
                rf"newton{_MA_MARKER}", rf"burlington{_MA_MARKER}"]),
    ("new york", [r"new york", r"\bnyc\b", r"brooklyn", r"manhattan", r"jersey city",
                  r"\bny\b", r"\bnj\b"]),
    ("sf bay area", [r"san francisco", r"\bsf\b", r"bay area", r"palo alto",
                     r"mountain view", r"sunnyvale", r"santa clara", r"san jose",
                     r"menlo park", r"oakland"]),
    ("socal", [r"los angeles", r"irvine", r"san diego", r"santa monica",
               r"orange county", r"pasadena", r"culver city"]),
    ("seattle", [r"\bseattle\b", r"bellevue", r"redmond"]),
    ("remote-us", [r"remote.*(us|united states)", r"(us|united states).*remote",
                   r"^remote$"]),
    ("remote", [r"remote"]),
]


def norm(text: str) -> str:
    text = (text or "").lower()
    text = re.sub(r"[^\w\s]", " ", text)
    for pattern, replacement in _TITLE_VARIANTS.items():
        text = re.sub(pattern, replacement, text)
    return re.sub(r"\s+", " ", text).strip()


def location_bucket(location: str) -> str:
    text = norm(location)
    for bucket, patterns in _LOCATION_BUCKETS:
        if any(re.search(pattern, text) for pattern in patterns):
            return bucket
    return text or "unspecified"


def content_hash(company: str, title: str, location: str, team: str | None = None) -> str:
    """team folds a coarse department/team label into the dedup key, when an
    adapter's raw API response exposes one (Ashby, Greenhouse, Lever,
    SmartRecruiters, BambooHR, Rippling all do) -- confirmed-low-risk-today
    but real-risk-at-scale collision case: two genuinely different reqs at
    the same company/title/location bucket. Omitting team
    (the default) hashes identically to before this parameter existed, so
    already-ingested rows keep their hash until a full re-ingest recomputes
    it with the richer key."""
    parts = [norm(company), norm(title), location_bucket(location)]
    if team:
        parts.append(norm(team))
    return hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()
