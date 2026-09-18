from __future__ import annotations

from html.parser import HTMLParser

from jobfinder.adapters.base import Adapter
from jobfinder.adapters.registry import register
from jobfinder.http import session
from jobfinder.models import RawJob

JOBS_URL = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs"
JOB_URL = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs/{job_id}"


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.chunks: list[str] = []

    def handle_data(self, data: str) -> None:
        self.chunks.append(data)


def strip_html(raw: str) -> str:
    parser = _TextExtractor()
    parser.feed(raw)
    return " ".join(chunk.strip() for chunk in parser.chunks if chunk.strip())


@register
class GreenhouseAdapter(Adapter):
    name = "greenhouse"

    def fetch(self, board: dict) -> list[RawJob]:
        token = board["token"]
        company = board.get("company", token)

        resp = session.get(JOBS_URL.format(token=token), params={"content": "true"}, timeout=15)
        resp.raise_for_status()
        payload = resp.json()

        jobs = []
        for item in payload.get("jobs", []):
            location = (item.get("location") or {}).get("name", "")
            departments = item.get("departments") or []
            jobs.append(
                RawJob(
                    adapter=self.name,
                    company=company,
                    board_token=token,
                    external_id=str(item["id"]),
                    title=item.get("title", ""),
                    location=location,
                    url=item.get("absolute_url", ""),
                    body=strip_html(item.get("content") or ""),
                    posted_at=item.get("updated_at"),
                    team=departments[0].get("name") if departments else None,
                )
            )
        return jobs

    def fetch_questions(self, job: RawJob) -> list[dict] | None:
        resp = session.get(
            JOB_URL.format(token=job.board_token, job_id=job.external_id),
            params={"questions": "true"},
            timeout=15,
        )
        resp.raise_for_status()
        payload = resp.json()

        questions = []
        for q in payload.get("questions", []):
            field = (q.get("fields") or [{}])[0]
            questions.append(
                {
                    "name": field.get("name", ""),
                    "label": q.get("label", ""),
                    "field_type": field.get("type", ""),
                    "required": bool(q.get("required")),
                    "values": [v.get("label") for v in (field.get("values") or [])],
                }
            )
        return questions
