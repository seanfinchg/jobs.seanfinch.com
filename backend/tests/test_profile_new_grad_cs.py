"""Regression tests against the real shipped profile, not a synthetic
fixture -- these exist because every bug fixed in this file was found by
looking at real pipeline output."""

from jobfinder.config import Filters
from jobfinder.engine import load_profile, passes_filters
from jobfinder.models import RawJob


def _job(**overrides: str) -> RawJob:
    base = dict(
        adapter="greenhouse",
        company="Acme",
        board_token="acme",
        external_id="1",
        title="Security Engineer",
        location="Boston, MA",
        url="https://example.com",
        body="",
    )
    base.update(overrides)
    return RawJob(**base)


def _filters() -> Filters:
    filters = load_profile("new-grad-cs").get("filters")
    assert filters is not None
    return filters


def test_electronic_security_technician_is_filtered_out() -> None:
    filters = _filters()
    job = _job(title="Electronic Security Technician", location="Lexington, SC")
    assert not passes_filters(job, filters)


def test_cambridge_uk_does_not_get_the_boston_bonus() -> None:
    filters = _filters()
    job = _job(title="Software Engineer", location="Cambridge, UK")
    assert not passes_filters(job, filters)


def test_generic_new_grad_swe_with_no_security_signal_is_filtered_out() -> None:
    filters = _filters()
    job = _job(
        title="Software Engineer, New Grad - Ads Infrastructure",
        location="San Jose, CA",
        body="you'll build ad ranking systems at massive scale",
    )
    assert not passes_filters(job, filters)


def test_bare_risk_analyst_title_is_filtered_out() -> None:
    # A bare "risk" title with no security signal at all shouldn't pass --
    # it might be a financial/insurance role, not a security one.
    filters = _filters()
    assert not passes_filters(_job(title="Risk Analyst"), filters)


def test_generic_new_grad_swe_with_security_signal_in_body_still_passes() -> None:
    filters = _filters()
    job = _job(
        title="Software Engineer, New Grad",
        location="San Jose, CA",
        body="you'll partner closely with our security engineering team on threat detection",
    )
    assert passes_filters(job, filters)
