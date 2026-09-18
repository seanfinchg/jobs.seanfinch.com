from jobfinder.normalize import content_hash, location_bucket, norm


def test_norm_collapses_known_variants():
    assert norm("Sr. Software Engineer") == norm("Senior Software Engineer")
    assert norm("SWE II") == norm("Software Engineer II")


def test_location_bucket_collides_new_york_variants():
    assert location_bucket("New York, NY") == location_bucket("New York, New York, United States")


def test_location_bucket_distinguishes_regions():
    assert location_bucket("Boston, MA") != location_bucket("New York, NY")


def test_content_hash_collides_same_role_different_source_text():
    a = content_hash("Acme", "Senior Software Engineer", "New York, NY")
    b = content_hash("Acme", "Sr. Software Engineer", "New York, New York, United States")
    assert a == b


def test_content_hash_distinguishes_different_roles():
    a = content_hash("Acme", "Security Engineer", "Boston, MA")
    b = content_hash("Acme", "Sales Engineer", "Boston, MA")
    assert a != b


def test_location_bucket_does_not_confuse_cambridge_uk_with_massachusetts():
    assert location_bucket("Cambridge, UK") != location_bucket("Cambridge, MA")
    assert location_bucket("Cambridge, MA") == "boston"


def test_location_bucket_does_not_confuse_lexington_sc_with_massachusetts():
    assert location_bucket("Lexington, SC") != "boston"
    assert location_bucket("Lexington, MA") == "boston"


def test_content_hash_omitting_team_matches_the_pre_team_hash():
    # Adapters/rows with no team info must hash identically to before this
    # parameter existed, so already-ingested rows don't all shift hash on
    # the next run just because the function signature grew.
    assert content_hash("Acme", "Software Engineer", "Boston, MA") == content_hash(
        "Acme", "Software Engineer", "Boston, MA", None
    )


def test_content_hash_distinguishes_same_role_different_team():
    a = content_hash("Acme", "Software Engineer", "Boston, MA", "Platform")
    b = content_hash("Acme", "Software Engineer", "Boston, MA", "Sales")
    assert a != b


def test_content_hash_with_team_still_collides_on_text_variants():
    a = content_hash("Acme", "Senior Software Engineer", "New York, NY", "Platform")
    b = content_hash("Acme", "Sr. Software Engineer", "New York, New York, United States", "platform")
    assert a == b
