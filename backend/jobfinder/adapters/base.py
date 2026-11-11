from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel, ConfigDict

from jobfinder.config import Board
from jobfinder.models import Question, RawJob


class ApiModel(BaseModel):
    """Base for the shape of an ATS API response. Only the fields an adapter
    reads are declared; everything else is ignored. Numbers are accepted for
    string fields (some ATSes send numeric ids), and every field has the
    same default the adapter's old `.get(key, default)` used."""

    model_config = ConfigDict(coerce_numbers_to_str=True)


class Adapter(ABC):
    name: str
    # False for aggregators (e.g. simplify_listings) whose apply_url points
    # at some other ATS rather than being the canonical source.
    is_native: bool = True

    @abstractmethod
    def fetch(self, board: Board) -> list[RawJob]:
        """Return every current posting for one board config entry.

        Must not filter. Must not raise on a board with zero open
        postings -- only on transport/parse failure, so the engine can log
        the board as unhealthy and move on.
        """
        raise NotImplementedError

    def fetch_questions(self, job: RawJob) -> list[Question] | None:
        return None

    def fetch_body(self, job: RawJob) -> str | None:
        """A second, per-posting request for adapters whose list endpoint
        doesn't include description text. None (the default) means the
        engine never calls this for adapters that don't override it -- see
        engine.run(), which only calls it for a job that already cleared the
        title/location filters, to bound the extra requests to postings that
        already look relevant."""
        return None
