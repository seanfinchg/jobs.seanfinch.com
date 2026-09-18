from dataclasses import dataclass


@dataclass
class RawJob:
    adapter: str
    company: str
    board_token: str
    external_id: str
    title: str
    location: str
    url: str
    body: str = ""
    posted_at: str | None = None
    # Coarse department/team label, only when an adapter's raw API response
    # actually exposes one (see normalize.content_hash) -- None everywhere
    # else, which hashes identically to before this field existed.
    team: str | None = None


def source_uid(job: RawJob) -> str:
    return f"{job.adapter}:{job.board_token}:{job.external_id}"
