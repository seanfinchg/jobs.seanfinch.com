from __future__ import annotations

import re

_SALARY_RE = re.compile(r"\$\s?(\d{2,3})(?:,?(\d{3}))?\s*(k)?", re.IGNORECASE)
_MIN_PLAUSIBLE_SALARY = 20000


def _salary_figures(body: str) -> list[int]:
    """Every plausible dollar figure in the text. Not a real comp parser --
    just enough to tell "this posting states pay" from "it doesn't"."""
    figures = []
    for whole, thousands, k_suffix in _SALARY_RE.findall(body or ""):
        if k_suffix or not thousands:
            value = int(whole) * 1000
        else:
            value = int(whole) * 1000 + int(thousands)
        if value >= _MIN_PLAUSIBLE_SALARY:
            figures.append(value)
    return figures


def extract_salary_floor(body: str) -> int | None:
    """Best-effort lowest dollar figure in the text."""
    figures = _salary_figures(body)
    return min(figures) if figures else None


def extract_salary_range(body: str) -> tuple[int | None, int | None]:
    """Best-effort (min, max) dollar figures in the text, for display on the
    dashboard. Same heuristics/limitations as extract_salary_floor -- a
    posting stating one figure gets (that figure, that figure); a posting
    stating none gets (None, None)."""
    figures = _salary_figures(body)
    if not figures:
        return None, None
    return min(figures), max(figures)
