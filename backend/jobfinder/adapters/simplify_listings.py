from __future__ import annotations

from datetime import UTC, datetime

from pydantic import TypeAdapter

from jobfinder.adapters.base import Adapter, ApiModel
from jobfinder.adapters.registry import register
from jobfinder.config import Board
from jobfinder.http import session
from jobfinder.models import RawJob

LISTINGS_PATH = ".github/scripts/listings.json"
NEW_GRAD_REPO = "SimplifyJobs/New-Grad-Positions"


class _Listing(ApiModel):
    id: str | None = ""
    company_name: str | None = ""
    title: str | None = ""
    url: str | None = ""
    active: bool | None = True
    date_posted: float | None = None
    locations: list[str] | None = None


_LISTINGS = TypeAdapter(list[_Listing])


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

    def fetch(self, board: Board) -> list[RawJob]:
        token = board.get("token", "new-grad")
        url = board.get("url")
        if not url:
            repo = _repo_for(board.get("season", "new-grad"), board.get("year"))
            url = f"https://raw.githubusercontent.com/{repo}/dev/{LISTINGS_PATH}"

        resp = session.get(url, timeout=30)
        resp.raise_for_status()
        entries = _LISTINGS.validate_python(resp.json())

        jobs: list[RawJob] = []
        for entry in entries:
            if not entry.active:
                continue
            posted_ms = entry.date_posted
            posted_at = datetime.fromtimestamp(posted_ms, tz=UTC).isoformat() if posted_ms else None
            locations = entry.locations or []
            jobs.append(
                RawJob(
                    adapter=self.name,
                    company=entry.company_name or "",
                    board_token=token,
                    external_id=entry.id or "",
                    title=entry.title or "",
                    location="; ".join(locations),
                    url=entry.url or "",
                    body="",
                    posted_at=posted_at,
                )
            )
        return jobs
