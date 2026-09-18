from __future__ import annotations

import requests

# Every adapter used to call `requests.get`/`requests.post` directly, which
# means every outbound request carried the library's default User-Agent
# ("python-requests/x.x.x") -- one of the most commonly flagged automated-
# client signatures, independent of request volume or pacing. A shared
# session with an ordinary browser User-Agent is a small, low-risk change
# that makes this look like normal traffic instead of an obvious script,
# on top of (not instead of) engine.py's inter-request delays and the
# workday adapter's inter-page delay -- volume/pacing and fingerprint are
# separate risk factors, not substitutes for each other.
session = requests.Session()
session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    ),
})
