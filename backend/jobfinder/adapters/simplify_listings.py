from __future__ import annotations

from datetime import datetime, timezone

from jobfinder.adapters.base import Adapter
from jobfinder.adapters.registry import register
from jobfinder.http import session
from jobfinder.models import RawJob

LISTINGS_PATH = ".github/scripts/listings.json"
NEW_GRAD_REPO = "SimplifyJobs/New-Grad-Positions"


def _repo_for(season: str, year: int | None) -> str:
    """SimplifyJobs runs one evergreen new-grad repo and a fresh
    Summer<year>-Internships repo each year -- both publish the same
    generated listings.json on their `dev` branch. `year` moves this
    forward every season by editing the board config, not the adapter."""
    if season == "new-grad":
        return NEW_GRAD_REPO
    if season == "summer-internship":
        if not year:
            raise ValueError("simplify_listings board with season=summer-internship needs a year")
        return f"SimplifyJobs/Summer{year}-Internships"
    raise ValueError(f"unknown simplify_listings season {season!r}")


@register
class SimplifyListingsAdapter(Adapter):
    """Aggregator, not a real ATS: each entry's url already points at the
    underlying board (Greenhouse, Lever, Workday, ...). Useful for spotting
    postings/tokens the other adapters don't have configured yet, not as a
    primary source -- so it never wins the native-apply_url tiebreak in dedup.
    """

    name = "simplify_listings"
    is_native = False

    def fetch(self, board: dict) -> list[RawJob]:
        token = board.get("token", "new-grad")
        url = board.get("url")
        if not url:
            repo = _repo_for(board.get("season", "new-grad"), board.get("year"))
            url = f"https://raw.githubusercontent.com/{repo}/dev/{LISTINGS_PATH}"

        resp = session.get(url, timeout=30)
        resp.raise_for_status()
        entries = resp.json()

        jobs = []
        for entry in entries:
            if not entry.get("active", True):
                continue
            posted_ms = entry.get("date_posted")
            posted_at = (
                datetime.fromtimestamp(posted_ms, tz=timezone.utc).isoformat()
                if posted_ms
                else None
            )
            locations = entry.get("locations") or []
            jobs.append(
                RawJob(
                    adapter=self.name,
                    company=entry.get("company_name", ""),
                    board_token=token,
                    external_id=entry.get("id", ""),
                    title=entry.get("title", ""),
                    location="; ".join(locations),
                    url=entry.get("url", ""),
                    body="",
                    posted_at=posted_at,
                )
            )
        return jobs
