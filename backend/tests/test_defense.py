from jobfinder.defense import is_defense_surveillance


def test_known_defense_primes_are_flagged():
    for company in ["Lockheed Martin", "Northrop Grumman", "General Dynamics", "RTX", "Leidos"]:
        assert is_defense_surveillance(company), company


def test_surveillance_companies_are_flagged_even_though_not_classic_defense():
    for company in ["Clearview AI", "Axon", "Palantir"]:
        assert is_defense_surveillance(company), company


def test_case_and_whitespace_insensitive():
    assert is_defense_surveillance("  lockheed martin  ")
    assert is_defense_surveillance("PALANTIR")


def test_unrelated_company_is_not_flagged():
    assert not is_defense_surveillance("Some Random Startup LLC")
