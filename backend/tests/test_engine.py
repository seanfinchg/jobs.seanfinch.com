import inspect
import os
import time
from pathlib import Path

import pytest
import yaml

from jobfinder import classify, db, engine
from jobfinder.adapters.base import Adapter
from jobfinder.adapters.registry import register
from jobfinder.models import RawJob


def _job(**overrides):
    base = dict(
        adapter="fake", company="Acme", board_token="acme", external_id="1",
        title="Security Engineer", location="Boston, MA", url="https://example.com/1",
        body="",
    )
    base.update(overrides)
    return RawJob(**base)


def test_engine_source_has_no_seniority_keyword():
    source = inspect.getsource(engine)
    for banned in ["new grad", "intern", "senior"]:
        assert banned not in source.lower()


def test_engine_imports_no_concrete_adapter_module():
    source = inspect.getsource(engine)
    for concrete in ["greenhouse", "lever", "ashby", "smartrecruiters", "workable", "simplify_listings"]:
        assert f"adapters.{concrete}" not in source
        assert f"adapters import {concrete}" not in source


def test_passes_filters_include_exclude():
    filters = {
        "title_include": [r"security"],
        "title_exclude": [r"senior|manager"],
    }
    assert engine.passes_filters(_job(title="Security Engineer"), filters)
    assert not engine.passes_filters(_job(title="Senior Security Engineer"), filters)


def test_weak_title_alone_is_rejected_without_body_support():
    filters = {
        "title_include": [r"\bsecurity\b"],
        "title_include_weak": [r"software engineer.*new grad"],
        "body_include_for_weak_title": [r"\bsecurity\b", r"cyber"],
    }
    generic = _job(title="Software Engineer, New Grad", body="we build a checkout flow")
    assert not engine.passes_filters(generic, filters)


def test_weak_title_passes_with_body_support():
    filters = {
        "title_include": [r"\bsecurity\b"],
        "title_include_weak": [r"software engineer.*new grad"],
        "body_include_for_weak_title": [r"\bsecurity\b", r"cyber"],
    }
    supported = _job(title="Software Engineer, New Grad", body="you'll work with our security team")
    assert engine.passes_filters(supported, filters)


def test_strong_title_bypasses_the_weak_tier_entirely():
    filters = {
        "title_include": [r"\bsecurity\b"],
        "title_include_weak": [r"software engineer.*new grad"],
        "body_include_for_weak_title": [r"\bsecurity\b"],
    }
    strong = _job(title="Security Software Engineer, New Grad", body="no signal here")
    assert engine.passes_filters(strong, filters)


def test_weak_tier_alone_with_no_body_requirement_configured_passes():
    filters = {"title_include_weak": [r"software engineer"]}
    assert engine.passes_filters(_job(title="Software Engineer", body=""), filters)
    assert not engine.passes_filters(_job(title="Sales Manager"), filters)


def test_load_profile_merges_included_boards(tmp_path):
    boards_dir = tmp_path / "boards"
    boards_dir.mkdir()
    (boards_dir / "shared.yaml").write_text(
        yaml.safe_dump({"boards": {"greenhouse": [{"token": "shared-co"}]}})
    )

    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    (profiles_dir / "test-profile.yaml").write_text(
        yaml.safe_dump({
            "include": "boards/shared.yaml",
            "boards": {"greenhouse": [{"token": "own-co"}]},
            "filters": {},
        })
    )

    profile = engine.load_profile("test-profile", profiles_dir)
    tokens = [b["token"] for b in profile["boards"]["greenhouse"]]
    assert tokens == ["shared-co", "own-co"]


