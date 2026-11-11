from __future__ import annotations

from jobfinder.adapters.base import Adapter, ApiModel
from jobfinder.adapters.greenhouse import strip_html
from jobfinder.adapters.registry import register
from jobfinder.config import Board, required_str
from jobfinder.http import session
from jobfinder.models import RawJob

BOARD_URL = "https://api.ashbyhq.com/posting-api/job-board/{token}"


class _AshbyJob(ApiModel):
    id: str | None = ""
    title: str | None = ""
    location: str | None = ""
    jobUrl: str | None = ""
    descriptionHtml: str | None = None
    publishedAt: str | None = None
    department: str | None = None


class _AshbyBoard(ApiModel):
    jobs: list[_AshbyJob] = []


@register
class AshbyAdapter(Adapter):
    name = "ashby"

    def fetch(self, board: Board) -> list[RawJob]:
        token = required_str(board, "token")
        company = board.get("company", token)

        resp = session.get(BOARD_URL.format(token=token), timeout=15)
        resp.raise_for_status()
        payload = _AshbyBoard.model_validate(resp.json())

        jobs: list[RawJob] = []
        for item in payload.jobs:
            jobs.append(
                RawJob(
                    adapter=self.name,
                    company=company,
                    board_token=token,
                    external_id=item.id or "",
                    title=item.title or "",
                    location=item.location or "",
                    url=item.jobUrl or "",
                    body=strip_html(item.descriptionHtml or ""),
                    posted_at=item.publishedAt,
                    team=item.department or None,
                )
            )
        return jobs
