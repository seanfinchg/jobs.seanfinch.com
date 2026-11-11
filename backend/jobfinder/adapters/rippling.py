from __future__ import annotations

from pydantic import TypeAdapter

from jobfinder.adapters.base import Adapter, ApiModel
from jobfinder.adapters.registry import register
from jobfinder.config import Board, required_str
from jobfinder.http import session
from jobfinder.models import RawJob

# Confirmed live against a real board (Rippling's own careers page, which
# runs on Rippling's own ATS): a flat JSON list, no auth, no description
# text and no posted-date field in this response at all -- same body-less
# shape as smartrecruiters/workable, so body_bonus/body_exclude/salary
# extraction never fire for jobs from this adapter either.
BOARD_URL = "https://api.rippling.com/platform/api/ats/v1/board/{board_slug}/jobs"


class _RipplingLabel(ApiModel):
    label: str | None = None


class _RipplingJob(ApiModel):
    uuid: str | None = ""
    name: str | None = ""
    url: str | None = ""
    workLocation: _RipplingLabel | None = None
    department: _RipplingLabel | None = None


_JOBS = TypeAdapter(list[_RipplingJob])


@register
class RipplingAdapter(Adapter):
    name = "rippling"

    def fetch(self, board: Board) -> list[RawJob]:
        slug = required_str(board, "token")
        company = board.get("company", slug)

        resp = session.get(BOARD_URL.format(board_slug=slug), timeout=15)
        resp.raise_for_status()
        items = _JOBS.validate_python(resp.json())

        jobs: list[RawJob] = []
        for item in items:
            location = item.workLocation.label if item.workLocation else ""
            jobs.append(
                RawJob(
                    adapter=self.name,
                    company=company,
                    board_token=slug,
                    external_id=item.uuid or "",
                    title=item.name or "",
                    location=location or "",
                    url=item.url or "",
                    posted_at=None,
                    team=(item.department.label if item.department else None) or None,
                )
            )
        return jobs
