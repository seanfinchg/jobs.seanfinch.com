from jobfinder.featured import is_featured


def test_security_vendor_peers_are_all_featured():
    # research.md names these five together as target companies; CrowdStrike
    # and Cloudflare were already on the list, Okta/SentinelOne/Zscaler
    # weren't -- found by a direct user question about why Zscaler/Okta
    # weren't showing up as featured.
    for company in ["CrowdStrike", "Cloudflare", "Okta", "SentinelOne", "Zscaler", "CyberArk"]:
        assert is_featured(company), company


def test_palantir_matches_the_real_short_company_name():
    # is_featured() does an exact match, not a substring -- real postings
    # use "Palantir", not "Palantir Technologies", so the old entry never
    # actually matched anything live.
    assert is_featured("Palantir")


def test_case_and_whitespace_insensitive():
    assert is_featured("  ZSCALER  ")
    assert is_featured("okta")


def test_unfeatured_company_is_not_featured():
    assert not is_featured("Some Random Startup LLC")


def test_real_exact_string_variants_from_live_data_are_featured():
    # Found by checking real ingested company names against the list, not
    # by guessing -- an ATS posting's legal/brand name often differs from
    # the short form ("Micron Technology" not "Micron," bare "Motorola"
    # not "Motorola Solutions," "Hewlett Packard Enterprise" not "HPE").
    # is_featured() does an exact match, so both variants need to be listed.
    for company in [
        "Micron Technology", "Motorola", "Hewlett Packard Enterprise",
        "Hewlett Packard (HP)", "JP Morgan Chase",
    ]:
        assert is_featured(company), company


def test_user_requested_and_high_frequency_real_companies_are_featured():
    # Tesla/TikTok/Disney/Schwab were asked about directly; the rest were
    # found by cross-checking real ingested company names against the old
    # list and picking out the ones with genuine mainstream (not just
    # tech-industry) brand recognition.
    for company in [
        "Tesla", "TikTok", "ByteDance", "The Walt Disney Company",
        "Charles Schwab", "American Express", "Fidelity Investments",
        "Capital One", "Goldman Sachs", "Dropbox", "Squarespace", "Roblox",
        "Blue Origin", "Neuralink", "The Boeing Company", "General Motors",
        "Nokia", "Honeywell", "Northrop Grumman", "RTX",
        "L3Harris Technologies", "Twilio", "Asana", "Deloitte",
    ]:
        assert is_featured(company), company


def test_niche_b2b_companies_were_removed_as_not_broadly_recognizable():
    # These were on the original list but are enterprise/B2B names a
    # non-engineer wouldn't recognize -- removed after a direct complaint
    # that "random" unfamiliar companies were showing up as "featured."
    # Not exhaustive, just guards the specific ones flagged.
    for company in [
        "Roper Technologies", "Trimble", "Arrow Electronics", "Jabil",
        "TE Connectivity", "Amphenol", "Keysight Technologies", "Teradyne",
        "Zebra Technologies", "Fiserv", "Synopsys", "Cadence Design Systems",
        "Analog Devices", "Applied Materials", "Lam Research", "KLA",
        "Juniper Networks", "F5", "VeriSign", "Cargill", "SambaNova Systems",
        "Cerebras Systems", "Vanta", "HashiCorp", "PagerDuty", "Confluent",
        "Grafana Labs", "JetBrains", "Carta", "Samsara", "Klaviyo",
        "Rippling", "Cohere", "Gusto",
    ]:
        assert not is_featured(company), company
