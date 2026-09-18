"""Local-only, never runs in CI (same spirit as apply.py/seed_answers.py).

Confirms real ATS board tokens against live endpoints instead of guessing.
Two modes:

  python scripts/discover_tokens.py --from-aggregator
      Zero requests -- reverse-engineers adapter+token straight out of
      apply URLs already collected via the simplify_listings aggregator.

  python scripts/discover_tokens.py "Company A" "Company B" ...
      Tries slug variants of each name against every adapter's real
      endpoint, live.

Never writes a board YAML file directly -- prints a ready-to-paste
fragment; a human reviews and pastes it into boards/broad-tech.yaml, same
convention that file's own comments already use.
"""

from __future__ import annotations

import re
import sys
import time
from collections.abc import Callable

import requests
import yaml

TIMEOUT = 15
SLEEP_BETWEEN_REQUESTS = 0.3

_STRIP_SUFFIXES = [" inc", " corp", " corporation", " co", " llc", " ltd", " limited", " company"]


def slug_variants(company_name: str) -> list[str]:
    base = re.sub(r"[,.]", "", company_name.strip().lower())
    for suffix in _STRIP_SUFFIXES:
        if base.endswith(suffix):
            base = base[: -len(suffix)]
            break
    base = base.strip()
    variants = {re.sub(r"\s+", "", base), re.sub(r"\s+", "-", base)}
    return sorted(v for v in variants if v)


def _probe_greenhouse(slug: str) -> tuple[bool, int]:
    resp = requests.get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs", timeout=TIMEOUT)
    if resp.status_code != 200:
        return False, 0
    jobs = resp.json().get("jobs", [])
    return bool(jobs), len(jobs)


def _probe_lever(slug: str) -> tuple[bool, int]:
    resp = requests.get(f"https://api.lever.co/v0/postings/{slug}?mode=json", timeout=TIMEOUT)
    if resp.status_code != 200:
        return False, 0
    jobs = resp.json()
    return (bool(jobs), len(jobs)) if isinstance(jobs, list) else (False, 0)


def _probe_ashby(slug: str) -> tuple[bool, int]:
    resp = requests.get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}", timeout=TIMEOUT)
    if resp.status_code != 200:
        return False, 0
    jobs = resp.json().get("jobs", [])
    return bool(jobs), len(jobs)


def _probe_smartrecruiters(slug: str) -> tuple[bool, int]:
    resp = requests.get(f"https://api.smartrecruiters.com/v1/companies/{slug}/postings", timeout=TIMEOUT)
    if resp.status_code != 200:
        return False, 0
    jobs = resp.json().get("content", [])
    return bool(jobs), len(jobs)


def _probe_workable(slug: str) -> tuple[bool, int]:
    resp = requests.post(
        f"https://apply.workable.com/api/v3/accounts/{slug}/jobs",
        json={"query": "", "location": [], "department": [], "worktype": [], "remote": []},
        headers={"Content-Type": "application/json"},
        timeout=TIMEOUT,
    )
    if resp.status_code != 200:
        return False, 0
    jobs = resp.json().get("results", [])
    return bool(jobs), len(jobs)


def _probe_rippling(slug: str) -> tuple[bool, int]:
    resp = requests.get(f"https://api.rippling.com/platform/api/ats/v1/board/{slug}/jobs", timeout=TIMEOUT)
    if resp.status_code != 200:
        return False, 0
    jobs = resp.json()
    return (bool(jobs), len(jobs)) if isinstance(jobs, list) else (False, 0)


def _probe_bamboohr(slug: str) -> tuple[bool, int]:
    resp = requests.get(f"https://{slug}.bamboohr.com/careers/list", timeout=TIMEOUT)
    if resp.status_code != 200:
        return False, 0
    payload = resp.json()
    count = (payload.get("meta") or {}).get("totalCount", 0)
    return bool(count), count


ADAPTER_PROBES: dict[str, Callable[[str], tuple[bool, int]]] = {
    "greenhouse": _probe_greenhouse,
    "lever": _probe_lever,
    "ashby": _probe_ashby,
    "smartrecruiters": _probe_smartrecruiters,
    "workable": _probe_workable,
    "rippling": _probe_rippling,
    "bamboohr": _probe_bamboohr,
}


