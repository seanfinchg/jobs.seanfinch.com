from __future__ import annotations

from datetime import UTC, datetime

from pydantic import TypeAdapter

from jobfinder.adapters.base import Adapter, ApiModel
from jobfinder.adapters.registry import register
from jobfinder.config import Board, required_str
from jobfinder.http import session
from jobfinder.models import RawJob

POSTINGS_URL = "https://api.lever.co/v0/postings/{token}?mode=json"


class _LeverCategories(ApiModel):
    location: str | None = ""
    team: str | None = None


class _LeverPosting(ApiModel):
    id: str | None = ""
    text: str | None = ""
    hostedUrl: str | None = ""
    descriptionPlain: str | None = ""
    createdAt: float | None = None
    categories: _LeverCategories | None = None


_POSTINGS = TypeAdapter(list[_LeverPosting])


@register
class LeverAdapter(Adapter):
    name = "lever"

    def fetch(self, board: Board) -> list[RawJob]:
        token = required_str(board, "token")
        company = board.get("company", token)

        resp = session.get(POSTINGS_URL.format(token=token), timeout=15)
        resp.raise_for_status()
        postings = _POSTINGS.validate_python(resp.json())

        jobs: list[RawJob] = []
        for item in postings:
            created_ms = item.createdAt
            categories = item.categories or _LeverCategories(location="")
            posted_at = (
                datetime.fromtimestamp(created_ms / 1000, tz=UTC).isoformat()
                if created_ms
                else None
            )
            jobs.append(
                RawJob(
                    adapter=self.name,
                    company=company,
                    board_token=token,
                    external_id=item.id or "",
                    title=item.text or "",
                    location=categories.location or "",
                    url=item.hostedUrl or "",
                    body=item.descriptionPlain or "",
                    posted_at=posted_at,
                    team=categories.team or None,
                )
            )
        return jobs
