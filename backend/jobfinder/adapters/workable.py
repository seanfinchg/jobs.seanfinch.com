from __future__ import annotations

from jobfinder.adapters.base import Adapter
from jobfinder.adapters.registry import register
from jobfinder.http import session
from jobfinder.models import RawJob

JOBS_URL = "https://apply.workable.com/api/v3/accounts/{token}/jobs"


@register
class WorkableAdapter(Adapter):
    name = "workable"

    def fetch(self, board: dict) -> list[RawJob]:
        token = board["token"]
        company = board.get("company", token)

        resp = session.post(
            JOBS_URL.format(token=token),
            json={"query": "", "location": [], "department": [], "worktype": [], "remote": []},
            headers={"Content-Type": "application/json"},
            timeout=15,
        )
        resp.raise_for_status()
        payload = resp.json()

        # Same tradeoff as smartrecruiters: the search endpoint has no
        # description field and there's no documented public detail endpoint,
        # so body stays empty. Title/location filtering is unaffected.
        # (Confirmed again while building fetch_body() for smartrecruiters/
        # bamboohr: neither /api/v3/accounts/{token}/jobs/{shortcode} nor a
        # widget-style detail path returns JSON for Workable -- still no real
        # per-posting endpoint.)
        #
        # `team` is left unset here too, not because the field doesn't exist
        # (the search POST body's `department: []` filter param implies the
        # results carry one) but because live verification hit Workable's
        # rate limit (429, Retry-After ~8.4 hours) mid-session --
        # not worth guessing the field's exact shape unverified. Revisit and
        # confirm live before adding it.
        jobs = []
        for item in payload.get("results", []):
            location = item.get("location") or {}
            location_str = ", ".join(part for part in [location.get("city"), location.get("country")] if part)
            jobs.append(
                RawJob(
                    adapter=self.name,
                    company=company,
                    board_token=token,
                    external_id=item.get("shortcode", ""),
                    title=item.get("title", ""),
                    location=location_str,
                    url=f"https://apply.workable.com/{token}/j/{item.get('shortcode', '')}/",
                    body="",
                    posted_at=item.get("published"),
                )
            )
        return jobs