def probe_company(company_name: str, *, sleep: float = SLEEP_BETWEEN_REQUESTS) -> list[dict]:
    hits = []
    for slug in slug_variants(company_name):
        for adapter, probe in ADAPTER_PROBES.items():
            try:
                confirmed, job_count = probe(slug)
            except requests.RequestException:
                confirmed, job_count = False, 0
            time.sleep(sleep)
            if confirmed:
                hits.append({"company": company_name, "adapter": adapter, "token": slug, "job_count": job_count})
    return hits


# Recognizable per-adapter URL fingerprints, for reverse-engineering a token
# out of an apply URL with zero requests.
_URL_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("ashby", re.compile(r"jobs\.ashbyhq\.com/([^/]+)/")),
    ("greenhouse", re.compile(r"boards\.greenhouse\.io/([^/]+)/")),
    ("lever", re.compile(r"jobs\.lever\.co/([^/]+)/")),
    ("workable", re.compile(r"apply\.workable\.com/([^/]+)/")),
    ("smartrecruiters", re.compile(r"jobs\.smartrecruiters\.com/([^/]+)/")),
    ("rippling", re.compile(r"ats\.rippling\.com/([^/]+)/")),
    ("bamboohr", re.compile(r"https?://([^./]+)\.bamboohr\.com/careers/")),
]


def discover_from_aggregator(db_path: str = "jobfinder.db") -> list[dict]:
    from jobfinder.adapters.workday import parse_workday_url
    from jobfinder import db as jobfinder_db

    conn = jobfinder_db.connect(db_path)
    rows = conn.execute(
        "SELECT DISTINCT jobs.company, sightings.apply_url FROM jobs "
        "JOIN sightings USING (content_hash) "
        "WHERE sightings.adapter = 'simplify_listings'"
    ).fetchall()
    conn.close()

    seen: set[tuple] = set()
    hits = []
    for row in rows:
        url = row["apply_url"] or ""

        # Workday needs three identifiers, not one guessable slug -- handled
        # separately since it doesn't fit the single-capture-group patterns
        # below, but a real apply URL spells out tenant/wd/site directly.
        workday_ids = parse_workday_url(url)
        if workday_ids:
            key = ("workday", workday_ids["tenant"], workday_ids["wd"], workday_ids["site"])
            if key not in seen:
                seen.add(key)
                hits.append({"company": row["company"], "adapter": "workday", "job_count": None, **workday_ids})
            continue

        for adapter, pattern in _URL_PATTERNS:
            match = pattern.search(url)
            if not match:
                continue
            token = match.group(1)
            if (adapter, token) in seen:
                continue
            seen.add((adapter, token))
            hits.append({"company": row["company"], "adapter": adapter, "token": token, "job_count": None})
    return hits


def _print_yaml_fragment(hits: list[dict]) -> None:
    by_adapter: dict[str, list[dict]] = {}
    for hit in hits:
        by_adapter.setdefault(hit["adapter"], []).append(hit)

    for adapter, adapter_hits in sorted(by_adapter.items()):
        print(f"  {adapter}:")
        for hit in adapter_hits:
            note = f"{hit['job_count']} jobs" if hit.get("job_count") is not None else "via aggregator"
            if adapter == "workday":
                entry = {
                    "company": hit["company"], "token": hit["tenant"],
                    "tenant": hit["tenant"], "wd": hit["wd"], "site": hit["site"],
                }
            else:
                entry = {"company": hit["company"], "token": hit["token"]}
            # width=1000 avoids yaml.safe_dump wrapping a long flow-style
            # entry (workday's 5 keys) across multiple lines -- this is
            # meant to be a ready-to-paste single-line fragment.
            flow = yaml.safe_dump(entry, default_flow_style=True, width=1000).strip()
            print(f"    - {flow}  # {note}")


def main(argv: list[str]) -> None:
    if not argv:
        print("usage: discover_tokens.py --from-aggregator | <company name> [<company name> ...]", file=sys.stderr)
        raise SystemExit(1)

    if argv[0] == "--from-aggregator":
        hits = discover_from_aggregator()
    else:
        hits = []
        for name in argv:
            hits.extend(probe_company(name))

    if not hits:
        print("no confirmed hits", file=sys.stderr)
        return

    _print_yaml_fragment(hits)


if __name__ == "__main__":
    main(sys.argv[1:])
