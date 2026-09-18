import importlib.util
from pathlib import Path

import requests

from jobfinder import db
from jobfinder.models import RawJob

SCRIPT_PATH = Path(__file__).parent.parent / "scripts" / "discover_tokens.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("discover_tokens", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_slug_variants_strips_common_corporate_suffixes():
    module = _load_module()
    assert module.slug_variants("Acme Corporation") == ["acme"]
    assert module.slug_variants("Acme Inc.") == ["acme"]
    assert module.slug_variants("Acme, LLC") == ["acme"]


def test_slug_variants_returns_both_spacing_conventions_for_multiword_names():
    module = _load_module()
    assert module.slug_variants("Blue Origin") == ["blue-origin", "blueorigin"]


def test_slug_variants_dedupes_when_spacing_variants_collide():
    module = _load_module()
    # A single-word name has only one variant either way -- both the
    # no-space and hyphenated forms collapse to the same string.
    assert module.slug_variants("Acme") == ["acme"]


def _sighting_job(url: str, company: str = "Acme", token: str = "acme-1") -> RawJob:
    return RawJob(
        adapter="simplify_listings", company=company, board_token=token, external_id=token,
        title="Software Engineer", location="Remote", url=url,
    )


def test_discover_from_aggregator_reverse_engineers_token_from_apply_url(tmp_path):
    module = _load_module()
    db_path = tmp_path / "jobfinder.db"
    conn = db.connect(str(db_path))
    db.upsert_job(
        conn, _sighting_job("https://boards.greenhouse.io/acme/jobs/12345", token="gh-1"),
        profile="p", is_native=False, now="t1",
    )
    conn.close()

    hits = module.discover_from_aggregator(db_path=str(db_path))

    assert hits == [{"company": "Acme", "adapter": "greenhouse", "token": "acme", "job_count": None}]


def test_discover_from_aggregator_handles_workday_urls_as_a_special_case(tmp_path):
    module = _load_module()
    db_path = tmp_path / "jobfinder.db"
    conn = db.connect(str(db_path))
    db.upsert_job(
        conn,
        _sighting_job("https://acme.wd5.myworkdayjobs.com/careers/job/x/y_123", token="wd-1"),
        profile="p", is_native=False, now="t1",
    )
    conn.close()

    hits = module.discover_from_aggregator(db_path=str(db_path))

    assert hits == [
        {"company": "Acme", "adapter": "workday", "job_count": None, "tenant": "acme", "wd": "wd5", "site": "careers"}
    ]


def test_discover_from_aggregator_dedupes_workday_by_tenant_wd_site_not_by_url(tmp_path):
    # Workday hits dedupe on a different key (tenant, wd, site) than the
    # single-token adapters above (adapter, token) -- two distinct postings
    # at the same tenant/pod/site must still collapse to one hit.
    module = _load_module()
    db_path = tmp_path / "jobfinder.db"
    conn = db.connect(str(db_path))
    db.upsert_job(
        conn, _sighting_job("https://acme.wd5.myworkdayjobs.com/careers/job/a/x_1", token="wd-1"),
        profile="p", is_native=False, now="t1",
    )
    db.upsert_job(
        conn, _sighting_job("https://acme.wd5.myworkdayjobs.com/careers/job/b/y_2", token="wd-2"),
        profile="p", is_native=False, now="t1",
    )
    conn.close()

    hits = module.discover_from_aggregator(db_path=str(db_path))

    assert len(hits) == 1


def test_discover_from_aggregator_dedupes_repeat_tokens_across_sightings(tmp_path):
    module = _load_module()
    db_path = tmp_path / "jobfinder.db"
    conn = db.connect(str(db_path))
    db.upsert_job(
        conn, _sighting_job("https://boards.greenhouse.io/acme/jobs/1", token="gh-1"),
        profile="p", is_native=False, now="t1",
    )
    db.upsert_job(
        conn, _sighting_job("https://boards.greenhouse.io/acme/jobs/2", token="gh-2"),
        profile="p", is_native=False, now="t1",
    )
    conn.close()

    hits = module.discover_from_aggregator(db_path=str(db_path))

    assert len(hits) == 1


def test_discover_from_aggregator_ignores_sightings_from_other_adapters(tmp_path):
    module = _load_module()
    db_path = tmp_path / "jobfinder.db"
    conn = db.connect(str(db_path))
    job = RawJob(
        adapter="greenhouse", company="Acme", board_token="acme", external_id="1",
        title="Software Engineer", location="Remote", url="https://boards.greenhouse.io/acme/jobs/1",
    )
    db.upsert_job(conn, job, profile="p", is_native=True, now="t1")
    conn.close()

    hits = module.discover_from_aggregator(db_path=str(db_path))

    assert hits == []


def test_probe_company_collects_confirmed_hits_and_swallows_request_errors(monkeypatch):
    module = _load_module()

    def fake_greenhouse(slug):
        if slug == "acme":
            return True, 12
        raise requests.RequestException("boom")

    def fake_lever(slug):
        return False, 0

    monkeypatch.setattr(module, "ADAPTER_PROBES", {"greenhouse": fake_greenhouse, "lever": fake_lever})

    hits = module.probe_company("Acme", sleep=0)

    assert hits == [{"company": "Acme", "adapter": "greenhouse", "token": "acme", "job_count": 12}]


def test_print_yaml_fragment_formats_plain_and_workday_hits(capsys):
    module = _load_module()
    hits = [
        {"company": "Acme", "adapter": "greenhouse", "token": "acme", "job_count": 12},
        {"company": "Globex", "adapter": "workday", "job_count": None, "tenant": "globex", "wd": "wd1", "site": "careers"},
    ]

    module._print_yaml_fragment(hits)

    out = capsys.readouterr().out
    assert "greenhouse:" in out
    assert "workday:" in out
    assert "12 jobs" in out
    assert "via aggregator" in out
    assert "tenant: globex" in out