def test_load_profile_merges_a_list_of_included_board_files(tmp_path):
    # boards/manual.yaml needs to layer on top of boards/broad-tech.yaml
    # within the same profile -- `include` accepting a list, not just one
    # path, is what makes that possible without duplicating board entries
    # inline in the profile itself.
    boards_dir = tmp_path / "boards"
    boards_dir.mkdir()
    (boards_dir / "first.yaml").write_text(
        yaml.safe_dump({"boards": {"greenhouse": [{"token": "first-co"}]}})
    )
    (boards_dir / "second.yaml").write_text(
        yaml.safe_dump({"boards": {"greenhouse": [{"token": "second-co"}], "manual": [{"token": "manual-co"}]}})
    )

    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    (profiles_dir / "test-profile.yaml").write_text(
        yaml.safe_dump({
            "include": ["boards/first.yaml", "boards/second.yaml"],
            "filters": {},
        })
    )

    profile = engine.load_profile("test-profile", profiles_dir)
    tokens = [b["token"] for b in profile["boards"]["greenhouse"]]
    assert tokens == ["first-co", "second-co"]
    assert [b["token"] for b in profile["boards"]["manual"]] == ["manual-co"]


def test_two_profiles_same_raw_postings_different_matches(tmp_path, monkeypatch):
    @register
    class _FakeAdapter(Adapter):
        name = "fake-engine-test"

        def fetch(self, board):
            return [
                _job(adapter=self.name, title="Security Engineer, New Grad", external_id="1"),
                _job(adapter=self.name, title="Sales Manager", external_id="2"),
            ]

    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()

    (profiles_dir / "wide.yaml").write_text(yaml.safe_dump({
        "boards": {"fake-engine-test": [{"token": "acme"}]},
        "filters": {},
    }))
    (profiles_dir / "narrow.yaml").write_text(yaml.safe_dump({
        "boards": {"fake-engine-test": [{"token": "acme"}]},
        "filters": {"title_include": [r"security"]},
    }))

    conn_wide = db.connect(":memory:")
    engine.run("wide", db_path=":memory:", profiles_dir=profiles_dir, conn=conn_wide)
    wide_titles = {row["title"] for row in db.open_jobs(conn_wide)}

    conn_narrow = db.connect(":memory:")
    engine.run("narrow", db_path=":memory:", profiles_dir=profiles_dir, conn=conn_narrow)
    narrow_titles = {row["title"] for row in db.open_jobs(conn_narrow)}

    assert wide_titles == {"Security Engineer, New Grad", "Sales Manager"}
    assert narrow_titles == {"Security Engineer, New Grad"}


def test_reclassify_skips_jobs_that_no_longer_pass_a_tightened_filter(tmp_path):
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    (profiles_dir / "loose.yaml").write_text(yaml.safe_dump({
        "boards": {"fake-reclassify-test": [{"token": "acme"}]},
        "filters": {"title_include": [r"systems engineer"]},
    }))

    @register
    class _FakeReclassifyAdapter(Adapter):
        name = "fake-reclassify-test"

        def fetch(self, board):
            return [_job(title="GTM Systems Engineer", external_id="1")]

    conn = db.connect(":memory:")
    engine.run("loose", db_path=":memory:", profiles_dir=profiles_dir, conn=conn)
    assert {row["title"] for row in db.open_jobs(conn)} == {"GTM Systems Engineer"}

    # Tighten the same profile file in place, as if a real filter fix landed.
    (profiles_dir / "loose.yaml").write_text(yaml.safe_dump({
        "boards": {"fake-reclassify-test": [{"token": "acme"}]},
        "filters": {
            "title_include": [r"systems engineer"],
            "title_exclude": [r"gtm systems engineer"],
        },
    }))

    updated, newly_skipped = engine.reclassify("loose", profiles_dir=profiles_dir, conn=conn)
    assert newly_skipped == 1
    assert updated == 0
    assert db.open_jobs(conn) == []


def test_reclassify_updates_matched_fields_for_jobs_that_still_pass(tmp_path):
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    (profiles_dir / "reclass.yaml").write_text(yaml.safe_dump({
        "boards": {"fake-reclass-test": [{"token": "acme"}]},
        "filters": {"title_include": [r"security"]},
    }))

    @register
    class _FakeReclassAdapter(Adapter):
        name = "fake-reclass-test"

        def fetch(self, board):
            return [_job(title="Security Engineer", external_id="1")]

    conn = db.connect(":memory:")
    engine.run("reclass", db_path=":memory:", profiles_dir=profiles_dir, conn=conn)
    before = {row["title"]: row["level"] for row in db.open_jobs(conn)}
    assert "Security Engineer" in before

    updated, newly_skipped = engine.reclassify("reclass", profiles_dir=profiles_dir, conn=conn)
    assert updated == 1
    assert newly_skipped == 0


