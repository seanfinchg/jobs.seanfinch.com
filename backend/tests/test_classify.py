from datetime import date

import yaml

from jobfinder import classify
from jobfinder.classify import (
    classify_fields,
    classify_grad_year,
    classify_level,
    classify_subfields,
    grad_year_pattern,
)

_TODAY = date(2026, 8, 29)


def test_systems_subfields_from_real_title_shapes():
    assert "firmware" in classify_subfields("Firmware Engineer, Robotics")
    assert "embedded" in classify_subfields("Embedded Systems Engineer")
    assert "os-kernel" in classify_subfields("Operating Systems Engineer")
    assert "distributed-systems" in classify_subfields("Distributed Systems Engineer")
    assert "networking" in classify_subfields("Networking Operating System Firmware Engineer")


def test_systems_engineer_alone_gets_no_subfield_tag():
    # A generic "Systems Engineer" title has no specific sub-specialty
    # signal -- an empty subfield list is correct, not a gap.
    assert classify_subfields("Systems Engineer") == []


def test_classify_level_unaffected_by_field_changes():
    assert classify_level("Senior Firmware Engineer") == "senior"
    assert classify_level("Systems Engineer") == "mid"


def test_bare_graduate_titles_classify_as_new_grad():
    # No "new"/"university" prefix -- a distinct, very common convention
    # (trading firms' "Graduate Software Engineer", ByteDance/TikTok's
    # "<Role> Engineer Graduate - <team>", "(2027 Graduate)") that the
    # "new ?grad"/"university grad" patterns alone never caught.
    assert classify_level("Graduate Software Engineer") == "new-grad"
    assert classify_level("Machine Learning Engineer Graduate - Ads Delivery") == "new-grad"
    assert classify_level("Information Security Engineer (2027 Graduate)") == "new-grad"


def test_undergraduate_research_titles_do_not_match_bare_graduate():
    # "undergraduate" has no word boundary before "graduate" ("r" then "g"
    # are both word characters), so \bgraduate\b correctly leaves these
    # academic research-assistant postings alone rather than relabeling
    # them as new-grad industry roles.
    assert classify_level("Undergraduate Research Assistant - Engineering") == "mid"


def test_talent_program_titles_classify_as_new_grad():
    # Real titles found in the dataset ("Software Engineer - Full Stack -
    # Emerging Talent", "Software Engineer - Exceptional Talent") plus
    # "early talent", a common official new-grad-program name at several
    # larger companies -- specific phrases only, not a bare \btalent\b
    # match, since that would also catch HR/recruiting titles.
    assert classify_level("Software Engineer - Full Stack - Emerging Talent") == "new-grad"
    assert classify_level("Software Engineer - Exceptional Talent") == "new-grad"
    assert classify_level("Software Engineer, Early Talent Program") == "new-grad"


def test_bare_talent_does_not_false_positive_on_recruiting_titles():
    assert classify_level("Talent Acquisition Manager") == "manager"
    assert classify_level("Head of Talent") == "director"


def test_mlops_and_applied_ai_titles_get_mlops_subfield():
    assert "mlops" in classify_subfields("Machine Learning Engineer - MLOps Framework")
    assert "mlops" in classify_subfields("Applied AI Engineer, Enterprise")


def test_release_and_observability_titles_get_devops_sre_subfields():
    assert "release-engineering" in classify_subfields("Release Engineer | Consumer Devices")
    assert "release-engineering" in classify_subfields("Staff Site Reliability Engineer - Release Engineering")
    assert "observability" in classify_subfields("Senior Observability Engineer, Platform")


def test_cross_platform_mobile_titles_get_subfield():
    assert "cross-platform" in classify_subfields("React Native Engineer, Merchant Experience Mobile")
    assert "cross-platform" in classify_subfields("Staff Flutter Engineer")


def test_ai_security_titles_get_subfield_not_generic_appsec():
    tags = classify_subfields("Staff Security Software Engineer, AI Security")
    assert "ai-security" in tags
    assert "appsec" not in tags


def test_devsecops_title_gets_tag_despite_no_literal_devops_substring():
    # "DevSecOps" contains no "devops" substring ("Dev" + "Sec" + "Ops"), so
    # it would otherwise match neither the devops nor any bare security
    # pattern and fall through unclassified.
    assert "devsecops" in classify_subfields("DevSecOps Research Computing Software Engineer")


def test_soc_chip_title_does_not_false_positive_as_security_detection_response():
    # "SoC" here is system-on-chip, not a security-operations-center role --
    # must not pick up the detection-response (SOC) security tag.
    assert "detection-response" not in classify_subfields("SoC Firmware Engineer")


def test_grad_year_extracted_from_title():
    assert classify_grad_year("New Grad 2027", today=_TODAY) == 2027
    assert classify_grad_year("Software Engineer, Summer 2026 Intern", today=_TODAY) == 2026
    assert classify_grad_year("Information Security Engineer (2027 Graduate)", today=_TODAY) == 2027


def test_grad_year_falls_back_to_body_when_title_has_none():
    assert classify_grad_year(
        "Software Engineer Intern", "Join our Summer 2027 internship class.", today=_TODAY
    ) == 2027


def test_grad_year_none_when_not_stated():
    assert classify_grad_year("Senior Software Engineer", today=_TODAY) is None


