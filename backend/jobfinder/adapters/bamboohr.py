from __future__ import annotations

from jobfinder.adapters.base import Adapter, ApiModel
from jobfinder.adapters.greenhouse import strip_html
from jobfinder.adapters.registry import register
from jobfinder.config import Board, required_str
from jobfinder.http import session
from jobfinder.models import RawJob

# Spike result: the embed widget (/jobs/embed2.php) returns pre-rendered
# HTML, not JSON -- not worth parsing. The board itself is also
# backed by a real, unauthenticated JSON endpoint though, confirmed live
# against several real tenants pulled from simplify_listings aggregator data
# (asuresoftware, lexical, alkira, nexthopai, fullbay, ...). No description
# text in this list response -- fetch_body() below covers it lazily via the
# confirmed-live /careers/{id}/detail endpoint (see engine.run()).
LIST_URL = "https://{token}.bamboohr.com/careers/list"
DETAIL_URL = "https://{token}.bamboohr.com/careers/{job_id}/detail"


class _BambooLocation(ApiModel):
    city: str | None = None
    state: str | None = None
    country: str | None = None


class _BambooItem(ApiModel):
    id: str | None = ""
    jobOpeningName: str | None = None
    departmentLabel: str | None = None
    location: _BambooLocation | None = None
    atsLocation: _BambooLocation | None = None


class _BambooList(ApiModel):
    result: list[_BambooItem] = []


class _BambooOpening(ApiModel):
    description: str | None = None


class _BambooDetailResult(ApiModel):
    jobOpening: _BambooOpening | None = None


class _BambooDetail(ApiModel):
    result: _BambooDetailResult | None = None


def _location_str(item: _BambooItem) -> str:
    location = item.location or _BambooLocation()
    parts = [location.city, location.state]
    if not any(parts):
        ats_location = item.atsLocation or _BambooLocation()
        parts = [ats_location.city, ats_location.state, ats_location.country]
    return ", ".join(part for part in parts if part)


@register
class BambooHRAdapter(Adapter):
    name = "bamboohr"

    def fetch(self, board: Board) -> list[RawJob]:
        token = required_str(board, "token")
        company = board.get("company", token)

        resp = session.get(LIST_URL.format(token=token), timeout=15)
        resp.raise_for_status()
        payload = _BambooList.model_validate(resp.json())

        jobs: list[RawJob] = []
        for item in payload.result:
            job_id = str(item.id)
            jobs.append(
                RawJob(
                    adapter=self.name,
                    company=company,
                    board_token=token,
                    external_id=job_id,
                    title=(item.jobOpeningName or "").strip(),
                    location=_location_str(item),
                    url=f"https://{token}.bamboohr.com/careers/{job_id}",
                    body="",
                    team=item.departmentLabel or None,
                )
            )
        return jobs

    def fetch_body(self, job: RawJob) -> str | None:
        resp = session.get(
            DETAIL_URL.format(token=job.board_token, job_id=job.external_id), timeout=15
        )
        resp.raise_for_status()
        detail = _BambooDetail.model_validate(resp.json())
        job_opening = (detail.result or _BambooDetailResult()).jobOpening or _BambooOpening()
        return strip_html(job_opening.description or "")
