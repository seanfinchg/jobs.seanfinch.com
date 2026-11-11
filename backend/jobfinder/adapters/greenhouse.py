from __future__ import annotations

from html.parser import HTMLParser

from jobfinder.adapters.base import Adapter, ApiModel
from jobfinder.adapters.registry import register
from jobfinder.config import Board, required_str
from jobfinder.http import session
from jobfinder.models import Question, RawJob

JOBS_URL = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs"
JOB_URL = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs/{job_id}"


class _GreenhouseLocation(ApiModel):
    name: str | None = ""


class _GreenhouseDepartment(ApiModel):
    name: str | None = None


class _GreenhouseJob(ApiModel):
    id: int | str
    title: str | None = ""
    absolute_url: str | None = ""
    content: str | None = None
    updated_at: str | None = None
    location: _GreenhouseLocation | None = None
    departments: list[_GreenhouseDepartment] | None = None


class _GreenhouseJobs(ApiModel):
    jobs: list[_GreenhouseJob] = []


class _GreenhouseValue(ApiModel):
    label: str | None = None


class _GreenhouseField(ApiModel):
    name: str | None = ""
    type: str | None = ""
    values: list[_GreenhouseValue] | None = None


class _GreenhouseQuestion(ApiModel):
    label: str | None = ""
    required: bool | None = None
    fields: list[_GreenhouseField] | None = None


class _GreenhouseQuestions(ApiModel):
    questions: list[_GreenhouseQuestion] = []


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

    def fetch(self, board: Board) -> list[RawJob]:
        token = required_str(board, "token")
        company = board.get("company", token)

        resp = session.get(JOBS_URL.format(token=token), params={"content": "true"}, timeout=15)
        resp.raise_for_status()
        payload = _GreenhouseJobs.model_validate(resp.json())

        jobs: list[RawJob] = []
        for item in payload.jobs:
            location = item.location.name if item.location else ""
            departments = item.departments or []
            jobs.append(
                RawJob(
                    adapter=self.name,
                    company=company,
                    board_token=token,
                    external_id=str(item.id),
                    title=item.title or "",
                    location=location or "",
                    url=item.absolute_url or "",
                    body=strip_html(item.content or ""),
                    posted_at=item.updated_at,
                    team=departments[0].name if departments else None,
                )
            )
        return jobs

    def fetch_questions(self, job: RawJob) -> list[Question] | None:
        resp = session.get(
            JOB_URL.format(token=job.board_token, job_id=job.external_id),
            params={"questions": "true"},
            timeout=15,
        )
        resp.raise_for_status()
        payload = _GreenhouseQuestions.model_validate(resp.json())

        questions: list[Question] = []
        for q in payload.questions:
            field = (q.fields or [_GreenhouseField()])[0]
            questions.append(
                {
                    "name": field.name or "",
                    "label": q.label or "",
                    "field_type": field.type or "",
                    "required": bool(q.required),
                    "values": [v.label for v in (field.values or [])],
                }
            )
        return questions
