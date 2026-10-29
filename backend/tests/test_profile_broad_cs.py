"""Regression tests against the real shipped broad-cs profile -- found by
cross-checking real pipeline output (a live run, ~3,950 postings) against
jobfinder/classify.py's own field classification, the same method
used for the new-grad-cs profile's accuracy passes."""

from jobfinder.engine import load_profile, passes_filters
from jobfinder.models import RawJob


def _job(**overrides):
    base = dict(
        adapter="greenhouse", company="Acme", board_token="acme", external_id="1",
        title="Software Engineer", location="Remote", url="https://example.com",
        body="",
    )
    base.update(overrides)
    return RawJob(**base)


def _profile():
    return load_profile("broad-cs")


def test_business_systems_engineer_titles_are_filtered_out():
    # Bare "systems engineer" also matches business/GTM/finance titles with
    # nothing to do with computer systems -- found in real broad-cs output:
    # "GTM Systems Engineer, Salesforce", "Senior Financial Systems Engineer".
    profile = _profile()
    for title in ["GTM Systems Engineer, Salesforce", "Senior Financial Systems Engineer"]:
        assert not passes_filters(_job(title=title), profile["filters"]), title


def test_real_systems_engineer_titles_still_pass():
    profile = _profile()
    for title in ["Firmware Engineer, Robotics", "Android Systems Engineer, Consumer Devices"]:
        assert passes_filters(_job(title=title), profile["filters"]), title


def test_hardware_test_engineer_titles_are_filtered_out_of_qa():
    # Bare "test engineer" also matches hardware/silicon manufacturing test
    # roles -- found in real broad-cs output: "Bench Test Engineer -
    # Hardware Engineering", "Senior HiL Test Engineer - Automotive". These
    # aren't software QA/SDET work.
    profile = _profile()
    for title in ["Bench Test Engineer - Hardware Engineering", "Senior HiL Test Engineer - Automotive"]:
        assert not passes_filters(_job(title=title), profile["filters"]), title


def test_accounting_quality_assurance_is_not_treated_as_software_qa():
    profile = _profile()
    job = _job(title="Manager, Accounting Quality Assurance & Governance")
    assert not passes_filters(job, profile["filters"])


def test_qa_automation_engineer_word_order_still_matches():
    # "\bqa engineer\b" doesn't match this word order -- the real gap that
    # motivated the broadened pattern.
    profile = _profile()
    job = _job(title="QA Automation Engineer")
    assert passes_filters(job, profile["filters"])


def test_physical_qa_technician_and_construction_titles_are_filtered_out():
    # Contract-manufacturer/fab boards (Jabil, Micron) post dozens of
    # physical-production test/QA titles with none of the field's existing
    # hardware-keyword excludes in the title -- found in real broad-cs
    # output: "Test Engineering Technician II - 401 Shift", "Product
    # Quality Assurance Technician", "Construction Program Manager -
    # Quality Assurance / Quality Control", "MSB Site Quality Assurance
    # (QA) In Line Process Control Inspector".
    profile = _profile()
    for title in [
        "Test Engineering Technician II - 401 Shift",
        "Product Quality Assurance Technician",
        "Construction Program Manager - Quality Assurance / Quality Control",
        "MSB Site Quality Assurance (QA) In Line Process Control Inspector",
    ]:
        assert not passes_filters(_job(title=title), profile["filters"]), title


def test_mobile_engineering_services_facilities_title_is_filtered_out():
    # "Mobile engineer" is also UK facilities-management terminology for a
    # traveling maintenance technician -- found in real broad-cs output:
    # "General Maintenance Operative - Mobile Engineering Services" (JLL),
    # which the old unbounded "mobile engineer" pattern prefix-matched via
    # "Mobile Engineering".
    profile = _profile()
    job = _job(title="General Maintenance Operative - Mobile Engineering Services")
    assert not passes_filters(job, profile["filters"])


def test_real_mobile_engineer_titles_still_pass():
    profile = _profile()
    for title in ["Mobile Engineer, Android", "Senior Mobile Engineer (iOS or Android)"]:
        assert passes_filters(_job(title=title), profile["filters"]), title