def test_run_trims_whitespace_from_company_title_location(tmp_path):
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    (profiles_dir / "trim.yaml").write_text(yaml.safe_dump({
        "boards": {"fake-trim-test": [{"token": "acme"}]},
        "filters": {},
    }))

    @register
    class _FakeTrimAdapter(Adapter):
        name = "fake-trim-test"

        def fetch(self, board):
            return [_job(
                company=" Acme Corp ", title="Security Operations Analyst ",
                location=" Boston, MA", external_id="1",
            )]

    conn = db.connect(":memory:")
    engine.run("trim", db_path=":memory:", profiles_dir=profiles_dir, conn=conn)
    row = db.open_jobs(conn)[0]
    assert row["company"] == "Acme Corp"
    assert row["title"] == "Security Operations Analyst"
    assert row["location"] == "Boston, MA"


def test_default_fetch_body_returns_none():
    class _NoBodyFetch(Adapter):
        name = "fake-default-fetch-body-test"

        def fetch(self, board):
            return []

    assert _NoBodyFetch().fetch_body(_job()) is None


def test_engine_skips_fetch_body_entirely_for_adapters_that_dont_override_it(tmp_path, monkeypatch):
    calls = []
    original = Adapter.fetch_body

    def spy(self, job):
        calls.append(job)
        return original(self, job)

    monkeypatch.setattr(Adapter, "fetch_body", spy)

    @register
    class _PlainAdapter(Adapter):
        name = "fake-plain-body-test"

        def fetch(self, board):
            return [_job(title="Security Engineer, New Grad")]

    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    (profiles_dir / "plain.yaml").write_text(yaml.safe_dump({
        "boards": {"fake-plain-body-test": [{"token": "acme"}]},
        "filters": {"title_include": [r"security"]},
    }))

    conn = db.connect(":memory:")
    engine.run("plain", db_path=":memory:", profiles_dir=profiles_dir, conn=conn)

    assert calls == []
    assert {row["title"] for row in db.open_jobs(conn)} == {"Security Engineer, New Grad"}


def test_engine_calls_fetch_body_only_after_the_cheap_title_filter_passes(tmp_path):
    fetched_ids = []

    @register
    class _LazyBodyAdapter(Adapter):
        name = "fake-lazy-body-test"

        def fetch(self, board):
            return [
                _job(title="Security Engineer, New Grad", external_id="1"),
                _job(title="Sales Manager", external_id="2"),
            ]

        def fetch_body(self, job):
            fetched_ids.append(job.external_id)
            return "we run a bug bounty program"

    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    (profiles_dir / "lazy.yaml").write_text(yaml.safe_dump({
        "boards": {"fake-lazy-body-test": [{"token": "acme"}]},
        "filters": {"title_include": [r"security"]},
    }))

    conn = db.connect(":memory:")
    engine.run("lazy", db_path=":memory:", profiles_dir=profiles_dir, conn=conn)

    assert fetched_ids == ["1"]
    jobs = db.open_jobs(conn)
    assert {row["title"] for row in jobs} == {"Security Engineer, New Grad"}
    assert jobs[0]["body"] == "we run a bug bounty program"


def test_engine_applies_body_exclude_after_lazy_fetch(tmp_path):
    @register
    class _LazyExcludeAdapter(Adapter):
        name = "fake-lazy-exclude-test"

        def fetch(self, board):
            return [_job(title="Security Engineer, New Grad", external_id="1")]

        def fetch_body(self, job):
            return "this role requires an active security clearance"

    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    (profiles_dir / "lazy-exclude.yaml").write_text(yaml.safe_dump({
        "boards": {"fake-lazy-exclude-test": [{"token": "acme"}]},
        "filters": {"title_include": [r"security"], "body_exclude": [r"security clearance"]},
    }))

    conn = db.connect(":memory:")
    engine.run("lazy-exclude", db_path=":memory:", profiles_dir=profiles_dir, conn=conn)

    assert db.open_jobs(conn) == []