def test_grad_year_ignores_unrelated_years_with_no_grad_context():
    body = "We are hiring for our 2026 fiscal year budget, no relation to graduation."
    assert classify_grad_year("Senior Software Engineer", body, today=_TODAY) is None


def test_lean_six_sigma_business_titles_do_not_classify_as_mechanical_engineering():
    # Bare "six sigma"/"dfmea" is a general business-process-improvement
    # methodology, not specific to mechanical design work -- found in real
    # broad-cs output landing "Business Process Manager - Six Sigma Black
    # Belt" (HPE) and "Lean Six Sigma SME I/II" (Jabil) in the
    # mechanical-engineering field, none of which mention "engineer".
    for title in [
        "Business Process Manager - Six Sigma Black Belt",
        "Lean Six Sigma SME I",
        "Sr. Lean Six Sigma Manager",
    ]:
        assert "mechanical-engineering" not in classify_fields(title), title
        assert "quality-six-sigma" not in classify_subfields(title), title


def test_six_sigma_engineer_title_still_classifies_as_mechanical_engineering():
    assert "mechanical-engineering" in classify_fields("Manufacturing Engineer - Six Sigma Black Belt")
    assert "quality-six-sigma" in classify_subfields("Manufacturing Engineer - Six Sigma Black Belt")


def test_hardware_portfolio_analyst_does_not_classify_as_finance():
    # Bare "portfolio analyst" also matches a product/business-unit
    # "portfolio" with nothing to do with investment management -- found in
    # real broad-cs output: "Worldwide Global Business Unit Home Hardware
    # Portfolio Analyst" (HP).
    title = "Worldwide Global Business Unit Home Hardware Portfolio Analyst"
    assert "finance" not in classify_fields(title)
    assert "portfolio-investments" not in classify_subfields(title)


def test_investment_portfolio_analyst_title_still_classifies_as_finance():
    title = "Quantitative Portfolio Analyst – 2026 Grad"
    assert "finance" in classify_fields(title)
    assert "portfolio-investments" in classify_subfields(title)


def test_facilities_mobile_engineering_services_does_not_classify_as_mobile():
    # "Mobile engineer" is also UK facilities-management terminology for a
    # traveling maintenance technician -- found in real broad-cs output:
    # "General Maintenance Operative - Mobile Engineering Services" (JLL),
    # which an unbounded "mobile engineer" pattern prefix-matched via
    # "Mobile Engineering".
    title = "General Maintenance Operative - Mobile Engineering Services"
    assert "mobile" not in classify_fields(title)


def test_real_mobile_engineer_titles_still_classify_as_mobile():
    assert "mobile" in classify_fields("Mobile Engineer, Android")
    assert "mobile" in classify_fields("Senior Mobile Engineer (iOS or Android)")


def test_grad_year_ignores_years_outside_the_near_future_window():
    # Bare "class of" mention with a stale/past year -- grad_year_pattern()
    # only extends 2 years past the current one, so this shouldn't match.
    assert classify_grad_year("Engineer, class of 2019 alumni program", today=_TODAY) is None


def test_grad_year_pattern_spans_current_through_two_years_out():
    assert grad_year_pattern(_TODAY) == "2026|2027|2028"


def test_grad_year_does_not_false_positive_on_internal_containing_intern():
    # Real-data catch: "Retool's 2026 State of Internal Software report"
    # (an Elastic Director posting) -- "intern" with no word boundary would
    # match the "Intern" substring inside "Internal", wrongly tagging a
    # director-level posting with a grad year.
    body = "Retool's 2026 State of Internal Software report found that engineering teams..."
    assert classify_grad_year("Director - IT Software Engineering", body, today=_TODAY) is None


def test_grad_year_pattern_stays_correct_across_a_decade_boundary():
    assert grad_year_pattern(date(2029, 1, 1)) == "2029|2030|2031"


def test_classify_subfields_reads_tag_pattern_from_field_yaml(tmp_path):
    # Subfields are declared per-field in profiles/fields/<name>.yaml's own
    # `subfields:` list (see profiles/_schema.md), not a hardcoded Python
    # dict -- this is the loader mechanism itself, independent of any one
    # field's real vocabulary (covered by the tests above, which exercise
    # the real shipped YAML files).
    fields_dir = tmp_path / "profiles" / "fields"
    fields_dir.mkdir(parents=True)
    (fields_dir / "widgets.yaml").write_text(yaml.safe_dump({
        "label": "Widgets",
        "subfields": [{"tag": "gizmo", "label": "Gizmo", "pattern": r"gizmo engineer"}],
    }))

    classify._field_subfield_patterns_cache.clear()
    try:
        assert classify_subfields("Gizmo Engineer", fields_dir=fields_dir) == ["gizmo"]
        assert classify_subfields("Unrelated Title", fields_dir=fields_dir) == []
    finally:
        classify._field_subfield_patterns_cache.clear()


def test_classify_subfields_field_with_no_subfields_key_contributes_none(tmp_path):
    fields_dir = tmp_path / "profiles" / "fields"
    fields_dir.mkdir(parents=True)
    (fields_dir / "plain.yaml").write_text(yaml.safe_dump({"label": "Plain", "filters": {}}))

    classify._field_subfield_patterns_cache.clear()
    try:
        assert classify_subfields("Anything", fields_dir=fields_dir) == []
    finally:
        classify._field_subfield_patterns_cache.clear()
