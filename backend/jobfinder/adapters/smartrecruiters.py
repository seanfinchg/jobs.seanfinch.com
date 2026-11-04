from __future__ import annotations

from jobfinder.adapters.base import Adapter, ApiModel
from jobfinder.adapters.greenhouse import strip_html
from jobfinder.adapters.registry import register
from jobfinder.config import Board, required_str
from jobfinder.http import session
from jobfinder.models import RawJob

POSTINGS_URL = "https://api.smartrecruiters.com/v1/companies/{token}/postings"
# Confirmed live: unlike Workable (no documented detail endpoint at all --
# checked while building this), SmartRecruiters has a real per-posting
# detail endpoint with the full description, just not on the list endpoint.
POSTING_URL = "https://api.smartrecruiters.com/v1/companies/{token}/postings/{posting_id}"


class _SmartLocation(ApiModel):
    fullLocation: str | None = ""


class _SmartLabel(ApiModel):
    label: str | None = None


class _SmartPosting(ApiModel):
    id: str | None = ""
    name: str | None = ""
    releasedDate: str | None = None
    location: _SmartLocation | None = None
    function: _SmartLabel | None = None


class _SmartPostings(ApiModel):
    content: list[_SmartPosting] = []


class _SmartSection(ApiModel):
    text: str | None = None


class _SmartJobAd(ApiModel):
    sections: dict[str, _SmartSection] | None = None


class _SmartPostingDetail(ApiModel):
    jobAd: _SmartJobAd | None = None


@register
class SmartRecruitersAdapter(Adapter):
    name = "smartrecruiters"

    def fetch(self, board: Board) -> list[RawJob]:
        token = required_str(board, "token")
        company = board.get("company", token)

        resp = session.get(POSTINGS_URL.format(token=token), timeout=15)
        resp.raise_for_status()
        payload = _SmartPostings.model_validate(resp.json())

        # The list endpoint doesn't include the job description -- fetch_body()
        # below covers it lazily (see engine.run()), only for postings that
        # already cleared the cheap title/location filters.
        jobs: list[RawJob] = []
        for item in payload.content:
            location = item.location.fullLocation if item.location else ""
            # "department" is a free-text field real customers leave empty in
            # practice (confirmed live across several boards) -- "function"
            # is SmartRecruiters' own fixed taxonomy field and is what's
            # actually populated, so it's the real department-equivalent
            # signal here.
            team = item.function.label if item.function else None
            jobs.append(
                RawJob(
                    adapter=self.name,
                    company=company,
                    board_token=token,
                    external_id=str(item.id),
                    title=item.name or "",
                    location=location or "",
                    url=f"https://jobs.smartrecruiters.com/{token}/{item.id}",
                    body="",
                    posted_at=item.releasedDate,
                    team=team or None,
                )
            )
        return jobs

    def fetch_body(self, job: RawJob) -> str | None:
        resp = session.get(
            POSTING_URL.format(token=job.board_token, posting_id=job.external_id), timeout=15
        )
        resp.raise_for_status()
        detail = _SmartPostingDetail.model_validate(resp.json())
        sections = (detail.jobAd or _SmartJobAd()).sections or {}
        texts = [strip_html(section.text or "") for section in sections.values()]
        return " ".join(text for text in texts if text)
