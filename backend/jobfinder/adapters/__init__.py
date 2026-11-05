# Importing each adapter module registers it (see registry.register).
from jobfinder.adapters import (
    ashby,
    bamboohr,
    greenhouse,
    lever,
    manual,
    rippling,
    simplify_listings,
    smartrecruiters,
    workable,
    workday,
)

__all__ = [
    "ashby",
    "bamboohr",
    "greenhouse",
    "lever",
    "manual",
    "rippling",
    "simplify_listings",
    "smartrecruiters",
    "workable",
    "workday",
]
