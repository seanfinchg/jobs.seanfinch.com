from __future__ import annotations

from jobfinder.adapters.base import Adapter
from jobfinder.adapters.registry import register
from jobfinder.models import RawJob


@register
class ManualAdapter(Adapter):
    """Hand-entered postings for companies with no usable public JSON API --
    fully custom/proprietary in-house career platforms (Meta, IBM, Cisco,
    and the like) that no other adapter can reach. Same spirit as
    simplify_listings.py's "not a real ATS" comment, but simpler: no fetch
    at all, no aggregator, just a human (me) pasting in a real posting found
    by hand on the company's actual careers site. Each board entry in
    boards/manual.yaml is exactly one posting; `token` exists purely for the
    same health-tracking/stale-sighting-closure convention every other
    adapter uses, not for any lookup or dedup key beyond that.
    """

    name = "manual"

    def fetch(self, board: dict) -> list[RawJob]:
        token = board["token"]
        return [
            RawJob(
                adapter=self.name,
                company=board["company"],
                board_token=token,
                external_id=token,
                title=board["title"],
                location=board.get("location", ""),
                url=board["url"],
                posted_at=board.get("posted_at"),
            )
        ]
