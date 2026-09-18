from __future__ import annotations

from jobfinder.adapters.base import Adapter
from jobfinder.adapters.greenhouse import strip_html
from jobfinder.adapters.registry import register
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


def _location_str(item: dict) -> str:
    location = item.get("location") or {}
    parts = [location.get("city"), location.get("state")]
    if not any(parts):
        ats_location = item.get("atsLocation") or {}
        parts = [ats_location.get("city"), ats_location.get("state"), ats_location.get("country")]
    return ", ".join(part for part in parts if part)


@register
class BambooHRAdapter(Adapter):
    name = "bamboohr"

    def fetch(self, board: dict) -> list[RawJob]:
        token = board["token"]
        company = board.get("company", token)

        resp = session.get(LIST_URL.format(token=token), timeout=15)
        resp.raise_for_status()
        payload = resp.json()

        jobs = []
        for item in payload.get("result", []):
            job_id = str(item.get("id", ""))
            jobs.append(
                RawJob(
                    adapter=self.name,
                    company=company,
                    board_token=token,
                    external_id=job_id,
                    title=(item.get("jobOpeningName") or "").strip(),
                    location=_location_str(item),
                    url=f"https://{token}.bamboohr.com/careers/{job_id}",
                    body="",
                    team=item.get("departmentLabel") or None,
                )
            )
        return jobs

    def fetch_body(self, job: RawJob) -> str | None:
        resp = session.get(DETAIL_URL.format(token=job.board_token, job_id=job.external_id), timeout=15)
        resp.raise_for_status()
        job_opening = (resp.json().get("result") or {}).get("jobOpening") or {}
        return strip_html(job_opening.get("description") or "")
