from __future__ import annotations

import re
import time
from datetime import datetime, timedelta, timezone

from jobfinder.adapters.base import Adapter
from jobfinder.adapters.registry import register
from jobfinder.http import session
from jobfinder.models import RawJob

# A large tenant (Jabil's ~1,930 postings, Micron's ~2,790) means dozens to
# well over a hundred paginated requests to the *same* host with zero delay
# otherwise -- a much tighter, more repetitive burst against one host than
# engine.py's own inter-board delay (which only ever hits a given host once
# per run) was ever designed to cover. Found while investigating a real
# rate-limiting incident on a live run.
PAGE_DELAY_SECONDS = 0.3

# Corrected assumption from an earlier version of this file: every
# Workday-hosted career site IS backed by a real, unauthenticated JSON
# endpoint -- the same one the site's own search box calls (POST, no login
# required). Confirmed live against a real tenant
# (salesforce.wd12.myworkdayjobs.com/External_Career_Site) before writing
# this. Needs a board config with `token` (used the same way every other
# adapter uses it -- health tracking, stale-sighting closure -- pick
# something short and stable, e.g. the tenant name) plus the three
# identifiers the URL itself needs: `tenant`, `wd` (the pod, e.g. "wd12"),
# `site`.
JOBS_URL = "https://{tenant}.{wd}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs"
PAGE_LIMIT = 20

WORKDAY_HOST_MARKER = "myworkdayjobs.com"

# The three board identifiers a fresh Workday tenant needs (tenant/wd/site)
# aren't guessable the way a single-slug adapter's token is -- but a real
# apply URL already contains all three, so any URL sighted via another
# source (the simplify_listings aggregator, most often) can be reverse-
# engineered into a full board entry with zero new requests. See
# scripts/discover_tokens.py's discover_from_aggregator(), which uses this.
#
# Some tenants' human-facing URLs insert a locale segment (e.g. "en-US")
# between the pod and the real site name -- confirmed live that the actual
# `site` the /wday/cxs/ API wants is the segment right before "/job/", not
# whatever comes right after the pod (leidos.wd5.myworkdayjobs.com/en-US/
# external/job/... needs site="external", not "en-US"; POSTing with "en-US"
# as the site 404s). The optional locale group only matches the standard
# xx-XX shape so it doesn't accidentally eat a real site name that happens
# to be short.
_URL_RE = re.compile(
    r"https?://([^./]+)\.(wd\d+)\.myworkdayjobs\.com/(?:[a-z]{2}-[A-Z]{2}/)?([^/]+)/job/"
)


def is_workday_url(url: str) -> bool:
    return WORKDAY_HOST_MARKER in url


def parse_workday_url(url: str) -> dict[str, str] | None:
    match = _URL_RE.search(url or "")
    if not match:
        return None
    tenant, wd, site = match.groups()
    return {"tenant": tenant, "wd": wd, "site": site}


def _parse_posted_on(text: str) -> str | None:
    """Workday returns a relative human string ("Posted Today", "Posted 3
    Days Ago", "Posted 30+ Days Ago"), never a real date -- best-effort
    parse only, same spirit as this repo's salary extraction."""
    text = (text or "").strip().lower()
    now = datetime.now(timezone.utc)
    if text == "posted today":
        return now.isoformat()
    if text == "posted yesterday":
        return (now - timedelta(days=1)).isoformat()
    match = re.search(r"posted (\d+)\+? days? ago", text)
    if match:
        return (now - timedelta(days=int(match.group(1)))).isoformat()
    return None


@register
class WorkdayAdapter(Adapter):
    name = "workday"

    def fetch(self, board: dict) -> list[RawJob]:
        tenant, wd, site = board["tenant"], board["wd"], board["site"]
        token = board["token"]
        company = board.get("company", tenant)
        base_url = f"https://{tenant}.{wd}.myworkdayjobs.com/{site}"

        jobs: list[RawJob] = []
        offset = 0
        while True:
            resp = session.post(
                JOBS_URL.format(tenant=tenant, wd=wd, site=site),
                json={"appliedFacets": {}, "limit": PAGE_LIMIT, "offset": offset, "searchText": ""},
                timeout=15,
            )
            resp.raise_for_status()
            postings = resp.json().get("jobPostings", [])

            for item in postings:
                bullet_fields = item.get("bulletFields") or []
                external_id = bullet_fields[0] if bullet_fields else item.get("externalPath", "")
                jobs.append(
                    RawJob(
                        adapter=self.name,
                        company=company,
                        board_token=token,
                        external_id=external_id,
                        title=item.get("title", ""),
                        location=item.get("locationsText", ""),
                        url=base_url + item.get("externalPath", ""),
                        posted_at=_parse_posted_on(item.get("postedOn", "")),
                    )
                )

            if len(postings) < PAGE_LIMIT:
                break
            offset += PAGE_LIMIT
            time.sleep(PAGE_DELAY_SECONDS)

        return jobs
