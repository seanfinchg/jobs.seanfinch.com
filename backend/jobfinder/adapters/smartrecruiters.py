from __future__ import annotations

from jobfinder.adapters.base import Adapter
from jobfinder.adapters.greenhouse import strip_html
from jobfinder.adapters.registry import register
from jobfinder.http import session
from jobfinder.models import RawJob

POSTINGS_URL = "https://api.smartrecruiters.com/v1/companies/{token}/postings"
# Confirmed live: unlike Workable (no documented detail endpoint at all --
# checked while building this), SmartRecruiters has a real per-posting
# detail endpoint with the full description, just not on the list endpoint.
POSTING_URL = "https://api.smartrecruiters.com/v1/companies/{token}/postings/{posting_id}"


@register
class SmartRecruitersAdapter(Adapter):
    name = "smartrecruiters"

    def fetch(self, board: dict) -> list[RawJob]:
        token = board["token"]
        company = board.get("company", token)

        resp = session.get(POSTINGS_URL.format(token=token), timeout=15)
        resp.raise_for_status()
        payload = resp.json()

        # The list endpoint doesn't include the job description -- fetch_body()
        # below covers it lazily (see engine.run()), only for postings that
        # already cleared the cheap title/location filters.
        jobs = []
        for item in payload.get("content", []):
            location = (item.get("location") or {}).get("fullLocation", "")
            # "department" is a free-text field real customers leave empty in
            # practice (confirmed live across several boards) -- "function"
            # is SmartRecruiters' own fixed taxonomy field and is what's
            # actually populated, so it's the real department-equivalent
            # signal here.
            team = (item.get("function") or {}).get("label")
            jobs.append(
                RawJob(
                    adapter=self.name,
                    company=company,
                    board_token=token,
                    external_id=str(item.get("id", "")),
                    title=item.get("name", ""),
                    location=location,
                    url=f"https://jobs.smartrecruiters.com/{token}/{item.get('id', '')}",
                    body="",
                    posted_at=item.get("releasedDate"),
                    team=team or None,
                )
            )
        return jobs

    def fetch_body(self, job: RawJob) -> str | None:
        resp = session.get(
            POSTING_URL.format(token=job.board_token, posting_id=job.external_id), timeout=15
        )
        resp.raise_for_status()
        sections = (resp.json().get("jobAd") or {}).get("sections") or {}
        texts = [strip_html(section.get("text") or "") for section in sections.values()]
        return " ".join(text for text in texts if text)
