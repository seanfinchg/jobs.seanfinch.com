from __future__ import annotations

from jobfinder.adapters.base import Adapter
from jobfinder.adapters.registry import register
from jobfinder.adapters.greenhouse import strip_html
from jobfinder.http import session
from jobfinder.models import RawJob

BOARD_URL = "https://api.ashbyhq.com/posting-api/job-board/{token}"


@register
class AshbyAdapter(Adapter):
    name = "ashby"

    def fetch(self, board: dict) -> list[RawJob]:
        token = board["token"]
        company = board.get("company", token)

        resp = session.get(BOARD_URL.format(token=token), timeout=15)
        resp.raise_for_status()
        payload = resp.json()

        jobs = []
        for item in payload.get("jobs", []):
            jobs.append(
                RawJob(
                    adapter=self.name,
                    company=company,
                    board_token=token,
                    external_id=item.get("id", ""),
                    title=item.get("title", ""),
                    location=item.get("location", ""),
                    url=item.get("jobUrl", ""),
                    body=strip_html(item.get("descriptionHtml") or ""),
                    posted_at=item.get("publishedAt"),
                    team=item.get("department") or None,
                )
            )
        return jobs