def test_unknown_adapter_in_profile_is_logged_and_skipped(tmp_path, caplog):
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    (profiles_dir / "bad.yaml").write_text(yaml.safe_dump({
        "boards": {"not-a-real-adapter": [{"token": "x"}]},
        "filters": {},
    }))

    conn = db.connect(":memory:")
    engine.run("bad", db_path=":memory:", profiles_dir=profiles_dir, conn=conn)  # should not raise
    assert db.open_jobs(conn) == []


def test_grad_years_placeholder_is_substituted_with_the_real_year_window(tmp_path):
    """{grad_years} lets a profile/level/field regex reference "graduating
    soon" without a literal year a human has to remember to bump -- see
    profiles/levels/new-grad.yaml's body_bonus for the real shipped case."""
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    (profiles_dir / "gradyear.yaml").write_text(yaml.safe_dump({
        "filters": {"title_include": [r"engineer.*(new grad|{grad_years})"]},
    }))

    profile = engine.load_profile("gradyear", profiles_dir)
    pattern = classify.grad_year_pattern()
    assert "{grad_years}" not in profile["filters"]["title_include"][0]
    assert pattern in profile["filters"]["title_include"][0]

    a_real_year = pattern.split("|")[0]
    assert engine.passes_filters(_job(title=f"Software Engineer ({a_real_year} Grad)"), profile["filters"])


def test_memory_db_never_creates_a_run_lock():
    # :memory: is exclusively a test/isolated-check path -- no real network
    # calls ever happen against it, so it has no concurrent-real-run problem
    # to guard against, and shouldn't pay the lock-file overhead either.
    assert engine._acquire_run_lock(":memory:") is None


def test_run_lock_blocks_a_second_concurrent_run_against_the_same_db(tmp_path):
    db_path = tmp_path / "jobfinder.db"
    lock_path = engine._acquire_run_lock(db_path)
    assert lock_path == Path(str(db_path) + ".run-lock")
    assert lock_path.exists()

    with pytest.raises(engine.RunAlreadyInProgress):
        engine._acquire_run_lock(db_path)

    engine._release_run_lock(lock_path)
    assert not lock_path.exists()


def test_stale_run_lock_is_treated_as_abandoned_not_blocking(tmp_path):
    # A lock left over from a process that crashed (not a clean exit)
    # shouldn't block every future run forever -- age it past the stale
    # threshold and confirm a new run proceeds instead of raising.
    db_path = tmp_path / "jobfinder.db"
    lock_path = Path(str(db_path) + ".run-lock")
    lock_path.write_text("stale")
    old_time = time.time() - engine.RUN_LOCK_MAX_AGE_SECONDS - 60
    os.utime(lock_path, (old_time, old_time))

    new_lock_path = engine._acquire_run_lock(db_path)
    assert new_lock_path == lock_path
    engine._release_run_lock(new_lock_path)


def test_run_raises_run_already_in_progress_when_a_lock_already_exists(tmp_path):
    db_path = tmp_path / "jobfinder.db"
    lock_path = Path(str(db_path) + ".run-lock")
    lock_path.write_text("already running")

    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    (profiles_dir / "locked.yaml").write_text(yaml.safe_dump({"boards": {}, "filters": {}}))

    with pytest.raises(engine.RunAlreadyInProgress):
        engine.run("locked", db_path=db_path, profiles_dir=profiles_dir)

    # The pre-existing lock must survive untouched -- run() raising here must
    # not have deleted a lock it didn't itself create.
    assert lock_path.exists()
    lock_path.unlink()


def test_run_releases_its_own_lock_after_a_clean_run(tmp_path):
    db_path = tmp_path / "jobfinder.db"
    lock_path = Path(str(db_path) + ".run-lock")

    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    (profiles_dir / "unlocked.yaml").write_text(yaml.safe_dump({"boards": {}, "filters": {}}))

    engine.run("unlocked", db_path=db_path, profiles_dir=profiles_dir)

    assert not lock_path.exists()
