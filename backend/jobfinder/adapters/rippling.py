from __future__ import annotations

from jobfinder.adapters.base import Adapter
from jobfinder.adapters.registry import register
from jobfinder.http import session
from jobfinder.models import RawJob

# Confirmed live against a real board (Rippling's own careers page, which
# runs on Rippling's own ATS): a flat JSON list, no auth, no description
# text and no posted-date field in this response at all -- same body-less
# shape as smartrecruiters/workable, so body_bonus/body_exclude/salary
# extraction never fire for jobs from this adapter either.
BOARD_URL = "https://api.rippling.com/platform/api/ats/v1/board/{board_slug}/jobs"


@register
class RipplingAdapter(Adapter):
    name = "rippling"

    def fetch(self, board: dict) -> list[RawJob]:
        slug = board["token"]
        company = board.get("company", slug)

        resp = session.get(BOARD_URL.format(board_slug=slug), timeout=15)
        resp.raise_for_status()
        items = resp.json()

        jobs = []
        for item in items:
            location = item.get("workLocation") or {}
            jobs.append(
                RawJob(
                    adapter=self.name,
                    company=company,
                    board_token=slug,
                    external_id=item.get("uuid", ""),
                    title=item.get("name", ""),
                    location=location.get("label", ""),
                    url=item.get("url", ""),
                    posted_at=None,
                    team=(item.get("department") or {}).get("label") or None,
                )
            )
        return jobs
