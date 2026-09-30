from __future__ import annotations

import re

_SALARY_RE = re.compile(r"\$\s?(\d{2,3})(?:,?(\d{3}))?\s*(k)?", re.IGNORECASE)
_MIN_PLAUSIBLE_SALARY = 20000
# A real base-salary range rarely spans more than 3x low-to-high -- a wider
# spread is a real sign _salary_figures() swept up an unrelated dollar figure
# elsewhere in the body (a signing bonus, a benefits amount, a referral
# bonus) rather than two ends of the same stated range. Found by a real
# example: a posting read as $75k-$500k on the dashboard because $500k was a
# life-insurance benefit mention, not a comp ceiling.
_MAX_PLAUSIBLE_SALARY_RATIO = 3


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
    stating none gets (None, None). A pair whose ratio is too implausible to
    be a real range (see _MAX_PLAUSIBLE_SALARY_RATIO) also gets (None, None)
    -- reporting no salary data is more honest than reporting two unrelated
    numbers as if they were a stated range."""
    figures = _salary_figures(body)
    if not figures:
        return None, None
    lo, hi = min(figures), max(figures)
    if hi / lo > _MAX_PLAUSIBLE_SALARY_RATIO:
        return None, None
    return lo, hi
