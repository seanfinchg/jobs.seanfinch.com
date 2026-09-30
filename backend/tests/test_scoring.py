from jobfinder.scoring import extract_salary_range


def test_no_dollar_figures_returns_none_none():
    assert extract_salary_range("Join our team and build great things.") == (None, None)


def test_single_figure_becomes_a_zero_width_range():
    assert extract_salary_range("This role pays $120,000 per year.") == (120000, 120000)


def test_plausible_range_is_kept():
    assert extract_salary_range("Salary range: $120,000 - $160,000") == (120000, 160000)


def test_implausible_ratio_is_dropped_as_unreliable():
    # Real example: a posting read as $75k-$500k on the dashboard because
    # $500k was a life-insurance benefit mention, not a comp ceiling.
    assert extract_salary_range("Base pay $75,000. Life insurance benefit up to $500,000.") == (None, None)


def test_figures_below_the_floor_are_ignored_entirely():
    # A stray "$5" or "$50" (a price, a fee) shouldn't surface as a salary
    # at all, let alone pass the ratio check against a real figure nearby.
    assert extract_salary_range("Coffee's on us -- $5 gift card included. Pays $130,000.") == (130000, 130000)
