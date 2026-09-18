from __future__ import annotations

from datetime import datetime, timezone

from jobfinder.adapters.base import Adapter
from jobfinder.adapters.registry import register
from jobfinder.http import session
from jobfinder.models import RawJob

POSTINGS_URL = "https://api.lever.co/v0/postings/{token}?mode=json"


@register
class LeverAdapter(Adapter):
    name = "lever"

    def fetch(self, board: dict) -> list[RawJob]:
        token = board["token"]
        company = board.get("company", token)

        resp = session.get(POSTINGS_URL.format(token=token), timeout=15)
        resp.raise_for_status()
        postings = resp.json()

        jobs = []
        for item in postings:
            created_ms = item.get("createdAt")
            posted_at = (
                datetime.fromtimestamp(created_ms / 1000, tz=timezone.utc).isoformat()
                if created_ms
                else None
            )
            jobs.append(
                RawJob(
                    adapter=self.name,
                    company=company,
                    board_token=token,
                    external_id=item.get("id", ""),
                    title=item.get("text", ""),
                    location=(item.get("categories") or {}).get("location", ""),
                    url=item.get("hostedUrl", ""),
                    body=item.get("descriptionPlain", "") or "",
                    posted_at=posted_at,
                    team=(item.get("categories") or {}).get("team") or None,
                )
            )
        return jobs
