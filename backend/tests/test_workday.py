from jobfinder.adapters.workday import is_workday_url, parse_workday_url


def test_recognizes_workday_hosts():
    assert is_workday_url(
        "https://globalhr.wd5.myworkdayjobs.com/rec_rtx_ext_gateway/job/x/y_01815408"
    )


def test_does_not_flag_other_hosts():
    assert not is_workday_url("https://boards.greenhouse.io/acme/jobs/1001")


def test_parse_workday_url_extracts_tenant_wd_and_site():
    url = "https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite/job/US-CA-Santa-Clara/x_JR1"
    assert parse_workday_url(url) == {"tenant": "nvidia", "wd": "wd5", "site": "NVIDIAExternalCareerSite"}


def test_parse_workday_url_returns_none_for_a_non_workday_url():
    assert parse_workday_url("https://boards.greenhouse.io/acme/jobs/1001") is None


def test_parse_workday_url_skips_a_locale_segment_before_the_real_site():
    url = "https://leidos.wd5.myworkdayjobs.com/en-US/external/job/Columbia-MD/x_R-00180476"
    assert parse_workday_url(url) == {"tenant": "leidos", "wd": "wd5", "site": "external"}
