from jobfinder.adapters import manual


def test_fetch_returns_the_one_configured_posting():
    board = {
        "token": "meta-swe-newgrad-2027",
        "company": "Meta",
        "title": "Software Engineer, University Grad",
        "url": "https://www.metacareers.com/jobs/1234567890",
        "location": "Menlo Park, CA",
        "posted_at": "2026-08-01T00:00:00+00:00",
    }

    jobs = manual.ManualAdapter().fetch(board)

    assert len(jobs) == 1
    job = jobs[0]
    assert job.adapter == "manual"
    assert job.company == "Meta"
    assert job.board_token == "meta-swe-newgrad-2027"
    assert job.external_id == "meta-swe-newgrad-2027"
    assert job.title == "Software Engineer, University Grad"
    assert job.location == "Menlo Park, CA"
    assert job.url == "https://www.metacareers.com/jobs/1234567890"
    assert job.posted_at == "2026-08-01T00:00:00+00:00"


def test_location_and_posted_at_are_optional():
    board = {
        "token": "ibm-swe-2027",
        "company": "IBM",
        "title": "Software Engineer",
        "url": "https://www.ibm.com/careers/job/1",
    }

    jobs = manual.ManualAdapter().fetch(board)

    assert len(jobs) == 1
    job = jobs[0]
    assert job.location == ""
    assert job.posted_at is None


def test_is_native():
    assert manual.ManualAdapter.is_native is True
