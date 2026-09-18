from __future__ import annotations

# Curated, not fetched from anywhere -- for the dashboard's "featured"
# spotlight (a company on this list posting something today is worth
# calling out above the fold). Deliberately editorial and manually
# maintained rather than pulled from a live market-cap/valuation API: most
# of the private companies here have no public valuation at all, a live
# feed would be a new external dependency for a list that changes slowly,
# and the bar that actually matters here is "would someone outside tech
# recognize this name," which isn't the same axis as pure valuation --
# Charles Schwab and The Walt Disney Company aren't tech-sector companies
# by any valuation metric, but they're exactly this list's target audience.
# Checked against real ingested company names (not guessed) to catch exact-
# string mismatches -- e.g. a posting says "Micron Technology," not "Micron."
FEATURED_COMPANIES: frozenset[str] = frozenset(
    name.lower()
    for name in [
        # Mega-cap tech
        "Apple", "Microsoft", "Alphabet", "Google", "Amazon", "Meta",
        "Nvidia", "Tesla", "Broadcom", "Oracle", "IBM", "Cisco", "Intel",
        "AMD", "Qualcomm", "Texas Instruments", "Dell",
        "HP", "Hewlett Packard (HP)", "HPE", "Hewlett Packard Enterprise",

        # Enterprise / consumer software
        "Salesforce", "Adobe", "Intuit", "ServiceNow", "Workday",
        "Accenture", "Deloitte", "PayPal", "Visa", "Mastercard", "Netflix",
        "Uber", "Airbnb", "eBay", "Booking Holdings", "Expedia", "Spotify",
        "Dropbox", "Squarespace", "Roblox", "Datadog", "Autodesk", "Splunk",
        "Zoom", "DocuSign", "Block", "Robinhood", "Coinbase", "Snap",
        "Pinterest", "Etsy", "Yelp", "Roku", "Twilio", "Asana",

        # Semiconductors / hardware (recognizable brands, not niche
        # equipment/component suppliers -- Corning/Micron/Western Digital/
        # Seagate are names a non-engineer would still recognize)
        "Corning", "Micron", "Micron Technology", "Garmin", "NetApp",
        "Western Digital", "Seagate",

        # Telecom
        "Verizon", "AT&T", "T-Mobile", "Comcast", "Charter Communications",
        "Motorola", "Motorola Solutions", "Nokia",

        # Security vendors
        "Palo Alto Networks", "Fortinet", "CrowdStrike", "Cloudflare",
        "Zscaler", "Okta", "SentinelOne", "CyberArk", "Akamai",

        # Gaming / media / entertainment
        "Electronic Arts", "Take-Two Interactive", "Activision Blizzard",
        "Epic Games", "Unity", "TikTok", "ByteDance",
        "The Walt Disney Company",

        # Finance / fintech brands recognizable outside tech -- this
        # dashboard's board list pulls tech-hiring divisions of companies
        # that aren't tech-sector at all, and those postings are exactly
        # the ones worth flagging as "a name you know is hiring."
        "Charles Schwab", "American Express", "Fidelity Investments",
        "Capital One", "JP Morgan Chase", "Goldman Sachs",

        # Aerospace / defense / automotive
        "The Boeing Company", "General Motors", "Honeywell",
        "Northrop Grumman", "RTX", "L3Harris Technologies", "Blue Origin",
        "Neuralink",

        # Notable large private / not-yet-public tech employers -- real
        # news-cycle name recognition, not just valuation
        "SpaceX", "Anthropic", "OpenAI", "Stripe", "Databricks",
        "Discord", "Canva", "Figma", "Notion", "Chime", "Plaid", "Brex",
        "Ramp", "Anduril", "Scale AI", "Perplexity", "xAI", "Hugging Face",
        "Wiz", "1Password", "Instacart", "DoorDash", "Toast", "MongoDB",
        "Elastic", "Docker", "GitLab", "GitHub", "Automattic", "Reddit",
        "Duolingo", "Niantic",
        # "Palantir", not "Palantir Technologies" -- real postings use the
        # short name, and is_featured() does an exact match, not a substring.
        "Palantir", "Affirm",
    ]
)


def is_featured(company: str) -> bool:
    return (company or "").strip().lower() in FEATURED_COMPANIES
